"""Tests for repos API endpoints."""

import pytest
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

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


@pytest.fixture
def editor_user(db_session: Session):
    """Create an editor user and return it."""
    from src.auth.models import User

    user = User(
        email="editor@test.com",
        username="editor",
        hashed_password=hash_password("editor123"),
        role=Role.EDITOR,
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture
def seed_repo(db_session: Session, admin_user):
    """Insert a repository and return it."""
    repo = _make_repo(admin_user.id, name="seed-repo")
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)
    return repo


class TestListRepos:
    def test_list_authenticated(self, client, admin_user):
        response = client.get(
            "/api/v1/repos",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_unauthenticated(self, client):
        response = client.get("/api/v1/repos")
        assert response.status_code == 401


class TestCreateRepo:
    @patch("src.repos.router.dispatch_task")
    def test_create_as_admin(self, mock_dispatch, client, admin_user):
        mock_dispatch.return_value = MagicMock(id="fake-task-id")
        payload = {
            "name": "new-repo",
            "git_url": "https://github.com/org/new-repo.git",
            "default_branch": "main",
            "auto_sync": True,
            "sync_interval_minutes": 15,
        }
        response = client.post(
            "/api/v1/repos",
            json=payload,
            headers=auth_header(admin_user),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "new-repo"
        assert data["git_url"] == "https://github.com/org/new-repo.git"
        assert data["created_by"] == admin_user.id
        mock_dispatch.assert_called_once()

    @patch("src.repos.router.dispatch_task")
    def test_create_as_editor(self, mock_dispatch, client, editor_user):
        mock_dispatch.return_value = MagicMock(id="fake-task-id")
        payload = {
            "name": "editor-repo",
            "git_url": "https://github.com/org/editor-repo.git",
        }
        response = client.post(
            "/api/v1/repos",
            json=payload,
            headers=auth_header(editor_user),
        )
        assert response.status_code == 201
        assert response.json()["name"] == "editor-repo"

    def test_create_as_viewer_forbidden(self, client, viewer_user):
        payload = {
            "name": "viewer-repo",
            "git_url": "https://github.com/org/viewer-repo.git",
        }
        response = client.post(
            "/api/v1/repos",
            json=payload,
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403

    @patch("src.repos.router.dispatch_task")
    def test_create_duplicate_name_conflict(self, mock_dispatch, client, admin_user, seed_repo):
        mock_dispatch.return_value = MagicMock(id="fake-task-id")
        payload = {
            "name": "seed-repo",
            "git_url": "https://github.com/org/seed-repo.git",
        }
        response = client.post(
            "/api/v1/repos",
            json=payload,
            headers=auth_header(admin_user),
        )
        assert response.status_code == 409


class TestGetRepo:
    def test_get_existing(self, client, admin_user, seed_repo):
        response = client.get(
            f"/api/v1/repos/{seed_repo.id}",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == seed_repo.id
        assert data["name"] == "seed-repo"

    def test_get_not_found(self, client, admin_user):
        response = client.get(
            "/api/v1/repos/99999",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_get_unauthenticated(self, client, seed_repo):
        response = client.get(f"/api/v1/repos/{seed_repo.id}")
        assert response.status_code == 401


class TestUpdateRepo:
    def test_update_as_admin(self, client, admin_user, seed_repo):
        response = client.patch(
            f"/api/v1/repos/{seed_repo.id}",
            json={"auto_sync": False, "sync_interval_minutes": 60},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["auto_sync"] is False
        assert data["sync_interval_minutes"] == 60

    def test_update_as_editor(self, client, editor_user, seed_repo):
        response = client.patch(
            f"/api/v1/repos/{seed_repo.id}",
            json={"default_branch": "develop"},
            headers=auth_header(editor_user),
        )
        assert response.status_code == 200
        assert response.json()["default_branch"] == "develop"

    def test_update_as_viewer_forbidden(self, client, viewer_user, seed_repo):
        response = client.patch(
            f"/api/v1/repos/{seed_repo.id}",
            json={"auto_sync": False},
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403

    def test_update_not_found(self, client, admin_user):
        response = client.patch(
            "/api/v1/repos/99999",
            json={"auto_sync": False},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404


class TestDeleteRepo:
    def test_delete_as_admin(self, client, admin_user, seed_repo):
        response = client.delete(
            f"/api/v1/repos/{seed_repo.id}",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 204

        # Confirm it's gone
        get_response = client.get(
            f"/api/v1/repos/{seed_repo.id}",
            headers=auth_header(admin_user),
        )
        assert get_response.status_code == 404

    def test_delete_as_editor_forbidden(self, client, editor_user, seed_repo):
        response = client.delete(
            f"/api/v1/repos/{seed_repo.id}",
            headers=auth_header(editor_user),
        )
        assert response.status_code == 403

    def test_delete_as_viewer_forbidden(self, client, viewer_user, seed_repo):
        response = client.delete(
            f"/api/v1/repos/{seed_repo.id}",
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403

    def test_delete_not_found(self, client, admin_user):
        response = client.delete(
            "/api/v1/repos/99999",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_delete_unauthenticated(self, client, seed_repo):
        response = client.delete(f"/api/v1/repos/{seed_repo.id}")
        assert response.status_code == 401


class TestProjectMembers:
    """Tests for project member CRUD endpoints."""

    def test_list_members_empty(self, client, admin_user, seed_repo):
        response = client.get(
            f"/api/v1/repos/{seed_repo.id}/members",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_add_member(self, client, admin_user, seed_repo, viewer_user):
        response = client.post(
            f"/api/v1/repos/{seed_repo.id}/members",
            json={"user_id": viewer_user.id, "role": "viewer"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == viewer_user.id
        assert data["role"] == "viewer"
        assert data["username"] == "viewer"
        assert data["email"] == "viewer@test.com"
        assert data["repository_id"] == seed_repo.id

    def test_add_member_as_editor(self, client, editor_user, seed_repo, viewer_user):
        response = client.post(
            f"/api/v1/repos/{seed_repo.id}/members",
            json={"user_id": viewer_user.id, "role": "runner"},
            headers=auth_header(editor_user),
        )
        assert response.status_code == 201
        assert response.json()["role"] == "runner"

    def test_add_member_as_viewer_forbidden(self, client, viewer_user, seed_repo):
        response = client.post(
            f"/api/v1/repos/{seed_repo.id}/members",
            json={"user_id": viewer_user.id, "role": "viewer"},
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403

    def test_add_member_user_not_found(self, client, admin_user, seed_repo):
        response = client.post(
            f"/api/v1/repos/{seed_repo.id}/members",
            json={"user_id": 99999, "role": "viewer"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_add_member_repo_not_found(self, client, admin_user, viewer_user):
        response = client.post(
            "/api/v1/repos/99999/members",
            json={"user_id": viewer_user.id, "role": "viewer"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_list_members_after_add(self, client, admin_user, seed_repo, viewer_user):
        # Add a member first
        client.post(
            f"/api/v1/repos/{seed_repo.id}/members",
            json={"user_id": viewer_user.id, "role": "editor"},
            headers=auth_header(admin_user),
        )
        response = client.get(
            f"/api/v1/repos/{seed_repo.id}/members",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        members = response.json()
        assert len(members) == 1
        assert members[0]["username"] == "viewer"
        assert members[0]["role"] == "editor"

    def test_update_member_role(self, client, admin_user, seed_repo, viewer_user):
        # Add member
        add_resp = client.post(
            f"/api/v1/repos/{seed_repo.id}/members",
            json={"user_id": viewer_user.id, "role": "viewer"},
            headers=auth_header(admin_user),
        )
        member_id = add_resp.json()["id"]
        # Update role
        response = client.patch(
            f"/api/v1/repos/{seed_repo.id}/members/{member_id}",
            json={"role": "editor"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert response.json()["role"] == "editor"

    def test_update_member_not_found(self, client, admin_user, seed_repo):
        response = client.patch(
            f"/api/v1/repos/{seed_repo.id}/members/99999",
            json={"role": "editor"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_delete_member(self, client, admin_user, seed_repo, viewer_user):
        # Add member
        add_resp = client.post(
            f"/api/v1/repos/{seed_repo.id}/members",
            json={"user_id": viewer_user.id, "role": "viewer"},
            headers=auth_header(admin_user),
        )
        member_id = add_resp.json()["id"]
        # Delete member
        response = client.delete(
            f"/api/v1/repos/{seed_repo.id}/members/{member_id}",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 204
        # Verify removed
        list_resp = client.get(
            f"/api/v1/repos/{seed_repo.id}/members",
            headers=auth_header(admin_user),
        )
        assert len(list_resp.json()) == 0

    def test_delete_member_not_found(self, client, admin_user, seed_repo):
        response = client.delete(
            f"/api/v1/repos/{seed_repo.id}/members/99999",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_delete_member_as_viewer_forbidden(self, client, admin_user, seed_repo, viewer_user):
        # Add member as admin
        add_resp = client.post(
            f"/api/v1/repos/{seed_repo.id}/members",
            json={"user_id": viewer_user.id, "role": "viewer"},
            headers=auth_header(admin_user),
        )
        member_id = add_resp.json()["id"]
        # Try to delete as viewer
        response = client.delete(
            f"/api/v1/repos/{seed_repo.id}/members/{member_id}",
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403

    @patch("src.repos.router.dispatch_task")
    def test_create_repo_auto_adds_creator_as_member(self, mock_dispatch, client, editor_user):
        """Creating a repo should auto-add the creator as an editor member."""
        mock_dispatch.return_value = MagicMock(id="fake-task-id")
        payload = {
            "name": "auto-member-repo",
            "git_url": "https://github.com/org/auto.git",
        }
        create_resp = client.post(
            "/api/v1/repos",
            json=payload,
            headers=auth_header(editor_user),
        )
        assert create_resp.status_code == 201
        repo_id = create_resp.json()["id"]
        # Check members
        members_resp = client.get(
            f"/api/v1/repos/{repo_id}/members",
            headers=auth_header(editor_user),
        )
        assert members_resp.status_code == 200
        members = members_resp.json()
        assert len(members) == 1
        assert members[0]["user_id"] == editor_user.id
        assert members[0]["role"] == "editor"

    def test_list_members_unauthenticated(self, client, seed_repo):
        response = client.get(f"/api/v1/repos/{seed_repo.id}/members")
        assert response.status_code == 401
