"""Tests for environment management API endpoints."""

import pytest
from unittest.mock import patch, MagicMock

from src.environments.models import Environment, EnvironmentPackage, EnvironmentVariable
from tests.conftest import auth_header


# Base URL prefix for environment endpoints
URL = "/api/v1/environments"


class TestListEnvironments:
    def test_list_environments_authenticated(self, client, db_session, admin_user):
        # Create some environments directly in the DB
        env = Environment(
            name="test-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()

        response = client.get(URL, headers=auth_header(admin_user))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "test-env"

    def test_list_environments_unauthenticated(self, client):
        response = client.get(URL)
        assert response.status_code == 401


class TestCreateEnvironment:
    def test_create_environment_as_admin(self, client, admin_user):
        response = client.post(
            URL,
            json={
                "name": "new-env",
                "python_version": "3.11",
                "description": "A brand new environment",
            },
            headers=auth_header(admin_user),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "new-env"
        assert data["python_version"] == "3.11"
        assert data["description"] == "A brand new environment"
        assert data["created_by"] == admin_user.id
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_environment_as_viewer_forbidden(self, client, viewer_user):
        response = client.post(
            URL,
            json={"name": "viewer-env"},
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403

    def test_create_environment_as_runner_forbidden(self, client, runner_user):
        response = client.post(
            URL,
            json={"name": "runner-env"},
            headers=auth_header(runner_user),
        )
        assert response.status_code == 403


class TestGetEnvironment:
    def test_get_environment(self, client, db_session, admin_user):
        env = Environment(
            name="detail-env",
            python_version="3.12",
            description="Detailed",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        response = client.get(
            f"{URL}/{env.id}",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == env.id
        assert data["name"] == "detail-env"
        assert data["description"] == "Detailed"

    def test_get_environment_not_found(self, client, admin_user):
        response = client.get(
            f"{URL}/99999",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_get_environment_unauthenticated(self, client, db_session, admin_user):
        env = Environment(
            name="unauth-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        response = client.get(f"{URL}/{env.id}")
        assert response.status_code == 401


class TestUpdateEnvironment:
    def test_update_environment_as_admin(self, client, db_session, admin_user):
        env = Environment(
            name="update-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        response = client.patch(
            f"{URL}/{env.id}",
            json={"name": "renamed-env", "description": "Now updated"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "renamed-env"
        assert data["description"] == "Now updated"

    def test_update_environment_not_found(self, client, admin_user):
        response = client.patch(
            f"{URL}/99999",
            json={"name": "ghost"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_update_environment_as_viewer_forbidden(self, client, db_session, admin_user, viewer_user):
        env = Environment(
            name="no-update-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        response = client.patch(
            f"{URL}/{env.id}",
            json={"name": "hacked"},
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403


class TestDeleteEnvironment:
    def test_delete_environment_as_admin(self, client, db_session, admin_user):
        env = Environment(
            name="delete-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        response = client.delete(
            f"{URL}/{env.id}",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 204

        # Confirm it's gone
        get_response = client.get(
            f"{URL}/{env.id}",
            headers=auth_header(admin_user),
        )
        assert get_response.status_code == 404

    def test_delete_environment_not_found(self, client, admin_user):
        response = client.delete(
            f"{URL}/99999",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_delete_environment_as_runner_forbidden(self, client, db_session, admin_user, runner_user):
        env = Environment(
            name="no-delete-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        response = client.delete(
            f"{URL}/{env.id}",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 403

    def test_delete_environment_as_viewer_forbidden(self, client, db_session, admin_user, viewer_user):
        env = Environment(
            name="no-delete-viewer-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        response = client.delete(
            f"{URL}/{env.id}",
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403


class TestCloneEnvironment:
    def test_clone_environment(self, client, db_session, admin_user):
        env = Environment(
            name="original-env",
            python_version="3.11",
            docker_image="python:3.11",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        # Add a package and variable to the source
        pkg = EnvironmentPackage(
            environment_id=env.id,
            package_name="requests",
            version="2.31.0",
        )
        var = EnvironmentVariable(
            environment_id=env.id,
            key="MY_VAR",
            value="my_value",
        )
        db_session.add_all([pkg, var])
        db_session.flush()

        response = client.post(
            f"{URL}/{env.id}/clone",
            params={"new_name": "cloned-env"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "cloned-env"
        assert data["python_version"] == "3.11"
        assert data["docker_image"] == "python:3.11"
        assert data["description"] == "Clone of original-env"

        # Verify packages were cloned
        pkg_response = client.get(
            f"{URL}/{data['id']}/packages",
            headers=auth_header(admin_user),
        )
        assert pkg_response.status_code == 200
        cloned_packages = pkg_response.json()
        assert len(cloned_packages) == 1
        assert cloned_packages[0]["package_name"] == "requests"

        # Verify variables were cloned
        var_response = client.get(
            f"{URL}/{data['id']}/variables",
            headers=auth_header(admin_user),
        )
        assert var_response.status_code == 200
        cloned_vars = var_response.json()
        assert len(cloned_vars) == 1
        assert cloned_vars[0]["key"] == "MY_VAR"

    def test_clone_environment_not_found(self, client, admin_user):
        response = client.post(
            f"{URL}/99999/clone",
            params={"new_name": "ghost-clone"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404


class TestPackages:
    def test_list_packages(self, client, db_session, admin_user):
        env = Environment(
            name="pkg-list-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        pkg = EnvironmentPackage(
            environment_id=env.id,
            package_name="flask",
            version="3.0.0",
        )
        db_session.add(pkg)
        db_session.flush()

        response = client.get(
            f"{URL}/{env.id}/packages",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["package_name"] == "flask"
        assert data[0]["version"] == "3.0.0"

    def test_list_packages_env_not_found(self, client, admin_user):
        response = client.get(
            f"{URL}/99999/packages",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    @patch("src.environments.router.dispatch_task")
    def test_add_package(self, mock_dispatch, client, db_session, admin_user):
        mock_dispatch.return_value = MagicMock(id="fake-task-id")

        env = Environment(
            name="pkg-add-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        response = client.post(
            f"{URL}/{env.id}/packages",
            json={"package_name": "requests", "version": "2.31.0"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["package_name"] == "requests"
        assert data["version"] == "2.31.0"
        assert data["environment_id"] == env.id

    @patch("src.environments.router.dispatch_task")
    def test_add_package_env_not_found(self, mock_dispatch, client, admin_user):
        mock_dispatch.return_value = MagicMock(id="fake-task-id")

        response = client.post(
            f"{URL}/99999/packages",
            json={"package_name": "requests"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    @patch("src.environments.router.dispatch_task")
    def test_remove_package(self, mock_dispatch, client, db_session, admin_user):
        mock_dispatch.return_value = MagicMock(id="fake-task-id")

        env = Environment(
            name="pkg-rm-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        pkg = EnvironmentPackage(
            environment_id=env.id,
            package_name="old-pkg",
            version="1.0.0",
        )
        db_session.add(pkg)
        db_session.flush()

        response = client.delete(
            f"{URL}/{env.id}/packages/old-pkg",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 204

    @patch("src.environments.router.dispatch_task")
    def test_remove_package_env_not_found(self, mock_dispatch, client, admin_user):
        mock_dispatch.return_value = MagicMock(id="fake-task-id")

        response = client.delete(
            f"{URL}/99999/packages/nope",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404


class TestVariables:
    def test_list_variables(self, client, db_session, admin_user):
        env = Environment(
            name="var-list-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        var = EnvironmentVariable(
            environment_id=env.id,
            key="MY_VAR",
            value="hello",
            is_secret=False,
        )
        db_session.add(var)
        db_session.flush()

        response = client.get(
            f"{URL}/{env.id}/variables",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["key"] == "MY_VAR"
        assert data[0]["value"] == "hello"
        assert data[0]["is_secret"] is False

    def test_list_variables_secrets_masked(self, client, db_session, admin_user):
        env = Environment(
            name="var-mask-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        secret_var = EnvironmentVariable(
            environment_id=env.id,
            key="SECRET_KEY",
            value="super-secret-value",
            is_secret=True,
        )
        plain_var = EnvironmentVariable(
            environment_id=env.id,
            key="PLAIN_KEY",
            value="plain-value",
            is_secret=False,
        )
        db_session.add_all([secret_var, plain_var])
        db_session.flush()

        response = client.get(
            f"{URL}/{env.id}/variables",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Variables are ordered by key
        plain = next(v for v in data if v["key"] == "PLAIN_KEY")
        secret = next(v for v in data if v["key"] == "SECRET_KEY")

        assert plain["value"] == "plain-value"
        assert plain["is_secret"] is False

        # Secret value should be masked
        assert secret["value"] == "********"
        assert secret["is_secret"] is True

    def test_list_variables_env_not_found(self, client, admin_user):
        response = client.get(
            f"{URL}/99999/variables",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_add_variable(self, client, db_session, admin_user):
        env = Environment(
            name="var-add-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        response = client.post(
            f"{URL}/{env.id}/variables",
            json={"key": "NEW_VAR", "value": "new_value", "is_secret": False},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["key"] == "NEW_VAR"
        assert data["value"] == "new_value"
        assert data["is_secret"] is False
        assert data["environment_id"] == env.id

    def test_add_secret_variable(self, client, db_session, admin_user):
        env = Environment(
            name="var-add-secret-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        response = client.post(
            f"{URL}/{env.id}/variables",
            json={"key": "TOKEN", "value": "abc123", "is_secret": True},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["key"] == "TOKEN"
        assert data["is_secret"] is True

    def test_add_variable_env_not_found(self, client, admin_user):
        response = client.post(
            f"{URL}/99999/variables",
            json={"key": "X", "value": "Y"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_add_variable_as_viewer_forbidden(self, client, db_session, admin_user, viewer_user):
        env = Environment(
            name="var-viewer-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        response = client.post(
            f"{URL}/{env.id}/variables",
            json={"key": "NOPE", "value": "denied"},
            headers=auth_header(viewer_user),
        )
        assert response.status_code == 403
