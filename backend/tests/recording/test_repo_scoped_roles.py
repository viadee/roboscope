"""Recording v1 endpoints must gate on the EFFECTIVE role for the
recording's OWN repository, not a global role floor (audit finding 2.1).

Before this fix, `require_role(Role.RUNNER/EDITOR)` on `create` / `start` /
`start-browser` / `event` / `stop` / `cancel` / `delete` was global: a global
RUNNER/EDITOR could act on ANY repo's recordings, even one they have no
team/project grant on. A global VIEWER with a project-level EDITOR grant
on repo A (but nothing on repo B) is the regression-proving case: they must
be allowed on A and rejected on B.
"""

import pytest
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.service import hash_password
from src.recording.models import RecordingSession, RecordingStatus
from src.repos.models import ProjectMember, Repository
from tests.conftest import auth_header


@pytest.fixture
def scoped_viewer(db_session: Session) -> User:
    u = User(
        email="scoped-viewer@test.com",
        username="scoped-viewer",
        hashed_password=hash_password("pw123456"),
        role="viewer",
    )
    db_session.add(u)
    db_session.flush()
    db_session.refresh(u)
    return u


def _mk_repo(db_session: Session, admin_user, name: str) -> Repository:
    repo = Repository(
        name=name,
        repo_type="local",
        local_path=f"/tmp/{name}",
        created_by=admin_user.id,
    )
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)
    return repo


def _mk_recording(db_session: Session, admin_user, repo: Repository) -> RecordingSession:
    rec = RecordingSession(
        repository_id=repo.id,
        status=RecordingStatus.PENDING,
        triggered_by=admin_user.id,
    )
    db_session.add(rec)
    db_session.flush()
    db_session.refresh(rec)
    return rec


class TestCreateRecordingRepoScoped:
    def test_project_grant_on_repo_a_allows_create_on_a(
        self, client, db_session, admin_user, scoped_viewer
    ):
        repo_a = _mk_repo(db_session, admin_user, "repo-a")
        db_session.add(
            ProjectMember(user_id=scoped_viewer.id, repository_id=repo_a.id, role="runner")
        )
        db_session.commit()

        resp = client.post(
            "/api/v1/recordings",
            json={"repository_id": repo_a.id, "source": "playwright"},
            headers=auth_header(scoped_viewer),
        )
        assert resp.status_code == 201

    def test_no_grant_on_repo_b_rejects_create_on_b(
        self, client, db_session, admin_user, scoped_viewer
    ):
        repo_a = _mk_repo(db_session, admin_user, "repo-a2")
        repo_b = _mk_repo(db_session, admin_user, "repo-b2")
        db_session.add(
            ProjectMember(user_id=scoped_viewer.id, repository_id=repo_a.id, role="runner")
        )
        db_session.commit()

        resp = client.post(
            "/api/v1/recordings",
            json={"repository_id": repo_b.id, "source": "playwright"},
            headers=auth_header(scoped_viewer),
        )
        assert resp.status_code == 403

    def test_create_404s_on_missing_repo(self, client, scoped_viewer):
        resp = client.post(
            "/api/v1/recordings",
            json={"repository_id": 999999, "source": "playwright"},
            headers=auth_header(scoped_viewer),
        )
        assert resp.status_code == 404


class TestDeleteRecordingRepoScoped:
    def test_project_editor_grant_allows_delete(
        self, client, db_session, admin_user, scoped_viewer
    ):
        repo_a = _mk_repo(db_session, admin_user, "repo-a3")
        rec = _mk_recording(db_session, admin_user, repo_a)
        db_session.add(
            ProjectMember(user_id=scoped_viewer.id, repository_id=repo_a.id, role="editor")
        )
        db_session.commit()

        resp = client.delete(
            f"/api/v1/recordings/{rec.id}", headers=auth_header(scoped_viewer)
        )
        assert resp.status_code == 204

    def test_no_grant_rejects_delete(self, client, db_session, admin_user, scoped_viewer):
        repo_b = _mk_repo(db_session, admin_user, "repo-b3")
        rec = _mk_recording(db_session, admin_user, repo_b)
        db_session.commit()

        resp = client.delete(
            f"/api/v1/recordings/{rec.id}", headers=auth_header(scoped_viewer)
        )
        assert resp.status_code == 403

    def test_runner_grant_is_insufficient_for_delete(
        self, client, db_session, admin_user, scoped_viewer
    ):
        """EDITOR floor for delete — a mere RUNNER grant must not suffice."""
        repo_a = _mk_repo(db_session, admin_user, "repo-a4")
        rec = _mk_recording(db_session, admin_user, repo_a)
        db_session.add(
            ProjectMember(user_id=scoped_viewer.id, repository_id=repo_a.id, role="runner")
        )
        db_session.commit()

        resp = client.delete(
            f"/api/v1/recordings/{rec.id}", headers=auth_header(scoped_viewer)
        )
        assert resp.status_code == 403

    def test_delete_404s_on_missing_recording(self, client, scoped_viewer):
        resp = client.delete(
            "/api/v1/recordings/999999", headers=auth_header(scoped_viewer)
        )
        assert resp.status_code == 404


class TestStartRecordingRepoScoped:
    def test_project_runner_grant_allows_start(
        self, client, db_session, admin_user, scoped_viewer
    ):
        repo_a = _mk_repo(db_session, admin_user, "repo-a5")
        rec = _mk_recording(db_session, admin_user, repo_a)
        db_session.add(
            ProjectMember(user_id=scoped_viewer.id, repository_id=repo_a.id, role="runner")
        )
        db_session.commit()

        resp = client.post(
            f"/api/v1/recordings/{rec.id}/start", headers=auth_header(scoped_viewer)
        )
        assert resp.status_code == 200

    def test_no_grant_rejects_start(self, client, db_session, admin_user, scoped_viewer):
        repo_b = _mk_repo(db_session, admin_user, "repo-b5")
        rec = _mk_recording(db_session, admin_user, repo_b)
        db_session.commit()

        resp = client.post(
            f"/api/v1/recordings/{rec.id}/start", headers=auth_header(scoped_viewer)
        )
        assert resp.status_code == 403
