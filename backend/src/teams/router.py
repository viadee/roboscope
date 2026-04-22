"""Team + TeamMember CRUD endpoints (Story 3-1).

All mutating endpoints require ADMIN. GET endpoints are also ADMIN-only in
this story — the user-is-team-member visibility rule is Story 3.13's
responsibility.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.audit.event_types import AuditEventType
from src.audit.service import log_event
from src.auth.constants import Role
from src.auth.dependencies import require_role
from src.auth.models import User
from src.database import get_db
from src.teams import service as team_service
from src.teams.schemas import (
    GroupMappingCreate,
    GroupMappingResponse,
    GroupMappingUpdate,
    TeamCreate,
    TeamDetailResponse,
    TeamImportFromGroupsRequest,
    TeamImportSummary,
    TeamMemberCreate,
    TeamMemberDetail,
    TeamMemberResponse,
    TeamMemberUpdate,
    TeamResponse,
    TeamUpdate,
)

router = APIRouter()

# Separate router for delete-by-id of group mappings — mounted at
# /api/v1/group-mappings so callers can delete without the team_id.
group_mappings_router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ---------- Teams -----------------------------------------------------------


@router.post(
    "/import-from-idp-groups", response_model=TeamImportSummary
)
def import_from_idp_groups(
    data: TeamImportFromGroupsRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Bulk-create teams + group mappings from an IdP group list (Story 3-4).

    Per-row atomicity: one failing row does not roll back earlier successes.
    Audit events (`team.created`, `group_mapping.created`) are emitted once
    per newly-created row; skipped rows do not emit duplicates.
    """
    try:
        summary, new_team_ids, new_mapping_ids = (
            team_service.import_teams_from_idp_groups(
                db, data.idp_id, data.groups
            )
        )
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    ip = _client_ip(request)
    for tid in new_team_ids:
        log_event(
            db,
            AuditEventType.TEAM_CREATED,
            user_id=current_user.id,
            resource_id=tid,
            detail={"source": "import_from_idp_groups"},
            ip_address=ip,
        )
    for mid in new_mapping_ids:
        log_event(
            db,
            AuditEventType.GROUP_MAPPING_CREATED,
            user_id=current_user.id,
            resource_id=mid,
            detail={"source": "import_from_idp_groups"},
            ip_address=ip,
        )
    return summary


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(
    data: TeamCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    try:
        team = team_service.create_team(db, data)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
        ) from err
    log_event(
        db,
        AuditEventType.TEAM_CREATED,
        user_id=current_user.id,
        resource_id=team.id,
        detail={"name": team.name},
        ip_address=_client_ip(request),
    )
    return team


@router.get("", response_model=list[TeamResponse])
def list_teams(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    return team_service.list_teams(db)


@router.get("/{team_id}", response_model=TeamDetailResponse)
def get_team_detail(
    team_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    team = team_service.get_team(db, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    member_rows = team_service.list_members_with_user(db, team_id)
    members = [
        TeamMemberDetail(
            id=m.id,
            user_id=u.id,
            email=u.email,
            role=m.role,
            source=m.source,
        )
        for m, u in member_rows
    ]
    return TeamDetailResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        external_id=team.external_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        members=members,
    )


@router.put("/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: int,
    data: TeamUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    try:
        team = team_service.update_team(db, team_id, data)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
        ) from err
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    log_event(
        db,
        AuditEventType.TEAM_UPDATED,
        user_id=current_user.id,
        resource_id=team.id,
        detail={"name": team.name},
        ip_address=_client_ip(request),
    )
    return team


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    if not team_service.delete_team(db, team_id):
        raise HTTPException(status_code=404, detail="Team not found")
    log_event(
        db,
        AuditEventType.TEAM_DELETED,
        user_id=current_user.id,
        resource_id=team_id,
        ip_address=_client_ip(request),
    )
    return None


# ---------- Members ---------------------------------------------------------


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    team_id: int,
    data: TeamMemberCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    try:
        member = team_service.add_member(db, team_id, data)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
        ) from err
    if member is None:
        raise HTTPException(status_code=404, detail="Team not found")
    log_event(
        db,
        AuditEventType.TEAM_MEMBER_ADDED,
        user_id=current_user.id,
        resource_id=member.id,
        detail={
            "team_id": member.team_id,
            "user_id": member.user_id,
            "role": member.role,
        },
        ip_address=_client_ip(request),
    )
    return member


@router.patch("/{team_id}/members/{member_id}", response_model=TeamMemberResponse)
def update_member(
    team_id: int,
    member_id: int,
    data: TeamMemberUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    member = team_service.update_member(db, team_id, member_id, data)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    log_event(
        db,
        AuditEventType.TEAM_MEMBER_UPDATED,
        user_id=current_user.id,
        resource_id=member.id,
        detail={
            "team_id": member.team_id,
            "user_id": member.user_id,
            "role": member.role,
            "source": member.source,
        },
        ip_address=_client_ip(request),
    )
    return member


@router.delete(
    "/{team_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    team_id: int,
    member_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    if not team_service.remove_member(db, team_id, member_id):
        raise HTTPException(status_code=404, detail="Member not found")
    log_event(
        db,
        AuditEventType.TEAM_MEMBER_REMOVED,
        user_id=current_user.id,
        resource_id=member_id,
        detail={"team_id": team_id},
        ip_address=_client_ip(request),
    )
    return None


# ---------- Group mappings (Story 3-3) --------------------------------------


@router.post(
    "/{team_id}/group-mappings",
    response_model=GroupMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_group_mapping(
    team_id: int,
    data: GroupMappingCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    try:
        mapping = team_service.create_group_mapping(db, team_id, data)
    except ValueError as err:
        # Duplicate pair (idp_id, group_name) → 409. Missing IdP → 404.
        if str(err) == "group_mapping.duplicate":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(err)
            ) from err
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(err)
        ) from err
    if mapping is None:
        raise HTTPException(status_code=404, detail="Team not found")
    log_event(
        db,
        AuditEventType.GROUP_MAPPING_CREATED,
        user_id=current_user.id,
        resource_id=mapping.id,
        detail={
            "team_id": team_id,
            "idp_id": mapping.idp_id,
            "group_claim_value": mapping.group_claim_value,
            "role": mapping.role,
        },
        ip_address=_client_ip(request),
    )
    return mapping


@router.get(
    "/{team_id}/group-mappings",
    response_model=list[GroupMappingResponse],
)
def list_group_mappings(
    team_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    if team_service.get_team(db, team_id) is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team_service.list_group_mappings_for_team(db, team_id)


@group_mappings_router.patch(
    "/{mapping_id}", response_model=GroupMappingResponse
)
def update_group_mapping(
    mapping_id: int,
    data: GroupMappingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    mapping = team_service.update_group_mapping(db, mapping_id, data)
    if mapping is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    log_event(
        db,
        AuditEventType.GROUP_MAPPING_UPDATED,
        user_id=current_user.id,
        resource_id=mapping.id,
        detail={
            "team_id": mapping.team_id,
            "idp_id": mapping.idp_id,
            "group_claim_value": mapping.group_claim_value,
            "role": mapping.role,
        },
        ip_address=_client_ip(request),
    )
    return mapping


@group_mappings_router.delete(
    "/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_group_mapping(
    mapping_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    if not team_service.delete_group_mapping(db, mapping_id):
        raise HTTPException(status_code=404, detail="Mapping not found")
    log_event(
        db,
        AuditEventType.GROUP_MAPPING_DELETED,
        user_id=current_user.id,
        resource_id=mapping_id,
        ip_address=_client_ip(request),
    )
    return None
