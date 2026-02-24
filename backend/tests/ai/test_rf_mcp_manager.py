"""Unit tests for the rf-mcp server process manager."""

import socket
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.ai import rf_mcp_manager


class TestGetEffectiveUrl:
    def test_returns_empty_when_stopped(self):
        rf_mcp_manager._process = None
        rf_mcp_manager._status = "stopped"
        with patch.object(rf_mcp_manager.settings, "RF_MCP_URL", ""):
            assert rf_mcp_manager.get_effective_url() == ""

    def test_returns_configured_url_when_no_managed_server(self):
        rf_mcp_manager._process = None
        with patch.object(rf_mcp_manager.settings, "RF_MCP_URL", "http://external:9090/mcp"):
            assert rf_mcp_manager.get_effective_url() == "http://external:9090/mcp"

    def test_returns_managed_url_when_running(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running
        rf_mcp_manager._process = mock_proc
        rf_mcp_manager._port = 9090
        rf_mcp_manager._status = "running"
        assert rf_mcp_manager.get_effective_url() == "http://localhost:9090/mcp"
        # cleanup
        rf_mcp_manager._process = None
        rf_mcp_manager._status = "stopped"


class TestIsRunning:
    def test_false_when_no_process(self):
        rf_mcp_manager._process = None
        assert rf_mcp_manager.is_running() is False

    def test_true_when_process_alive(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        rf_mcp_manager._process = mock_proc
        rf_mcp_manager._status = "running"
        assert rf_mcp_manager.is_running() is True
        rf_mcp_manager._process = None
        rf_mcp_manager._status = "stopped"

    def test_false_when_process_exited(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # exited with code 1
        rf_mcp_manager._process = mock_proc
        rf_mcp_manager._status = "running"
        assert rf_mcp_manager.is_running() is False
        assert rf_mcp_manager._status == "stopped"
        assert rf_mcp_manager._process is None


class TestCheckInstalled:
    def test_not_installed(self):
        with (
            patch("subprocess.run") as mock_run,
            patch("src.ai.rf_mcp_manager.get_python_path", return_value="/fake/venv/bin/python"),
            patch("src.ai.rf_mcp_manager.Path") as mock_path,
            patch("src.ai.rf_mcp_manager.pip_show_cmd", return_value=["uv", "pip", "show", "--python", "/fake/venv/bin/python", "rf-mcp"]),
        ):
            mock_path.return_value.exists.return_value = True
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
            installed, version = rf_mcp_manager.check_installed("/fake/venv")
            assert installed is False
            assert version is None

    def test_installed_with_version(self):
        with (
            patch("subprocess.run") as mock_run,
            patch("src.ai.rf_mcp_manager.get_python_path", return_value="/fake/venv/bin/python"),
            patch("src.ai.rf_mcp_manager.Path") as mock_path,
            patch("src.ai.rf_mcp_manager.pip_show_cmd", return_value=["uv", "pip", "show", "--python", "/fake/venv/bin/python", "rf-mcp"]),
        ):
            mock_path.return_value.exists.return_value = True
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Name: robotframework-mcp\nVersion: 1.2.3\nSummary: RF MCP\n",
                stderr="",
            )
            installed, version = rf_mcp_manager.check_installed("/fake/venv")
            assert installed is True
            assert version == "1.2.3"

    def test_python_not_found(self):
        """When python doesn't exist in venv, returns not installed."""
        with (
            patch("src.ai.rf_mcp_manager.get_python_path", return_value="/nonexistent/venv/bin/python"),
        ):
            installed, version = rf_mcp_manager.check_installed("/nonexistent/venv")
            assert installed is False
            assert version is None


class TestGetStatus:
    def test_stopped_status(self):
        rf_mcp_manager._process = None
        rf_mcp_manager._status = "stopped"
        rf_mcp_manager._error_message = ""
        rf_mcp_manager._environment_id = None

        status = rf_mcp_manager.get_status()
        assert status["status"] == "stopped"
        assert status["running"] is False
        assert status["port"] is None
        assert status["pid"] is None

    def test_running_status(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 12345
        rf_mcp_manager._process = mock_proc
        rf_mcp_manager._port = 9090
        rf_mcp_manager._status = "running"
        rf_mcp_manager._environment_id = 1
        rf_mcp_manager._installed_version = "1.2.3"

        status = rf_mcp_manager.get_status()
        assert status["status"] == "running"
        assert status["running"] is True
        assert status["port"] == 9090
        assert status["pid"] == 12345
        assert status["environment_id"] == 1
        assert status["installed_version"] == "1.2.3"

        # cleanup
        rf_mcp_manager._process = None
        rf_mcp_manager._status = "stopped"
        rf_mcp_manager._environment_id = None

    def test_error_status(self):
        rf_mcp_manager._process = None
        rf_mcp_manager._status = "error"
        rf_mcp_manager._error_message = "Something went wrong"

        status = rf_mcp_manager.get_status()
        assert status["status"] == "error"
        assert status["error_message"] == "Something went wrong"

        rf_mcp_manager._status = "stopped"
        rf_mcp_manager._error_message = ""


class TestStopServer:
    def test_stop_when_not_running(self):
        rf_mcp_manager._process = None
        result = rf_mcp_manager.stop_server()
        assert result["status"] == "stopped"

    def test_stop_running_server(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running
        mock_proc.pid = 999
        mock_proc.wait.return_value = 0
        rf_mcp_manager._process = mock_proc
        rf_mcp_manager._status = "running"

        result = rf_mcp_manager.stop_server()
        assert result["status"] == "stopped"
        mock_proc.terminate.assert_called_once()
        assert rf_mcp_manager._process is None
        assert rf_mcp_manager._status == "stopped"


# --- Test: _install_package ---


class TestInstallPackage:
    def test_successful_install(self):
        with (
            patch("subprocess.run") as mock_run,
            patch("src.ai.rf_mcp_manager.pip_install_cmd", return_value=["uv", "pip", "install", "--python", "/fake/venv/bin/python", "rf-mcp", "fastmcp<3"]),
        ):
            # pip install succeeds
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            with patch.object(rf_mcp_manager, "check_installed", return_value=(True, "1.0.0")):
                result = rf_mcp_manager._install_package("/fake/venv")

            assert result["status"] == "success"
            assert result["version"] == "1.0.0"

    def test_install_failure(self):
        with (
            patch("subprocess.run") as mock_run,
            patch("src.ai.rf_mcp_manager.pip_install_cmd", return_value=["uv", "pip", "install", "--python", "/fake/venv/bin/python", "rf-mcp", "fastmcp<3"]),
        ):
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="ERROR: Could not find a version"
            )
            result = rf_mcp_manager._install_package("/fake/venv")
            assert result["status"] == "error"
            assert "Could not find" in result["message"]

    def test_install_timeout(self):
        with (
            patch("subprocess.run") as mock_run,
            patch("src.ai.rf_mcp_manager.pip_install_cmd", return_value=["uv", "pip", "install", "--python", "/fake/venv/bin/python", "rf-mcp", "fastmcp<3"]),
        ):
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="uv", timeout=300)
            result = rf_mcp_manager._install_package("/fake/venv")
            assert result["status"] == "error"
            assert "timed out" in result["message"]


# --- Test: _start_server ---


class TestStartServer:
    def test_successful_start(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running after sleep
        mock_proc.pid = 42

        with (
            patch("src.ai.rf_mcp_manager.get_venv_bin_dir", return_value="/fake/venv/bin"),
            patch("src.ai.rf_mcp_manager.Path") as mock_path,
            patch("subprocess.Popen", return_value=mock_proc),
            patch("time.sleep"),
            patch.object(rf_mcp_manager, "_find_available_port", return_value=9090),
        ):
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__truediv__ = lambda self, x: mock_path.return_value
            mock_path.return_value.__str__ = lambda self: "/fake/venv/bin/robotmcp"
            rf_mcp_manager._process = None
            rf_mcp_manager._status = "stopped"

            result = rf_mcp_manager._start_server("/fake/venv", 9090)

        assert result["status"] == "started"
        assert result["port"] == 9090
        assert result["pid"] == 42
        assert rf_mcp_manager._status == "running"
        # cleanup
        rf_mcp_manager._process = None
        rf_mcp_manager._status = "stopped"

    def test_server_exits_immediately(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # exited
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = b"ModuleNotFoundError: robotmcp"

        with (
            patch("src.ai.rf_mcp_manager.get_venv_bin_dir", return_value="/fake/venv/bin"),
            patch("src.ai.rf_mcp_manager.Path") as mock_path,
            patch("subprocess.Popen", return_value=mock_proc),
            patch("time.sleep"),
            patch.object(rf_mcp_manager, "_find_available_port", return_value=9090),
        ):
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__truediv__ = lambda self, x: mock_path.return_value
            mock_path.return_value.__str__ = lambda self: "/fake/venv/bin/robotmcp"
            rf_mcp_manager._process = None

            result = rf_mcp_manager._start_server("/fake/venv", 9090)

        assert result["status"] == "error"
        assert "ModuleNotFoundError" in result["message"]
        assert rf_mcp_manager._status == "error"
        assert rf_mcp_manager._process is None

    def test_robotmcp_not_found(self):
        with patch("src.ai.rf_mcp_manager.get_venv_bin_dir", return_value="/nonexistent/venv/bin"):
            result = rf_mcp_manager._start_server("/nonexistent/venv", 9090)
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_already_running(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 100
        rf_mcp_manager._process = mock_proc
        rf_mcp_manager._port = 9090
        rf_mcp_manager._status = "running"

        result = rf_mcp_manager._start_server("/fake/venv", 9090)
        assert result["status"] == "already_running"
        # cleanup
        rf_mcp_manager._process = None
        rf_mcp_manager._status = "stopped"

    def test_race_condition_uses_local_ref(self):
        """_start_server uses local proc ref so concurrent is_running() can't null it."""
        mock_proc = MagicMock()
        # First poll (from _start_server check): None (still running)
        mock_proc.poll.return_value = None
        mock_proc.pid = 55

        with (
            patch("src.ai.rf_mcp_manager.get_venv_bin_dir", return_value="/fake/venv/bin"),
            patch("src.ai.rf_mcp_manager.Path") as mock_path,
            patch("subprocess.Popen", return_value=mock_proc),
            patch("time.sleep"),
            patch.object(rf_mcp_manager, "_find_available_port", return_value=9090),
        ):
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__truediv__ = lambda self, x: mock_path.return_value
            mock_path.return_value.__str__ = lambda self: "/fake/venv/bin/robotmcp"
            rf_mcp_manager._process = None

            result = rf_mcp_manager._start_server("/fake/venv", 9090)

        # Should succeed even if _process was cleared by concurrent thread
        assert result["status"] == "started"
        assert result["pid"] == 55
        # cleanup
        rf_mcp_manager._process = None
        rf_mcp_manager._status = "stopped"


# --- Test: setup() error handling ---


class TestSetup:
    def test_setup_catches_unhandled_exceptions(self):
        """setup() wraps in try/except so _status always reaches a terminal state."""
        rf_mcp_manager._status = "stopped"
        rf_mcp_manager._error_message = ""

        with patch.object(rf_mcp_manager, "_setup_inner", side_effect=RuntimeError("DB exploded")):
            result = rf_mcp_manager.setup(1, 9090)

        assert result["status"] == "error"
        assert "DB exploded" in result["message"]
        assert rf_mcp_manager._status == "error"
        assert "DB exploded" in rf_mcp_manager._error_message
        # cleanup
        rf_mcp_manager._status = "stopped"
        rf_mcp_manager._error_message = ""

    def test_setup_sets_environment_id(self):
        """setup() should set _environment_id before calling _setup_inner."""
        rf_mcp_manager._environment_id = None

        with patch.object(rf_mcp_manager, "_setup_inner", return_value={"status": "started"}):
            rf_mcp_manager.setup(42, 9090)

        assert rf_mcp_manager._environment_id == 42
        # cleanup
        rf_mcp_manager._environment_id = None
        rf_mcp_manager._status = "stopped"

    def test_setup_inner_env_not_found(self):
        """_setup_inner should error when environment doesn't exist."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        with patch("src.database.get_sync_session", return_value=mock_session):
            result = rf_mcp_manager._setup_inner(999, 9090)

        assert result["status"] == "error"
        assert rf_mcp_manager._status == "error"
        assert "not found" in rf_mcp_manager._error_message
        # cleanup
        rf_mcp_manager._status = "stopped"
        rf_mcp_manager._error_message = ""

    def test_setup_inner_install_and_start(self):
        """_setup_inner should install if not installed, then start."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_env = MagicMock()
        mock_env.venv_path = "/fake/venv"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_env

        with (
            patch("src.database.get_sync_session", return_value=mock_session),
            patch.object(rf_mcp_manager, "check_installed", return_value=(False, None)),
            patch.object(rf_mcp_manager, "_install_package", return_value={"status": "success", "version": "1.0.0"}),
            patch.object(rf_mcp_manager, "_start_server", return_value={"status": "started", "port": 9090, "pid": 99}),
        ):
            result = rf_mcp_manager._setup_inner(1, 9090)

        assert result["status"] == "started"
        assert rf_mcp_manager._status == "running"
        assert rf_mcp_manager._installed_version == "1.0.0"
        # cleanup
        rf_mcp_manager._status = "stopped"
        rf_mcp_manager._installed_version = None

    def test_setup_inner_already_installed(self):
        """_setup_inner should skip install when already installed."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_env = MagicMock()
        mock_env.venv_path = "/fake/venv"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_env

        with (
            patch("src.database.get_sync_session", return_value=mock_session),
            patch.object(rf_mcp_manager, "check_installed", return_value=(True, "2.0.0")),
            patch.object(rf_mcp_manager, "_install_package") as mock_install,
            patch.object(rf_mcp_manager, "_start_server", return_value={"status": "started", "port": 9090, "pid": 99}),
        ):
            result = rf_mcp_manager._setup_inner(1, 9090)

        mock_install.assert_not_called()
        assert rf_mcp_manager._installed_version == "2.0.0"
        assert result["status"] == "started"
        # cleanup
        rf_mcp_manager._status = "stopped"
        rf_mcp_manager._installed_version = None

    def test_setup_inner_install_failure(self):
        """_setup_inner should return error when install fails."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_env = MagicMock()
        mock_env.venv_path = "/fake/venv"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_env

        with (
            patch("src.database.get_sync_session", return_value=mock_session),
            patch.object(rf_mcp_manager, "check_installed", return_value=(False, None)),
            patch.object(rf_mcp_manager, "_install_package", return_value={"status": "error", "message": "pip failed"}),
        ):
            result = rf_mcp_manager._setup_inner(1, 9090)

        assert result["status"] == "error"
        assert rf_mcp_manager._status == "error"
        assert "pip failed" in rf_mcp_manager._error_message
        # cleanup
        rf_mcp_manager._status = "stopped"
        rf_mcp_manager._error_message = ""


# --- Test: _find_available_port ---


class TestFindAvailablePort:
    def test_returns_same_port_when_available(self):
        """When the start port is free, returns it directly."""
        # Use a high port unlikely to be in use
        port = rf_mcp_manager._find_available_port(59123)
        assert port == 59123

    def test_returns_next_port_when_blocked(self):
        """When the start port is occupied, returns the next available one."""
        # Occupy the port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 59200))
            s.listen(1)
            port = rf_mcp_manager._find_available_port(59200)
            assert port == 59201

    def test_returns_start_port_when_all_blocked(self):
        """When all ports in range are blocked, falls back to start_port."""
        sockets = []
        try:
            for offset in range(3):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("127.0.0.1", 59300 + offset))
                s.listen(1)
                sockets.append(s)
            port = rf_mcp_manager._find_available_port(59300, max_attempts=3)
            assert port == 59300  # fallback
        finally:
            for s in sockets:
                s.close()
