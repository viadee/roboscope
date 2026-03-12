"""rf-mcp server process manager.

Manages the lifecycle of an rf-mcp server instance.
rf-mcp is a default dependency of RoboScope — no separate installation needed.

The server can be started in two modes:
1. Bundled mode (start_bundled): Uses RoboScope's own Python with optional
   environment site-packages for library discovery.
2. Legacy mode (setup): For backwards compatibility with the Settings UI.
"""

import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from src.config import settings
from src.environments.venv_utils import get_venv_bin_dir

logger = logging.getLogger("roboscope.ai.rf_mcp_manager")

RF_MCP_PACKAGE = "rf-mcp"

# Module-level singleton state for the managed server process
_process: subprocess.Popen | None = None
_environment_id: int | None = None
_venv_path: str | None = None
_port: int = 9090
_status: str = "stopped"  # stopped, starting, running, error
_error_message: str = ""
_installed_version: str | None = None


def get_effective_url() -> str:
    """Get the effective rf-mcp URL.

    Returns the managed server URL if running, otherwise the configured URL.
    """
    if is_running():
        return f"http://localhost:{_port}/mcp"
    return settings.RF_MCP_URL


def is_running() -> bool:
    """Check if the managed rf-mcp server process is alive."""
    global _process, _status
    proc = _process  # Local ref to avoid race with concurrent threads
    if proc is None:
        return False
    if proc.poll() is not None:
        # Process has exited
        _status = "stopped"
        _process = None
        return False
    return True


def _find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port."""
    for offset in range(max_attempts):
        port = start_port + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    return start_port


def _get_env_site_packages(venv_path: str) -> str | None:
    """Get the site-packages directory from an environment's venv."""
    venv = Path(venv_path)
    # Unix: lib/pythonX.Y/site-packages
    for sp in venv.glob("lib/python*/site-packages"):
        if sp.is_dir():
            return str(sp)
    # Windows: Lib/site-packages
    sp = venv / "Lib" / "site-packages"
    if sp.is_dir():
        return str(sp)
    return None


def _start_server_process(port: int, env_site_packages: str | None = None) -> dict:
    """Start the rf-mcp server process using RoboScope's own Python.

    Args:
        port: Port to listen on.
        env_site_packages: Optional path to an environment's site-packages
            for additional library discovery.
    """
    global _process, _port, _status

    port = _find_available_port(port)

    if is_running():
        proc = _process
        return {"status": "already_running", "port": _port, "pid": proc.pid if proc else 0}

    from src.ai.rf_knowledge import reset_session
    reset_session()

    _port = port

    try:
        env = {**os.environ}

        # Add environment's site-packages to PYTHONPATH for library discovery
        if env_site_packages:
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = env_site_packages + (os.pathsep + existing if existing else "")

        # Use RoboScope's own Python to run robotmcp (it's a default dependency)
        proc = subprocess.Popen(
            [sys.executable, "-m", "robotmcp.server",
             "--transport", "http", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        _process = proc

        # Give server a moment to start (or fail)
        time.sleep(2)

        if proc.poll() is not None:
            stderr = ""
            if proc.stderr:
                stderr = proc.stderr.read().decode(errors="replace")
            _process = None
            _status = "error"
            return {"status": "error", "message": f"Server exited immediately: {stderr[:500]}"}

        _status = "running"
        logger.info("Started rf-mcp on port %d (PID: %d)", port, proc.pid)
        return {"status": "started", "port": port, "pid": proc.pid}
    except FileNotFoundError:
        _status = "error"
        msg = "Could not start rf-mcp. The robotmcp module was not found."
        logger.error(msg)
        return {"status": "error", "message": msg}
    except Exception as e:
        logger.exception("Failed to start rf-mcp")
        _status = "error"
        return {"status": "error", "message": str(e)}


def start_bundled(env_id: int | None = None, port: int = 0) -> dict:
    """Start rf-mcp using RoboScope's bundled installation.

    Args:
        env_id: Optional environment ID whose site-packages should be available
            for library keyword discovery.
        port: Port to listen on. 0 = use settings.RF_MCP_PORT.
    """
    global _environment_id, _error_message, _status

    if is_running():
        return get_status()

    _environment_id = env_id
    _error_message = ""
    _status = "starting"
    port = port or settings.RF_MCP_PORT

    env_site_packages = None
    if env_id:
        try:
            from sqlalchemy import select

            import src.auth.models  # noqa: F401
            from src.database import get_sync_session
            from src.environments.models import Environment

            with get_sync_session() as session:
                env = session.execute(
                    select(Environment).where(Environment.id == env_id)
                ).scalar_one_or_none()
                if env and env.venv_path:
                    env_site_packages = _get_env_site_packages(env.venv_path)
        except Exception:
            logger.warning("Could not resolve environment %d site-packages", env_id)

    result = _start_server_process(port, env_site_packages)
    if result["status"] in ("started", "already_running"):
        _status = "running"

        # Try to get installed version
        global _installed_version
        try:
            import importlib.metadata
            _installed_version = importlib.metadata.version("rf-mcp")
        except Exception:
            _installed_version = None

        return result

    _status = "error"
    _error_message = result.get("message", "Failed to start server")
    return result


def stop_server() -> dict:
    """Stop the managed rf-mcp server."""
    global _process, _status, _error_message

    from src.ai.rf_knowledge import reset_session
    reset_session()

    proc = _process
    if proc is None or not is_running():
        _process = None
        _status = "stopped"
        _error_message = ""
        return {"status": "stopped"}

    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

        pid = proc.pid
        _process = None
        _status = "stopped"
        _error_message = ""
        logger.info("Stopped rf-mcp server (PID: %d)", pid)
        return {"status": "stopped"}
    except Exception as e:
        logger.exception("Failed to stop rf-mcp")
        return {"status": "error", "message": str(e)}


def get_status() -> dict:
    """Get detailed status of the rf-mcp server."""
    running = is_running()
    effective_status = _status
    if running:
        effective_status = "running"
    elif effective_status not in ("starting", "error"):
        effective_status = "stopped"

    return {
        "status": effective_status,
        "running": running,
        "port": _port if running else None,
        "pid": _process.pid if running and _process else None,
        "url": get_effective_url(),
        "environment_id": _environment_id,
        "error_message": _error_message if effective_status == "error" else "",
        "installed_version": _installed_version,
    }


def setup(env_id: int, port: int = 9090) -> dict:
    """Background task: start the rf-mcp server.

    Kept for backwards compatibility with the Settings UI / dispatch_task().
    Since rf-mcp is now a default dependency, no installation step is needed.
    """
    global _status, _error_message, _environment_id
    _environment_id = env_id
    _error_message = ""

    try:
        return start_bundled(env_id, port)
    except Exception as e:
        logger.exception("rf-mcp setup failed unexpectedly")
        _status = "error"
        _error_message = str(e)
        return {"status": "error", "message": str(e)}
