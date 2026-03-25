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
    check_rfbrowser_initialized,
    create_venv_cmd,
    get_venv_bin_dir,
    pip_install_cmd,
    pip_show_cmd,
    pip_uninstall_cmd,
    rfbrowser_init_cmd,
)

logger = logging.getLogger("roboscope.environments.tasks")

# Track active package install/upgrade tasks so we can detect stuck packages.
# Key: (env_id, package_name), value: True while task is running.
_active_package_tasks: dict[tuple[int, str], bool] = {}


def is_package_task_active(env_id: int, package_name: str) -> bool:
    """Check whether an install/upgrade task is currently running for this package."""
    return _active_package_tasks.get((env_id, package_name), False)


def _broadcast_package_status(env_id: int, package_name: str, status: str, **extra) -> None:
    """Broadcast a package status change from a sync background thread."""
    from src.websocket.manager import ws_manager
    from src.main import _event_loop

    coro = ws_manager.broadcast_package_status(env_id, package_name, status, **extra)

    if _event_loop and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, _event_loop)
    else:
        logger.warning("No event loop available to broadcast package %s status", package_name)


def _mark_packages_changed(session, env_id: int) -> None:
    """Update packages_changed_at timestamp on the environment."""
    from datetime import datetime, timezone
    env = session.execute(
        select(Environment).where(Environment.id == env_id)
    ).scalar_one_or_none()
    if env:
        env.packages_changed_at = datetime.now(timezone.utc)


BROWSER_PACKAGE_NAMES = {"robotframework-browser", "robotframework_browser"}
BATTERIES_PACKAGE_NAMES = {"robotframework-browser-batteries", "robotframework_browser_batteries"}
ALL_BROWSER_VARIANTS = BROWSER_PACKAGE_NAMES | BATTERIES_PACKAGE_NAMES


def _is_browser_package(package_name: str) -> bool:
    """Check if a package name refers to robotframework-browser (standard)."""
    return package_name.lower().replace("_", "-") in BROWSER_PACKAGE_NAMES


def _is_batteries_package(package_name: str) -> bool:
    """Check if a package name refers to robotframework-browser-batteries."""
    return package_name.lower().replace("_", "-") in BATTERIES_PACKAGE_NAMES


def _is_any_browser_variant(package_name: str) -> bool:
    """Check if a package is any Browser library variant."""
    normalized = package_name.lower().replace("_", "-")
    return normalized in BROWSER_PACKAGE_NAMES or normalized in BATTERIES_PACKAGE_NAMES


