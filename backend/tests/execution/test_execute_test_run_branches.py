"""Story TEST-5 — `execute_test_run` orchestrator early-exit branches.

The orchestrator is ~200 lines that thread through env-config
resolution, runner selection, listener setup, retries, etc. End-to-end
testing requires real subprocess + venv + parser plumbing.

These tests focus on the **early-exit** branches that don't need a real
runner — each represents a user-visible error mode that has shipped
to production at least once:

1. `run_id` doesn't match a row → `Run not found`
2. `environment_id` set but the env was deleted → "no longer exists"
3. Docker runner requested but env has no `docker_image` →
   "no Docker image" guidance

For each we pin down: (a) the run row's terminal status (ERROR), (b)
the broadcast was emitted, (c) the return-dict shape downstream
callers depend on.

The non-early branches (happy path, cancellation race, retries) are
covered indirectly by the existing webhook + repo integration tests
and would need extensive runner-side mocking to isolate; deferred to
future TEST-* stories if the value materialises.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from src.execution.models import ExecutionRun, RunStatus, RunnerType
from src.repos.models import Repository


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(db_session: Session, admin_user, tmp_path) -> Repository:
    local = tmp_path / "repo"
    local.mkdir()
    r = Repository(
        name="exec-test-repo",
        repo_type="git",
        git_url="https://example.com/x.git",
        local_path=str(local),
        default_branch="main",
        created_by=admin_user.id,
    )
    db_session.add(r)
    db_session.flush()
    db_session.refresh(r)
    return r


def _make_run(
    db: Session, repo: Repository, admin_user, **overrides,
) -> ExecutionRun:
    defaults = dict(
        repository_id=repo.id,
        environment_id=None,
        target_path="suite.robot",
        branch="main",
        status=RunStatus.PENDING,
        runner_type=RunnerType.SUBPROCESS,
        triggered_by=admin_user.id,
    )
    defaults.update(overrides)
    run = ExecutionRun(**defaults)
    db.add(run)
    db.flush()
    db.refresh(run)
    return run


@contextmanager
def _patched_session(test_db: Session):
    """`execute_test_run` opens its own `get_sync_session()` — re-route
    that to the test's transactional session so the rows we insert
    here (and roll back at teardown) are visible to the orchestrator.

    Mirrors the same trick used in `tests/repos/test_auto_sync.py`
    and elsewhere.
    """
    @contextmanager
    def reuse():
        yield test_db
    with patch("src.execution.tasks.get_sync_session", reuse):
        yield


# ---------------------------------------------------------------------------
# Branch 1 — run row missing
# ---------------------------------------------------------------------------


class TestRunNotFound:
    def test_unknown_run_id_returns_error_dict(self, db_session: Session):
        from src.execution.tasks import execute_test_run

        broadcasts: list = []
        with patch(
            "src.execution.tasks._broadcast_run_status",
            side_effect=lambda *a, **kw: broadcasts.append((a, kw)),
        ), _patched_session(db_session):
            result = execute_test_run(99999)

        assert result == {"status": "error", "message": "Run not found"}
        # No broadcast happens for a missing run — there's no run_id to
        # broadcast against in a useful way.
        assert broadcasts == []


# ---------------------------------------------------------------------------
# Branch 2 — environment_id set but env deleted
# ---------------------------------------------------------------------------


class TestEnvironmentMissing:
    def test_returns_error_and_broadcasts(
        self, db_session: Session, admin_user, repo,
    ):
        # Reference an environment id that doesn't exist.
        run = _make_run(db_session, repo, admin_user, environment_id=99999)

        from src.execution.tasks import execute_test_run

        broadcasts: list = []
        with patch(
            "src.execution.tasks._broadcast_run_status",
            side_effect=lambda *a, **kw: broadcasts.append(a),
        ), _patched_session(db_session):
            result = execute_test_run(run.id)

        assert result["status"] == "error"
        assert "no longer exists" in result["message"]

        # The orchestrator broadcasts RUNNING then ERROR.
        statuses = [a[1] for a in broadcasts]
        assert RunStatus.RUNNING in statuses
        assert RunStatus.ERROR in statuses

        db_session.refresh(run)
        assert run.status == RunStatus.ERROR
        assert run.error_message is not None
        assert "no longer exists" in run.error_message
        assert run.finished_at is not None


# ---------------------------------------------------------------------------
# Branch 3 — Docker runner requested but env has no docker_image
# ---------------------------------------------------------------------------


class TestDockerRunnerMissingImage:
    def test_returns_error_and_broadcasts(
        self, db_session: Session, admin_user, repo,
    ):
        # Run requests Docker; env_config exists but has no docker_image
        # → orchestrator must fail-early with the configurable-image
        # guidance, NOT call into the docker SDK.
        run = _make_run(
            db_session, repo, admin_user,
            runner_type=RunnerType.DOCKER, environment_id=42,
        )

        # Stub _get_env_config to return an env without docker_image.
        from src.execution.tasks import execute_test_run

        broadcasts: list = []
        with patch(
            "src.execution.tasks._get_env_config",
            return_value={
                "name": "stubbed-env",
                "default_runner_type": RunnerType.SUBPROCESS,
                "docker_image": None,
                "venv_path": None,
                "packages": [],
            },
        ), patch(
            "src.execution.tasks._broadcast_run_status",
            side_effect=lambda *a, **kw: broadcasts.append(a),
        ), _patched_session(db_session):
            result = execute_test_run(run.id)

        assert result["status"] == "error"
        assert "no Docker image" in result["message"]
        # The error message names the environment so admins know which
        # env is misconfigured — regression guard for the formatting.
        assert "stubbed-env" in result["message"]

        statuses = [a[1] for a in broadcasts]
        assert RunStatus.ERROR in statuses

        db_session.refresh(run)
        assert run.status == RunStatus.ERROR
        assert run.finished_at is not None
