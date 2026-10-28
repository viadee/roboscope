"""Story V15.3 — auto-retry of FAILED/TIMEOUT runs + inert run options."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.execution.models import ExecutionRun, RunnerType, RunStatus, Schedule
from src.execution.runners.base import RunResult
from src.repos.models import Repository
from tests.conftest import auth_header


@pytest.fixture
def repo(db_session: Session, admin_user, tmp_path) -> Repository:
    local = tmp_path / "repo"
    local.mkdir()
    r = Repository(
        name="retry-repo",
        repo_type="git",
        git_url="https://example.com/x.git",
        local_path=str(local),
        default_branch="main",
        created_by=admin_user.id,
    )
    db_session.add(r)
    db_session.flush()
    return r


@pytest.fixture
def schedule(db_session: Session, repo, admin_user) -> Schedule:
    s = Schedule(
        name="Nightly",
        cron_expression="0 2 * * *",
        repository_id=repo.id,
        target_path="suite.robot",
        branch="main",
        runner_type="subprocess",
        created_by=admin_user.id,
        is_active=True,
    )
    db_session.add(s)
    db_session.flush()
    return s


def _make_run(db: Session, repo, user, **kw) -> ExecutionRun:
    defaults = {
        "repository_id": repo.id,
        "target_path": "suite.robot",
        "branch": "main",
        "status": RunStatus.PENDING,
        "runner_type": RunnerType.SUBPROCESS,
        "triggered_by": user.id,
        "tags_include": "smoke",
    }
    defaults.update(kw)
    run = ExecutionRun(**defaults)
    db.add(run)
    db.flush()
    return run


def _execute(db: Session, run_id: int, result: RunResult | Exception, retry_side_effect=None):
    """Run execute_test_run with the runner, sync, broadcast and dispatch patched."""
    from src.execution import tasks

    runner = MagicMock()
    if isinstance(result, Exception):
        runner.execute.side_effect = result
    else:
        runner.execute.return_value = result

    @contextmanager
    def reuse():
        yield db

    dispatch = MagicMock(return_value=MagicMock(id="task-retry"))
    patches = [
        patch.object(tasks, "get_sync_session", reuse),
        patch.object(tasks, "_get_runner", return_value=runner),
        patch.object(tasks, "_broadcast_run_status"),
        patch("src.repos.service.sync_for_run", return_value=("skipped", None)),
        patch("src.task_executor.dispatch_task", dispatch),
    ]
    if retry_side_effect is not None:
        patches.append(patch("src.execution.service.retry_run", side_effect=retry_side_effect))
    for p in patches:
        p.start()
    try:
        tasks.execute_test_run(run_id)
    finally:
        for p in reversed(patches):
            p.stop()
    return dispatch


def _runs(db: Session, repo) -> list[ExecutionRun]:
    return list(
        db.execute(
            select(ExecutionRun)
            .where(ExecutionRun.repository_id == repo.id)
            .order_by(ExecutionRun.id)
        ).scalars()
    )


FAILED = RunResult(success=False, exit_code=1, error_message="1 test failed")
TIMEOUT = RunResult(success=False, exit_code=-1, timed_out=True, error_message="hung")


class TestAutoRetry:
    @pytest.mark.parametrize(
        "result,status", [(FAILED, RunStatus.FAILED), (TIMEOUT, RunStatus.TIMEOUT)]
    )
    def test_failed_or_timeout_retries_once(
        self, db_session, repo, admin_user, schedule, result, status
    ):
        run = _make_run(db_session, repo, admin_user, max_retries=2, schedule_id=schedule.id)
        dispatch = _execute(db_session, run.id, result)

        runs = _runs(db_session, repo)
        assert [r.status for r in runs] == [status, RunStatus.PENDING]
        new = runs[1]
        assert new.retry_count == 1 and new.max_retries == 2
        assert new.schedule_id == schedule.id
        assert (new.target_path, new.environment_id, new.tags_include) == (
            "suite.robot",
            None,
            "smoke",
        )
        assert new.advanced_config is None
        assert new.task_id == "task-retry"
        dispatch.assert_called_once()
        assert dispatch.call_args.args[1] == new.id

    def test_chain_ends_at_max_retries(self, db_session, repo, admin_user):
        run = _make_run(db_session, repo, admin_user, max_retries=2, retry_count=2)
        dispatch = _execute(db_session, run.id, FAILED)
        assert len(_runs(db_session, repo)) == 1
        dispatch.assert_not_called()

    def test_no_retries_configured(self, db_session, repo, admin_user):
        run = _make_run(db_session, repo, admin_user)
        dispatch = _execute(db_session, run.id, FAILED)
        assert len(_runs(db_session, repo)) == 1
        dispatch.assert_not_called()

    def test_passed_is_not_retried(self, db_session, repo, admin_user):
        run = _make_run(db_session, repo, admin_user, max_retries=3)
        dispatch = _execute(db_session, run.id, RunResult(success=True))
        assert [r.status for r in _runs(db_session, repo)] == [RunStatus.PASSED]
        dispatch.assert_not_called()

    def test_cancelled_is_not_retried(self, db_session, repo, admin_user):
        run = _make_run(db_session, repo, admin_user, max_retries=3)
        dispatch = _execute(db_session, run.id, RunResult(success=False, cancelled=True))
        assert [r.status for r in _runs(db_session, repo)] == [RunStatus.CANCELLED]
        dispatch.assert_not_called()

    def test_error_is_not_retried(self, db_session, repo, admin_user):
        run = _make_run(db_session, repo, admin_user, max_retries=3)
        dispatch = _execute(db_session, run.id, RuntimeError("boom"))
        assert [r.status for r in _runs(db_session, repo)] == [RunStatus.ERROR]
        dispatch.assert_not_called()

    def test_retry_failure_keeps_original_status(self, db_session, repo, admin_user):
        run = _make_run(db_session, repo, admin_user, max_retries=1)
        dispatch = _execute(db_session, run.id, FAILED, retry_side_effect=RuntimeError("db down"))
        runs = _runs(db_session, repo)
        assert [r.status for r in runs] == [RunStatus.FAILED]
        dispatch.assert_not_called()


class TestRunCreateOptions:
    def _payload(self, repo_id: int, **kw) -> dict:
        return {"repository_id": repo_id, "target_path": "tests/", **kw}

    def test_parallel_true_rejected(self, client, admin_user, repo):
        r = client.post(
            "/api/v1/runs",
            json=self._payload(repo.id, parallel=True),
            headers=auth_header(admin_user),
        )
        assert r.status_code == 422
        assert "Parallel execution is not supported" in r.text

    @patch("src.execution.router.dispatch_task")
    def test_parallel_false_and_retries_accepted(self, mock_dispatch, client, admin_user, repo):
        mock_dispatch.return_value = MagicMock(id="t")
        r = client.post(
            "/api/v1/runs",
            json=self._payload(repo.id, parallel=False, max_retries=2),
            headers=auth_header(admin_user),
        )
        assert r.status_code == 201
        assert r.json()["parallel"] is False and r.json()["max_retries"] == 2

    def test_retries_with_advanced_config_rejected_before_gate(self, client, admin_user, repo):
        with patch("src.governance.dependencies.gate_advanced_execution") as gate:
            r = client.post(
                "/api/v1/runs",
                json=self._payload(repo.id, max_retries=1, advanced_config={"args": ["--dryrun"]}),
                headers=auth_header(admin_user),
            )
        assert r.status_code == 422
        assert "advanced options" in r.text
        gate.assert_not_called()
