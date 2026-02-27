"""Background tasks for environment operations."""

import asyncio
import logging
import subprocess
from pathlib import Path

from sqlalchemy import select

import src.auth.models  # noqa: F401

from src.database import get_sync_session
from src.environments.models import Environment, EnvironmentPackage
from src.environments.venv_utils import (
    create_venv_cmd,
    get_venv_bin_dir,
    pip_install_cmd,
    pip_show_cmd,
    pip_uninstall_cmd,
    rfbrowser_init_cmd,
)

logger = logging.getLogger("roboscope.environments.tasks")


def _broadcast_package_status(env_id: int, package_name: str, status: str, **extra) -> None:
    """Broadcast a package status change from a sync background thread."""
    from src.websocket.manager import ws_manager
    from src.main import _event_loop

    coro = ws_manager.broadcast_package_status(env_id, package_name, status, **extra)

    if _event_loop and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, _event_loop)
    else:
        logger.warning("No event loop available to broadcast package %s status", package_name)


BROWSER_PACKAGE_NAMES = {"robotframework-browser", "robotframework_browser"}


def _is_browser_package(package_name: str) -> bool:
    """Check if a package name refers to robotframework-browser."""
    return package_name.lower().replace("_", "-") in BROWSER_PACKAGE_NAMES


def _run_rfbrowser_init(
    venv_path: str,
    env_id: int,
    package_name: str,
    pkg,
    session,
) -> None:
    """Run 'rfbrowser init' after robotframework-browser install/upgrade.

    Downloads Playwright Node.js dependencies and browser binaries.
    On failure, marks the package as failed with an informative error.
    """
    import os

    logger.info("Running rfbrowser init for env %d ...", env_id)
    _broadcast_package_status(env_id, package_name, "initializing")

    try:
        env_vars = os.environ.copy()
        bin_dir = get_venv_bin_dir(venv_path)
        env_vars["PATH"] = bin_dir + os.pathsep + env_vars.get("PATH", "")

        result = subprocess.run(
            rfbrowser_init_cmd(venv_path),
            capture_output=True,
            text=True,
            timeout=600,
            env=env_vars,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                rfbrowser_init_cmd(venv_path),
                output=result.stdout,
                stderr=result.stderr,
            )
        logger.info("rfbrowser init completed for env %d", env_id)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        stderr = getattr(exc, "stderr", "") or ""
        raw = stderr or str(exc)
        if any(hint in raw.lower() for hint in ("node", "npm", "npx", "enoent")):
            error_msg = (
                "rfbrowser init failed: Node.js is required but was not found. "
                "Install Node.js 18+ from https://nodejs.org/ — Details: " + raw
            )
        else:
            error_msg = f"rfbrowser init failed: {raw}"
        logger.error(error_msg)
        if pkg:
            pkg.install_status = "failed"
            pkg.install_error = error_msg[:2000]
            session.commit()
            _broadcast_package_status(
                env_id, package_name, "failed", error=error_msg[:500],
            )
        raise


