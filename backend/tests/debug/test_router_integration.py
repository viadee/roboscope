"""DEBUG-6: HTTP router → real RobotCode → events round-trip.

These tests are the missing layer between unit tests in
``test_router.py`` (HTTP shape with mocked sessions) and
``test_robot_debug_session.py::TestRealControlButtons`` (real DAP
without HTTP). They drive the actual control endpoints
(``/debug/sessions/{id}/{cmd}``) against a session that spawns real
``robotcode`` and assert the cached state advances per command —
which is what the frontend buttons do via ``debug.store.ts::control``.

Marked ``@pytest.mark.integration``: needs the user's
``~/.roboscope/venvs/roboscope-default`` venv and takes ~10 s per test.
Run manually with::

    pytest -m integration tests/debug/test_router_integration.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.debug.session_manager import _default_factory, session_manager
from src.environments.models import Environment
from src.execution.models import ExecutionRun
from src.repos.models import Repository
from tests.conftest import auth_header

_DEFAULT_ROBOSCOPE_VENV = Path.home() / ".roboscope" / "venvs" / "roboscope-default"


def _check_or_skip() -> Path:
    """Mirrors `TestRealRobotCodeSpawn._check_or_skip` — kept local to
    avoid a cross-module fixture dependency."""
    env_python = _DEFAULT_ROBOSCOPE_VENV / "bin" / "python"
    if not env_python.is_file():
        pytest.skip("RoboScope default venv not found")
    if not (env_python.parent / "robotcode").is_file():
        pytest.skip("robotcode binary missing")
    if not list(_DEFAULT_ROBOSCOPE_VENV.glob(
        "lib/python*/site-packages/robotcode/debugger",
    )):
        pytest.skip("robotcode-debugger plugin missing")
    if not list(_DEFAULT_ROBOSCOPE_VENV.glob(
        "lib/python*/site-packages/robot",
    )):
        pytest.skip("robotframework missing")
    return env_python


@pytest.fixture
def real_session_factory():
    """Restore the production factory for this test (overrides the
    fake-session factory the unit tests inject). Reverted on teardown."""
    session_manager.set_factory(_default_factory)
    yield
    # The other test files' autouse fixtures will re-inject as needed.


def _make_repo_run(db, user, tmp_path: Path) -> tuple[Repository, ExecutionRun, Path]:
    """Set up a repo + env (pointing at the real default venv) + a
    failed run with a tiny breakable .robot file."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    robot = repo_root / "demo.robot"
    # Lines: 1=section, 2=test name, 3-7=keyword body. Breakpoint
    # candidate is line 3 (Log one).
    robot.write_text(
        "*** Test Cases ***\n"
        "Demo\n"
        "    Log    one\n"
        "    Log    two\n"
        "    Log    three\n",
        encoding="utf-8",
    )

    env = Environment(
        name="real-default",
        python_version="3.12",
        venv_path=str(_DEFAULT_ROBOSCOPE_VENV),
        created_by=user.id,
    )
    db.add(env)
    db.flush()

    repo = Repository(
        name=f"router-int-{user.id}",
        repo_type="local",
        local_path=str(repo_root.resolve()),  # macOS /var/.../private path
        environment_id=env.id,
        created_by=user.id,
    )
    db.add(repo)
    db.flush()

    run = ExecutionRun(
        repository_id=repo.id,
        environment_id=env.id,
        status="failed",
        target_path=str(robot.resolve()),
        triggered_by=user.id,
    )
    db.add(run)
    db.flush()
    db.commit()
    return repo, run, robot.resolve()


