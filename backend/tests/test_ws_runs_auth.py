"""`/ws/runs/{run_id}` must reject unauthenticated / inactive / nonexistent-
run connections (audit finding 1.2) and must not regress `/ws/notifications`'s
existing is_active check (audit finding 2.5).

Both endpoints resolve their DB session via `Depends(get_db)` (not a raw
`SessionLocal()`), specifically so these tests can exercise them through the
same `app.dependency_overrides[get_db]` swap the `client` fixture already
sets up — see main.py's `_ws_authenticate` / `_ws_authorize_run` docstrings.
"""

from starlette.testclient import WebSocketDisconnect

from src.auth.constants import Role
from src.auth.service import create_access_token, hash_password
from src.execution.models import ExecutionRun
from src.repos.models import Repository


def _make_repo(db_session, creator, name="ws-repo"):
    repo = Repository(
        name=name, repo_type="local", local_path=f"/tmp/{name}", created_by=creator.id
    )
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)
    return repo


def _make_run(db_session, repo, triggered_by):
    run = ExecutionRun(
        repository_id=repo.id,
        target_path="suite.robot",
        branch="main",
        triggered_by=triggered_by.id,
    )
    db_session.add(run)
    db_session.flush()
    db_session.refresh(run)
    return run


def _make_user(db_session, role=Role.VIEWER, is_active=True, suffix="a"):
    from src.auth.models import User

    user = User(
        email=f"ws-{suffix}@test.com",
        username=f"ws-{suffix}",
        hashed_password=hash_password("pw123456"),
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


class TestWsRunOutputAuth:
    def test_rejects_missing_token(self, client, db_session, admin_user):
        repo = _make_repo(db_session, admin_user)
        run = _make_run(db_session, repo, admin_user)
        db_session.commit()

        try:
            with client.websocket_connect(f"/ws/runs/{run.id}"):
                pass
            assert False, "expected the server to close the connection"
        except WebSocketDisconnect as exc:
            assert exc.code == 4401

    def test_rejects_invalid_token(self, client, db_session, admin_user):
        repo = _make_repo(db_session, admin_user)
        run = _make_run(db_session, repo, admin_user)
        db_session.commit()

        try:
            with client.websocket_connect(f"/ws/runs/{run.id}?token=not-a-real-jwt"):
                pass
            assert False, "expected the server to close the connection"
        except WebSocketDisconnect as exc:
            assert exc.code == 4401

    def test_rejects_deactivated_user(self, client, db_session, admin_user):
        repo = _make_repo(db_session, admin_user)
        run = _make_run(db_session, repo, admin_user)
        user = _make_user(db_session, is_active=False, suffix="deactivated")
        db_session.commit()
        token = create_access_token(user.id, user.role)

        try:
            with client.websocket_connect(f"/ws/runs/{run.id}?token={token}"):
                pass
            assert False, "expected the server to close the connection"
        except WebSocketDisconnect as exc:
            assert exc.code == 4401

    def test_rejects_nonexistent_run(self, client, db_session):
        user = _make_user(db_session, suffix="norun")
        db_session.commit()
        token = create_access_token(user.id, user.role)

        try:
            with client.websocket_connect(f"/ws/runs/999999?token={token}"):
                pass
            assert False, "expected the server to close the connection"
        except WebSocketDisconnect as exc:
            assert exc.code == 4403

    def test_accepts_any_active_authenticated_user(self, client, db_session, admin_user):
        """Pins the intentional 'read is open' design: `effective_role()`
        has no-deny semantics (module docstring), so a plain VIEWER with
        no team/project grant on this repo still connects — same as
        `GET /runs/{run_id}` requiring only authentication. The
        hardening from 1.2 is the existence + is_active checks above,
        not a new access restriction."""
        repo = _make_repo(db_session, admin_user)
        run = _make_run(db_session, repo, admin_user)
        user = _make_user(db_session, role=Role.VIEWER, suffix="viewer-noaccess")
        db_session.commit()
        token = create_access_token(user.id, user.role)

        with client.websocket_connect(f"/ws/runs/{run.id}?token={token}") as ws:
            ws.send_text("ping")
            assert ws.receive_text() == "pong"


class TestWsNotificationsAuth:
    def test_rejects_deactivated_user(self, client, db_session):
        user = _make_user(db_session, is_active=False, suffix="deactivated-notif")
        db_session.commit()
        token = create_access_token(user.id, user.role)

        try:
            with client.websocket_connect(f"/ws/notifications?token={token}"):
                pass
            assert False, "expected the server to close the connection"
        except WebSocketDisconnect as exc:
            assert exc.code == 4401

    def test_accepts_active_user(self, client, db_session):
        user = _make_user(db_session, suffix="active-notif")
        db_session.commit()
        token = create_access_token(user.id, user.role)

        with client.websocket_connect(f"/ws/notifications?token={token}") as ws:
            ws.send_text("ping")
            assert ws.receive_text() == "pong"
