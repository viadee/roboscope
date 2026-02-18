"""Tests for environment management service."""

import pytest

from src.environments.models import Environment, EnvironmentPackage, EnvironmentVariable
from src.environments.schemas import EnvCreate, EnvUpdate, EnvVarCreate, PackageCreate
from src.environments.service import (
    add_package,
    add_variable,
    clone_environment,
    create_environment,
    delete_environment,
    get_environment,
    list_environments,
    list_packages,
    list_variables,
    remove_package,
    update_environment,
)


class TestListEnvironments:
    def test_list_environments_empty(self, db_session):
        result = list_environments(db_session)
        assert result == []

    def test_list_environments_with_envs(self, db_session, admin_user):
        env1 = Environment(
            name="alpha",
            python_version="3.12",
            created_by=admin_user.id,
        )
        env2 = Environment(
            name="beta",
            python_version="3.11",
            created_by=admin_user.id,
        )
        db_session.add_all([env1, env2])
        db_session.flush()

        result = list_environments(db_session)
        assert len(result) == 2
        # Ordered by name
        assert result[0].name == "alpha"
        assert result[1].name == "beta"


class TestGetEnvironment:
    def test_get_environment_found(self, db_session, admin_user):
        env = Environment(
            name="test-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        result = get_environment(db_session, env.id)
        assert result is not None
        assert result.id == env.id
        assert result.name == "test-env"

    def test_get_environment_not_found(self, db_session):
        result = get_environment(db_session, 99999)
        assert result is None


class TestCreateEnvironment:
    def test_create_environment(self, db_session, admin_user):
        data = EnvCreate(
            name="new-env",
            python_version="3.11",
            description="A test environment",
            is_default=False,
        )
        env = create_environment(db_session, data, admin_user.id)

        assert env.id is not None
        assert env.name == "new-env"
        assert env.python_version == "3.11"
        assert env.description == "A test environment"
        assert env.is_default is False
        assert env.created_by == admin_user.id
        assert env.venv_path is not None

    def test_create_environment_default_unsets_others(self, db_session, admin_user):
        data1 = EnvCreate(name="env-one", is_default=True)
        env1 = create_environment(db_session, data1, admin_user.id)
        assert env1.is_default is True

        data2 = EnvCreate(name="env-two", is_default=True)
        env2 = create_environment(db_session, data2, admin_user.id)

        # Refresh env1 to see the updated value
        db_session.refresh(env1)
        assert env1.is_default is False
        assert env2.is_default is True


class TestUpdateEnvironment:
    def test_update_environment(self, db_session, admin_user):
        env = Environment(
            name="orig-env",
            python_version="3.12",
            description="Original",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        data = EnvUpdate(name="updated-env", description="Updated description")
        updated = update_environment(db_session, env, data)

        assert updated.name == "updated-env"
        assert updated.description == "Updated description"
        # Unchanged fields remain
        assert updated.python_version == "3.12"

    def test_update_environment_partial(self, db_session, admin_user):
        env = Environment(
            name="partial-env",
            python_version="3.12",
            description="Original",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        data = EnvUpdate(description="Only description changed")
        updated = update_environment(db_session, env, data)

        assert updated.name == "partial-env"
        assert updated.description == "Only description changed"


class TestDeleteEnvironment:
    def test_delete_environment(self, db_session, admin_user):
        env = Environment(
            name="doomed-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)
        env_id = env.id

        # Add a package and variable so we test cascade deletion in service
        pkg = EnvironmentPackage(
            environment_id=env_id,
            package_name="requests",
            version="2.31.0",
        )
        var = EnvironmentVariable(
            environment_id=env_id,
            key="API_KEY",
            value="secret",
            is_secret=True,
        )
        db_session.add_all([pkg, var])
        db_session.flush()

        delete_environment(db_session, env)

        # Environment should be gone
        result = get_environment(db_session, env_id)
        assert result is None

        # Packages and variables should be gone
        packages = list_packages(db_session, env_id)
        assert packages == []
        variables = list_variables(db_session, env_id)
        assert variables == []


class TestCloneEnvironment:
    def test_clone_environment(self, db_session, admin_user):
        # Create source environment
        data = EnvCreate(
            name="source-env",
            python_version="3.11",
            docker_image="python:3.11-slim",
            description="Source",
        )
        source = create_environment(db_session, data, admin_user.id)

        # Add packages and variables to source
        add_package(
            db_session, source.id, PackageCreate(package_name="requests", version="2.31.0")
        )
        add_package(
            db_session, source.id, PackageCreate(package_name="pytest", version="8.0.0")
        )
        add_variable(
            db_session, source.id, EnvVarCreate(key="DB_HOST", value="localhost")
        )
        add_variable(
            db_session, source.id, EnvVarCreate(key="SECRET", value="hidden", is_secret=True)
        )

        # Clone
        cloned = clone_environment(db_session, source, "cloned-env", admin_user.id)

        assert cloned.id != source.id
        assert cloned.name == "cloned-env"
        assert cloned.python_version == "3.11"
        assert cloned.docker_image == "python:3.11-slim"
        assert cloned.description == "Clone of source-env"
        assert cloned.is_default is False
        assert cloned.created_by == admin_user.id

        # Verify packages were copied
        cloned_packages = list_packages(db_session, cloned.id)
        assert len(cloned_packages) == 2
        pkg_names = {p.package_name for p in cloned_packages}
        assert pkg_names == {"pytest", "requests"}

        # Verify variables were copied
        cloned_vars = list_variables(db_session, cloned.id)
        assert len(cloned_vars) == 2
        var_keys = {v.key for v in cloned_vars}
        assert var_keys == {"DB_HOST", "SECRET"}
        secret_var = next(v for v in cloned_vars if v.key == "SECRET")
        assert secret_var.is_secret is True


class TestPackages:
    def test_list_packages_empty(self, db_session, admin_user):
        env = Environment(
            name="pkg-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        result = list_packages(db_session, env.id)
        assert result == []

    def test_add_package(self, db_session, admin_user):
        env = Environment(
            name="pkg-add-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        data = PackageCreate(package_name="flask", version="3.0.0")
        pkg = add_package(db_session, env.id, data)

        assert pkg.id is not None
        assert pkg.environment_id == env.id
        assert pkg.package_name == "flask"
        assert pkg.version == "3.0.0"

    def test_add_package_without_version(self, db_session, admin_user):
        env = Environment(
            name="pkg-nover-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        data = PackageCreate(package_name="numpy")
        pkg = add_package(db_session, env.id, data)

        assert pkg.package_name == "numpy"
        assert pkg.version is None

    def test_remove_package(self, db_session, admin_user):
        env = Environment(
            name="pkg-rm-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        data = PackageCreate(package_name="django", version="5.0")
        add_package(db_session, env.id, data)

        packages_before = list_packages(db_session, env.id)
        assert len(packages_before) == 1

        remove_package(db_session, env.id, "django")

        packages_after = list_packages(db_session, env.id)
        assert len(packages_after) == 0

    def test_remove_package_nonexistent(self, db_session, admin_user):
        env = Environment(
            name="pkg-rm-none-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        # Should not raise
        remove_package(db_session, env.id, "nonexistent-pkg")

    def test_list_packages_ordered_by_name(self, db_session, admin_user):
        env = Environment(
            name="pkg-order-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        add_package(db_session, env.id, PackageCreate(package_name="zebra"))
        add_package(db_session, env.id, PackageCreate(package_name="alpha"))
        add_package(db_session, env.id, PackageCreate(package_name="middle"))

        packages = list_packages(db_session, env.id)
        assert [p.package_name for p in packages] == ["alpha", "middle", "zebra"]


class TestVariables:
    def test_list_variables_empty(self, db_session, admin_user):
        env = Environment(
            name="var-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        result = list_variables(db_session, env.id)
        assert result == []

    def test_add_variable(self, db_session, admin_user):
        env = Environment(
            name="var-add-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        data = EnvVarCreate(key="DATABASE_URL", value="postgres://localhost/db")
        var = add_variable(db_session, env.id, data)

        assert var.id is not None
        assert var.environment_id == env.id
        assert var.key == "DATABASE_URL"
        assert var.value == "postgres://localhost/db"
        assert var.is_secret is False

    def test_add_secret_variable(self, db_session, admin_user):
        env = Environment(
            name="var-secret-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        data = EnvVarCreate(key="API_TOKEN", value="super-secret-token", is_secret=True)
        var = add_variable(db_session, env.id, data)

        assert var.key == "API_TOKEN"
        assert var.value == "super-secret-token"
        assert var.is_secret is True

    def test_list_variables_ordered_by_key(self, db_session, admin_user):
        env = Environment(
            name="var-order-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        add_variable(db_session, env.id, EnvVarCreate(key="ZZZ", value="last"))
        add_variable(db_session, env.id, EnvVarCreate(key="AAA", value="first"))
        add_variable(db_session, env.id, EnvVarCreate(key="MMM", value="middle"))

        variables = list_variables(db_session, env.id)
        assert [v.key for v in variables] == ["AAA", "MMM", "ZZZ"]