async def _wait_for_paused(
    client: TestClient,
    session_id: str,
    runner_user,
    timeout: float = 20.0,
) -> dict:
    """Poll the state endpoint until the session reports paused.

    Mirrors what the frontend does after receiving a `stopped` event —
    it doesn't wait for the WebSocket payload, it polls/uses the cache.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    last_state: dict = {}
    while asyncio.get_running_loop().time() < deadline:
        resp = client.get(
            f"/api/v1/debug/sessions/{session_id}/state",
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 200, resp.text
        last_state = resp.json()
        if last_state.get("paused"):
            return last_state
        await asyncio.sleep(0.2)
    pytest.fail(f"Session {session_id} never reached paused state. Last: {last_state}")


async def _wait_for_terminated(
    client: TestClient,
    session_id: str,
    runner_user,
    timeout: float = 20.0,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        resp = client.get(
            f"/api/v1/debug/sessions/{session_id}/state",
            headers=auth_header(runner_user),
        )
        if resp.status_code == 404:
            # session_manager reaped the session — equivalent to terminated.
            return
        body = resp.json()
        if body.get("terminated"):
            return
        await asyncio.sleep(0.2)
    pytest.fail(f"Session {session_id} never terminated within {timeout}s")


# ---------------------------------------------------------------------------
# Real HTTP router → real RobotCode session
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("real_session_factory")
class TestRealRouterControls:
    """Each test starts a session via POST and drives one control
    command per the frontend's debug.store.ts contract."""

    @pytest.mark.asyncio
    async def test_post_start_then_continue_to_termination(
        self,
        client: TestClient,
        db_session,
        runner_user,
        tmp_path,
    ) -> None:
        _check_or_skip()
        _, run, _robot = _make_repo_run(db_session, runner_user, tmp_path)

        start = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert start.status_code == 201, start.text
        sid = start.json()["session_id"]

        await _wait_for_paused(client, sid, runner_user)

        cont = client.post(
            f"/api/v1/debug/sessions/{sid}/continue",
            headers=auth_header(runner_user),
        )
        assert cont.status_code == 204, cont.text

        await _wait_for_terminated(client, sid, runner_user)

    @pytest.mark.asyncio
    async def test_post_start_then_step_over(
        self,
        client: TestClient,
        db_session,
        runner_user,
        tmp_path,
    ) -> None:
        _check_or_skip()
        _, run, _robot = _make_repo_run(db_session, runner_user, tmp_path)

        start = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert start.status_code == 201
        sid = start.json()["session_id"]

        first = await _wait_for_paused(client, sid, runner_user)
        first_line = (first.get("paused_at") or {}).get("line")

        step = client.post(
            f"/api/v1/debug/sessions/{sid}/next",
            headers=auth_header(runner_user),
        )
        assert step.status_code == 204, step.text

        # After step-over, paused state should reset and re-fire on the
        # NEXT line. Wait for a fresh pause whose line differs.
        deadline = asyncio.get_running_loop().time() + 15.0
        second_line = first_line
        while asyncio.get_running_loop().time() < deadline:
            resp = client.get(
                f"/api/v1/debug/sessions/{sid}/state",
                headers=auth_header(runner_user),
            )
            if resp.status_code == 404:
                break
            body = resp.json()
            cur = (body.get("paused_at") or {}).get("line")
            if body.get("paused") and cur != first_line and cur is not None:
                second_line = cur
                break
            await asyncio.sleep(0.2)
        assert second_line != first_line, (
            f"step-over didn't advance. first={first_line} second={second_line}"
        )

        # Tear down cleanly so we don't leave a paused subprocess.
        client.post(
            f"/api/v1/debug/sessions/{sid}/disconnect",
            headers=auth_header(runner_user),
        )

    @pytest.mark.asyncio
    async def test_post_start_then_step_in(
        self,
        client: TestClient,
        db_session,
        runner_user,
        tmp_path,
    ) -> None:
        _check_or_skip()
        _, run, _robot = _make_repo_run(db_session, runner_user, tmp_path)

        start = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert start.status_code == 201
        sid = start.json()["session_id"]
        first = await _wait_for_paused(client, sid, runner_user)
        first_line = (first.get("paused_at") or {}).get("line")

        step = client.post(
            f"/api/v1/debug/sessions/{sid}/stepIn",
            headers=auth_header(runner_user),
        )
        assert step.status_code == 204, step.text

        # stepIn into a built-in (Log) behaves like step-over for our
        # purposes: a fresh pause on the next line.
        deadline = asyncio.get_running_loop().time() + 15.0
        advanced = False
        while asyncio.get_running_loop().time() < deadline:
            resp = client.get(
                f"/api/v1/debug/sessions/{sid}/state",
                headers=auth_header(runner_user),
            )
            if resp.status_code == 404:
                advanced = True
                break
            body = resp.json()
            cur = (body.get("paused_at") or {}).get("line")
            if body.get("paused") and cur != first_line:
                advanced = True
                break
            if body.get("terminated"):
                advanced = True  # terminated is also acceptable progress
                break
            await asyncio.sleep(0.2)
        assert advanced, f"stepIn didn't advance. first_line={first_line}"

        client.post(
            f"/api/v1/debug/sessions/{sid}/disconnect",
            headers=auth_header(runner_user),
        )

    @pytest.mark.asyncio
    async def test_post_start_then_step_out(
        self,
        client: TestClient,
        db_session,
        runner_user,
        tmp_path,
    ) -> None:
        _check_or_skip()
        _, run, _robot = _make_repo_run(db_session, runner_user, tmp_path)

        start = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert start.status_code == 201
        sid = start.json()["session_id"]
        await _wait_for_paused(client, sid, runner_user)

        step = client.post(
            f"/api/v1/debug/sessions/{sid}/stepOut",
            headers=auth_header(runner_user),
        )
        assert step.status_code == 204, step.text

        # stepOut from a flat test runs to the end → terminated is the
        # expected outcome. Either a stopped event on a teardown line
        # or terminated is OK.
        deadline = asyncio.get_running_loop().time() + 20.0
        done = False
        while asyncio.get_running_loop().time() < deadline:
            resp = client.get(
                f"/api/v1/debug/sessions/{sid}/state",
                headers=auth_header(runner_user),
            )
            if resp.status_code == 404:
                done = True
                break
            body = resp.json()
            if body.get("terminated") or (body.get("paused") and body.get("paused_at")):
                done = True
                break
            await asyncio.sleep(0.2)
        assert done, "stepOut produced no observable progress"

        client.post(
            f"/api/v1/debug/sessions/{sid}/disconnect",
            headers=auth_header(runner_user),
        )

    @pytest.mark.asyncio
    async def test_post_start_then_disconnect_kills_session(
        self,
        client: TestClient,
        db_session,
        runner_user,
        tmp_path,
    ) -> None:
        """``Stop`` button ergonomics: disconnect must reap the session
        (404 on subsequent state lookup) and the underlying subprocess
        tree."""
        _check_or_skip()
        _, run, _robot = _make_repo_run(db_session, runner_user, tmp_path)

        start = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert start.status_code == 201
        sid = start.json()["session_id"]
        await _wait_for_paused(client, sid, runner_user)

        disc = client.post(
            f"/api/v1/debug/sessions/{sid}/disconnect",
            headers=auth_header(runner_user),
        )
        assert disc.status_code == 204, disc.text

        # Allow cleanup tasks to run.
        await asyncio.sleep(1.0)

        # State endpoint should 404 (session reaped) OR report terminated.
        resp = client.get(
            f"/api/v1/debug/sessions/{sid}/state",
            headers=auth_header(runner_user),
        )
        assert resp.status_code in {404, 200}
        if resp.status_code == 200:
            body = resp.json()
            assert body.get("terminated") or not body.get("paused"), body

        # Disconnect is idempotent — second call must also 204.
        disc2 = client.post(
            f"/api/v1/debug/sessions/{sid}/disconnect",
            headers=auth_header(runner_user),
        )
        assert disc2.status_code == 204