def create_venv(env_id: int) -> dict:
    """Create a virtual environment."""
    with get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()

        if env is None or env.venv_path is None:
            return {"status": "error", "message": "Environment not found"}

        try:
            venv_path = Path(env.venv_path)
            if not venv_path.exists():
                subprocess.run(
                    create_venv_cmd(str(venv_path), env.python_version),
                    check=True,
                    capture_output=True,
                    text=True,
                )

            # Install robotframework by default
            subprocess.run(
                pip_install_cmd(str(venv_path), "robotframework"),
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
    with get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()

        if env is None or env.venv_path is None:
            return {"status": "error", "message": "Environment not found or no venv"}

        # Mark as installing
        pkg = session.execute(
            select(EnvironmentPackage).where(
                EnvironmentPackage.environment_id == env_id,
                EnvironmentPackage.package_name == package_name,
            )
        ).scalar_one_or_none()

        if pkg:
            pkg.install_status = "installing"
            pkg.install_error = None
            session.commit()
            _broadcast_package_status(env_id, package_name, "installing")

        try:
            pkg_spec = f"{package_name}=={version}" if version else package_name

            subprocess.run(
                pip_install_cmd(env.venv_path, pkg_spec),
                check=True,
                capture_output=True,
                text=True,
            )

            # Get installed version
            show_result = subprocess.run(
                pip_show_cmd(env.venv_path, package_name),
                capture_output=True,
                text=True,
            )
            installed_version = None
            for line in show_result.stdout.splitlines():
                if line.startswith("Version:"):
                    installed_version = line.split(":", 1)[1].strip()
                    break

            # Update DB record — success
            if pkg:
                pkg.installed_version = installed_version
                pkg.install_status = "installed"
                pkg.install_error = None
                session.commit()
                _broadcast_package_status(
                    env_id, package_name, "installed",
                    installed_version=installed_version,
                )

            logger.info("Installed %s==%s in env %d", package_name, installed_version, env_id)

            # Auto-init rfbrowser after robotframework-browser install
            if _is_browser_package(package_name):
                _run_rfbrowser_init(env.venv_path, env_id, package_name, pkg, session)
                # Warn if Docker image needs rebuild
                if env.docker_image:
                    _broadcast_package_status(
                        env_id, package_name, "warning",
                        warning=(
                            "robotframework-browser was initialized in the local venv, "
                            "but the Docker image needs rebuilding to include Node.js "
                            "and browser binaries. Go to Package Manager → Build Docker Image."
                        ),
                    )

            return {"status": "success", "package": package_name, "version": installed_version}
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            logger.error("pip install failed: %s", error_msg)
            if pkg:
                pkg.install_status = "failed"
                pkg.install_error = error_msg[:2000]
                session.commit()
                _broadcast_package_status(
                    env_id, package_name, "failed", error=error_msg[:500],
                )
            return {"status": "error", "message": error_msg}
        except Exception as exc:
            error_msg = str(exc)
            logger.exception("Failed to install package %s in env %d", package_name, env_id)
            if pkg:
                pkg.install_status = "failed"
                pkg.install_error = error_msg[:2000]
                session.commit()
                _broadcast_package_status(
                    env_id, package_name, "failed", error=error_msg[:500],
                )
            return {"status": "error", "message": error_msg}


def upgrade_package(env_id: int, package_name: str) -> dict:
    """Upgrade a pip package to its latest version."""
    with get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()

        if env is None or env.venv_path is None:
            return {"status": "error", "message": "Environment not found or no venv"}

        # Mark as installing
        pkg = session.execute(
            select(EnvironmentPackage).where(
                EnvironmentPackage.environment_id == env_id,
                EnvironmentPackage.package_name == package_name,
            )
        ).scalar_one_or_none()

        if pkg:
            pkg.install_status = "installing"
            pkg.install_error = None
            session.commit()
            _broadcast_package_status(env_id, package_name, "installing")

        try:
            subprocess.run(
                pip_install_cmd(env.venv_path, "--upgrade", package_name),
                check=True,
                capture_output=True,
                text=True,
            )

            # Get installed version
            show_result = subprocess.run(
                pip_show_cmd(env.venv_path, package_name),
                capture_output=True,
                text=True,
            )
            installed_version = None
            for line in show_result.stdout.splitlines():
                if line.startswith("Version:"):
                    installed_version = line.split(":", 1)[1].strip()
                    break

            # Update DB record — success
            if pkg:
                pkg.installed_version = installed_version
                pkg.install_status = "installed"
                pkg.install_error = None
                session.commit()
                _broadcast_package_status(
                    env_id, package_name, "installed",
                    installed_version=installed_version,
                )

            logger.info("Upgraded %s to %s in env %d", package_name, installed_version, env_id)

            # Auto-init rfbrowser after robotframework-browser upgrade
            if _is_browser_package(package_name):
                _run_rfbrowser_init(env.venv_path, env_id, package_name, pkg, session)
                # Warn if Docker image needs rebuild
                if env.docker_image:
                    _broadcast_package_status(
                        env_id, package_name, "warning",
                        warning=(
                            "robotframework-browser was initialized in the local venv, "
                            "but the Docker image needs rebuilding to include Node.js "
                            "and browser binaries. Go to Package Manager → Build Docker Image."
                        ),
                    )

            return {"status": "success", "package": package_name, "version": installed_version}
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            logger.error("pip upgrade failed: %s", error_msg)
            if pkg:
                pkg.install_status = "failed"
                pkg.install_error = error_msg[:2000]
                session.commit()
                _broadcast_package_status(
                    env_id, package_name, "failed", error=error_msg[:500],
                )
            return {"status": "error", "message": error_msg}
        except Exception as exc:
            error_msg = str(exc)
            logger.exception("Failed to upgrade %s in env %d", package_name, env_id)
            if pkg:
                pkg.install_status = "failed"
                pkg.install_error = error_msg[:2000]
                session.commit()
                _broadcast_package_status(
                    env_id, package_name, "failed", error=error_msg[:500],
                )
            return {"status": "error", "message": error_msg}


def build_docker_image(env_id: int) -> dict:
    """Build a Docker image for an environment with all its packages."""
    with get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()

        if env is None:
            return {"status": "error", "message": "Environment not found"}

        packages = session.execute(
            select(EnvironmentPackage).where(EnvironmentPackage.environment_id == env_id)
        ).scalars().all()

        if not packages:
            return {"status": "error", "message": "No packages to install"}

        try:
            from src.environments.service import generate_dockerfile

            pkg_specs = []
            for pkg in packages:
                if pkg.version:
                    pkg_specs.append(f"{pkg.package_name}=={pkg.version}")
                else:
                    pkg_specs.append(pkg.package_name)

            dockerfile_content = generate_dockerfile(
                python_version=env.python_version or "3.12",
                packages=pkg_specs,
            )

            # Get Docker client (same fallback logic as docker_runner.py)
            import docker

            client = None
            try:
                client = docker.from_env()
                client.ping()
            except Exception:
                import json as _json

                base_url = None
                try:
                    out = subprocess.check_output(
                        ["docker", "context", "inspect"], text=True, timeout=5,
                    )
                    ctx = _json.loads(out)
                    if isinstance(ctx, list) and ctx:
                        host = ctx[0].get("Endpoints", {}).get("docker", {}).get("Host", "")
                        if host:
                            base_url = host
                except Exception:
                    pass

                if base_url:
                    client = docker.DockerClient(base_url=base_url)
                else:
                    raise

            # Build image from in-memory tarball
            import io
            import tarfile

            dockerfile_bytes = dockerfile_content.encode("utf-8")
            f = io.BytesIO()
            with tarfile.open(fileobj=f, mode="w") as tar:
                info = tarfile.TarInfo(name="Dockerfile")
                info.size = len(dockerfile_bytes)
                tar.addfile(info, io.BytesIO(dockerfile_bytes))
            f.seek(0)

            safe_name = env.name.lower().replace(" ", "-")
            tag = f"roboscope/{safe_name}:latest"

            logger.info("Building Docker image %s for env %d", tag, env_id)
            client.images.build(fileobj=f, custom_context=True, tag=tag, rm=True)

            # Update environment's docker_image in DB
            env.docker_image = tag
            session.commit()

            logger.info("Built Docker image %s for env %d", tag, env_id)
            return {"status": "success", "image_tag": tag}

        except Exception as exc:
            logger.exception("Failed to build Docker image for env %d", env_id)
            return {"status": "error", "message": str(exc)}


def uninstall_package(env_id: int, package_name: str) -> dict:
    """Uninstall a pip package from an environment's virtualenv."""
    with get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()

        if env is None or env.venv_path is None:
            return {"status": "error", "message": "Environment not found or no venv"}

        try:
            subprocess.run(
                pip_uninstall_cmd(env.venv_path, package_name),
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Uninstalled %s from env %d", package_name, env_id)
            return {"status": "success", "message": f"Uninstalled {package_name}"}
        except subprocess.CalledProcessError as e:
            logger.error("pip uninstall failed: %s", e.stderr)
            return {"status": "error", "message": e.stderr}
