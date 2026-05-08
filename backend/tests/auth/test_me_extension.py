"""Story 4-1: /auth/me extension with teams, effective_roles_by_repo, first_login_complete."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.service import hash_password
from src.repos.models import ProjectMember, Repository
from src.teams.models import Team, TeamMember
from tests.conftest import auth_header


def _mk_user(db: Session, *, role: str, email: str) -> User:
    u = User(
        email=email,
        username=email.split("@")[0],
        hashed_password=hash_password("pw"),
        role=role,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


class TestMeExtension:
    def test_existing_fields_still_present(
        self, client: TestClient, admin_user: User
    ) -> None:
        resp = client.get("/api/v1/auth/me", headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        for field in ("id", "email", "username", "role", "is_active", "created_at"):
            assert field in body

    def test_new_fields_always_present_for_solo_user(
        self, client: TestClient, admin_user: User
    ) -> None:
        """A user with zero teams + zero project-memberships still gets the
        additive fields, not null or missing."""
        resp = client.get("/api/v1/auth/me", headers=auth_header(admin_user))
        body = resp.json()
        assert body["teams"] == []
        assert body["default_team_id"] is None
        assert body["effective_roles_by_repo"] == {}
        assert body["first_login_complete"] is False

    def test_teams_populated_and_default_is_lowest_id(
        self, client: TestClient, db_session: Session
    ) -> None:
        alice = _mk_user(db_session, role="viewer", email="alice-me@test.com")
        t1 = Team(name="Team-A")
        t2 = Team(name="Team-B")
        db_session.add_all([t1, t2])
        db_session.commit()
        db_session.refresh(t1)
        db_session.refresh(t2)
        db_session.add_all([
            TeamMember(team_id=t1.id, user_id=alice.id, role="editor", source="manual"),
            TeamMember(team_id=t2.id, user_id=alice.id, role="viewer", source="manual"),
        ])
        db_session.commit()

        resp = client.get("/api/v1/auth/me", headers=auth_header(alice))
        body = resp.json()
        assert {t["id"] for t in body["teams"]} == {t1.id, t2.id}
        assert body["default_team_id"] == min(t1.id, t2.id)

    def test_effective_roles_by_repo_covers_team_and_project(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        alice = _mk_user(db_session, role="viewer", email="alice-rbr@test.com")
        team = Team(name="Alpha")
        db_session.add(team)
        db_session.commit()
        db_session.refresh(team)
        db_session.add(
            TeamMember(team_id=team.id, user_id=alice.id, role="editor", source="manual")
        )

        team_repo = Repository(
            name="rbr-team",
            git_url="https://github.com/x/y.git",
            default_branch="main",
            local_path="/tmp/rbr-team",
            created_by=admin_user.id,
            team_id=team.id,
        )
        solo_repo = Repository(
            name="rbr-solo",
            git_url="https://github.com/x/z.git",
            default_branch="main",
            local_path="/tmp/rbr-solo",
            created_by=admin_user.id,
            team_id=None,
        )
        db_session.add_all([team_repo, solo_repo])
        db_session.commit()
        db_session.refresh(team_repo)
        db_session.refresh(solo_repo)

        db_session.add(
            ProjectMember(user_id=alice.id, repository_id=solo_repo.id, role="runner")
        )
        db_session.commit()

        resp = client.get("/api/v1/auth/me", headers=auth_header(alice))
        body = resp.json()
        rbr = body["effective_roles_by_repo"]
        assert rbr[str(team_repo.id)] == "editor"
        assert rbr[str(solo_repo.id)] == "runner"

    def test_patch_first_login_complete(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        resp = client.patch(
            "/api/v1/auth/me/first-login-complete",
            json={"value": True},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["first_login_complete"] is True

        db_session.expire_all()
        refreshed = db_session.get(User, admin_user.id)
        assert refreshed is not None
        assert refreshed.first_login_complete is True

    def test_first_login_default_is_false_for_new_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        fresh = _mk_user(db_session, role="viewer", email="fresh-flag@test.com")
        resp = client.get("/api/v1/auth/me", headers=auth_header(fresh))
        assert resp.json()["first_login_complete"] is False
