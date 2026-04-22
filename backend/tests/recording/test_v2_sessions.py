"""Story W.1 (stub) — v2 recording session endpoints.

Locks in:
  - POST /recordings/sessions creates a RecordingSession row with status
    recording + audits recording.session.started.
  - DELETE aborts a session the user owns, marks it cancelled, audits
    recording.session.aborted with reason=user_abort. Non-owner non-
    admin gets 403.
  - Per-user cap (AR-10): a second POST by the same user aborts the
    first active session (audit reason=superseded) before creating
    the new row.
  - Requires EDITOR+ effective role on the target repo.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.audit.models import AuditLog
from src.auth.models import User
from src.auth.service import hash_password
from src.recording.models import RecordingSession, RecordingStatus
from src.repos.models import Repository
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


def _mk_repo(db: Session, owner: User) -> Repository:
    r = Repository(
        name=f"rec-sess-{owner.id}",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path=f"/tmp/rec-sess-{owner.id}",
        created_by=owner.id,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


class TestCreateSession:
    def test_editor_creates_session_and_audits(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        repo = _mk_repo(db_session, admin_user)
        resp = client.post(
            "/api/v1/recordings/sessions",
            json={"transport": "web_playwright", "repo_id": repo.id},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["transport"] == "web_playwright"
        assert body["status"] == "recording"
        session_id = body["session_id"]

        audits = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "recording.session.started")
            .all()
        )
        assert len(audits) == 1
        detail = json.loads(audits[0].detail)
        assert detail["session_id"] == session_id
        assert detail["transport"] == "web_playwright"

    def test_viewer_forbidden(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        viewer = _mk_user(db_session, role="viewer", email="v-rec@test.com")
        repo = _mk_repo(db_session, admin_user)
        resp = client.post(
            "/api/v1/recordings/sessions",
            json={"transport": "web_playwright", "repo_id": repo.id},
            headers=auth_header(viewer),
        )
        assert resp.status_code == 403

    def test_viewer_with_team_editor_grant_is_allowed(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        viewer = _mk_user(db_session, role="viewer", email="v-team@test.com")
        team = Team(name="rec-team")
        db_session.add(team)
        db_session.commit()
        db_session.refresh(team)
        db_session.add(
            TeamMember(team_id=team.id, user_id=viewer.id, role="editor", source="manual")
        )
        repo = _mk_repo(db_session, admin_user)
        repo.team_id = team.id
        db_session.commit()

        resp = client.post(
            "/api/v1/recordings/sessions",
            json={"transport": "web_playwright", "repo_id": repo.id},
            headers=auth_header(viewer),
        )
        assert resp.status_code == 201


class TestPerUserCap:
    def test_second_create_supersedes_first(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        repo = _mk_repo(db_session, admin_user)
        first = client.post(
            "/api/v1/recordings/sessions",
            json={"transport": "web_playwright", "repo_id": repo.id},
            headers=auth_header(admin_user),
        ).json()

        second = client.post(
            "/api/v1/recordings/sessions",
            json={"transport": "web_playwright", "repo_id": repo.id},
            headers=auth_header(admin_user),
        ).json()

        assert first["session_id"] != second["session_id"]

        db_session.expire_all()
        first_row = db_session.get(RecordingSession, first["session_id"])
        second_row = db_session.get(RecordingSession, second["session_id"])
        assert first_row is not None and first_row.status == RecordingStatus.CANCELLED
        assert second_row is not None and second_row.status == RecordingStatus.RECORDING

        superseded = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "recording.session.aborted")
            .all()
        )
        reasons = {json.loads(a.detail)["reason"] for a in superseded}
        assert "superseded" in reasons


class TestAbortSession:
    def test_owner_aborts(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        repo = _mk_repo(db_session, admin_user)
        created = client.post(
            "/api/v1/recordings/sessions",
            json={"transport": "web_playwright", "repo_id": repo.id},
            headers=auth_header(admin_user),
        ).json()

        resp = client.delete(
            f"/api/v1/recordings/sessions/{created['session_id']}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 204

        db_session.expire_all()
        row = db_session.get(RecordingSession, created["session_id"])
        assert row is not None and row.status == RecordingStatus.CANCELLED

    def test_non_owner_forbidden(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        owner = _mk_user(db_session, role="editor", email="o-rec@test.com")
        repo = _mk_repo(db_session, owner)
        created = client.post(
            "/api/v1/recordings/sessions",
            json={"transport": "web_playwright", "repo_id": repo.id},
            headers=auth_header(owner),
        ).json()

        other = _mk_user(db_session, role="editor", email="other-rec@test.com")
        resp = client.delete(
            f"/api/v1/recordings/sessions/{created['session_id']}",
            headers=auth_header(other),
        )
        assert resp.status_code == 403

    def test_admin_can_abort_any(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        owner = _mk_user(db_session, role="editor", email="admcan-rec@test.com")
        repo = _mk_repo(db_session, owner)
        created = client.post(
            "/api/v1/recordings/sessions",
            json={"transport": "web_playwright", "repo_id": repo.id},
            headers=auth_header(owner),
        ).json()

        resp = client.delete(
            f"/api/v1/recordings/sessions/{created['session_id']}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 204

    def test_404_on_unknown(
        self, client: TestClient, admin_user: User
    ) -> None:
        resp = client.delete(
            "/api/v1/recordings/sessions/99999",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404
