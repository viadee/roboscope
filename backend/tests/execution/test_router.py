"""Tests for execution API endpoints: runs and schedules."""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.constants import Role
from src.auth.service import hash_password
from src.execution.models import RunStatus, RunType, RunnerType
from src.repos.models import Repository
from tests.conftest import auth_header


@pytest_asyncio.fixture
async def repo(db_session: AsyncSession, admin_user):
    """Create a repository for execution tests."""
    repository = Repository(
        name="exec-test-repo",
        git_url="https://github.com/test/exec-repo.git",
        default_branch="main",
        local_path="/tmp/repos/exec-repo",
        created_by=admin_user.id,
    )
    db_session.add(repository)
    await db_session.flush()
    await db_session.refresh(repository)
    return repository


@pytest_asyncio.fixture
async def editor_user(db_session: AsyncSession):
    """Create an editor user."""
    from src.auth.models import User

    user = User(
        email="editor@test.com",
        username="editor",
        hashed_password=hash_password("editor123"),
        role=Role.EDITOR,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


def _run_payload(repo_id: int, **overrides) -> dict:
    """Build a JSON payload for creating a run."""
    defaults = {
        "repository_id": repo_id,
        "target_path": "tests/smoke",
        "branch": "main",
    }
    defaults.update(overrides)
    return defaults


def _schedule_payload(repo_id: int, **overrides) -> dict:
    """Build a JSON payload for creating a schedule."""
    defaults = {
        "name": "Nightly smoke",
        "cron_expression": "0 2 * * *",
        "repository_id": repo_id,
        "target_path": "tests/smoke",
        "branch": "main",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Execution Runs
# ---------------------------------------------------------------------------


class TestExecutionRuns:
    """Tests for /api/v1/runs endpoints."""

    @patch("src.execution.router.execute_test_run", create=True)
    async def test_create_run(self, mock_task, client, runner_user, repo):
        """POST /runs with RUNNER role succeeds and returns 201."""
        # Mock the Celery task dispatch
        mock_task_result = MagicMock()
        mock_task_result.id = "celery-task-001"
        with patch("src.execution.router.execute_test_run") as mock_task_inner:
            mock_task_inner.delay.return_value = mock_task_result

            response = await client.post(
                "/api/v1/runs",
                json=_run_payload(repo.id),
                headers=auth_header(runner_user),
            )

        assert response.status_code == 201
        data = response.json()
        assert data["repository_id"] == repo.id
        assert data["status"] == RunStatus.PENDING
        assert data["target_path"] == "tests/smoke"
        assert data["branch"] == "main"
        assert data["triggered_by"] == runner_user.id
        assert data["id"] is not None

    async def test_create_run_as_viewer_forbidden(self, client, viewer_user, repo):
        """POST /runs with VIEWER role returns 403."""
        response = await client.post(
            "/api/v1/runs",
            json=_run_payload(repo.id),
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403

    async def test_create_run_as_admin(self, client, admin_user, repo):
        """POST /runs with ADMIN role succeeds (ADMIN > RUNNER in hierarchy)."""
        mock_task_result = MagicMock()
        mock_task_result.id = "celery-task-admin"
        with patch("src.execution.router.execute_test_run") as mock_task:
            mock_task.delay.return_value = mock_task_result

            response = await client.post(
                "/api/v1/runs",
                json=_run_payload(repo.id),
                headers=auth_header(admin_user),
            )
        assert response.status_code == 201

    async def test_create_run_unauthenticated(self, client, repo):
        """POST /runs without auth returns 403."""
        response = await client.post(
            "/api/v1/runs",
            json=_run_payload(repo.id),
        )
        assert response.status_code == 403

    async def test_list_runs_empty(self, client, admin_user, repo):
        """GET /runs with no runs returns empty list."""
        response = await client.get(
            "/api/v1/runs",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    async def test_list_runs_paginated(self, client, runner_user, repo, db_session):
        """GET /runs returns paginated results."""
        from src.execution.service import create_run as svc_create_run
        from src.execution.schemas import RunCreate

        for i in range(5):
            data = RunCreate(
                repository_id=repo.id,
                target_path=f"tests/t{i}",
                branch="main",
            )
            await svc_create_run(db_session, data, runner_user.id)

        response = await client.get(
            "/api/v1/runs?page=1&page_size=2",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    async def test_list_runs_filter_by_status(self, client, runner_user, repo, db_session):
        """GET /runs?status=pending filters correctly."""
        from src.execution.service import create_run as svc_create_run, update_run_status
        from src.execution.schemas import RunCreate

        run1 = await svc_create_run(
            db_session, RunCreate(repository_id=repo.id, target_path="t1", branch="main"), runner_user.id
        )
        run2 = await svc_create_run(
            db_session, RunCreate(repository_id=repo.id, target_path="t2", branch="main"), runner_user.id
        )
        await update_run_status(db_session, run2, RunStatus.RUNNING)

        response = await client.get(
            "/api/v1/runs?status=pending",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == run1.id

    async def test_get_run_detail(self, client, runner_user, repo, db_session):
        """GET /runs/{run_id} returns run details."""
        from src.execution.service import create_run as svc_create_run
        from src.execution.schemas import RunCreate

        run = await svc_create_run(
            db_session,
            RunCreate(repository_id=repo.id, target_path="tests/detail", branch="main"),
            runner_user.id,
        )

        response = await client.get(
            f"/api/v1/runs/{run.id}",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == run.id
        assert data["target_path"] == "tests/detail"
        assert data["status"] == RunStatus.PENDING

    async def test_get_run_not_found(self, client, admin_user):
        """GET /runs/{run_id} with bad ID returns 404."""
        response = await client.get(
            "/api/v1/runs/99999",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    async def test_cancel_pending_run(self, client, runner_user, repo, db_session):
        """POST /runs/{run_id}/cancel on a pending run succeeds."""
        from src.execution.service import create_run as svc_create_run
        from src.execution.schemas import RunCreate

        run = await svc_create_run(
            db_session,
            RunCreate(repository_id=repo.id, target_path="tests/cancel_me", branch="main"),
            runner_user.id,
        )

        response = await client.post(
            f"/api/v1/runs/{run.id}/cancel",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == RunStatus.CANCELLED

    async def test_cancel_running_run_with_celery_revoke(
        self, client, runner_user, repo, db_session
    ):
        """POST /runs/{run_id}/cancel on a running run revokes the Celery task."""
        from src.execution.service import create_run as svc_create_run, update_run_status
        from src.execution.schemas import RunCreate

        run = await svc_create_run(
            db_session,
            RunCreate(repository_id=repo.id, target_path="tests/cancel_celery", branch="main"),
            runner_user.id,
        )
        await update_run_status(
            db_session, run, RunStatus.RUNNING, celery_task_id="celery-revoke-me"
        )

        with patch("src.celery_app.celery_app") as mock_celery:
            response = await client.post(
                f"/api/v1/runs/{run.id}/cancel",
                headers=auth_header(runner_user),
            )
            mock_celery.control.revoke.assert_called_once_with(
                "celery-revoke-me", terminate=True, signal="SIGTERM"
            )

        assert response.status_code == 200
        assert response.json()["status"] == RunStatus.CANCELLED

    async def test_cancel_finished_run_returns_400(self, client, runner_user, repo, db_session):
        """POST /runs/{run_id}/cancel on a passed run returns 400."""
        from src.execution.service import create_run as svc_create_run, update_run_status
        from src.execution.schemas import RunCreate

        run = await svc_create_run(
            db_session,
            RunCreate(repository_id=repo.id, target_path="tests/done", branch="main"),
            runner_user.id,
        )
        await update_run_status(db_session, run, RunStatus.PASSED)

        response = await client.post(
            f"/api/v1/runs/{run.id}/cancel",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 400
        assert "Cannot cancel" in response.json()["detail"]

    async def test_cancel_run_not_found(self, client, runner_user):
        """POST /runs/{run_id}/cancel with bad ID returns 404."""
        response = await client.post(
            "/api/v1/runs/99999/cancel",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 404

    async def test_retry_failed_run(self, client, runner_user, repo, db_session):
        """POST /runs/{run_id}/retry on a failed run creates a new pending run."""
        from src.execution.service import create_run as svc_create_run, update_run_status
        from src.execution.schemas import RunCreate

        run = await svc_create_run(
            db_session,
            RunCreate(repository_id=repo.id, target_path="tests/retry_me", branch="main"),
            runner_user.id,
        )
        await update_run_status(db_session, run, RunStatus.FAILED)

        mock_task_result = MagicMock()
        mock_task_result.id = "celery-retry-001"
        with patch("src.execution.router.execute_test_run") as mock_task:
            mock_task.delay.return_value = mock_task_result

            response = await client.post(
                f"/api/v1/runs/{run.id}/retry",
                headers=auth_header(runner_user),
            )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] != run.id
        assert data["status"] == RunStatus.PENDING
        assert data["repository_id"] == repo.id
        assert data["target_path"] == "tests/retry_me"
        assert data["retry_count"] == 1
        assert data["triggered_by"] == runner_user.id

    async def test_retry_error_run(self, client, runner_user, repo, db_session):
        """POST /runs/{run_id}/retry on an errored run succeeds."""
        from src.execution.service import create_run as svc_create_run, update_run_status
        from src.execution.schemas import RunCreate

        run = await svc_create_run(
            db_session,
            RunCreate(repository_id=repo.id, target_path="tests/errored", branch="main"),
            runner_user.id,
        )
        await update_run_status(db_session, run, RunStatus.ERROR, error_message="boom")

        mock_task_result = MagicMock()
        mock_task_result.id = "celery-retry-err"
        with patch("src.execution.router.execute_test_run") as mock_task:
            mock_task.delay.return_value = mock_task_result

            response = await client.post(
                f"/api/v1/runs/{run.id}/retry",
                headers=auth_header(runner_user),
            )
        assert response.status_code == 201

    async def test_retry_pending_run_returns_400(self, client, runner_user, repo, db_session):
        """POST /runs/{run_id}/retry on a pending run returns 400."""
        from src.execution.service import create_run as svc_create_run
        from src.execution.schemas import RunCreate

        run = await svc_create_run(
            db_session,
            RunCreate(repository_id=repo.id, target_path="tests/pending", branch="main"),
            runner_user.id,
        )

        response = await client.post(
            f"/api/v1/runs/{run.id}/retry",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 400
        assert "only retry" in response.json()["detail"].lower() or "Can only retry" in response.json()["detail"]

    async def test_retry_passed_run_returns_400(self, client, runner_user, repo, db_session):
        """POST /runs/{run_id}/retry on a passed run returns 400."""
        from src.execution.service import create_run as svc_create_run, update_run_status
        from src.execution.schemas import RunCreate

        run = await svc_create_run(
            db_session,
            RunCreate(repository_id=repo.id, target_path="tests/passed", branch="main"),
            runner_user.id,
        )
        await update_run_status(db_session, run, RunStatus.PASSED)

        response = await client.post(
            f"/api/v1/runs/{run.id}/retry",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 400

    async def test_retry_run_not_found(self, client, runner_user):
        """POST /runs/{run_id}/retry with bad ID returns 404."""
        response = await client.post(
            "/api/v1/runs/99999/retry",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------


class TestSchedules:
    """Tests for /api/v1/schedules endpoints."""

    async def test_list_schedules_empty(self, client, admin_user):
        """GET /schedules returns empty list when none exist."""
        response = await client.get(
            "/api/v1/schedules",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert response.json() == []

    async def test_create_schedule_as_editor(self, client, editor_user, repo):
        """POST /schedules with EDITOR role succeeds."""
        response = await client.post(
            "/api/v1/schedules",
            json=_schedule_payload(repo.id),
            headers=auth_header(editor_user),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Nightly smoke"
        assert data["cron_expression"] == "0 2 * * *"
        assert data["repository_id"] == repo.id
        assert data["target_path"] == "tests/smoke"
        assert data["is_active"] is True
        assert data["created_by"] == editor_user.id
        assert data["id"] is not None

    async def test_create_schedule_as_admin(self, client, admin_user, repo):
        """POST /schedules with ADMIN role succeeds (ADMIN > EDITOR)."""
        response = await client.post(
            "/api/v1/schedules",
            json=_schedule_payload(repo.id, name="Admin schedule"),
            headers=auth_header(admin_user),
        )
        assert response.status_code == 201

    async def test_create_schedule_as_runner_forbidden(self, client, runner_user, repo):
        """POST /schedules with RUNNER role returns 403."""
        response = await client.post(
            "/api/v1/schedules",
            json=_schedule_payload(repo.id),
            headers=auth_header(runner_user),
        )
        assert response.status_code == 403

    async def test_create_schedule_as_viewer_forbidden(self, client, viewer_user, repo):
        """POST /schedules with VIEWER role returns 403."""
        response = await client.post(
            "/api/v1/schedules",
            json=_schedule_payload(repo.id),
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403

    async def test_list_schedules_returns_created(self, client, editor_user, repo):
        """GET /schedules returns schedules after creation."""
        await client.post(
            "/api/v1/schedules",
            json=_schedule_payload(repo.id, name="Alpha"),
            headers=auth_header(editor_user),
        )
        await client.post(
            "/api/v1/schedules",
            json=_schedule_payload(repo.id, name="Beta"),
            headers=auth_header(editor_user),
        )

        response = await client.get(
            "/api/v1/schedules",
            headers=auth_header(editor_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = [s["name"] for s in data]
        assert "Alpha" in names
        assert "Beta" in names

    async def test_patch_schedule(self, client, editor_user, repo):
        """PATCH /schedules/{id} updates fields."""
        create_resp = await client.post(
            "/api/v1/schedules",
            json=_schedule_payload(repo.id, name="Before patch"),
            headers=auth_header(editor_user),
        )
        schedule_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/schedules/{schedule_id}",
            json={"name": "After patch", "branch": "develop"},
            headers=auth_header(editor_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "After patch"
        assert data["branch"] == "develop"
        # Unchanged fields preserved
        assert data["cron_expression"] == "0 2 * * *"

    async def test_patch_schedule_not_found(self, client, editor_user):
        """PATCH /schedules/{id} with bad ID returns 404."""
        response = await client.patch(
            "/api/v1/schedules/99999",
            json={"name": "Ghost"},
            headers=auth_header(editor_user),
        )
        assert response.status_code == 404

    async def test_patch_schedule_as_runner_forbidden(self, client, runner_user, repo, editor_user):
        """PATCH /schedules/{id} with RUNNER role returns 403."""
        create_resp = await client.post(
            "/api/v1/schedules",
            json=_schedule_payload(repo.id),
            headers=auth_header(editor_user),
        )
        schedule_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/schedules/{schedule_id}",
            json={"name": "Hacked"},
            headers=auth_header(runner_user),
        )
        assert response.status_code == 403

    async def test_delete_schedule(self, client, editor_user, repo):
        """DELETE /schedules/{id} returns 204 and removes schedule."""
        create_resp = await client.post(
            "/api/v1/schedules",
            json=_schedule_payload(repo.id, name="To delete"),
            headers=auth_header(editor_user),
        )
        schedule_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/schedules/{schedule_id}",
            headers=auth_header(editor_user),
        )
        assert response.status_code == 204

        # Confirm it's gone
        get_resp = await client.get(
            "/api/v1/schedules",
            headers=auth_header(editor_user),
        )
        ids = [s["id"] for s in get_resp.json()]
        assert schedule_id not in ids

    async def test_delete_schedule_not_found(self, client, editor_user):
        """DELETE /schedules/{id} with bad ID returns 404."""
        response = await client.delete(
            "/api/v1/schedules/99999",
            headers=auth_header(editor_user),
        )
        assert response.status_code == 404

    async def test_delete_schedule_as_runner_forbidden(self, client, runner_user, repo, editor_user):
        """DELETE /schedules/{id} with RUNNER role returns 403."""
        create_resp = await client.post(
            "/api/v1/schedules",
            json=_schedule_payload(repo.id),
            headers=auth_header(editor_user),
        )
        schedule_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/schedules/{schedule_id}",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 403

    async def test_toggle_schedule(self, client, editor_user, repo):
        """POST /schedules/{id}/toggle flips is_active."""
        create_resp = await client.post(
            "/api/v1/schedules",
            json=_schedule_payload(repo.id),
            headers=auth_header(editor_user),
        )
        schedule_id = create_resp.json()["id"]
        assert create_resp.json()["is_active"] is True

        # Toggle off
        response = await client.post(
            f"/api/v1/schedules/{schedule_id}/toggle",
            headers=auth_header(editor_user),
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

        # Toggle back on
        response = await client.post(
            f"/api/v1/schedules/{schedule_id}/toggle",
            headers=auth_header(editor_user),
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is True

    async def test_toggle_schedule_not_found(self, client, editor_user):
        """POST /schedules/{id}/toggle with bad ID returns 404."""
        response = await client.post(
            "/api/v1/schedules/99999/toggle",
            headers=auth_header(editor_user),
        )
        assert response.status_code == 404

    async def test_toggle_schedule_as_runner_forbidden(
        self, client, runner_user, repo, editor_user
    ):
        """POST /schedules/{id}/toggle with RUNNER role returns 403."""
        create_resp = await client.post(
            "/api/v1/schedules",
            json=_schedule_payload(repo.id),
            headers=auth_header(editor_user),
        )
        schedule_id = create_resp.json()["id"]

        response = await client.post(
            f"/api/v1/schedules/{schedule_id}/toggle",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 403
