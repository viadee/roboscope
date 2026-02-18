"""Environment management service."""

import json
import logging
import shutil
import subprocess
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.environments.models import Environment, EnvironmentPackage, EnvironmentVariable
from src.environments.schemas import EnvCreate, EnvUpdate, EnvVarCreate, PackageCreate

logger = logging.getLogger("mateox.environments")


def list_environments(db: Session) -> list[Environment]:
    """List all environments."""
    result = db.execute(select(Environment).order_by(Environment.name))
    return list(result.scalars().all())


def get_environment(db: Session, env_id: int) -> Environment | None:
    """Get an environment by ID."""
    result = db.execute(select(Environment).where(Environment.id == env_id))
    return result.scalar_one_or_none()


def create_environment(db: Session, data: EnvCreate, user_id: int) -> Environment:
    """Create a new environment."""
    venv_dir = Path(settings.VENVS_DIR)
    venv_dir.mkdir(parents=True, exist_ok=True)
    venv_path = str(venv_dir / data.name)

    env = Environment(
        name=data.name,
        python_version=data.python_version,
        venv_path=venv_path,
        docker_image=data.docker_image,
        is_default=data.is_default,
        description=data.description,
        created_by=user_id,
    )

    # If this is the new default, unset other defaults
    if data.is_default:
        _unset_defaults(db)

    db.add(env)
    db.flush()
    db.refresh(env)
    return env


def update_environment(db: Session, env: Environment, data: EnvUpdate) -> Environment:
    """Update an environment."""
    update_data = data.model_dump(exclude_unset=True)

    if update_data.get("is_default"):
        _unset_defaults(db)

    for key, value in update_data.items():
        setattr(env, key, value)

    db.flush()
    db.refresh(env)
    return env


def delete_environment(db: Session, env: Environment) -> None:
    """Delete an environment and its venv."""
    if env.venv_path:
        venv_path = Path(env.venv_path)
        if venv_path.exists():
            shutil.rmtree(venv_path, ignore_errors=True)

    # Delete related packages and variables
    packages = db.execute(
        select(EnvironmentPackage).where(EnvironmentPackage.environment_id == env.id)
    )
    for pkg in packages.scalars().all():
        db.delete(pkg)

    variables = db.execute(
        select(EnvironmentVariable).where(EnvironmentVariable.environment_id == env.id)
    )
    for var in variables.scalars().all():
        db.delete(var)

    db.delete(env)
    db.flush()


def clone_environment(db: Session, env: Environment, new_name: str, user_id: int) -> Environment:
    """Clone an environment with a new name."""
    new_env = create_environment(
        db,
        EnvCreate(
            name=new_name,
            python_version=env.python_version,
            docker_image=env.docker_image,
            is_default=False,
            description=f"Clone of {env.name}",
        ),
        user_id,
    )

    # Copy packages
    packages = list_packages(db, env.id)
    for pkg in packages:
        new_pkg = EnvironmentPackage(
            environment_id=new_env.id,
            package_name=pkg.package_name,
            version=pkg.version,
        )
        db.add(new_pkg)

    # Copy variables
    variables = list_variables(db, env.id)
    for var in variables:
        new_var = EnvironmentVariable(
            environment_id=new_env.id,
            key=var.key,
            value=var.value,
            is_secret=var.is_secret,
        )
        db.add(new_var)

    db.flush()
    db.refresh(new_env)
    return new_env


# --- Packages ---


def list_packages(db: Session, env_id: int) -> list[EnvironmentPackage]:
    """List packages in an environment."""
    result = db.execute(
        select(EnvironmentPackage)
        .where(EnvironmentPackage.environment_id == env_id)
        .order_by(EnvironmentPackage.package_name)
    )
    return list(result.scalars().all())


def add_package(db: Session, env_id: int, data: PackageCreate) -> EnvironmentPackage:
    """Add a package to an environment."""
    pkg = EnvironmentPackage(
        environment_id=env_id,
        package_name=data.package_name,
        version=data.version,
    )
    db.add(pkg)
    db.flush()
    db.refresh(pkg)
    return pkg


