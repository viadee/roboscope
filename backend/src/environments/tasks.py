"""Background tasks for environment operations."""

import logging
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.config import settings

import src.auth.models  # noqa: F401

from src.environments.models import Environment, EnvironmentPackage

logger = logging.getLogger("mateox.environments.tasks")

_sync_url = settings.sync_database_url
_sync_engine = create_engine(_sync_url)


def _get_sync_session() -> Session:
    return Session(_sync_engine)


def _get_pip_path(venv_path: str) -> str:
    return str(Path(venv_path) / "bin" / "pip")


def _get_python_path(venv_path: str) -> str:
    return str(Path(venv_path) / "bin" / "python")


def create_venv(env_id: int) -> dict:
    """Create a virtual environment."""
    with _get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()

        if env is None or env.venv_path is None:
            return {"status": "error", "message": "Environment not found"}

        try:
            venv_path = Path(env.venv_path)
            if not venv_path.exists():
                subprocess.run(
                    [sys.executable, "-m", "venv", str(venv_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )

            # Install robotframework by default
            pip = _get_pip_path(str(venv_path))
            subprocess.run(
                [pip, "install", "robotframework"],
                check=True,
                capture_output=True,
                text=True,
            )

            logger.info("Created venv at %s", venv_path)
            return {"status": "success", "message": f"Created venv at {venv_path}"}
        except Exception as exc:
            logger.exception("Failed to create venv for env %d", env_id)
            return {"status": "error", "message": str(exc)}


def install_package(env_id: int, package_name: str, version: str | None = None) -> dict:
    """Install a pip package in an environment's virtualenv."""
    with _get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()

        if env is None or env.venv_path is None:
            return {"status": "error", "message": "Environment not found or no venv"}

        try:
            pip = _get_pip_path(env.venv_path)
            pkg_spec = f"{package_name}=={version}" if version else package_name

            subprocess.run(
                [pip, "install", pkg_spec],
                check=True,
                capture_output=True,
                text=True,
            )

            # Get installed version
            show_result = subprocess.run(
                [pip, "show", package_name],
                capture_output=True,
                text=True,
            )
            installed_version = None
            for line in show_result.stdout.splitlines():
                if line.startswith("Version:"):
                    installed_version = line.split(":", 1)[1].strip()
                    break

            # Update DB record
            pkg = session.execute(
                select(EnvironmentPackage).where(
                    EnvironmentPackage.environment_id == env_id,
                    EnvironmentPackage.package_name == package_name,
                )
            ).scalar_one_or_none()

            if pkg and installed_version:
                pkg.installed_version = installed_version
                session.commit()

            logger.info("Installed %s==%s in env %d", package_name, installed_version, env_id)
            return {"status": "success", "package": package_name, "version": installed_version}
        except subprocess.CalledProcessError as e:
            logger.error("pip install failed: %s", e.stderr)
            return {"status": "error", "message": e.stderr}
        except Exception as exc:
            logger.exception("Failed to install package %s in env %d", package_name, env_id)
            return {"status": "error", "message": str(exc)}


def upgrade_package(env_id: int, package_name: str) -> dict:
    """Upgrade a pip package to its latest version."""
    with _get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()

        if env is None or env.venv_path is None:
            return {"status": "error", "message": "Environment not found or no venv"}

        try:
            pip = _get_pip_path(env.venv_path)
            subprocess.run(
                [pip, "install", "--upgrade", package_name],
                check=True,
                capture_output=True,
                text=True,
            )

            # Get installed version
            show_result = subprocess.run(
                [pip, "show", package_name],
                capture_output=True,
                text=True,
            )
            installed_version = None
            for line in show_result.stdout.splitlines():
                if line.startswith("Version:"):
                    installed_version = line.split(":", 1)[1].strip()
                    break

            # Update DB record
            pkg = session.execute(
                select(EnvironmentPackage).where(
                    EnvironmentPackage.environment_id == env_id,
                    EnvironmentPackage.package_name == package_name,
                )
            ).scalar_one_or_none()

            if pkg and installed_version:
                pkg.installed_version = installed_version
                session.commit()

            logger.info("Upgraded %s to %s in env %d", package_name, installed_version, env_id)
            return {"status": "success", "package": package_name, "version": installed_version}
        except subprocess.CalledProcessError as e:
            logger.error("pip upgrade failed: %s", e.stderr)
            return {"status": "error", "message": e.stderr}
        except Exception as exc:
            logger.exception("Failed to upgrade %s in env %d", package_name, env_id)
            return {"status": "error", "message": str(exc)}


def uninstall_package(env_id: int, package_name: str) -> dict:
    """Uninstall a pip package from an environment's virtualenv."""
    with _get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()

        if env is None or env.venv_path is None:
            return {"status": "error", "message": "Environment not found or no venv"}

        try:
            pip = _get_pip_path(env.venv_path)
            subprocess.run(
                [pip, "uninstall", "-y", package_name],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Uninstalled %s from env %d", package_name, env_id)
            return {"status": "success", "message": f"Uninstalled {package_name}"}
        except subprocess.CalledProcessError as e:
            logger.error("pip uninstall failed: %s", e.stderr)
            return {"status": "error", "message": e.stderr}
