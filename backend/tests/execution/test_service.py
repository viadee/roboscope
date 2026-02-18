"""Tests for execution service: run management and scheduling."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.constants import Role
from src.auth.service import hash_password
from src.execution.models import ExecutionRun, RunStatus, RunType, RunnerType, Schedule
from src.execution.schemas import RunCreate, ScheduleCreate, ScheduleUpdate
from src.execution.service import (
    cancel_run,
    create_run,
    create_schedule,
    delete_schedule,
    get_run,
    get_schedule,
    list_runs,
    list_schedules,
    retry_run,
    toggle_schedule,
    update_run_status,
)
from src.repos.models import Repository


@pytest_asyncio.fixture
async def user(db_session: AsyncSession):
    """Create a user that can trigger runs."""
    from src.auth.models import User

    user = User(
        email="exec_user@test.com",
        username="exec_user",
        hashed_password=hash_password("pass123"),
        role=Role.RUNNER,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def repo(db_session: AsyncSession, user):
    """Create a repository for execution runs."""
    repository = Repository(
        name="test-repo",
        git_url="https://github.com/test/test-repo.git",
        default_branch="main",
        local_path="/tmp/repos/test-repo",
        created_by=user.id,
    )
    db_session.add(repository)
    await db_session.flush()
    await db_session.refresh(repository)
    return repository


@pytest_asyncio.fixture
async def second_repo(db_session: AsyncSession, user):
    """Create a second repository for filtering tests."""
    repository = Repository(
        name="other-repo",
        git_url="https://github.com/test/other-repo.git",
        default_branch="develop",
        local_path="/tmp/repos/other-repo",
        created_by=user.id,
    )
    db_session.add(repository)
    await db_session.flush()
    await db_session.refresh(repository)
    return repository


def _run_create(repo_id: int, **overrides) -> RunCreate:
    """Helper to build a RunCreate with sensible defaults."""
    defaults = {
        "repository_id": repo_id,
        "target_path": "tests/smoke",
        "branch": "main",
        "run_type": RunType.SINGLE,
        "runner_type": RunnerType.SUBPROCESS,
    }
    defaults.update(overrides)
    return RunCreate(**defaults)


def _schedule_create(repo_id: int, **overrides) -> ScheduleCreate:
    """Helper to build a ScheduleCreate with sensible defaults."""
    defaults = {
        "name": "Nightly smoke",
        "cron_expression": "0 2 * * *",
        "repository_id": repo_id,
        "target_path": "tests/smoke",
        "branch": "main",
    }
    defaults.update(overrides)
    return ScheduleCreate(**defaults)


# ---------------------------------------------------------------------------
# Execution Runs
# ---------------------------------------------------------------------------


class TestCreateRun:
    async def test_create_run_defaults(self, db_session, user, repo):
        data = _run_create(repo.id)
        run = await create_run(db_session, data, user.id)

        assert run.id is not None
        assert run.repository_id == repo.id
        assert run.triggered_by == user.id
        assert run.status == RunStatus.PENDING
        assert run.target_path == "tests/smoke"
        assert run.branch == "main"
        assert run.run_type == RunType.SINGLE
        assert run.runner_type == RunnerType.SUBPROCESS
        assert run.parallel is False
        assert run.max_retries == 0
        assert run.timeout_seconds == 3600
        assert run.retry_count == 0

    async def test_create_run_with_all_fields(self, db_session, user, repo):
        data = _run_create(
            repo.id,
            run_type=RunType.FOLDER,
            runner_type=RunnerType.DOCKER,
            target_path="tests/integration",
            branch="develop",
            tags_include="smoke",
            tags_exclude="slow",
            variables={"ENV": "staging"},
            parallel=True,
            max_retries=3,
            timeout_seconds=7200,
        )
        run = await create_run(db_session, data, user.id)

        assert run.run_type == RunType.FOLDER
        assert run.runner_type == RunnerType.DOCKER
        assert run.target_path == "tests/integration"
        assert run.branch == "develop"
        assert run.tags_include == "smoke"
        assert run.tags_exclude == "slow"
        assert run.variables is not None  # JSON-serialised
        assert run.parallel is True
        assert run.max_retries == 3
        assert run.timeout_seconds == 7200


class TestGetRun:
    async def test_get_run_found(self, db_session, user, repo):
        data = _run_create(repo.id)
        created = await create_run(db_session, data, user.id)

        fetched = await get_run(db_session, created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.target_path == created.target_path

    async def test_get_run_not_found(self, db_session):
        fetched = await get_run(db_session, 99999)
        assert fetched is None


class TestListRuns:
    async def test_list_runs_empty(self, db_session, repo):
        runs, total = await list_runs(db_session)
        assert runs == []
        assert total == 0

    async def test_list_runs_with_runs(self, db_session, user, repo):
        for i in range(3):
            await create_run(db_session, _run_create(repo.id, target_path=f"tests/t{i}"), user.id)

        runs, total = await list_runs(db_session)
        assert total == 3
        assert len(runs) == 3

    async def test_list_runs_pagination(self, db_session, user, repo):
        for i in range(5):
            await create_run(db_session, _run_create(repo.id, target_path=f"tests/p{i}"), user.id)

        # Page 1
        runs_p1, total = await list_runs(db_session, page=1, page_size=2)
        assert total == 5
        assert len(runs_p1) == 2

        # Page 2
        runs_p2, _ = await list_runs(db_session, page=2, page_size=2)
        assert len(runs_p2) == 2

        # Page 3 (last, partial)
        runs_p3, _ = await list_runs(db_session, page=3, page_size=2)
        assert len(runs_p3) == 1

        # All IDs are distinct
        all_ids = [r.id for r in runs_p1 + runs_p2 + runs_p3]
        assert len(set(all_ids)) == 5

    async def test_list_runs_filter_by_status(self, db_session, user, repo):
        run1 = await create_run(db_session, _run_create(repo.id), user.id)
        run2 = await create_run(db_session, _run_create(repo.id), user.id)
        await update_run_status(db_session, run2, RunStatus.RUNNING)

        runs, total = await list_runs(db_session, status=RunStatus.PENDING)
        assert total == 1
        assert runs[0].id == run1.id

        runs, total = await list_runs(db_session, status=RunStatus.RUNNING)
        assert total == 1
        assert runs[0].id == run2.id

    async def test_list_runs_filter_by_repository_id(self, db_session, user, repo, second_repo):
        await create_run(db_session, _run_create(repo.id), user.id)
        await create_run(db_session, _run_create(second_repo.id), user.id)

        runs, total = await list_runs(db_session, repository_id=repo.id)
        assert total == 1
        assert runs[0].repository_id == repo.id

        runs, total = await list_runs(db_session, repository_id=second_repo.id)
        assert total == 1
        assert runs[0].repository_id == second_repo.id


class TestUpdateRunStatus:
    async def test_update_to_running_sets_started_at(self, db_session, user, repo):
        run = await create_run(db_session, _run_create(repo.id), user.id)
        assert run.started_at is None

        updated = await update_run_status(db_session, run, RunStatus.RUNNING)
        assert updated.status == RunStatus.RUNNING
        assert updated.started_at is not None

    async def test_update_to_passed_sets_finished_at(self, db_session, user, repo):
        run = await create_run(db_session, _run_create(repo.id), user.id)
        await update_run_status(db_session, run, RunStatus.RUNNING)

        updated = await update_run_status(
            db_session,
            run,
            RunStatus.PASSED,
            duration_seconds=12.5,
            output_dir="/tmp/output/1",
        )
        assert updated.status == RunStatus.PASSED
        assert updated.finished_at is not None
        assert updated.duration_seconds == 12.5
        assert updated.output_dir == "/tmp/output/1"

    async def test_update_with_error_message(self, db_session, user, repo):
        run = await create_run(db_session, _run_create(repo.id), user.id)
        updated = await update_run_status(
            db_session, run, RunStatus.ERROR, error_message="Segfault"
        )
        assert updated.status == RunStatus.ERROR
        assert updated.error_message == "Segfault"
        assert updated.finished_at is not None

    async def test_update_celery_task_id(self, db_session, user, repo):
        run = await create_run(db_session, _run_create(repo.id), user.id)
        updated = await update_run_status(
            db_session, run, RunStatus.RUNNING, celery_task_id="abc-123"
        )
        assert updated.celery_task_id == "abc-123"


class TestCancelRun:
    async def test_cancel_pending_run(self, db_session, user, repo):
        run = await create_run(db_session, _run_create(repo.id), user.id)
        assert run.status == RunStatus.PENDING

        cancelled = await cancel_run(db_session, run)
        assert cancelled.status == RunStatus.CANCELLED
        assert cancelled.finished_at is not None

    async def test_cancel_running_run_with_celery(self, db_session, user, repo):
        run = await create_run(db_session, _run_create(repo.id), user.id)
        await update_run_status(
            db_session, run, RunStatus.RUNNING, celery_task_id="task-xyz"
        )

        # Mock celery_app.control.revoke since Celery is not running in tests
        from unittest.mock import MagicMock, patch

        mock_celery = MagicMock()
        with patch("src.execution.service.celery_app", mock_celery, create=True):
            # The import happens inside cancel_run, so we patch at that level
            with patch("src.celery_app.celery_app") as patched_celery:
                cancelled = await cancel_run(db_session, run)
                patched_celery.control.revoke.assert_called_once_with(
                    "task-xyz", terminate=True, signal="SIGTERM"
                )

        assert cancelled.status == RunStatus.CANCELLED

    async def test_cancel_already_finished_raises(self, db_session, user, repo):
        run = await create_run(db_session, _run_create(repo.id), user.id)
        await update_run_status(db_session, run, RunStatus.PASSED)

        with pytest.raises(ValueError, match="Cannot cancel run with status"):
            await cancel_run(db_session, run)

    async def test_cancel_failed_run_raises(self, db_session, user, repo):
        run = await create_run(db_session, _run_create(repo.id), user.id)
        await update_run_status(db_session, run, RunStatus.FAILED)

        with pytest.raises(ValueError, match="Cannot cancel run with status"):
            await cancel_run(db_session, run)

    async def test_cancel_cancelled_run_raises(self, db_session, user, repo):
        run = await create_run(db_session, _run_create(repo.id), user.id)
        await update_run_status(db_session, run, RunStatus.CANCELLED)

        with pytest.raises(ValueError, match="Cannot cancel run with status"):
            await cancel_run(db_session, run)


class TestRetryRun:
    async def test_retry_creates_new_run(self, db_session, user, repo):
        original = await create_run(
            db_session,
            _run_create(repo.id, target_path="tests/retry_me", branch="feature"),
            user.id,
        )
        await update_run_status(db_session, original, RunStatus.FAILED)

        new_run = await retry_run(db_session, original, user.id)

        assert new_run.id != original.id
        assert new_run.status == RunStatus.PENDING
        assert new_run.repository_id == original.repository_id
        assert new_run.target_path == original.target_path
        assert new_run.branch == original.branch
        assert new_run.run_type == original.run_type
        assert new_run.runner_type == original.runner_type
        assert new_run.retry_count == original.retry_count + 1
        assert new_run.max_retries == original.max_retries
        assert new_run.timeout_seconds == original.timeout_seconds
        assert new_run.triggered_by == user.id

    async def test_retry_increments_retry_count(self, db_session, user, repo):
        run = await create_run(db_session, _run_create(repo.id), user.id)
        await update_run_status(db_session, run, RunStatus.ERROR)

        retry1 = await retry_run(db_session, run, user.id)
        assert retry1.retry_count == 1

        await update_run_status(db_session, retry1, RunStatus.ERROR)
        retry2 = await retry_run(db_session, retry1, user.id)
        assert retry2.retry_count == 2

    async def test_retry_preserves_variables(self, db_session, user, repo):
        original = await create_run(
            db_session,
            _run_create(repo.id, variables={"BROWSER": "firefox"}),
            user.id,
        )
        await update_run_status(db_session, original, RunStatus.FAILED)

        new_run = await retry_run(db_session, original, user.id)
        assert new_run.variables == original.variables


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------


class TestCreateSchedule:
    async def test_create_schedule_defaults(self, db_session, user, repo):
        data = _schedule_create(repo.id)
        schedule = await create_schedule(db_session, data, user.id)

        assert schedule.id is not None
        assert schedule.name == "Nightly smoke"
        assert schedule.cron_expression == "0 2 * * *"
        assert schedule.repository_id == repo.id
        assert schedule.target_path == "tests/smoke"
        assert schedule.branch == "main"
        assert schedule.runner_type == RunnerType.SUBPROCESS
        assert schedule.is_active is True
        assert schedule.created_by == user.id
        assert schedule.tags_include is None
        assert schedule.tags_exclude is None

    async def test_create_schedule_with_all_fields(self, db_session, user, repo):
        data = _schedule_create(
            repo.id,
            name="Weekly regression",
            cron_expression="0 0 * * 0",
            target_path="tests/regression",
            branch="release",
            runner_type=RunnerType.DOCKER,
            tags_include="regression",
            tags_exclude="flaky",
        )
        schedule = await create_schedule(db_session, data, user.id)

        assert schedule.name == "Weekly regression"
        assert schedule.cron_expression == "0 0 * * 0"
        assert schedule.target_path == "tests/regression"
        assert schedule.branch == "release"
        assert schedule.runner_type == RunnerType.DOCKER
        assert schedule.tags_include == "regression"
        assert schedule.tags_exclude == "flaky"


class TestListSchedules:
    async def test_list_schedules_empty(self, db_session):
        schedules = await list_schedules(db_session)
        assert schedules == []

    async def test_list_schedules_returns_all(self, db_session, user, repo):
        await create_schedule(
            db_session, _schedule_create(repo.id, name="Alpha"), user.id
        )
        await create_schedule(
            db_session, _schedule_create(repo.id, name="Beta"), user.id
        )

        schedules = await list_schedules(db_session)
        assert len(schedules) == 2
        # Ordered by name
        names = [s.name for s in schedules]
        assert names == ["Alpha", "Beta"]


class TestToggleSchedule:
    async def test_toggle_active_to_inactive(self, db_session, user, repo):
        schedule = await create_schedule(
            db_session, _schedule_create(repo.id), user.id
        )
        assert schedule.is_active is True

        toggled = await toggle_schedule(db_session, schedule)
        assert toggled.is_active is False

    async def test_toggle_inactive_to_active(self, db_session, user, repo):
        schedule = await create_schedule(
            db_session, _schedule_create(repo.id), user.id
        )
        await toggle_schedule(db_session, schedule)  # -> inactive

        toggled = await toggle_schedule(db_session, schedule)
        assert toggled.is_active is True

    async def test_double_toggle_returns_to_original(self, db_session, user, repo):
        schedule = await create_schedule(
            db_session, _schedule_create(repo.id), user.id
        )
        original_state = schedule.is_active

        await toggle_schedule(db_session, schedule)
        await toggle_schedule(db_session, schedule)

        assert schedule.is_active == original_state


class TestDeleteSchedule:
    async def test_delete_schedule_removes_it(self, db_session, user, repo):
        schedule = await create_schedule(
            db_session, _schedule_create(repo.id), user.id
        )
        schedule_id = schedule.id

        await delete_schedule(db_session, schedule)

        result = await get_schedule(db_session, schedule_id)
        assert result is None

    async def test_delete_schedule_does_not_affect_others(self, db_session, user, repo):
        s1 = await create_schedule(
            db_session, _schedule_create(repo.id, name="Keep me"), user.id
        )
        s2 = await create_schedule(
            db_session, _schedule_create(repo.id, name="Delete me"), user.id
        )

        await delete_schedule(db_session, s2)

        remaining = await list_schedules(db_session)
        assert len(remaining) == 1
        assert remaining[0].id == s1.id