def remove_package(db: Session, env_id: int, package_name: str) -> None:
    """Remove a package from an environment."""
    result = db.execute(
        select(EnvironmentPackage).where(
            EnvironmentPackage.environment_id == env_id,
            EnvironmentPackage.package_name == package_name,
        )
    )
    pkg = result.scalar_one_or_none()
    if pkg:
        db.delete(pkg)
        db.flush()


# --- Variables ---


def list_variables(db: Session, env_id: int) -> list[EnvironmentVariable]:
    """List variables in an environment."""
    result = db.execute(
        select(EnvironmentVariable)
        .where(EnvironmentVariable.environment_id == env_id)
        .order_by(EnvironmentVariable.key)
    )
    return list(result.scalars().all())


def add_variable(db: Session, env_id: int, data: EnvVarCreate) -> EnvironmentVariable:
    """Add a variable to an environment."""
    var = EnvironmentVariable(
        environment_id=env_id,
        key=data.key,
        value=data.value,
        is_secret=data.is_secret,
    )
    db.add(var)
    db.flush()
    db.refresh(var)
    return var


def _unset_defaults(db: Session) -> None:
    """Unset all default environments."""
    result = db.execute(
        select(Environment).where(Environment.is_default == True)
    )
    for env in result.scalars().all():
        env.is_default = False


# --- PyPI ---


def search_pypi(query: str) -> list[dict]:
    """Search PyPI for packages using the JSON API."""
    results = []
    try:
        with httpx.Client(timeout=10.0) as client:
            # PyPI doesn't have a search API anymore, use the simple JSON endpoint
            # Search by trying exact match first, then fall back to warehouse search
            response = client.get(
                f"https://pypi.org/pypi/{query}/json",
            )
            if response.status_code == 200:
                data = response.json()
                info = data.get("info", {})
                results.append({
                    "name": info.get("name", query),
                    "version": info.get("version", ""),
                    "summary": info.get("summary", ""),
                    "author": info.get("author", ""),
                })

            # Also search for robotframework-related packages if query is short
            if len(query) >= 2:
                search_response = client.get(
                    "https://pypi.org/simple/",
                    headers={"Accept": "application/vnd.pypi.simple.v1+json"},
                )
                if search_response.status_code == 200:
                    data = search_response.json()
                    projects = data.get("projects", [])
                    query_lower = query.lower()
                    matched = [
                        p for p in projects
                        if query_lower in p.get("name", "").lower()
                    ][:20]

                    for proj in matched:
                        name = proj.get("name", "")
                        if not any(r["name"] == name for r in results):
                            results.append({
                                "name": name,
                                "version": "",
                                "summary": "",
                                "author": "",
                            })
    except Exception as e:
        logger.warning("PyPI search failed: %s", e)

    return results[:20]


def generate_dockerfile(
    python_version: str,
    packages: list[str],
    base_image: str | None = None,
) -> str:
    """Generate a Dockerfile that installs the given packages.

    Pure function, no DB access.
    """
    base = base_image or f"python:{python_version}-slim"
    lines = [
        f"FROM {base}",
        "",
        "RUN pip install --no-cache-dir \\",
    ]
    for i, pkg in enumerate(packages):
        suffix = "" if i == len(packages) - 1 else " \\"
        lines.append(f"    {pkg}{suffix}")
    lines.append("")
    lines.append('CMD ["python", "-m", "robot", "--help"]')
    lines.append("")
    return "\n".join(lines)


def pip_list_installed(venv_path: str | None) -> list[dict]:
    """List all packages installed in a venv via pip list --format=json."""
    if not venv_path:
        return []

    pip_path = str(Path(venv_path) / "bin" / "pip")
    if not Path(pip_path).exists():
        return []

    try:
        result = subprocess.run(
            [pip_path, "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        logger.warning("pip list failed: %s", e)

    return []
