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
    async def test_list_environments_empty(self, db_session):
        result = await list_environments(db_session)
        assert result == []

    async def test_list_environments_with_envs(self, db_session, admin_user):
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
        await db_session.flush()

        result = await list_environments(db_session)
        assert len(result) == 2
        # Ordered by name
        assert result[0].name == "alpha"
        assert result[1].name == "beta"


class TestGetEnvironment:
    async def test_get_environment_found(self, db_session, admin_user):
        env = Environment(
            name="test-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        result = await get_environment(db_session, env.id)
        assert result is not None
        assert result.id == env.id
        assert result.name == "test-env"

    async def test_get_environment_not_found(self, db_session):
        result = await get_environment(db_session, 99999)
        assert result is None


class TestCreateEnvironment:
    async def test_create_environment(self, db_session, admin_user):
        data = EnvCreate(
            name="new-env",
            python_version="3.11",
            description="A test environment",
            is_default=False,
        )
        env = await create_environment(db_session, data, admin_user.id)

        assert env.id is not None
        assert env.name == "new-env"
        assert env.python_version == "3.11"
        assert env.description == "A test environment"
        assert env.is_default is False
        assert env.created_by == admin_user.id
        assert env.venv_path is not None

    async def test_create_environment_default_unsets_others(self, db_session, admin_user):
        data1 = EnvCreate(name="env-one", is_default=True)
        env1 = await create_environment(db_session, data1, admin_user.id)
        assert env1.is_default is True

        data2 = EnvCreate(name="env-two", is_default=True)
        env2 = await create_environment(db_session, data2, admin_user.id)

        # Refresh env1 to see the updated value
        await db_session.refresh(env1)
        assert env1.is_default is False
        assert env2.is_default is True


class TestUpdateEnvironment:
    async def test_update_environment(self, db_session, admin_user):
        env = Environment(
            name="orig-env",
            python_version="3.12",
            description="Original",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        data = EnvUpdate(name="updated-env", description="Updated description")
        updated = await update_environment(db_session, env, data)

        assert updated.name == "updated-env"
        assert updated.description == "Updated description"
        # Unchanged fields remain
        assert updated.python_version == "3.12"

    async def test_update_environment_partial(self, db_session, admin_user):
        env = Environment(
            name="partial-env",
            python_version="3.12",
            description="Original",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        data = EnvUpdate(description="Only description changed")
        updated = await update_environment(db_session, env, data)

        assert updated.name == "partial-env"
        assert updated.description == "Only description changed"


class TestDeleteEnvironment:
    async def test_delete_environment(self, db_session, admin_user):
        env = Environment(
            name="doomed-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)
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
        await db_session.flush()

        await delete_environment(db_session, env)

        # Environment should be gone
        result = await get_environment(db_session, env_id)
        assert result is None

        # Packages and variables should be gone
        packages = await list_packages(db_session, env_id)
        assert packages == []
        variables = await list_variables(db_session, env_id)
        assert variables == []


class TestCloneEnvironment:
    async def test_clone_environment(self, db_session, admin_user):
        # Create source environment
        data = EnvCreate(
            name="source-env",
            python_version="3.11",
            docker_image="python:3.11-slim",
            description="Source",
        )
        source = await create_environment(db_session, data, admin_user.id)

        # Add packages and variables to source
        await add_package(
            db_session, source.id, PackageCreate(package_name="requests", version="2.31.0")
        )
        await add_package(
            db_session, source.id, PackageCreate(package_name="pytest", version="8.0.0")
        )
        await add_variable(
            db_session, source.id, EnvVarCreate(key="DB_HOST", value="localhost")
        )
        await add_variable(
            db_session, source.id, EnvVarCreate(key="SECRET", value="hidden", is_secret=True)
        )

        # Clone
        cloned = await clone_environment(db_session, source, "cloned-env", admin_user.id)

        assert cloned.id != source.id
        assert cloned.name == "cloned-env"
        assert cloned.python_version == "3.11"
        assert cloned.docker_image == "python:3.11-slim"
        assert cloned.description == "Clone of source-env"
        assert cloned.is_default is False
        assert cloned.created_by == admin_user.id

        # Verify packages were copied
        cloned_packages = await list_packages(db_session, cloned.id)
        assert len(cloned_packages) == 2
        pkg_names = {p.package_name for p in cloned_packages}
        assert pkg_names == {"pytest", "requests"}

        # Verify variables were copied
        cloned_vars = await list_variables(db_session, cloned.id)
        assert len(cloned_vars) == 2
        var_keys = {v.key for v in cloned_vars}
        assert var_keys == {"DB_HOST", "SECRET"}
        secret_var = next(v for v in cloned_vars if v.key == "SECRET")
        assert secret_var.is_secret is True


class TestPackages:
    async def test_list_packages_empty(self, db_session, admin_user):
        env = Environment(
            name="pkg-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        result = await list_packages(db_session, env.id)
        assert result == []

    async def test_add_package(self, db_session, admin_user):
        env = Environment(
            name="pkg-add-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        data = PackageCreate(package_name="flask", version="3.0.0")
        pkg = await add_package(db_session, env.id, data)

        assert pkg.id is not None
        assert pkg.environment_id == env.id
        assert pkg.package_name == "flask"
        assert pkg.version == "3.0.0"

    async def test_add_package_without_version(self, db_session, admin_user):
        env = Environment(
            name="pkg-nover-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        data = PackageCreate(package_name="numpy")
        pkg = await add_package(db_session, env.id, data)

        assert pkg.package_name == "numpy"
        assert pkg.version is None

    async def test_remove_package(self, db_session, admin_user):
        env = Environment(
            name="pkg-rm-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        data = PackageCreate(package_name="django", version="5.0")
        await add_package(db_session, env.id, data)

        packages_before = await list_packages(db_session, env.id)
        assert len(packages_before) == 1

        await remove_package(db_session, env.id, "django")

        packages_after = await list_packages(db_session, env.id)
        assert len(packages_after) == 0

    async def test_remove_package_nonexistent(self, db_session, admin_user):
        env = Environment(
            name="pkg-rm-none-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        # Should not raise
        await remove_package(db_session, env.id, "nonexistent-pkg")

    async def test_list_packages_ordered_by_name(self, db_session, admin_user):
        env = Environment(
            name="pkg-order-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        await add_package(db_session, env.id, PackageCreate(package_name="zebra"))
        await add_package(db_session, env.id, PackageCreate(package_name="alpha"))
        await add_package(db_session, env.id, PackageCreate(package_name="middle"))

        packages = await list_packages(db_session, env.id)
        assert [p.package_name for p in packages] == ["alpha", "middle", "zebra"]


class TestVariables:
    async def test_list_variables_empty(self, db_session, admin_user):
        env = Environment(
            name="var-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        result = await list_variables(db_session, env.id)
        assert result == []

    async def test_add_variable(self, db_session, admin_user):
        env = Environment(
            name="var-add-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        data = EnvVarCreate(key="DATABASE_URL", value="postgres://localhost/db")
        var = await add_variable(db_session, env.id, data)

        assert var.id is not None
        assert var.environment_id == env.id
        assert var.key == "DATABASE_URL"
        assert var.value == "postgres://localhost/db"
        assert var.is_secret is False

    async def test_add_secret_variable(self, db_session, admin_user):
        env = Environment(
            name="var-secret-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        data = EnvVarCreate(key="API_TOKEN", value="super-secret-token", is_secret=True)
        var = await add_variable(db_session, env.id, data)

        assert var.key == "API_TOKEN"
        assert var.value == "super-secret-token"
        assert var.is_secret is True

    async def test_list_variables_ordered_by_key(self, db_session, admin_user):
        env = Environment(
            name="var-order-env",
            python_version="3.12",
            created_by=admin_user.id,
        )
        db_session.add(env)
        await db_session.flush()
        await db_session.refresh(env)

        await add_variable(db_session, env.id, EnvVarCreate(key="ZZZ", value="last"))
        await add_variable(db_session, env.id, EnvVarCreate(key="AAA", value="first"))
        await add_variable(db_session, env.id, EnvVarCreate(key="MMM", value="middle"))

        variables = await list_variables(db_session, env.id)
        assert [v.key for v in variables] == ["AAA", "MMM", "ZZZ"]
