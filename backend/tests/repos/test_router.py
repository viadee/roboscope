"""Tests for repos API endpoints."""

import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.constants import Role
from src.auth.service import hash_password
from src.repos.models import Repository
from tests.conftest import auth_header


def _make_repo(user_id: int, **overrides) -> Repository:
    """Helper to build a Repository instance with sensible defaults."""
    defaults = {
        "name": "test-repo",
        "git_url": "https://github.com/org/test-repo.git",
        "default_branch": "main",
        "local_path": "/tmp/workspace/test-repo",
        "auto_sync": True,
        "sync_interval_minutes": 15,
        "created_by": user_id,
    }
    defaults.update(overrides)
    return Repository(**defaults)


@pytest_asyncio.fixture
async def editor_user(db_session: AsyncSession):
    """Create an editor user and return it."""
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


@pytest_asyncio.fixture
async def seed_repo(db_session: AsyncSession, admin_user):
    """Insert a repository and return it."""
    repo = _make_repo(admin_user.id, name="seed-repo")
    db_session.add(repo)
    await db_session.flush()
    await db_session.refresh(repo)
    return repo


class TestListRepos:
    async def test_list_authenticated(self, client, admin_user):
        response = await client.get(
            "/api/v1/repos",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_list_unauthenticated(self, client):
        response = await client.get("/api/v1/repos")
        assert response.status_code == 403


class TestCreateRepo:
    @patch("src.repos.tasks.clone_repo_task")
    async def test_create_as_admin(self, mock_task, client, admin_user):
        mock_task.delay.return_value = MagicMock(id="fake-task-id")
        payload = {
            "name": "new-repo",
            "git_url": "https://github.com/org/new-repo.git",
            "default_branch": "main",
            "auto_sync": True,
            "sync_interval_minutes": 15,
        }
        response = await client.post(
            "/api/v1/repos",
            json=payload,
            headers=auth_header(admin_user),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "new-repo"
        assert data["git_url"] == "https://github.com/org/new-repo.git"
        assert data["created_by"] == admin_user.id
        mock_task.delay.assert_called_once()

    @patch("src.repos.tasks.clone_repo_task")
    async def test_create_as_editor(self, mock_task, client, editor_user):
        mock_task.delay.return_value = MagicMock(id="fake-task-id")
        payload = {
            "name": "editor-repo",
            "git_url": "https://github.com/org/editor-repo.git",
        }
        response = await client.post(
            "/api/v1/repos",
            json=payload,
            headers=auth_header(editor_user),
        )
        assert response.status_code == 201
        assert response.json()["name"] == "editor-repo"

    async def test_create_as_viewer_forbidden(self, client, viewer_user):
        payload = {
            "name": "viewer-repo",
            "git_url": "https://github.com/org/viewer-repo.git",
        }
        response = await client.post(
            "/api/v1/repos",
            json=payload,
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403

    @patch("src.repos.tasks.clone_repo_task")
    async def test_create_duplicate_name_conflict(self, mock_task, client, admin_user, seed_repo):
        mock_task.delay.return_value = MagicMock(id="fake-task-id")
        payload = {
            "name": "seed-repo",
            "git_url": "https://github.com/org/seed-repo.git",
        }
        response = await client.post(
            "/api/v1/repos",
            json=payload,
            headers=auth_header(admin_user),
        )
        assert response.status_code == 409


class TestGetRepo:
    async def test_get_existing(self, client, admin_user, seed_repo):
        response = await client.get(
            f"/api/v1/repos/{seed_repo.id}",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == seed_repo.id
        assert data["name"] == "seed-repo"

    async def test_get_not_found(self, client, admin_user):
        response = await client.get(
            "/api/v1/repos/99999",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    async def test_get_unauthenticated(self, client, seed_repo):
        response = await client.get(f"/api/v1/repos/{seed_repo.id}")
        assert response.status_code == 403


class TestUpdateRepo:
    async def test_update_as_admin(self, client, admin_user, seed_repo):
        response = await client.patch(
            f"/api/v1/repos/{seed_repo.id}",
            json={"auto_sync": False, "sync_interval_minutes": 60},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["auto_sync"] is False
        assert data["sync_interval_minutes"] == 60

    async def test_update_as_editor(self, client, editor_user, seed_repo):
        response = await client.patch(
            f"/api/v1/repos/{seed_repo.id}",
            json={"default_branch": "develop"},
            headers=auth_header(editor_user),
        )
        assert response.status_code == 200
        assert response.json()["default_branch"] == "develop"

    async def test_update_as_viewer_forbidden(self, client, viewer_user, seed_repo):
        response = await client.patch(
            f"/api/v1/repos/{seed_repo.id}",
            json={"auto_sync": False},
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403

    async def test_update_not_found(self, client, admin_user):
        response = await client.patch(
            "/api/v1/repos/99999",
            json={"auto_sync": False},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404


class TestDeleteRepo:
    async def test_delete_as_admin(self, client, admin_user, seed_repo):
        response = await client.delete(
            f"/api/v1/repos/{seed_repo.id}",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 204

        # Confirm it's gone
        get_response = await client.get(
            f"/api/v1/repos/{seed_repo.id}",
            headers=auth_header(admin_user),
        )
        assert get_response.status_code == 404

    async def test_delete_as_editor_forbidden(self, client, editor_user, seed_repo):
        response = await client.delete(
            f"/api/v1/repos/{seed_repo.id}",
            headers=auth_header(editor_user),
        )
        assert response.status_code == 403

    async def test_delete_as_viewer_forbidden(self, client, viewer_user, seed_repo):
        response = await client.delete(
            f"/api/v1/repos/{seed_repo.id}",
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403

    async def test_delete_not_found(self, client, admin_user):
        response = await client.delete(
            "/api/v1/repos/99999",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    async def test_delete_unauthenticated(self, client, seed_repo):
        response = await client.delete(f"/api/v1/repos/{seed_repo.id}")
        assert response.status_code == 403
