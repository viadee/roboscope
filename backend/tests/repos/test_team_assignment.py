"""Story 3-2: Repository-to-Team assignment endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.audit.models import AuditLog
from src.auth.models import User
from src.auth.service import hash_password
from src.repos.models import Repository
from src.teams.models import Team
from tests.conftest import auth_header


@pytest.fixture
def repo(db_session: Session, admin_user: User) -> Repository:
    r = Repository(
        name="team-assign-repo",
        git_url="https://github.com/test/team-assign.git",
        default_branch="main",
        local_path="/tmp/repos/team-assign",
        created_by=admin_user.id,
    )
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r


@pytest.fixture
def team(db_session: Session) -> Team:
    t = Team(name="Assign-Team")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture
def editor_user(db_session: Session) -> User:
    u = User(
        email="editor-assign@test.com",
        username="editor-assign",
        hashed_password=hash_password("pw"),
        role="editor",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


BASE = "/api/v1/repos"


class TestAssignTeam:
    def test_admin_assigns_team_and_audit_written(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        repo: Repository,
        team: Team,
    ) -> None:
        resp = client.put(
            f"{BASE}/{repo.id}/team",
            json={"team_id": team.id},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["team_id"] == team.id

        audits = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "repository.team_assigned")
            .all()
        )
        assert len(audits) == 1
        assert audits[0].resource_id == repo.id

    def test_unassign_via_null_emits_unassigned_audit(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        repo: Repository,
        team: Team,
    ) -> None:
        # Assign first.
        client.put(
            f"{BASE}/{repo.id}/team",
            json={"team_id": team.id},
            headers=auth_header(admin_user),
        )
        # Then unassign.
        resp = client.put(
            f"{BASE}/{repo.id}/team",
            json={"team_id": None},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["team_id"] is None

        unassigned = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "repository.team_unassigned")
            .all()
        )
        assert len(unassigned) == 1

    def test_nonexistent_team_returns_404(
        self,
        client: TestClient,
        admin_user: User,
        repo: Repository,
    ) -> None:
        resp = client.put(
            f"{BASE}/{repo.id}/team",
            json={"team_id": 99999},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    def test_nonexistent_repo_returns_404(
        self,
        client: TestClient,
        admin_user: User,
        team: Team,
    ) -> None:
        resp = client.put(
            f"{BASE}/99999/team",
            json={"team_id": team.id},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    def test_editor_cannot_assign(
        self,
        client: TestClient,
        editor_user: User,
        repo: Repository,
        team: Team,
    ) -> None:
        resp = client.put(
            f"{BASE}/{repo.id}/team",
            json={"team_id": team.id},
            headers=auth_header(editor_user),
        )
        assert resp.status_code == 403

    def test_response_includes_team_id_after_assign(
        self,
        client: TestClient,
        admin_user: User,
        repo: Repository,
        team: Team,
    ) -> None:
        client.put(
            f"{BASE}/{repo.id}/team",
            json={"team_id": team.id},
            headers=auth_header(admin_user),
        )
        get_resp = client.get(
            f"{BASE}/{repo.id}", headers=auth_header(admin_user)
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["team_id"] == team.id
