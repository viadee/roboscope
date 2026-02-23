"""rf-mcp server process manager.

Manages the lifecycle of an rf-mcp server instance:
- Install rf-mcp package into a RoboScope Python environment
- Start/stop the server process
- Check status (running, installed, etc.)

This enables a one-click setup from the Settings UI.
"""

import logging
import os
import socket
import subprocess
import time
from pathlib import Path

from src.config import settings

logger = logging.getLogger("roboscope.ai.rf_mcp_manager")

RF_MCP_PACKAGE = "rf-mcp"

# Module-level singleton state for the managed server process
_process: subprocess.Popen | None = None
_environment_id: int | None = None
_venv_path: str | None = None
_port: int = 9090
_status: str = "stopped"  # stopped, installing, starting, running, error
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


def _get_pip_path(venv_path: str) -> str:
    return str(Path(venv_path) / "bin" / "pip")


def _get_python_path(venv_path: str) -> str:
    return str(Path(venv_path) / "bin" / "python")


def check_installed(venv_path: str) -> tuple[bool, str | None]:
    """Check if rf-mcp is installed and return (installed, version)."""
    pip = _get_pip_path(venv_path)
    if not Path(pip).exists():
        return False, None
    try:
        result = subprocess.run(
            [pip, "show", RF_MCP_PACKAGE],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return False, None
        version = None
        for line in result.stdout.splitlines():
            if line.startswith("Version:"):
                version = line.split(":", 1)[1].strip()
        return True, version
    except Exception:
        return False, None


def _install_package(venv_path: str) -> dict:
    """Install rf-mcp into the given venv."""
    pip = _get_pip_path(venv_path)
    try:
        result = subprocess.run(
            [pip, "install", RF_MCP_PACKAGE, "fastmcp<3"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            return {"status": "error", "message": result.stderr}

        _, version = check_installed(venv_path)
        return {"status": "success", "version": version}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Installation timed out (5 minutes)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port.

    Tries binding to successive ports. Returns the first available one,
    or falls back to start_port if none are free (letting the subprocess report the error).
    """
    for offset in range(max_attempts):
        port = start_port + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    return start_port


def _start_server(venv_path: str, port: int = 9090) -> dict:
    """Start the rf-mcp server process."""
    global _process, _port, _status

    port = _find_available_port(port)

    if is_running():
        proc = _process  # Local ref after is_running confirmed non-None
        return {"status": "already_running", "port": _port, "pid": proc.pid if proc else 0}

    from src.ai.rf_knowledge import reset_session
    reset_session()

    robotmcp_bin = str(Path(venv_path) / "bin" / "robotmcp")
    if not Path(robotmcp_bin).exists():
        return {"status": "error", "message": f"robotmcp CLI not found: {robotmcp_bin}"}

    _port = port

    try:
        env = {**os.environ}
        bin_dir = str(Path(venv_path) / "bin")
        env["PATH"] = bin_dir + ":" + env.get("PATH", "")
        env["VIRTUAL_ENV"] = venv_path

        proc = subprocess.Popen(
            [robotmcp_bin, "--transport", "http", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        _process = proc  # Publish to global after creation

        # Give server a moment to start (or fail)
        time.sleep(2)

        # Use local ref to avoid race with concurrent is_running() calls
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
        msg = f"Could not start rf-mcp. Ensure '{RF_MCP_PACKAGE}' is properly installed (robotmcp CLI)."
        logger.error(msg)
        return {"status": "error", "message": msg}
    except Exception as e:
        logger.exception("Failed to start rf-mcp")
        _status = "error"
        return {"status": "error", "message": str(e)}


def stop_server() -> dict:
    """Stop the managed rf-mcp server."""
    global _process, _status, _error_message

    from src.ai.rf_knowledge import reset_session
    reset_session()

    proc = _process  # Local ref to avoid race with concurrent threads
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
    elif effective_status not in ("installing", "starting", "error"):
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
    """Background task: install rf-mcp if needed, then start the server.

    Called via dispatch_task() from the API endpoint.
    """
    global _status, _error_message, _environment_id, _venv_path, _installed_version

    _environment_id = env_id
    _error_message = ""

    try:
        return _setup_inner(env_id, port)
    except Exception as e:
        logger.exception("rf-mcp setup failed unexpectedly")
        _status = "error"
        _error_message = str(e)
        return {"status": "error", "message": str(e)}


def _setup_inner(env_id: int, port: int) -> dict:
    """Inner setup logic, called by setup() with error handling."""
    global _status, _error_message, _venv_path, _installed_version

    # Get environment venv path from DB
    from sqlalchemy import select

    import src.auth.models  # noqa: F401
    from src.database import get_sync_session
    from src.environments.models import Environment

    with get_sync_session() as session:
        env = session.execute(
            select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()
        if not env or not env.venv_path:
            _status = "error"
            _error_message = "Environment not found or has no virtual environment"
            return {"status": "error", "message": _error_message}
        _venv_path = env.venv_path

    # Check if already installed
    installed, version = check_installed(_venv_path)
    if not installed:
        _status = "installing"
        logger.info("Installing %s in env %d...", RF_MCP_PACKAGE, env_id)
        result = _install_package(_venv_path)
        if result["status"] != "success":
            _status = "error"
            _error_message = result.get("message", "Installation failed")
            return result
        _installed_version = result.get("version")
        logger.info("Installed %s %s", RF_MCP_PACKAGE, _installed_version)
    else:
        _installed_version = version

    # Start the server
    _status = "starting"
    result = _start_server(_venv_path, port)
    if result["status"] in ("started", "already_running"):
        _status = "running"
        return result

    _status = "error"
    _error_message = result.get("message", "Failed to start server")
    return result
