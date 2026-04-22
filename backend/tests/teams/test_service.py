"""Unit tests for the teams service layer (Story 3-1)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.auth.models import User
from src.teams.models import TeamMember
from src.teams.schemas import (
    TeamCreate,
    TeamMemberCreate,
    TeamMemberUpdate,
    TeamUpdate,
)
from src.teams.service import (
    add_member,
    create_team,
    delete_team,
    get_team,
    list_members_with_user,
    list_teams,
    remove_member,
    update_member,
    update_team,
)


@pytest.fixture
def other_user(db_session: Session, admin_user: User) -> User:
    """A second user so we can test membership of non-admins."""
    from src.auth.service import hash_password

    user = User(
        email="team-test-user@example.com",
        username="team-test-user",
        hashed_password=hash_password("sUperSecret123!"),
        role="editor",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestTeamCRUD:
    def test_create_team(self, db_session: Session) -> None:
        team = create_team(db_session, TeamCreate(name="Alpha", description="Test"))
        assert team.id is not None
        assert team.name == "Alpha"
        assert team.external_id is None

    def test_duplicate_name_raises_value_error(self, db_session: Session) -> None:
        create_team(db_session, TeamCreate(name="Dup"))
        db_session.commit()
        with pytest.raises(ValueError, match="team.name_taken"):
            create_team(db_session, TeamCreate(name="Dup"))

    def test_update_team(self, db_session: Session) -> None:
        team = create_team(db_session, TeamCreate(name="Alpha"))
        updated = update_team(
            db_session, team.id, TeamUpdate(description="new desc")
        )
        assert updated is not None
        assert updated.description == "new desc"

    def test_update_nonexistent_returns_none(self, db_session: Session) -> None:
        assert update_team(db_session, 99999, TeamUpdate(name="X")) is None

    def test_delete_team(self, db_session: Session) -> None:
        team = create_team(db_session, TeamCreate(name="Alpha"))
        assert delete_team(db_session, team.id) is True
        assert get_team(db_session, team.id) is None

    def test_delete_nonexistent_returns_false(self, db_session: Session) -> None:
        assert delete_team(db_session, 99999) is False

    def test_list_teams_sorted_by_name(self, db_session: Session) -> None:
        create_team(db_session, TeamCreate(name="Charlie"))
        create_team(db_session, TeamCreate(name="Alpha"))
        create_team(db_session, TeamCreate(name="Bravo"))
        names = [t.name for t in list_teams(db_session)]
        assert names == ["Alpha", "Bravo", "Charlie"]


class TestMemberCRUD:
    def test_add_member(
        self, db_session: Session, admin_user: User, other_user: User
    ) -> None:
        team = create_team(db_session, TeamCreate(name="Alpha"))
        member = add_member(
            db_session,
            team.id,
            TeamMemberCreate(user_id=other_user.id, role="editor"),
        )
        assert member is not None
        assert member.user_id == other_user.id
        assert member.role == "editor"
        assert member.source == "manual"

    def test_add_member_to_nonexistent_team_returns_none(
        self, db_session: Session, admin_user: User
    ) -> None:
        assert (
            add_member(
                db_session,
                99999,
                TeamMemberCreate(user_id=admin_user.id, role="editor"),
            )
            is None
        )

    def test_add_member_unknown_user_raises(
        self, db_session: Session
    ) -> None:
        team = create_team(db_session, TeamCreate(name="Alpha"))
        with pytest.raises(ValueError, match="team.member.user_not_found"):
            add_member(
                db_session,
                team.id,
                TeamMemberCreate(user_id=99999, role="viewer"),
            )

    def test_add_duplicate_member_raises(
        self, db_session: Session, admin_user: User, other_user: User
    ) -> None:
        team = create_team(db_session, TeamCreate(name="Alpha"))
        add_member(
            db_session,
            team.id,
            TeamMemberCreate(user_id=other_user.id, role="viewer"),
        )
        db_session.commit()
        with pytest.raises(ValueError, match="team.member.already_exists"):
            add_member(
                db_session,
                team.id,
                TeamMemberCreate(user_id=other_user.id, role="editor"),
            )

    def test_update_member_flips_idp_synced_to_manual(
        self, db_session: Session, admin_user: User, other_user: User
    ) -> None:
        team = create_team(db_session, TeamCreate(name="Alpha"))
        # Simulate a previously synced member.
        synced = TeamMember(
            team_id=team.id,
            user_id=other_user.id,
            role="viewer",
            source="idp_group_sync",
        )
        db_session.add(synced)
        db_session.commit()
        db_session.refresh(synced)

        updated = update_member(
            db_session, team.id, synced.id, TeamMemberUpdate(role="admin")
        )
        assert updated is not None
        assert updated.role == "admin"
        assert updated.source == "manual"

    def test_update_member_manual_stays_manual(
        self, db_session: Session, admin_user: User, other_user: User
    ) -> None:
        team = create_team(db_session, TeamCreate(name="Alpha"))
        member = add_member(
            db_session,
            team.id,
            TeamMemberCreate(user_id=other_user.id, role="viewer"),
        )
        assert member is not None
        updated = update_member(
            db_session, team.id, member.id, TeamMemberUpdate(role="editor")
        )
        assert updated is not None
        assert updated.source == "manual"

    def test_update_member_nonexistent_returns_none(
        self, db_session: Session
    ) -> None:
        team = create_team(db_session, TeamCreate(name="Alpha"))
        assert (
            update_member(
                db_session, team.id, 99999, TeamMemberUpdate(role="admin")
            )
            is None
        )

    def test_remove_member(
        self, db_session: Session, admin_user: User, other_user: User
    ) -> None:
        team = create_team(db_session, TeamCreate(name="Alpha"))
        member = add_member(
            db_session,
            team.id,
            TeamMemberCreate(user_id=other_user.id, role="viewer"),
        )
        assert member is not None
        assert remove_member(db_session, team.id, member.id) is True
        assert remove_member(db_session, team.id, member.id) is False

    def test_list_members_with_user(
        self, db_session: Session, admin_user: User, other_user: User
    ) -> None:
        team = create_team(db_session, TeamCreate(name="Alpha"))
        add_member(
            db_session,
            team.id,
            TeamMemberCreate(user_id=other_user.id, role="viewer"),
        )
        rows = list_members_with_user(db_session, team.id)
        assert len(rows) == 1
        member, user = rows[0]
        assert user.id == other_user.id
        assert member.role == "viewer"