def _get_conflicting_browser_package(env_id: int, package_name: str, session) -> str | None:
    """Return the name of a conflicting browser variant already installed, or None."""
    if not _is_any_browser_variant(package_name):
        return None
    pkgs = session.execute(
        select(EnvironmentPackage).where(
            EnvironmentPackage.environment_id == env_id,
            EnvironmentPackage.install_status.in_(["installed", "installing", "pending"]),
        )
    ).scalars().all()
    for p in pkgs:
        if p.package_name.lower().replace("_", "-") != package_name.lower().replace("_", "-"):
            if _is_any_browser_variant(p.package_name):
                return p.package_name
    return None


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

        # Verify node_modules was actually created
        if not check_rfbrowser_initialized(venv_path):
            error_msg = (
                "rfbrowser init completed (exit code 0) but Browser wrapper's "
                "node_modules directory was not created. This usually means "
                "Node.js/npm is installed but failed silently. "
                "Try running 'rfbrowser init' manually in the venv to see details."
            )
            logger.error(error_msg)
            if pkg:
                pkg.install_status = "failed"
                pkg.install_error = error_msg
                session.commit()
                _broadcast_package_status(
                    env_id, package_name, "failed", error=error_msg[:500],
                )
            return  # Don't raise — the install itself succeeded

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
    from src.environments.venv_utils import PythonVersionError, validate_python_version

    with get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()

        if env is None or env.venv_path is None:
            return {"status": "error", "message": "Environment not found"}

        try:
            # Validate Python version before attempting venv creation
            if env.python_version:
                try:
                    validate_python_version(env.python_version)
                except PythonVersionError as e:
                    logger.error("Invalid Python version for env %d: %s", env_id, e)
                    return {"status": "error", "message": str(e)}

            venv_path = Path(env.venv_path)
            if not venv_path.exists():
                result = subprocess.run(
                    create_venv_cmd(str(venv_path), env.python_version),
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    error_msg = result.stderr or result.stdout or "Unknown error"
                    if "No interpreter found" in error_msg or "not found" in error_msg.lower():
                        error_msg = (
                            f"Python {env.python_version} could not be found or installed by uv. "
                            f"Either install Python {env.python_version} manually, or use a "
                            f"supported version (3.9\u20133.13). Details: {error_msg}"
                        )
                    elif "download" in error_msg.lower():
                        error_msg = (
                            f"Failed to download Python {env.python_version}. This version may "
                            f"not be available yet. Details: {error_msg}"
                        )
                    logger.error("venv creation failed for env %d: %s", env_id, error_msg)
                    return {"status": "error", "message": error_msg}

            # Install robotframework by default
            result = subprocess.run(
                pip_install_cmd(str(venv_path), "robotframework"),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                if "No matching distribution" in error_msg or "requires-python" in error_msg.lower():
                    error_msg = (
                        f"robotframework is not yet available for Python {env.python_version}. "
                        f"Consider using Python 3.12 or 3.13 instead. Details: {error_msg}"
                    )
                logger.error("robotframework install failed for env %d: %s", env_id, error_msg)
                return {"status": "error", "message": error_msg}

            logger.info("Created venv at %s", venv_path)
            return {"status": "success", "message": f"Created venv at {venv_path}"}
        except Exception as exc:
            logger.exception("Failed to create venv for env %d", env_id)
            return {"status": "error", "message": str(exc)}


def install_package(env_id: int, package_name: str, version: str | None = None) -> dict:
    """Install a pip package in an environment's virtualenv."""
    _active_package_tasks[(env_id, package_name)] = True
    try:
        return _install_package_inner(env_id, package_name, version)
    finally:
        _active_package_tasks.pop((env_id, package_name), None)


def _install_package_inner(env_id: int, package_name: str, version: str | None = None) -> dict:
    """Inner install logic."""
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
                pip_install_cmd(
                    env.venv_path,
                    pkg_spec,
                    index_url=env.index_url,
                    extra_index_url=env.extra_index_url,
                ),
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
            _mark_packages_changed(session, env_id)
            session.commit()

            # Auto-init rfbrowser after robotframework-browser install (NOT for batteries)
            if _is_browser_package(package_name) and not _is_batteries_package(package_name):
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
    _active_package_tasks[(env_id, package_name)] = True
    try:
        return _upgrade_package_inner(env_id, package_name)
    finally:
        _active_package_tasks.pop((env_id, package_name), None)


def _upgrade_package_inner(env_id: int, package_name: str) -> dict:
    """Inner upgrade logic."""
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
                pip_install_cmd(
                    env.venv_path,
                    "--upgrade",
                    package_name,
                    index_url=env.index_url,
                    extra_index_url=env.extra_index_url,
                ),
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
            _mark_packages_changed(session, env_id)
            session.commit()

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


def _check_docker_disk_space(
    client: "docker.DockerClient",  # type: ignore[name-defined]
    env_id: int,
    log_lines: list[str],
    has_browser: bool = False,
) -> None:
    """Check available disk space in Docker and warn if low."""
    try:
        result = client.containers.run(
            "alpine", "df -h /", remove=True, stderr=True,
        )
        # Parse output: "overlay  2.9G  2.4G  464.0M  84%  /"
        for raw_line in result.decode().strip().splitlines():
            parts = raw_line.split()
            if len(parts) >= 4 and parts[0] != "Filesystem":
                avail = parts[3]
                # Parse available space to MB
                avail_mb = 0.0
                if avail.endswith("G"):
                    avail_mb = float(avail[:-1]) * 1024
                elif avail.endswith("M"):
                    avail_mb = float(avail[:-1])
                elif avail.endswith("K"):
                    avail_mb = float(avail[:-1]) / 1024

                # Browser packages need ~1.5 GB, normal builds ~500 MB
                threshold_mb = 2048 if has_browser else 1024
                threshold_label = "2 GB" if has_browser else "1 GB"

                info = f"Docker disk: {avail} available"
                log_lines.append(info)
                _broadcast_docker_build_log(env_id, info)

                if avail_mb < threshold_mb:
                    warning = (
                        f"WARNING: Low disk space ({avail} free, "
                        f"recommended: >{threshold_label}"
                        f"{' for robotframework-browser' if has_browser else ''})."
                        " Run 'docker system prune -a' to free space."
                    )
                    log_lines.append(warning)
                    _broadcast_docker_build_log(env_id, warning)
                break
    except Exception:
        pass  # Non-critical — don't block the build


def _broadcast_docker_build_log(env_id: int, line: str, done: bool = False) -> None:
    """Broadcast a Docker build log line from a sync background thread."""
    from src.websocket.manager import ws_manager
    from src.main import _event_loop

    coro = ws_manager.broadcast_docker_build_log(env_id, line, done=done)
    asyncio.run_coroutine_threadsafe(coro, _event_loop)


def build_docker_image(env_id: int) -> dict:
    """Build a Docker image for an environment with all its packages."""
    import io
    import json as _json
    import tarfile

    with get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()

        if env is None:
            return {"status": "error", "message": "Environment not found"}

        # Mark as building, clear previous log
        env.docker_build_status = "building"
        env.docker_build_error = None
        env.docker_build_log = None
        session.commit()

        packages = session.execute(
            select(EnvironmentPackage).where(EnvironmentPackage.environment_id == env_id)
        ).scalars().all()

        try:
            from src.environments.service import generate_dockerfile

            pkg_specs = []
            for pkg in packages:
                if pkg.version:
                    pkg_specs.append(f"{pkg.package_name}=={pkg.version}")
                else:
                    pkg_specs.append(pkg.package_name)

            # Always include robotframework — it's required to run tests
            if not any(s.split("==")[0].lower() == "robotframework" for s in pkg_specs):
                pkg_specs.insert(0, "robotframework")

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

            # Pre-build info
            log_lines: list[str] = []
            has_browser = any(
                _is_browser_package(s.split("==")[0]) for s in pkg_specs
            )
            _check_docker_disk_space(client, env_id, log_lines, has_browser=has_browser)
            if has_browser:
                msg = (
                    "Using Playwright base image (~2 GB). "
                    "Step 1 may take several minutes on first build."
                )
                log_lines.append(msg)
                _broadcast_docker_build_log(env_id, msg)

            resp = client.api.build(
                fileobj=f, custom_context=True, tag=tag, rm=True, decode=True,
            )
            for chunk in resp:
                if "stream" in chunk:
                    line = chunk["stream"].rstrip("\n")
                    if line:
                        log_lines.append(line)
                        _broadcast_docker_build_log(env_id, line)
                elif "error" in chunk:
                    error_msg = chunk["error"].rstrip("\n")
                    log_lines.append(f"ERROR: {error_msg}")
                    _broadcast_docker_build_log(env_id, f"ERROR: {error_msg}")
                    raise RuntimeError(error_msg)

            # Clean up dangling images from previous builds
            try:
                pruned = client.images.prune(filters={"dangling": True})
                reclaimed = pruned.get("SpaceReclaimed", 0)
                if reclaimed > 0:
                    mb = reclaimed / 1024 / 1024
                    msg = f"Cleaned up old images ({mb:.0f} MB freed)"
                    log_lines.append(msg)
                    _broadcast_docker_build_log(env_id, msg)
            except Exception:
                pass  # Non-critical

            # Signal completion
            _broadcast_docker_build_log(env_id, "", done=True)

            # Update environment's docker_image in DB
            from datetime import datetime, timezone
            env.docker_image = tag
            env.docker_image_built_at = datetime.now(timezone.utc)
            env.docker_build_status = "success"
            env.docker_build_error = None
            env.docker_build_log = "\n".join(log_lines)
            session.commit()

            logger.info("Built Docker image %s for env %d", tag, env_id)
            return {"status": "success", "image_tag": tag}

        except Exception as exc:
            logger.exception("Failed to build Docker image for env %d", env_id)
            error_msg = _enrich_docker_error(str(exc))
            env.docker_build_status = "error"
            env.docker_build_error = error_msg[:2000]
            env.docker_build_log = "\n".join(log_lines) if "log_lines" in locals() else None
            session.commit()
            _broadcast_docker_build_log(env_id, f"ERROR: {error_msg}", done=True)
            return {"status": "error", "message": error_msg}


def _enrich_docker_error(error: str) -> str:
    """Add actionable hints to common Docker errors."""
    lower = error.lower()
    if "no space left on device" in lower:
        # Try to get disk usage info
        disk_info = ""
        try:
            out = subprocess.check_output(
                ["docker", "system", "df", "--format",
                 "{{.Type}}: {{.Size}} ({{.Reclaimable}} reclaimable)"],
                text=True, timeout=5,
            ).strip()
            disk_info = f"\n\nDocker disk usage:\n{out}"
        except Exception:
            pass
        return (
            f"{error}\n\n"
            "Docker has run out of disk space. "
            "Run 'docker system prune' in a terminal to free up space "
            "(removes stopped containers and unused images). "
            "For a more aggressive cleanup: 'docker system prune -a'"
            f"{disk_info}"
        )
    if "connection refused" in lower or "cannot connect" in lower:
        return (
            f"{error}\n\n"
            "Cannot connect to Docker. "
            "Make sure Docker Desktop is running."
        )
    return error


def rfbrowser_init_task(env_id: int) -> dict:
    """Run 'rfbrowser init' for an environment (standalone task)."""
    with get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()
        if env is None or env.venv_path is None:
            return {"status": "error", "message": "Environment not found"}

        browser_pkg = session.execute(
            select(EnvironmentPackage).where(
                EnvironmentPackage.environment_id == env_id,
                EnvironmentPackage.install_status == "installed",
            )
        ).scalars().all()
        browser_pkg = next((p for p in browser_pkg if _is_browser_package(p.package_name)), None)

        try:
            _run_rfbrowser_init(env.venv_path, env_id, browser_pkg.package_name if browser_pkg else "robotframework-browser", browser_pkg, session)
            if browser_pkg:
                session.commit()
            return {"status": "success"}
        except Exception as exc:
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
            _mark_packages_changed(session, env_id)
            session.commit()
            return {"status": "success", "message": f"Uninstalled {package_name}"}
        except subprocess.CalledProcessError as e:
            logger.error("pip uninstall failed: %s", e.stderr)
            return {"status": "error", "message": e.stderr}
