"""Environment management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.constants import Role
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from src.celery_app import TaskDispatchError, dispatch_task
from src.database import get_db

logger = logging.getLogger("mateox.environments")
from src.environments.schemas import (
    EnvCreate,
    EnvResponse,
    EnvUpdate,
    EnvVarCreate,
    EnvVarResponse,
    PackageCreate,
    PackageResponse,
    PyPISearchResult,
)
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
    pip_list_installed,
    remove_package,
    search_pypi,
    update_environment,
)

router = APIRouter()


@router.get("", response_model=list[EnvResponse])
async def get_environments(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all environments."""
    return await list_environments(db)


@router.post("", response_model=EnvResponse, status_code=status.HTTP_201_CREATED)
async def add_environment(
    data: EnvCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Create a new environment."""
    return await create_environment(db, data, current_user.id)


@router.get("/{env_id}", response_model=EnvResponse)
async def get_env(
    env_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get environment details."""
    env = await get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return env


@router.patch("/{env_id}", response_model=EnvResponse)
async def patch_env(
    env_id: int,
    data: EnvUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Update an environment."""
    env = await get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return await update_environment(db, env, data)


@router.delete("/{env_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_env(
    env_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Delete an environment."""
    env = await get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    await delete_environment(db, env)


@router.post("/{env_id}/clone", response_model=EnvResponse, status_code=status.HTTP_201_CREATED)
async def clone_env(
    env_id: int,
    new_name: str = Query(..., min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Clone an environment."""
    env = await get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return await clone_environment(db, env, new_name, current_user.id)


# --- Packages ---

# Popular Robot Framework libraries for quick install
POPULAR_RF_LIBRARIES = [
    {"name": "robotframework", "description": "Robot Framework core"},
    {"name": "robotframework-seleniumlibrary", "description": "Web testing with Selenium"},
    {"name": "robotframework-browser", "description": "Web testing with Playwright"},
    {"name": "robotframework-requests", "description": "HTTP API testing"},
    {"name": "robotframework-databaselibrary", "description": "Database testing"},
    {"name": "robotframework-sshlibrary", "description": "SSH connections"},
    {"name": "robotframework-excellibrary", "description": "Excel file handling"},
    {"name": "robotframework-jsonlibrary", "description": "JSON handling"},
    {"name": "robotframework-faker", "description": "Test data generation"},
    {"name": "robotframework-pabot", "description": "Parallel test execution"},
    {"name": "robotframework-datadriver", "description": "Data-driven testing"},
    {"name": "robotframework-archiver", "description": "Test archiving"},
    {"name": "RESTinstance", "description": "REST API testing"},
    {"name": "robotframework-crypto", "description": "Encryption utilities"},
    {"name": "rpaframework", "description": "RPA libraries collection"},
]


@router.get("/packages/popular")
async def get_popular_packages(
    _current_user: User = Depends(get_current_user),
):
    """Get list of popular Robot Framework libraries."""
    return POPULAR_RF_LIBRARIES


@router.get("/packages/search", response_model=list[PyPISearchResult])
async def search_packages(
    q: str = Query(..., min_length=2, max_length=100),
    _current_user: User = Depends(get_current_user),
):
    """Search PyPI for packages."""
    return await search_pypi(q)


@router.get("/{env_id}/packages", response_model=list[PackageResponse])
async def get_packages(
    env_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List packages in an environment."""
    env = await get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return await list_packages(db, env_id)


@router.get("/{env_id}/packages/installed")
async def get_installed_packages(
    env_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all pip-installed packages in an environment's venv."""
    env = await get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return pip_list_installed(env.venv_path)


@router.post("/{env_id}/packages", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
async def install_package(
    env_id: int,
    data: PackageCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Install a package in an environment."""
    env = await get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    pkg = await add_package(db, env_id, data)

    # Trigger async installation
    try:
        from src.environments.tasks import install_package

        dispatch_task(install_package, env_id, data.package_name, data.version)
    except TaskDispatchError as e:
        logger.error("Failed to dispatch package install: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Task dispatch failed: {e}",
        )

    return pkg


@router.post("/{env_id}/packages/{package_name}/upgrade", response_model=PackageResponse)
async def upgrade_package(
    env_id: int,
    package_name: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Upgrade a package to its latest version."""
    env = await get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    # Find existing package record
    from sqlalchemy import select
    from src.environments.models import EnvironmentPackage
    result = await db.execute(
        select(EnvironmentPackage).where(
            EnvironmentPackage.environment_id == env_id,
            EnvironmentPackage.package_name == package_name,
        )
    )
    pkg = result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")

    # Clear version constraint and trigger upgrade
    pkg.version = None
    await db.flush()
    await db.refresh(pkg)

    try:
        from src.environments.tasks import upgrade_package

        dispatch_task(upgrade_package, env_id, package_name)
    except TaskDispatchError as e:
        logger.error("Failed to dispatch package upgrade: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Task dispatch failed: {e}",
        )

    return pkg


@router.delete("/{env_id}/packages/{package_name}", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_package(
    env_id: int,
    package_name: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Remove a package from an environment."""
    env = await get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    await remove_package(db, env_id, package_name)

    try:
        from src.environments.tasks import uninstall_package

        dispatch_task(uninstall_package, env_id, package_name)
    except TaskDispatchError as e:
        logger.error("Failed to dispatch package uninstall: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Task dispatch failed: {e}",
        )


# --- Variables ---


@router.get("/{env_id}/variables", response_model=list[EnvVarResponse])
async def get_variables(
    env_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List variables in an environment."""
    env = await get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    variables = await list_variables(db, env_id)
    # Mask secret values
    for var in variables:
        if var.is_secret:
            var.value = "********"
    return variables


@router.post("/{env_id}/variables", response_model=EnvVarResponse, status_code=status.HTTP_201_CREATED)
async def create_variable(
    env_id: int,
    data: EnvVarCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Add a variable to an environment."""
    env = await get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return await add_variable(db, env_id, data)
