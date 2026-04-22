"""Team + TeamMember service layer (Story 3-1).

Conventions:
  - Unique-violations surface as `ValueError("<translation-key>")` so the
    router can return a 400 with the key for i18n lookup on the frontend.
  - All writes flush() but leave commit() to the router — the audit-log
    middleware requires the request-level DB session for its own commit.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.models import IdPGroupMapping, IdentityProvider, User
from src.teams.models import Team, TeamMember
from src.teams.schemas import (
    GroupMappingCreate,
    GroupMappingUpdate,
    TeamCreate,
    TeamImportRow,
    TeamImportSummary,
    TeamMemberCreate,
    TeamMemberUpdate,
    TeamUpdate,
)


# ---------- Team ------------------------------------------------------------


def create_team(db: Session, data: TeamCreate) -> Team:
    team = Team(name=data.name, description=data.description)
    db.add(team)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ValueError("team.name_taken") from None
    db.refresh(team)
    return team


def get_team(db: Session, team_id: int) -> Team | None:
    return db.get(Team, team_id)


def list_teams(db: Session) -> list[Team]:
    result = db.execute(select(Team).order_by(Team.name))
    return list(result.scalars().all())


def update_team(db: Session, team_id: int, data: TeamUpdate) -> Team | None:
    team = get_team(db, team_id)
    if team is None:
        return None
    if data.name is not None:
        team.name = data.name
    if data.description is not None:
        team.description = data.description
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ValueError("team.name_taken") from None
    db.refresh(team)
    return team


def delete_team(db: Session, team_id: int) -> bool:
    team = get_team(db, team_id)
    if team is None:
        return False
    db.delete(team)
    db.flush()
    return True


# ---------- Members ---------------------------------------------------------


def add_member(
    db: Session, team_id: int, data: TeamMemberCreate
) -> TeamMember | None:
    if get_team(db, team_id) is None:
        return None
    if db.get(User, data.user_id) is None:
        raise ValueError("team.member.user_not_found")

    member = TeamMember(
        team_id=team_id,
        user_id=data.user_id,
        role=data.role,
        source="manual",
    )
    db.add(member)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ValueError("team.member.already_exists") from None
    db.refresh(member)
    return member


def update_member(
    db: Session, team_id: int, member_id: int, data: TeamMemberUpdate
) -> TeamMember | None:
    member = db.get(TeamMember, member_id)
    if member is None or member.team_id != team_id:
        return None
    member.role = data.role
    # AC2 — admin-initiated edits flip source to 'manual' so the next
    # login-time group sync does not overwrite the admin's decision.
    if member.source == "idp_group_sync":
        member.source = "manual"
    db.flush()
    db.refresh(member)
    return member


def remove_member(db: Session, team_id: int, member_id: int) -> bool:
    member = db.get(TeamMember, member_id)
    if member is None or member.team_id != team_id:
        return False
    db.delete(member)
    db.flush()
    return True


def list_members_with_user(db: Session, team_id: int) -> list[tuple[TeamMember, User]]:
    result = db.execute(
        select(TeamMember, User)
        .join(User, User.id == TeamMember.user_id)
        .where(TeamMember.team_id == team_id)
        .order_by(User.email)
    )
    return [(m, u) for m, u in result.all()]


# ---------- Group mappings --------------------------------------------------


def create_group_mapping(
    db: Session, team_id: int, data: GroupMappingCreate
) -> IdPGroupMapping | None:
    if get_team(db, team_id) is None:
        return None
    if db.get(IdentityProvider, data.idp_id) is None:
        raise ValueError("idp.not_found")

    mapping = IdPGroupMapping(
        idp_id=data.idp_id,
        team_id=team_id,
        group_claim_value=data.group_name,
        role=data.role,
    )
    db.add(mapping)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ValueError("group_mapping.duplicate") from None
    db.refresh(mapping)
    return mapping


def list_group_mappings_for_team(
    db: Session, team_id: int
) -> list[IdPGroupMapping]:
    result = db.execute(
        select(IdPGroupMapping)
        .where(IdPGroupMapping.team_id == team_id)
        .order_by(IdPGroupMapping.idp_id, IdPGroupMapping.group_claim_value)
    )
    return list(result.scalars().all())


def update_group_mapping(
    db: Session, mapping_id: int, data: GroupMappingUpdate
) -> IdPGroupMapping | None:
    mapping = db.get(IdPGroupMapping, mapping_id)
    if mapping is None:
        return None
    mapping.role = data.role
    db.flush()
    db.refresh(mapping)
    return mapping


def delete_group_mapping(db: Session, mapping_id: int) -> bool:
    mapping = db.get(IdPGroupMapping, mapping_id)
    if mapping is None:
        return False
    db.delete(mapping)
    db.flush()
    return True


def list_available_groups_for_idp(db: Session, idp_id: int) -> list[str]:
    """Sorted union of (admin-mapped groups, login-observed groups).

    Story 3-4 AC1 + Story 3-5 AC6 — admins see any group already known to
    RoboScope, whether it was hand-mapped or surfaced through a real login
    via the id_token `groups` claim.
    """
    from src.auth.seen_groups import list_seen_groups

    mapped = db.execute(
        select(IdPGroupMapping.group_claim_value)
        .where(IdPGroupMapping.idp_id == idp_id)
        .distinct()
    ).scalars().all()
    seen = list_seen_groups(db, idp_id)
    return sorted(set(mapped) | set(seen))


def import_teams_from_idp_groups(
    db: Session, idp_id: int, rows: list[TeamImportRow]
) -> tuple[TeamImportSummary, list[int], list[int]]:
    """Create Team + GroupMapping for each row, skipping duplicates.

    Returns (summary, newly_created_team_ids, newly_created_mapping_ids) so the
    router can emit per-row audit events for just the new rows.
    """
    if db.get(IdentityProvider, idp_id) is None:
        raise ValueError("idp.not_found")

    created = 0
    skipped = 0
    failed = 0
    team_ids: list[int] = []
    new_team_ids: list[int] = []
    new_mapping_ids: list[int] = []
    errors: list[str] = []

    for row in rows:
        team: Team | None = None
        try:
            # Team — create or reuse by name.
            existing_team = db.execute(
                select(Team).where(Team.name == row.team_name)
            ).scalar_one_or_none()
            if existing_team is None:
                team = Team(name=row.team_name)
                db.add(team)
                try:
                    db.flush()
                    db.refresh(team)
                except IntegrityError:
                    # Race: another request created it. Re-select.
                    db.rollback()
                    team = db.execute(
                        select(Team).where(Team.name == row.team_name)
                    ).scalar_one_or_none()
                    if team is None:
                        raise
                    existing_team = team
                else:
                    new_team_ids.append(team.id)
            else:
                team = existing_team

            team_ids.append(team.id)

            # Mapping — create or skip if pair already exists.
            existing_mapping = db.execute(
                select(IdPGroupMapping).where(
                    IdPGroupMapping.idp_id == idp_id,
                    IdPGroupMapping.group_claim_value == row.group_name,
                )
            ).scalar_one_or_none()

            if existing_mapping is None:
                mapping = IdPGroupMapping(
                    idp_id=idp_id,
                    team_id=team.id,
                    group_claim_value=row.group_name,
                    role=row.role,
                )
                db.add(mapping)
                try:
                    db.flush()
                    db.refresh(mapping)
                    new_mapping_ids.append(mapping.id)
                    created += 1
                except IntegrityError:
                    # Concurrent insert — count as skipped.
                    db.rollback()
                    skipped += 1
            else:
                skipped += 1

        except Exception as err:
            failed += 1
            errors.append(f"{row.team_name}: {err}")
            # Best-effort recovery so the next row still runs.
            try:
                db.rollback()
            except Exception:
                pass

    summary = TeamImportSummary(
        created=created,
        skipped=skipped,
        failed=failed,
        team_ids=team_ids,
        errors=errors,
    )
    return summary, new_team_ids, new_mapping_ids
