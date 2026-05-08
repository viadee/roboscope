"""Tests for recording API endpoints."""

import json

import pytest
from unittest.mock import patch

from sqlalchemy.orm import Session

from src.recording.models import RecordingSession, RecordingStatus, RecordingSource
from src.repos.models import Repository
from tests.conftest import auth_header


@pytest.fixture
def repo(db_session: Session, admin_user):
    """Create a repository for recording tests."""
    repository = Repository(
        name="rec-test-repo",
        git_url="https://github.com/test/rec-repo.git",
        default_branch="main",
        local_path="/tmp/repos/rec-repo",
        created_by=admin_user.id,
    )
    db_session.add(repository)
    db_session.flush()
    db_session.refresh(repository)
    return repository


def _recording_payload(repo_id: int, **overrides) -> dict:
    """Build a JSON payload for creating a recording."""
    defaults = {
        "repository_id": repo_id,
        "source": "playwright",
        "target_library": "Browser",
        "target_url": "https://example.com",
    }
    defaults.update(overrides)
    return defaults


class TestRecordingCRUD:
    """Tests for recording CRUD endpoints."""

    def test_create_recording(self, client, admin_user, repo):
        resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["repository_id"] == repo.id
        assert data["status"] == "pending"
        assert data["source"] == "playwright"
        assert data["target_library"] == "Browser"
        assert data["target_url"] == "https://example.com"
        assert data["event_count"] == 0

    def test_create_recording_extension_source(self, client, admin_user, repo):
        resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id, source="extension"),
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201
        assert resp.json()["source"] == "extension"

    def test_create_recording_viewer_forbidden(self, client, viewer_user, repo):
        resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(viewer_user),
        )
        assert resp.status_code == 403

    def test_list_recordings(self, client, admin_user, repo):
        # Create two recordings
        client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        resp = client.get(
            "/api/v1/recordings",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_recordings_filter_by_repo(self, client, admin_user, repo, db_session):
        # Create another repo
        repo2 = Repository(
            name="other-repo",
            git_url="https://github.com/test/other.git",
            default_branch="main",
            local_path="/tmp/repos/other",
            created_by=admin_user.id,
        )
        db_session.add(repo2)
        db_session.flush()

        client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo2.id),
            headers=auth_header(admin_user),
        )

        resp = client.get(
            f"/api/v1/recordings?repository_id={repo.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_get_recording(self, client, admin_user, repo):
        create_resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        rec_id = create_resp.json()["id"]

        resp = client.get(
            f"/api/v1/recordings/{rec_id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == rec_id

    def test_get_recording_not_found(self, client, admin_user):
        resp = client.get(
            "/api/v1/recordings/99999",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    def test_delete_recording(self, client, admin_user, repo):
        create_resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        rec_id = create_resp.json()["id"]

        resp = client.delete(
            f"/api/v1/recordings/{rec_id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 204

        resp = client.get(
            f"/api/v1/recordings/{rec_id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404


class TestRecordingLifecycle:
    """Tests for recording start/event/stop/cancel lifecycle."""

    def test_start_recording(self, client, admin_user, repo):
        create_resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        rec_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/recordings/{rec_id}/start",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "recording"
        assert resp.json()["started_at"] is not None

    def test_start_already_recording_fails(self, client, admin_user, repo):
        create_resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        rec_id = create_resp.json()["id"]

        client.post(f"/api/v1/recordings/{rec_id}/start", headers=auth_header(admin_user))
        resp = client.post(
            f"/api/v1/recordings/{rec_id}/start",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    def test_append_event(self, client, admin_user, repo):
        create_resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        rec_id = create_resp.json()["id"]
        client.post(f"/api/v1/recordings/{rec_id}/start", headers=auth_header(admin_user))

        resp = client.post(
            f"/api/v1/recordings/{rec_id}/event",
            json={
                "event_type": "click",
                "selector": "//button[@id='submit']",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["event_count"] == 1

    def test_append_multiple_events(self, client, admin_user, repo):
        create_resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        rec_id = create_resp.json()["id"]
        client.post(f"/api/v1/recordings/{rec_id}/start", headers=auth_header(admin_user))

        for i in range(3):
            client.post(
                f"/api/v1/recordings/{rec_id}/event",
                json={"event_type": "click", "selector": f"//div[{i}]"},
                headers=auth_header(admin_user),
            )

        resp = client.get(
            f"/api/v1/recordings/{rec_id}",
            headers=auth_header(admin_user),
        )
        assert resp.json()["event_count"] == 3

    def test_append_event_to_pending_fails(self, client, admin_user, repo):
        create_resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        rec_id = create_resp.json()["id"]
        # Don't start, try to append
        resp = client.post(
            f"/api/v1/recordings/{rec_id}/event",
            json={"event_type": "click", "selector": "//button"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    @patch("src.recording.router.dispatch_task")
    def test_stop_recording(self, mock_dispatch, client, admin_user, repo):
        from src.task_executor import TaskResult
        mock_dispatch.return_value = TaskResult()

        create_resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        rec_id = create_resp.json()["id"]
        client.post(f"/api/v1/recordings/{rec_id}/start", headers=auth_header(admin_user))
        client.post(
            f"/api/v1/recordings/{rec_id}/event",
            json={"event_type": "click", "selector": "//button"},
            headers=auth_header(admin_user),
        )

        resp = client.post(
            f"/api/v1/recordings/{rec_id}/stop",
            json={"generate_robot": True},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("processing", "completed")
        assert data["finished_at"] is not None
        mock_dispatch.assert_called_once()

    @patch("src.recording.router.dispatch_task")
    def test_stop_without_generation(self, mock_dispatch, client, admin_user, repo):
        create_resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        rec_id = create_resp.json()["id"]
        client.post(f"/api/v1/recordings/{rec_id}/start", headers=auth_header(admin_user))

        resp = client.post(
            f"/api/v1/recordings/{rec_id}/stop",
            json={"generate_robot": False},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        mock_dispatch.assert_not_called()

    def test_stop_pending_fails(self, client, admin_user, repo):
        create_resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        rec_id = create_resp.json()["id"]
        resp = client.post(
            f"/api/v1/recordings/{rec_id}/stop",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    def test_cancel_recording(self, client, admin_user, repo):
        create_resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        rec_id = create_resp.json()["id"]
        client.post(f"/api/v1/recordings/{rec_id}/start", headers=auth_header(admin_user))

        resp = client.post(
            f"/api/v1/recordings/{rec_id}/cancel",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_get_events(self, client, admin_user, repo):
        create_resp = client.post(
            "/api/v1/recordings",
            json=_recording_payload(repo.id),
            headers=auth_header(admin_user),
        )
        rec_id = create_resp.json()["id"]
        client.post(f"/api/v1/recordings/{rec_id}/start", headers=auth_header(admin_user))
        client.post(
            f"/api/v1/recordings/{rec_id}/event",
            json={"event_type": "navigate", "url": "https://example.com"},
            headers=auth_header(admin_user),
        )
        client.post(
            f"/api/v1/recordings/{rec_id}/event",
            json={"event_type": "click", "selector": "//button[@id='login']"},
            headers=auth_header(admin_user),
        )

        resp = client.get(
            f"/api/v1/recordings/{rec_id}/events",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert data["events"][0]["event_type"] == "navigate"
        assert data["events"][1]["selector"] == "//button[@id='login']"


class TestResetStuckSessions:
    """RECORDER-RESET-1 — panic-button cleanup of stuck v2 sessions.

    The endpoint exists for the failure mode where a v2 RecordingSession
    row stays in `RECORDING` even though the underlying Playwright task
    is gone (recorder thread crashed, browser closed manually, SSE
    dropped). Without this, the next launcher start trips AR-10's
    "abort other active sessions" guard silently and the user has no
    way to clear the state from the UI.
    """

    def _make_session(
        self,
        db_session: Session,
        user_id: int,
        repo_id: int,
        status: RecordingStatus = RecordingStatus.RECORDING,
    ) -> RecordingSession:
        from datetime import datetime, timezone
        sess = RecordingSession(
            repository_id=repo_id,
            triggered_by=user_id,
            source=RecordingSource.PLAYWRIGHT,
            status=status,
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(sess)
        db_session.flush()
        db_session.refresh(sess)
        return sess

    def test_reset_returns_zero_when_no_stuck_sessions(
        self, client, admin_user
    ):
        """Idempotent — no rows in `RECORDING` ⇒ aborted=0."""
        resp = client.post(
            "/api/v1/recordings/sessions/reset",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json() == {"aborted": 0}

    def test_reset_cancels_all_user_owned_recording_sessions(
        self, client, admin_user, repo, db_session
    ):
        s1 = self._make_session(db_session, admin_user.id, repo.id)
        s2 = self._make_session(db_session, admin_user.id, repo.id)
        db_session.commit()

        resp = client.post(
            "/api/v1/recordings/sessions/reset",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json() == {"aborted": 2}

        # Both rows are now CANCELLED.
        for s in [s1, s2]:
            db_session.refresh(s)
            assert s.status == RecordingStatus.CANCELLED
            assert s.finished_at is not None

    def test_reset_does_not_touch_already_terminal_sessions(
        self, client, admin_user, repo, db_session
    ):
        """Sessions in `COMPLETED` / `CANCELLED` / `FAILED` should NOT
        be re-aborted (would clobber `finished_at` and confuse audit)."""
        completed = self._make_session(
            db_session, admin_user.id, repo.id, RecordingStatus.COMPLETED
        )
        cancelled = self._make_session(
            db_session, admin_user.id, repo.id, RecordingStatus.CANCELLED
        )
        db_session.commit()
        original_completed_finish = completed.finished_at
        original_cancelled_finish = cancelled.finished_at

        resp = client.post(
            "/api/v1/recordings/sessions/reset",
            headers=auth_header(admin_user),
        )
        assert resp.json() == {"aborted": 0}

        db_session.refresh(completed)
        db_session.refresh(cancelled)
        assert completed.status == RecordingStatus.COMPLETED
        assert cancelled.status == RecordingStatus.CANCELLED
        assert completed.finished_at == original_completed_finish
        assert cancelled.finished_at == original_cancelled_finish

    def test_reset_does_not_touch_other_users_sessions(
        self, client, admin_user, runner_user, repo, db_session
    ):
        """Admin reset only clears the ADMIN's own stuck sessions —
        admin-wide nuke would let one admin kill another's live recording."""
        own = self._make_session(db_session, admin_user.id, repo.id)
        other = self._make_session(db_session, runner_user.id, repo.id)
        db_session.commit()

        resp = client.post(
            "/api/v1/recordings/sessions/reset",
            headers=auth_header(admin_user),
        )
        assert resp.json() == {"aborted": 1}

        db_session.refresh(own)
        db_session.refresh(other)
        assert own.status == RecordingStatus.CANCELLED
        assert other.status == RecordingStatus.RECORDING

    def test_reset_requires_authentication(self, client):
        resp = client.post("/api/v1/recordings/sessions/reset")
        assert resp.status_code == 401
