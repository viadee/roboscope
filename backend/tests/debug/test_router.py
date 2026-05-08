"""DEBUG-2 router tests with a fully-mocked RobotDebugSession.

We deliberately don't spawn `robotcode` here — the foundation tests
(`test_robot_debug_session.py`) already cover the spawn-handshake
pipeline against a fake DAP server. This file focuses on the HTTP
shape: routing, RBAC, audit emission, 409 dedup, ownership, and the
state cache → response wiring.

A `_FakeSession` stands in for `RobotDebugSession`. It supports
`__aenter__/__aexit__`, the four control coroutines, `disconnect`,
and exposes a real `asyncio.Queue` so the manager's forwarder can
sit on it without spinning.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.audit.event_types import AuditEventType
from src.audit.models import AuditLog
from src.auth.constants import Role
from src.auth.service import hash_password
from src.debug.session_manager import session_manager
from src.environments.models import Environment
from src.execution.models import ExecutionRun
from src.repos.models import Repository
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeSession:
    """Minimal stand-in for RobotDebugSession used by the manager."""

    instances: list["_FakeSession"] = []

    def __init__(
        self,
        *,
        robot_path: str,
        test_name: str | None,
        breakpoints: list,
        env_python_path: str,
    ) -> None:
        self.robot_path = robot_path
        self.test_name = test_name
        self.breakpoints = breakpoints
        self.env_python_path = env_python_path
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.continue_called = 0
        self.next_called = 0
        self.step_in_called = 0
        self.step_out_called = 0
        self.disconnected = False
        self.entered = False
        _FakeSession.instances.append(self)

    async def __aenter__(self) -> "_FakeSession":
        self.entered = True
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self.disconnected = True

    async def continue_(self) -> None:
        self.continue_called += 1

    async def next_(self) -> None:
        self.next_called += 1

    async def step_in(self) -> None:
        self.step_in_called += 1

    async def step_out(self) -> None:
        self.step_out_called += 1

    async def disconnect(self) -> None:
        self.disconnected = True


@pytest.fixture(autouse=True)
def _swap_factory_and_clear():
    """Inject the fake session factory + drain any leftover sessions
    from prior tests."""
    _FakeSession.instances.clear()
    session_manager.set_factory(_FakeSession)
    # Disable the forwarder + state-fetcher — we test those layers
    # separately and don't want a missing setup to crash the manager.
    session_manager.set_forwarder(lambda *a, **kw: None)
    session_manager.set_state_fetcher(None)  # type: ignore[arg-type]
    yield
    # Best-effort cleanup of any sessions left running.
    asyncio.get_event_loop().run_until_complete(session_manager.stop_all())


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_repo_run(db, user, tmp_path: Path, status: str = "failed") -> tuple[Repository, ExecutionRun]:
    """Create a repository + venv-equipped environment + a failed run
    pointing at a small `.robot` file on disk."""
    # Repo on disk so the fallback-line scan can read the file.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    target = repo_root / "tests.robot"
    target.write_text(
        "*** Test Cases ***\n"
        "Sample\n"
        "    Log    hello\n",
        encoding="utf-8",
    )

    venv_dir = tmp_path / "venv"
    venv_dir.mkdir()
    bin_dir = venv_dir / ("Scripts" if hasattr(__import__("os"), "name") and False else "bin")
    bin_dir.mkdir()
    (bin_dir / "python").write_text("# placeholder", encoding="utf-8")

    env = Environment(
        name="test-env",
        python_version="3.12",
        venv_path=str(venv_dir),
        created_by=user.id,
    )
    db.add(env)
    db.flush()

    repo = Repository(
        name=f"repo-{user.id}",
        repo_type="local",
        local_path=str(repo_root),
        environment_id=env.id,
        created_by=user.id,
    )
    db.add(repo)
    db.flush()

    run = ExecutionRun(
        repository_id=repo.id,
        environment_id=env.id,
        status=status,
        target_path=str(target),
        triggered_by=user.id,
    )
    db.add(run)
    db.flush()
    db.commit()
    return repo, run


# ---------------------------------------------------------------------------
# RBAC + 404 + audit
# ---------------------------------------------------------------------------


class TestStartSessionRBAC:
    def test_returns_404_for_unknown_run(self, client: TestClient, runner_user):
        resp = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": 99999},
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 404

    def test_viewer_is_forbidden(
        self, client: TestClient, db_session, viewer_user, tmp_path
    ):
        _, run = _make_repo_run(db_session, viewer_user, tmp_path)
        resp = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(viewer_user),
        )
        assert resp.status_code == 403

    def test_runner_can_start(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        _, run = _make_repo_run(db_session, runner_user, tmp_path)
        resp = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["session_id"]
        assert body["robot_file"].endswith("tests.robot")
        assert body["breakpoint_line"] >= 1


class TestAuditEmission:
    def test_started_event_logged(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        _, run = _make_repo_run(db_session, runner_user, tmp_path)
        resp = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 201
        # Audit row landed.
        rows = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == AuditEventType.DEBUG_SESSION_STARTED.value)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].user_id == runner_user.id
        assert rows[0].resource_id == run.id


# ---------------------------------------------------------------------------
# 409 dedup
# ---------------------------------------------------------------------------


class TestDedup:
    def test_second_start_returns_existing_session(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        _, run = _make_repo_run(db_session, runner_user, tmp_path)
        first = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert first.status_code == 201
        second = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert second.status_code == 409
        assert second.json()["detail"]["session_id"] == first.json()["session_id"]


# ---------------------------------------------------------------------------
# Control endpoints
# ---------------------------------------------------------------------------


class TestControl:
    def test_continue_step_disconnect(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        _, run = _make_repo_run(db_session, runner_user, tmp_path)
        start = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        sid = start.json()["session_id"]

        for ep, attr in (
            ("continue", "continue_called"),
            ("next", "next_called"),
            ("stepIn", "step_in_called"),
            ("stepOut", "step_out_called"),
        ):
            r = client.post(
                f"/api/v1/debug/sessions/{sid}/{ep}",
                headers=auth_header(runner_user),
            )
            assert r.status_code == 204, f"{ep}: {r.text}"

        # All control hits landed on the fake session.
        fake = _FakeSession.instances[-1]
        assert fake.continue_called == 1
        assert fake.next_called == 1
        assert fake.step_in_called == 1
        assert fake.step_out_called == 1

        # Disconnect is idempotent.
        d1 = client.post(
            f"/api/v1/debug/sessions/{sid}/disconnect",
            headers=auth_header(runner_user),
        )
        assert d1.status_code == 204
        d2 = client.post(
            f"/api/v1/debug/sessions/{sid}/disconnect",
            headers=auth_header(runner_user),
        )
        assert d2.status_code == 204  # idempotent — no 404 even after gone

    def test_other_user_cannot_drive_session(
        self, client: TestClient, db_session, runner_user, admin_user, tmp_path
    ):
        _, run = _make_repo_run(db_session, runner_user, tmp_path)
        start = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        sid = start.json()["session_id"]

        # Even ADMIN cannot drive someone else's debug subprocess.
        r = client.post(
            f"/api/v1/debug/sessions/{sid}/continue",
            headers=auth_header(admin_user),
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# State endpoint
# ---------------------------------------------------------------------------


class TestState:
    def test_initial_state_is_blank(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        _, run = _make_repo_run(db_session, runner_user, tmp_path)
        start = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        sid = start.json()["session_id"]
        r = client.get(
            f"/api/v1/debug/sessions/{sid}/state",
            headers=auth_header(runner_user),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["session_id"] == sid
        assert body["paused"] is False
        assert body["scopes"] == []
