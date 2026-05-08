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
import contextlib
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
    # Best-effort cleanup of any sessions left running. ``asyncio.run``
    # is robust to neighbour test files that close the thread's loop
    # via their own ``asyncio.run`` calls (e.g. test_prereq.py).
    try:
        asyncio.run(session_manager.stop_all())
    except RuntimeError:
        # Already inside a running loop or a stale loop is current —
        # try the legacy path as a fallback so we never block teardown.
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(session_manager.stop_all())
        finally:
            with contextlib.suppress(Exception):
                loop.close()


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
    # DEBUG-4: existing tests assume RobotCode + debugger plugin are
    # installed. Prereq check looks for the binary AND the debugger
    # site-packages dir, so seed both placeholders.
    (bin_dir / "robotcode").write_text("# placeholder", encoding="utf-8")
    debugger_dir = venv_dir / "lib" / "python3.12" / "site-packages" / "robotcode" / "debugger"
    debugger_dir.mkdir(parents=True)
    (debugger_dir / "__init__.py").write_text("", encoding="utf-8")

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


# ---------------------------------------------------------------------------
# DEBUG-3 — step-shape body ({file, test_name, line, repo_id})
# ---------------------------------------------------------------------------


def _make_repo_with_test(
    db, user, tmp_path: Path, *, test_name: str = "Login Test"
) -> tuple[Repository, Path]:
    """Set up a repo + venv'd env with a `.robot` file that contains the
    named test. Returns (repo, repo-relative-test-path).
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir(exist_ok=True)
    target = repo_root / "tests.robot"
    # 4-line test: header on line 2, body lines 3-4. Line 1 is the
    # section header. Means line 3 is the first executable body line
    # and line 2 is the test-header line we MUST reject.
    target.write_text(
        "*** Test Cases ***\n"
        f"{test_name}\n"
        "    Log    starting\n"
        "    Log    finished\n",
        encoding="utf-8",
    )

    venv_dir = tmp_path / "venv2"
    venv_dir.mkdir(exist_ok=True)
    bin_dir = venv_dir / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "python").write_text("# placeholder", encoding="utf-8")
    (bin_dir / "robotcode").write_text("# placeholder", encoding="utf-8")
    debugger_dir = venv_dir / "lib" / "python3.12" / "site-packages" / "robotcode" / "debugger"
    debugger_dir.mkdir(parents=True, exist_ok=True)
    (debugger_dir / "__init__.py").write_text("", encoding="utf-8")

    env = Environment(
        name=f"env-{user.id}",
        python_version="3.12",
        venv_path=str(venv_dir),
        created_by=user.id,
    )
    db.add(env)
    db.flush()

    repo = Repository(
        name=f"repo-step-{user.id}",
        repo_type="local",
        local_path=str(repo_root),
        environment_id=env.id,
        created_by=user.id,
    )
    db.add(repo)
    db.flush()
    db.commit()
    return repo, target.relative_to(repo_root)


class TestStartFromStepHappyPath:
    def test_runner_can_start_from_step(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        repo, rel_path = _make_repo_with_test(db_session, runner_user, tmp_path)
        resp = client.post(
            "/api/v1/debug/sessions",
            json={
                "file": str(rel_path),
                "test_name": "Login Test",
                "line": 3,
                "repo_id": repo.id,
            },
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["test_name"] == "Login Test"
        assert body["breakpoint_line"] == 3
        # Audit picked up the new ``source`` discriminator.
        rows = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == AuditEventType.DEBUG_SESSION_STARTED.value)
            .all()
        )
        assert len(rows) == 1
        import json as _json
        details = _json.loads(rows[0].detail) if rows[0].detail else {}
        assert details.get("source") == "flow_editor"


class TestStartFromStepValidation:
    def test_rejects_test_header_line(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        """AC4: line == test-case header line is a 422; RF won't break there."""
        repo, rel_path = _make_repo_with_test(db_session, runner_user, tmp_path)
        # The `Login Test` name lives on line 2 (header line above).
        resp = client.post(
            "/api/v1/debug/sessions",
            json={
                "file": str(rel_path),
                "test_name": "Login Test",
                "line": 2,
                "repo_id": repo.id,
            },
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 422
        assert "header" in resp.text.lower()

    def test_rejects_unknown_test_name(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        repo, rel_path = _make_repo_with_test(db_session, runner_user, tmp_path)
        resp = client.post(
            "/api/v1/debug/sessions",
            json={
                "file": str(rel_path),
                "test_name": "Nonexistent Test",
                "line": 3,
                "repo_id": repo.id,
            },
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 422
        assert "not found" in resp.text.lower()

    def test_rejects_line_outside_test(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        repo, rel_path = _make_repo_with_test(db_session, runner_user, tmp_path)
        # Line 1 is the section header, before the test starts.
        resp = client.post(
            "/api/v1/debug/sessions",
            json={
                "file": str(rel_path),
                "test_name": "Login Test",
                "line": 1,
                "repo_id": repo.id,
            },
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 422

    def test_rejects_missing_file(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        repo, _ = _make_repo_with_test(db_session, runner_user, tmp_path)
        resp = client.post(
            "/api/v1/debug/sessions",
            json={
                "file": "no-such-file.robot",
                "test_name": "Login Test",
                "line": 3,
                "repo_id": repo.id,
            },
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 422

    def test_rejects_path_traversal(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        """A `../../etc/passwd` payload must NOT escape the repo root."""
        repo, _ = _make_repo_with_test(db_session, runner_user, tmp_path)
        resp = client.post(
            "/api/v1/debug/sessions",
            json={
                "file": "../../../../etc/passwd",
                "test_name": "Login Test",
                "line": 3,
                "repo_id": repo.id,
            },
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 422

    def test_rejects_mixed_run_and_step_shape(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        """Body must be exactly one shape — neither both nor empty."""
        repo, rel_path = _make_repo_with_test(db_session, runner_user, tmp_path)
        resp = client.post(
            "/api/v1/debug/sessions",
            json={
                "run_id": 1,
                "file": str(rel_path),
                "test_name": "Login Test",
                "line": 3,
                "repo_id": repo.id,
            },
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 422

    def test_rejects_empty_body(
        self, client: TestClient, runner_user
    ):
        resp = client.post(
            "/api/v1/debug/sessions",
            json={},
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 422


class TestStartFromStepRBAC:
    def test_viewer_is_forbidden(
        self, client: TestClient, db_session, viewer_user, tmp_path
    ):
        repo, rel_path = _make_repo_with_test(db_session, viewer_user, tmp_path)
        resp = client.post(
            "/api/v1/debug/sessions",
            json={
                "file": str(rel_path),
                "test_name": "Login Test",
                "line": 3,
                "repo_id": repo.id,
            },
            headers=auth_header(viewer_user),
        )
        assert resp.status_code == 403


class TestStartFromStepDedup:
    def test_same_file_and_line_returns_existing(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        """AC6 silent-resume: clicking the same step twice yields 409."""
        repo, rel_path = _make_repo_with_test(db_session, runner_user, tmp_path)
        body = {
            "file": str(rel_path),
            "test_name": "Login Test",
            "line": 3,
            "repo_id": repo.id,
        }
        first = client.post(
            "/api/v1/debug/sessions",
            json=body,
            headers=auth_header(runner_user),
        )
        assert first.status_code == 201
        sid = first.json()["session_id"]

        second = client.post(
            "/api/v1/debug/sessions",
            json=body,
            headers=auth_header(runner_user),
        )
        assert second.status_code == 409
        assert second.json()["detail"]["session_id"] == sid

    def test_different_line_does_NOT_dedup(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        """AC6 different-step semantics: a different line in the same file
        is NOT a dedup match — two parallel sessions exist (the frontend
        is responsible for stopping the first before starting the second
        via a confirm-modal). The backend just allows both to coexist."""
        repo, rel_path = _make_repo_with_test(db_session, runner_user, tmp_path)
        first = client.post(
            "/api/v1/debug/sessions",
            json={
                "file": str(rel_path),
                "test_name": "Login Test",
                "line": 3,
                "repo_id": repo.id,
            },
            headers=auth_header(runner_user),
        )
        assert first.status_code == 201

        second = client.post(
            "/api/v1/debug/sessions",
            json={
                "file": str(rel_path),
                "test_name": "Login Test",
                "line": 4,
                "repo_id": repo.id,
            },
            headers=auth_header(runner_user),
        )
        assert second.status_code == 201
        assert second.json()["session_id"] != first.json()["session_id"]


# ---------------------------------------------------------------------------
# DEBUG-4 — robotcode prereq detection + install endpoint
# ---------------------------------------------------------------------------


class TestPrereq424:
    def test_run_shape_returns_424_when_robotcode_missing(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        _, run = _make_repo_run(db_session, runner_user, tmp_path)
        # Drop the placeholder binary the fixture creates so the prereq
        # check fires.
        env = db_session.query(Environment).first()
        assert env is not None
        (Path(env.venv_path) / "bin" / "robotcode").unlink()

        resp = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 424
        body = resp.json()
        assert body["detail"]["code"] == "robotcode_not_installed"
        assert body["detail"]["package"] == "robotcode[debugger]"
        assert body["detail"]["repo_id"]
        assert body["detail"]["env_id"]

    def test_step_shape_returns_424_when_robotcode_missing(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        repo, rel_path = _make_repo_with_test(db_session, runner_user, tmp_path)
        env = db_session.get(Environment, repo.environment_id)
        assert env is not None
        (Path(env.venv_path) / "bin" / "robotcode").unlink()

        resp = client.post(
            "/api/v1/debug/sessions",
            json={
                "file": str(rel_path),
                "test_name": "Login Test",
                "line": 3,
                "repo_id": repo.id,
            },
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 424
        assert resp.json()["detail"]["code"] == "robotcode_not_installed"

    def test_no_audit_emitted_for_424(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        _, run = _make_repo_run(db_session, runner_user, tmp_path)
        env = db_session.query(Environment).first()
        (Path(env.venv_path) / "bin" / "robotcode").unlink()

        resp = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 424

        rows = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == AuditEventType.DEBUG_SESSION_STARTED.value)
            .all()
        )
        assert rows == []


class TestPrereqInstallEndpoint:
    def test_install_returns_already_installed_when_present(
        self, client: TestClient, db_session, runner_user, tmp_path
    ):
        repo, _ = _make_repo_run(db_session, runner_user, tmp_path)
        # Fixture left robotcode in place — endpoint should short-circuit.
        resp = client.post(
            "/api/v1/debug/sessions/install-prerequisites",
            json={"repo_id": repo.id},
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["already_installed"] is True
        assert body["log_tail"] is None

    def test_install_invokes_uv_pip_when_missing(
        self, client: TestClient, db_session, runner_user, tmp_path, monkeypatch
    ):
        repo, _ = _make_repo_run(db_session, runner_user, tmp_path)
        env = db_session.query(Environment).first()
        (Path(env.venv_path) / "bin" / "robotcode").unlink()

        # Stub the install: drop a fresh placeholder + return success.
        async def fake_install(venv_path: str) -> str:
            v = Path(venv_path)
            (v / "bin" / "robotcode").write_text("# installed", encoding="utf-8")
            (v / "lib" / "python3.12" / "site-packages" / "robotcode" / "debugger").mkdir(
                parents=True, exist_ok=True,
            )
            return "Installed robotcode-1.2.3"

        monkeypatch.setattr(
            "src.debug.router.install_robotcode", fake_install
        )

        resp = client.post(
            "/api/v1/debug/sessions/install-prerequisites",
            json={"repo_id": repo.id},
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["already_installed"] is False
        assert body["log_tail"] == "Installed robotcode-1.2.3"

        # Audit row landed.
        rows = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == AuditEventType.DEBUG_ROBOTCODE_INSTALLED.value)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].user_id == runner_user.id

    def test_install_failure_returns_500(
        self, client: TestClient, db_session, runner_user, tmp_path, monkeypatch
    ):
        repo, _ = _make_repo_run(db_session, runner_user, tmp_path)
        env = db_session.query(Environment).first()
        (Path(env.venv_path) / "bin" / "robotcode").unlink()

        from src.debug.prereq import PrereqInstallFailed

        async def fail_install(venv_path: str) -> str:
            raise PrereqInstallFailed("uv pip install exited with code 1:\nERROR: …")

        monkeypatch.setattr(
            "src.debug.router.install_robotcode", fail_install
        )

        resp = client.post(
            "/api/v1/debug/sessions/install-prerequisites",
            json={"repo_id": repo.id},
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 500
        body = resp.json()
        assert body["detail"]["code"] == "robotcode_install_failed"
        assert "uv pip install" in body["detail"]["message"]

    def test_install_viewer_is_forbidden(
        self, client: TestClient, db_session, viewer_user, tmp_path
    ):
        repo, _ = _make_repo_run(db_session, viewer_user, tmp_path)
        resp = client.post(
            "/api/v1/debug/sessions/install-prerequisites",
            json={"repo_id": repo.id},
            headers=auth_header(viewer_user),
        )
        assert resp.status_code == 403
