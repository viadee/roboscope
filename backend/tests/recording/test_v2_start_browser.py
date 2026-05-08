"""Story W.1 full — /start-browser endpoint.

The env-var kill switch `ROBOSCOPE_RECORDER_DISABLED=1` gates the
actual Playwright dispatch so these tests run without Chromium.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.service import hash_password
from src.recording.models import RecordingSession, RecordingStatus
from src.repos.models import Repository
from tests.conftest import auth_header


ENDPOINT = "/api/v1/recordings/sessions/{}/start-browser"


@pytest.fixture(autouse=True)
def _disable_recorder(monkeypatch):
    monkeypatch.setenv("ROBOSCOPE_RECORDER_DISABLED", "1")


def _mk_session(
    db: Session, owner: User, *, status: str = RecordingStatus.RECORDING
) -> RecordingSession:
    r = Repository(
        name=f"sb-{owner.id}",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path=f"/tmp/sb-{owner.id}",
        created_by=owner.id,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    s = RecordingSession(
        repository_id=r.id,
        status=status,
        source="playwright",
        triggered_by=owner.id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _mk_user(db: Session, *, role: str = "editor") -> User:
    u = User(
        email=f"sb-{role}@test.com", username=f"sb-{role}",
        hashed_password=hash_password("pw"), role=role,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


class TestKillSwitch:
    def test_disabled_env_returns_202_with_null_task(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        session = _mk_session(db_session, admin_user)
        resp = client.post(
            ENDPOINT.format(session.id), headers=auth_header(admin_user)
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["session_id"] == session.id
        assert body["task_id"] is None


class TestAuth:
    def test_non_owner_non_admin_forbidden(
        self, client: TestClient, db_session: Session
    ) -> None:
        owner = _mk_user(db_session, role="editor")
        session = _mk_session(db_session, owner)
        other = User(
            email="sb-other@test.com", username="sb-other",
            hashed_password=hash_password("pw"), role="editor",
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        resp = client.post(
            ENDPOINT.format(session.id), headers=auth_header(other)
        )
        assert resp.status_code == 403

    def test_admin_can_start_any(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        owner = _mk_user(db_session, role="editor")
        session = _mk_session(db_session, owner)
        resp = client.post(
            ENDPOINT.format(session.id), headers=auth_header(admin_user)
        )
        assert resp.status_code == 202


class TestPreconditions:
    def test_404_on_unknown_session(
        self, client: TestClient, admin_user: User
    ) -> None:
        resp = client.post(
            ENDPOINT.format(99999), headers=auth_header(admin_user)
        )
        assert resp.status_code == 404

    def test_cannot_start_when_already_cancelled(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        session = _mk_session(
            db_session, admin_user, status=RecordingStatus.CANCELLED
        )
        resp = client.post(
            ENDPOINT.format(session.id), headers=auth_header(admin_user)
        )
        assert resp.status_code == 400


class TestTargetUrl:
    def test_target_url_passes_through_to_task_dispatcher(
        self, client: TestClient, db_session: Session, admin_user: User, monkeypatch
    ) -> None:
        """With the kill-switch off we'd normally hit Playwright; we
        instead monkey-patch dispatch_task to capture what would have
        been called."""
        monkeypatch.delenv("ROBOSCOPE_RECORDER_DISABLED", raising=False)

        called: dict = {}

        class _FakeResult:
            id = "fake-task-id"

        def _fake_dispatch(fn, *args, **kwargs):
            called["fn"] = fn.__name__
            called["args"] = args
            return _FakeResult()

        import src.recording.router as rr
        monkeypatch.setattr(rr, "dispatch_task", _fake_dispatch)

        session = _mk_session(db_session, admin_user)
        resp = client.post(
            ENDPOINT.format(session.id),
            json={"target_url": "https://example.com"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 202
        assert resp.json()["task_id"] == "fake-task-id"
        assert called["fn"] == "run_v2_recorder_session"
        assert called["args"] == (session.id, "https://example.com")


class TestTargetUrlValidation:
    """Reject any URL whose scheme isn't http/https before the
    recorder dispatch, so a `javascript:` or `file://` URL never
    reaches `page.goto(...)`. Empty / whitespace-only normalises
    to None (recorder opens to about:blank — same UX as a session
    started without a target_url at all)."""

    @pytest.fixture
    def _no_dispatch(self, monkeypatch):
        """Replace dispatch_task so we observe whether it was called.
        If validation correctly rejects, dispatch must NOT fire."""
        monkeypatch.delenv("ROBOSCOPE_RECORDER_DISABLED", raising=False)

        called: dict = {}

        class _FakeResult:
            id = "fake-task-id"

        def _fake(fn, *args, **kwargs):
            called["fn"] = fn.__name__
            called["args"] = args
            return _FakeResult()

        import src.recording.router as rr
        monkeypatch.setattr(rr, "dispatch_task", _fake)
        return called

    @pytest.mark.parametrize(
        "bad_url",
        [
            "javascript:alert(1)",
            "file:///etc/passwd",
            "ftp://server/",
            "data:text/html,<p>x</p>",
            "mailto:user@example.com",
            "not-a-url",
            "//missing-scheme.example.com",
        ],
        ids=["javascript", "file", "ftp", "data", "mailto", "no_scheme", "protocol_relative"],
    )
    def test_non_http_scheme_rejected_with_400(
        self, client, db_session, admin_user, _no_dispatch, bad_url,
    ):
        session = _mk_session(db_session, admin_user)
        resp = client.post(
            ENDPOINT.format(session.id),
            json={"target_url": bad_url},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400
        assert "http://" in resp.json()["detail"] or "https://" in resp.json()["detail"]
        # And critically — the recorder dispatch must NOT have run.
        assert _no_dispatch == {}, (
            f"validation rejected the URL but dispatch_task fired anyway: {_no_dispatch}"
        )

    def test_http_scheme_accepted(
        self, client, db_session, admin_user, _no_dispatch,
    ):
        session = _mk_session(db_session, admin_user)
        resp = client.post(
            ENDPOINT.format(session.id),
            json={"target_url": "http://internal.example.com/"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 202
        assert _no_dispatch["args"] == (session.id, "http://internal.example.com/")

    def test_https_scheme_accepted(
        self, client, db_session, admin_user, _no_dispatch,
    ):
        session = _mk_session(db_session, admin_user)
        resp = client.post(
            ENDPOINT.format(session.id),
            json={"target_url": "https://example.com/path?q=1"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 202
        assert _no_dispatch["args"] == (session.id, "https://example.com/path?q=1")

    def test_whitespace_only_normalised_to_none(
        self, client, db_session, admin_user, _no_dispatch,
    ):
        # Same UX as omitting target_url — recorder opens about:blank
        # and the user navigates manually.
        session = _mk_session(db_session, admin_user)
        resp = client.post(
            ENDPOINT.format(session.id),
            json={"target_url": "   \t\n  "},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 202
        assert _no_dispatch["args"] == (session.id, None)

    def test_leading_trailing_whitespace_stripped(
        self, client, db_session, admin_user, _no_dispatch,
    ):
        session = _mk_session(db_session, admin_user)
        resp = client.post(
            ENDPOINT.format(session.id),
            json={"target_url": "  https://example.com/  "},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 202
        assert _no_dispatch["args"] == (session.id, "https://example.com/")

    def test_omitted_target_url_still_works(
        self, client, db_session, admin_user, _no_dispatch,
    ):
        session = _mk_session(db_session, admin_user)
        resp = client.post(
            ENDPOINT.format(session.id),
            json={},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 202
        assert _no_dispatch["args"] == (session.id, None)


class TestTransportDispatch:
    """Story D.1 AC — transport-aware dispatch + Windows-only guard."""

    def test_desktop_windows_on_non_windows_returns_501(
        self, client: TestClient, db_session: Session, admin_user: User, monkeypatch
    ) -> None:
        monkeypatch.delenv("ROBOSCOPE_RECORDER_DISABLED", raising=False)
        monkeypatch.setattr("sys.platform", "darwin")
        session = _mk_session(db_session, admin_user)
        resp = client.post(
            ENDPOINT.format(session.id),
            json={"transport": "desktop_windows"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 501
        assert "Windows host" in resp.json()["detail"]

    def test_desktop_macos_returns_501_nogo(
        self, client: TestClient, db_session: Session, admin_user: User, monkeypatch
    ) -> None:
        monkeypatch.delenv("ROBOSCOPE_RECORDER_DISABLED", raising=False)
        session = _mk_session(db_session, admin_user)
        resp = client.post(
            ENDPOINT.format(session.id),
            json={"transport": "desktop_macos"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 501
        assert "DM.1" in resp.json()["detail"]

    def test_desktop_windows_on_windows_dispatches_desktop_task(
        self, client: TestClient, db_session: Session, admin_user: User, monkeypatch
    ) -> None:
        monkeypatch.delenv("ROBOSCOPE_RECORDER_DISABLED", raising=False)
        monkeypatch.setattr("sys.platform", "win32")

        called: dict = {}

        class _FakeResult:
            id = "fake-desktop-task"

        def _fake_dispatch(fn, *args, **kwargs):
            called["fn"] = fn.__name__
            called["args"] = args
            return _FakeResult()

        import src.recording.router as rr
        monkeypatch.setattr(rr, "dispatch_task", _fake_dispatch)

        session = _mk_session(db_session, admin_user)
        resp = client.post(
            ENDPOINT.format(session.id),
            json={"transport": "desktop_windows"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 202
        assert resp.json()["task_id"] == "fake-desktop-task"
        assert called["fn"] == "run_desktop_recorder_session"
        assert called["args"] == (session.id,)

    def test_chrome_extension_rejected_as_400(
        self, client: TestClient, db_session: Session, admin_user: User, monkeypatch
    ) -> None:
        monkeypatch.delenv("ROBOSCOPE_RECORDER_DISABLED", raising=False)
        session = _mk_session(db_session, admin_user)
        resp = client.post(
            ENDPOINT.format(session.id),
            json={"transport": "chrome_extension"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400
