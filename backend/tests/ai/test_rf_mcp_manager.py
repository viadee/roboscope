"""Unit tests for the rf-mcp server process manager."""

import socket
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


class TestGetEnvSitePackages:
    def test_finds_unix_site_packages(self, tmp_path):
        sp = tmp_path / "lib" / "python3.12" / "site-packages"
        sp.mkdir(parents=True)
        assert rf_mcp_manager._get_env_site_packages(str(tmp_path)) == str(sp)

    def test_finds_windows_site_packages(self, tmp_path):
        sp = tmp_path / "Lib" / "site-packages"
        sp.mkdir(parents=True)
        assert rf_mcp_manager._get_env_site_packages(str(tmp_path)) == str(sp)

    def test_returns_none_when_not_found(self, tmp_path):
        assert rf_mcp_manager._get_env_site_packages(str(tmp_path)) is None


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


class TestStartServerProcess:
    def test_successful_start(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running after sleep
        mock_proc.pid = 42

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("time.sleep"),
            patch.object(rf_mcp_manager, "_find_available_port", return_value=9090),
        ):
            rf_mcp_manager._process = None
            rf_mcp_manager._status = "stopped"

            result = rf_mcp_manager._start_server_process(9090)

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
            patch("subprocess.Popen", return_value=mock_proc),
            patch("time.sleep"),
            patch.object(rf_mcp_manager, "_find_available_port", return_value=9090),
        ):
            rf_mcp_manager._process = None
            result = rf_mcp_manager._start_server_process(9090)

        assert result["status"] == "error"
        assert "ModuleNotFoundError" in result["message"]
        assert rf_mcp_manager._status == "error"
        assert rf_mcp_manager._process is None

    def test_already_running(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 100
        rf_mcp_manager._process = mock_proc
        rf_mcp_manager._port = 9090
        rf_mcp_manager._status = "running"

        result = rf_mcp_manager._start_server_process(9090)
        assert result["status"] == "already_running"
        # cleanup
        rf_mcp_manager._process = None
        rf_mcp_manager._status = "stopped"

    def test_with_env_site_packages(self):
        """PYTHONPATH should include env site-packages when provided."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 55

        captured_env = {}

        def capture_popen(*args, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            return mock_proc

        with (
            patch("subprocess.Popen", side_effect=capture_popen),
            patch("time.sleep"),
            patch.object(rf_mcp_manager, "_find_available_port", return_value=9090),
        ):
            rf_mcp_manager._process = None
            result = rf_mcp_manager._start_server_process(9090, "/fake/env/lib/python3.12/site-packages")

        assert result["status"] == "started"
        assert "/fake/env/lib/python3.12/site-packages" in captured_env.get("PYTHONPATH", "")
        # cleanup
        rf_mcp_manager._process = None
        rf_mcp_manager._status = "stopped"


class TestStartBundled:
    def test_start_without_env(self):
        with patch.object(rf_mcp_manager, "_start_server_process", return_value={"status": "started", "port": 9090, "pid": 1}):
            rf_mcp_manager._process = None
            rf_mcp_manager._status = "stopped"
            result = rf_mcp_manager.start_bundled()

        assert result["status"] == "started"
        assert rf_mcp_manager._status == "running"
        assert rf_mcp_manager._environment_id is None
        # cleanup
        rf_mcp_manager._status = "stopped"

    def test_start_with_env(self):
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_env = MagicMock()
        mock_env.venv_path = "/fake/venv"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_env

        with (
            patch("src.database.get_sync_session", return_value=mock_session),
            patch.object(rf_mcp_manager, "_get_env_site_packages", return_value="/fake/venv/lib/python3.12/site-packages"),
            patch.object(rf_mcp_manager, "_start_server_process", return_value={"status": "started", "port": 9090, "pid": 1}) as mock_start,
        ):
            rf_mcp_manager._process = None
            rf_mcp_manager._status = "stopped"
            result = rf_mcp_manager.start_bundled(env_id=1, port=9090)

        assert result["status"] == "started"
        assert rf_mcp_manager._status == "running"
        assert rf_mcp_manager._environment_id == 1
        mock_start.assert_called_once_with(9090, "/fake/venv/lib/python3.12/site-packages")
        # cleanup
        rf_mcp_manager._status = "stopped"
        rf_mcp_manager._environment_id = None

    def test_returns_status_when_already_running(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 42
        rf_mcp_manager._process = mock_proc
        rf_mcp_manager._port = 9090
        rf_mcp_manager._status = "running"

        result = rf_mcp_manager.start_bundled()
        assert result["status"] == "running"
        # cleanup
        rf_mcp_manager._process = None
        rf_mcp_manager._status = "stopped"


class TestSetup:
    def test_setup_delegates_to_start_bundled(self):
        with patch.object(rf_mcp_manager, "start_bundled", return_value={"status": "running"}) as mock:
            result = rf_mcp_manager.setup(42, 9090)

        mock.assert_called_once_with(42, 9090)
        assert result["status"] == "running"
        assert rf_mcp_manager._environment_id == 42
        # cleanup
        rf_mcp_manager._environment_id = None

    def test_setup_catches_exceptions(self):
        rf_mcp_manager._status = "stopped"
        rf_mcp_manager._error_message = ""

        with patch.object(rf_mcp_manager, "start_bundled", side_effect=RuntimeError("DB exploded")):
            result = rf_mcp_manager.setup(1, 9090)

        assert result["status"] == "error"
        assert "DB exploded" in result["message"]
        assert rf_mcp_manager._status == "error"
        # cleanup
        rf_mcp_manager._status = "stopped"
        rf_mcp_manager._error_message = ""


class TestFindAvailablePort:
    def test_returns_same_port_when_available(self):
        port = rf_mcp_manager._find_available_port(59123)
        assert port == 59123

    def test_returns_next_port_when_blocked(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 59200))
            s.listen(1)
            port = rf_mcp_manager._find_available_port(59200)
            assert port == 59201

    def test_returns_start_port_when_all_blocked(self):
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
