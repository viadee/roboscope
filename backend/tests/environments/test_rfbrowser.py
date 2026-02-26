"""Tests for robotframework-browser (rfbrowser) auto-init support."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.environments import venv_utils
from src.environments.models import Environment, EnvironmentPackage
from src.environments.service import generate_dockerfile, _has_browser_package
from src.environments.tasks import (
    _is_browser_package,
    _run_rfbrowser_init,
    install_package,
)


# ---------------------------------------------------------------------------
# venv_utils: rfbrowser_init_cmd
# ---------------------------------------------------------------------------


class TestRfbrowserInitCmd:
    def test_unix(self):
        with patch.object(venv_utils.sys, "platform", "linux"):
            cmd = venv_utils.rfbrowser_init_cmd("/fake/venv")
        assert cmd == ["/fake/venv/bin/rfbrowser", "init"]

    def test_windows(self):
        with patch.object(venv_utils.sys, "platform", "win32"):
            cmd = venv_utils.rfbrowser_init_cmd("/fake/venv")
        assert cmd[1] == "init"
        assert "Scripts" in cmd[0]
        assert cmd[0].endswith("rfbrowser.exe")


# ---------------------------------------------------------------------------
# tasks: _is_browser_package
# ---------------------------------------------------------------------------


class TestIsBrowserPackage:
    def test_exact_name(self):
        assert _is_browser_package("robotframework-browser") is True

    def test_underscore_variant(self):
        assert _is_browser_package("robotframework_browser") is True

    def test_case_insensitive(self):
        assert _is_browser_package("RobotFramework-Browser") is True

    def test_unrelated_package(self):
        assert _is_browser_package("robotframework-seleniumlibrary") is False

    def test_robotframework_itself(self):
        assert _is_browser_package("robotframework") is False


# ---------------------------------------------------------------------------
# tasks: _run_rfbrowser_init
# ---------------------------------------------------------------------------


class TestRunRfbrowserInit:
    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_success(self, mock_run, mock_broadcast):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        pkg = MagicMock()
        session = MagicMock()

        with patch.object(venv_utils.sys, "platform", "linux"):
            _run_rfbrowser_init("/fake/venv", 1, "robotframework-browser", pkg, session)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["/fake/venv/bin/rfbrowser", "init"]
        assert mock_run.call_args[1]["timeout"] == 600
        # PATH should include venv bin dir
        env_vars = mock_run.call_args[1]["env"]
        assert env_vars["PATH"].startswith("/fake/venv/bin")

    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_failure_marks_package_failed(self, mock_run, mock_broadcast):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="node not found"
        )
        pkg = MagicMock()
        session = MagicMock()

        with (
            patch.object(venv_utils.sys, "platform", "linux"),
            pytest.raises(subprocess.CalledProcessError),
        ):
            _run_rfbrowser_init("/fake/venv", 1, "robotframework-browser", pkg, session)

        assert pkg.install_status == "failed"
        assert "rfbrowser init failed" in pkg.install_error
        session.commit.assert_called_once()
        mock_broadcast.assert_called()
        # Last broadcast should be "failed"
        last_call = mock_broadcast.call_args_list[-1]
        assert last_call[0][2] == "failed"

    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_timeout_marks_package_failed(self, mock_run, mock_broadcast):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="rfbrowser", timeout=600)
        pkg = MagicMock()
        session = MagicMock()

        with (
            patch.object(venv_utils.sys, "platform", "linux"),
            pytest.raises(subprocess.TimeoutExpired),
        ):
            _run_rfbrowser_init("/fake/venv", 1, "robotframework-browser", pkg, session)

        assert pkg.install_status == "failed"
        assert "rfbrowser init failed" in pkg.install_error


# ---------------------------------------------------------------------------
# tasks: install_package triggers rfbrowser init
# ---------------------------------------------------------------------------


class TestInstallPackageBrowserHook:
    @patch("src.environments.tasks._run_rfbrowser_init")
    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_install_browser_triggers_init(
        self, mock_run, mock_broadcast, mock_init, db_session
    ):
        env = Environment(
            name="test-env", venv_path="/tmp/test-venv",
            python_version="3.12", created_by=1,
        )
        db_session.add(env)
        db_session.flush()
        pkg = EnvironmentPackage(
            environment_id=env.id, package_name="robotframework-browser",
        )
        db_session.add(pkg)
        db_session.flush()
        db_session.commit()

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # install
            MagicMock(returncode=0, stdout="Name: robotframework-browser\nVersion: 18.0.0\n", stderr=""),  # show
        ]

        with patch("src.environments.tasks.get_sync_session") as mock_gs:
            mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_gs.return_value.__exit__ = MagicMock(return_value=False)
            result = install_package(env.id, "robotframework-browser")

        assert result["status"] == "success"
        mock_init.assert_called_once()
        call_args = mock_init.call_args
        assert call_args[0][0] == "/tmp/test-venv"  # venv_path
        assert call_args[0][1] == env.id  # env_id

    @patch("src.environments.tasks._run_rfbrowser_init")
    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_install_regular_package_no_init(
        self, mock_run, mock_broadcast, mock_init, db_session
    ):
        env = Environment(
            name="test-env", venv_path="/tmp/test-venv",
            python_version="3.12", created_by=1,
        )
        db_session.add(env)
        db_session.flush()
        pkg = EnvironmentPackage(
            environment_id=env.id, package_name="requests",
        )
        db_session.add(pkg)
        db_session.flush()
        db_session.commit()

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="Name: requests\nVersion: 2.31.0\n", stderr=""),
        ]

        with patch("src.environments.tasks.get_sync_session") as mock_gs:
            mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_gs.return_value.__exit__ = MagicMock(return_value=False)
            result = install_package(env.id, "requests")

        assert result["status"] == "success"
        mock_init.assert_not_called()


# ---------------------------------------------------------------------------
# service: generate_dockerfile
# ---------------------------------------------------------------------------


class TestGenerateDockerfileBrowser:
    def test_with_browser_package_includes_nodejs(self):
        df = generate_dockerfile("3.12", ["robotframework", "robotframework-browser==18.0.0"])
        assert "nodejs" in df
        assert "nodesource" in df
        assert "rfbrowser init" in df

    def test_without_browser_package_no_nodejs(self):
        df = generate_dockerfile("3.12", ["robotframework", "requests"])
        assert "nodejs" not in df
        assert "rfbrowser" not in df

    def test_browser_package_with_underscore(self):
        df = generate_dockerfile("3.12", ["robotframework_browser"])
        assert "nodejs" in df
        assert "rfbrowser init" in df

    def test_has_browser_package_helper(self):
        assert _has_browser_package(["robotframework-browser"]) is True
        assert _has_browser_package(["robotframework-browser==18.0.0"]) is True
        assert _has_browser_package(["robotframework_browser>=17.0"]) is True
        assert _has_browser_package(["robotframework"]) is False
        assert _has_browser_package([]) is False
