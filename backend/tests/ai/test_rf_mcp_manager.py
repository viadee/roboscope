"""Unit tests for the rf-mcp server process manager."""

from unittest.mock import MagicMock, patch

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
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
            installed, version = rf_mcp_manager.check_installed("/fake/venv")
            assert installed is False
            assert version is None

    def test_installed_with_version(self):
        with (
            patch("subprocess.run") as mock_run,
            patch("src.ai.rf_mcp_manager.Path") as mock_path,
        ):
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__truediv__ = lambda self, x: mock_path.return_value
            mock_path.return_value.__str__ = lambda self: "/fake/venv/bin/pip"
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Name: robotframework-mcp\nVersion: 1.2.3\nSummary: RF MCP\n",
                stderr="",
            )
            installed, version = rf_mcp_manager.check_installed("/fake/venv")
            assert installed is True
            assert version == "1.2.3"

    def test_pip_not_found(self):
        """When pip doesn't exist, returns not installed."""
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
