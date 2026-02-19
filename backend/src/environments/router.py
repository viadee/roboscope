"""Environment management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from sqlalchemy import select
from src.celery_app import TaskDispatchError, dispatch_task
from src.database import get_db
from src.environments.models import Environment

logger = logging.getLogger("roboscope.environments")
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
    generate_dockerfile,
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
def get_environments(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all environments."""
    return list_environments(db)


@router.post("", response_model=EnvResponse, status_code=status.HTTP_201_CREATED)
def add_environment(
    data: EnvCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Create a new environment."""
    return create_environment(db, data, current_user.id)


# Default RF packages for quick setup
DEFAULT_RF_PACKAGES = [
    "robotframework",
    "robotframework-seleniumlibrary",
    "robotframework-browser",
    "robotframework-requests",
]


@router.post("/setup-default", response_model=EnvResponse, status_code=status.HTTP_201_CREATED)
def setup_default_environment(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Create a default environment with essential Robot Framework libraries."""
    # Check if roboscope-default already exists
    result = db.execute(
        select(Environment).where(Environment.name == "roboscope-default")
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Default environment 'roboscope-default' already exists",
        )

    env = create_environment(
        db,
        EnvCreate(
            name="roboscope-default",
            python_version="3.12",
            is_default=True,
            description="Default environment with essential Robot Framework libraries",
        ),
        current_user.id,
    )

    for pkg_name in DEFAULT_RF_PACKAGES:
        add_package(db, env.id, PackageCreate(package_name=pkg_name))

    # Detect Docker availability and configure accordingly
    docker_available = _is_docker_available()
    if docker_available:
        env.default_runner_type = "docker"
        logger.info("Docker detected — default environment will use Docker runner")

    db.commit()

    # Dispatch venv creation first, then package installs (FIFO queue)
    try:
        from src.environments.tasks import (
            create_venv,
            install_package as install_package_task,
            build_docker_image,
        )

        dispatch_task(create_venv, env.id)
        for pkg_name in DEFAULT_RF_PACKAGES:
            dispatch_task(install_package_task, env.id, pkg_name, None)

        # If Docker is available, queue a Docker image build after packages
        if docker_available:
            dispatch_task(build_docker_image, env.id)
    except TaskDispatchError as e:
        logger.error("Failed to dispatch default env tasks: %s", e)

    return env


def _is_docker_available() -> bool:
    """Check if Docker is available on this system."""
    import subprocess as _sp

    try:
        result = _sp.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


@router.get("/{env_id}", response_model=EnvResponse)
def get_env(
    env_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get environment details."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return env


@router.patch("/{env_id}", response_model=EnvResponse)
def patch_env(
    env_id: int,
    data: EnvUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Update an environment."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return update_environment(db, env, data)


@router.delete("/{env_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_env(
    env_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Delete an environment."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    delete_environment(db, env)


@router.post("/{env_id}/clone", response_model=EnvResponse, status_code=status.HTTP_201_CREATED)
def clone_env(
    env_id: int,
    new_name: str = Query(..., min_length=1, max_length=255),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Clone an environment."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return clone_environment(db, env, new_name, current_user.id)


# --- Docker Image ---


@router.get("/{env_id}/dockerfile", response_class=PlainTextResponse)
def get_dockerfile(
    env_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Generate and return a Dockerfile for this environment."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    packages = list_packages(db, env_id)
    if not packages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Environment has no packages",
        )

    pkg_specs = []
    for pkg in packages:
        if pkg.version:
            pkg_specs.append(f"{pkg.package_name}=={pkg.version}")
        else:
            pkg_specs.append(pkg.package_name)

    content = generate_dockerfile(
        python_version=env.python_version or "3.12",
        packages=pkg_specs,
    )
    return PlainTextResponse(content)


@router.post("/{env_id}/docker-build")
def docker_build(
    env_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Build a Docker image for this environment."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    packages = list_packages(db, env_id)
    if not packages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Environment has no packages",
        )

    db.commit()

    safe_name = env.name.lower().replace(" ", "-")
    image_tag = f"roboscope/{safe_name}:latest"

    try:
        from src.environments.tasks import build_docker_image

        dispatch_task(build_docker_image, env_id)
    except TaskDispatchError as e:
        logger.error("Failed to dispatch Docker build: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Task dispatch failed: {e}",
        )

    return {"status": "building", "image_tag": image_tag}


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
def get_popular_packages(
    _current_user: User = Depends(get_current_user),
):
    """Get list of popular Robot Framework libraries."""
    return POPULAR_RF_LIBRARIES


@router.get("/packages/search", response_model=list[PyPISearchResult])
def search_packages(
    q: str = Query(..., min_length=2, max_length=100),
    _current_user: User = Depends(get_current_user),
):
    """Search PyPI for packages."""
    return search_pypi(q)


@router.get("/{env_id}/packages", response_model=list[PackageResponse])
def get_packages(
    env_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List packages in an environment."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return list_packages(db, env_id)


@router.get("/{env_id}/packages/installed")
def get_installed_packages(
    env_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all pip-installed packages in an environment's venv."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return pip_list_installed(env.venv_path)


@router.post("/{env_id}/packages", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
def install_package(
    env_id: int,
    data: PackageCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Install a package in an environment."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    pkg = add_package(db, env_id, data)

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
def upgrade_package(
    env_id: int,
    package_name: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Upgrade a package to its latest version."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    # Find existing package record
    from sqlalchemy import select
    from src.environments.models import EnvironmentPackage
    result = db.execute(
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
    db.flush()
    db.refresh(pkg)

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
def uninstall_package(
    env_id: int,
    package_name: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Remove a package from an environment."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    remove_package(db, env_id, package_name)

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
def get_variables(
    env_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List variables in an environment."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    variables = list_variables(db, env_id)
    # Mask secret values
    for var in variables:
        if var.is_secret:
            var.value = "********"
    return variables


@router.post("/{env_id}/variables", response_model=EnvVarResponse, status_code=status.HTTP_201_CREATED)
def create_variable(
    env_id: int,
    data: EnvVarCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Add a variable to an environment."""
    env = get_environment(db, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return add_variable(db, env_id, data)