# ---------------------------------------------------------------------------
# DEBUG-7: complex scenarios via the HTTP router
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("real_session_factory")
class TestComplexRouterScenarios:
    """End-to-end flows that mirror what a user actually does in the
    debug panel: pause, step several times, observe the cached state
    update each time, then continue/disconnect cleanly. Each test
    drives the same surface the frontend buttons hit."""

    @pytest.mark.asyncio
    async def test_full_walk_through_via_http(
        self,
        client: TestClient,
        db_session,
        runner_user,
        tmp_path,
    ) -> None:
        """User flow: hit a breakpoint, step over twice, then continue
        to terminate. The cached `paused_at.line` MUST advance with
        each step — that's the field the run-detail panel header
        renders, and it was the user's "doesn't feel clean" symptom."""
        _check_or_skip()
        _, run, _robot = _make_repo_run(db_session, runner_user, tmp_path)

        start = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert start.status_code == 201
        sid = start.json()["session_id"]

        first = await _wait_for_paused(client, sid, runner_user)
        line_a = (first.get("paused_at") or {}).get("line")
        assert line_a is not None

        # First step.
        s1 = client.post(
            f"/api/v1/debug/sessions/{sid}/next",
            headers=auth_header(runner_user),
        )
        assert s1.status_code == 204
        # Wait for the new line.
        deadline = asyncio.get_running_loop().time() + 10.0
        line_b = line_a
        while asyncio.get_running_loop().time() < deadline:
            r = client.get(
                f"/api/v1/debug/sessions/{sid}/state",
                headers=auth_header(runner_user),
            )
            if r.status_code == 404:
                pytest.fail("session 404'd before second pause — disconnect raced")
            body = r.json()
            cur = (body.get("paused_at") or {}).get("line")
            if body.get("paused") and cur and cur != line_a:
                line_b = cur
                break
            await asyncio.sleep(0.2)
        assert line_b != line_a, "first step did not advance line"

        # Second step.
        s2 = client.post(
            f"/api/v1/debug/sessions/{sid}/next",
            headers=auth_header(runner_user),
        )
        assert s2.status_code == 204
        deadline = asyncio.get_running_loop().time() + 10.0
        line_c = line_b
        while asyncio.get_running_loop().time() < deadline:
            r = client.get(
                f"/api/v1/debug/sessions/{sid}/state",
                headers=auth_header(runner_user),
            )
            if r.status_code == 404:
                # Reached end of test → that's fine, second step ran past EOF.
                line_c = -1
                break
            body = r.json()
            cur = (body.get("paused_at") or {}).get("line")
            if body.get("terminated"):
                line_c = -1
                break
            if body.get("paused") and cur and cur != line_b:
                line_c = cur
                break
            await asyncio.sleep(0.2)
        assert line_c != line_b, "second step did not advance state"

        # Continue (or disconnect) to clean up.
        if line_c != -1:
            client.post(
                f"/api/v1/debug/sessions/{sid}/continue",
                headers=auth_header(runner_user),
            )
        await _wait_for_terminated(client, sid, runner_user, timeout=15.0)

    @pytest.mark.asyncio
    async def test_409_returns_existing_session_id(
        self,
        client: TestClient,
        db_session,
        runner_user,
        tmp_path,
    ) -> None:
        """The frontend treats 409 as "silent resume" — the response
        MUST include the existing session_id so the panel can attach."""
        _check_or_skip()
        _, run, _robot = _make_repo_run(db_session, runner_user, tmp_path)

        first = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert first.status_code == 201
        sid = first.json()["session_id"]

        # Wait for the session to be active so dedup considers it.
        await _wait_for_paused(client, sid, runner_user)

        # Second start for the SAME run — must 409 with the existing id.
        second = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        assert second.status_code == 409, second.text
        detail = second.json()["detail"]
        assert isinstance(detail, dict)
        assert detail.get("session_id") == sid

        client.post(
            f"/api/v1/debug/sessions/{sid}/disconnect",
            headers=auth_header(runner_user),
        )

    @pytest.mark.asyncio
    async def test_control_after_disconnect_returns_404(
        self,
        client: TestClient,
        db_session,
        runner_user,
        tmp_path,
    ) -> None:
        """After Stop the session is reaped — any further control hit
        must 404, not crash. (Frontend has the disabled-state guard,
        but a stale tab racing disconnect must not take down the
        backend.)"""
        _check_or_skip()
        _, run, _robot = _make_repo_run(db_session, runner_user, tmp_path)

        start = client.post(
            "/api/v1/debug/sessions",
            json={"run_id": run.id},
            headers=auth_header(runner_user),
        )
        sid = start.json()["session_id"]
        await _wait_for_paused(client, sid, runner_user)

        client.post(
            f"/api/v1/debug/sessions/{sid}/disconnect",
            headers=auth_header(runner_user),
        )
        # disconnect is idempotent → 204
        idem = client.post(
            f"/api/v1/debug/sessions/{sid}/disconnect",
            headers=auth_header(runner_user),
        )
        assert idem.status_code == 204

        # Other controls 404 (the session is gone).
        await asyncio.sleep(0.5)
        cont = client.post(
            f"/api/v1/debug/sessions/{sid}/continue",
            headers=auth_header(runner_user),
        )
        assert cont.status_code == 404, cont.text
        nxt = client.post(
            f"/api/v1/debug/sessions/{sid}/next",
            headers=auth_header(runner_user),
        )
        assert nxt.status_code == 404
