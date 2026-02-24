"""Unit tests for environment background tasks."""

import subprocess
from unittest.mock import MagicMock, patch

from sqlalchemy import select

from src.environments.models import Environment, EnvironmentPackage
from src.environments.tasks import (
    create_venv,
    install_package,
    uninstall_package,
    upgrade_package,
)


def _make_env(db_session, name="test-env", venv_path="/tmp/test-venv") -> Environment:
    """Helper to create an Environment row."""
    env = Environment(
        name=name,
        venv_path=venv_path,
        python_version="3.12",
        created_by=1,
    )
    db_session.add(env)
    db_session.flush()
    db_session.refresh(env)
    return env


def _make_package(db_session, env_id: int, name: str = "requests") -> EnvironmentPackage:
    """Helper to create an EnvironmentPackage row."""
    pkg = EnvironmentPackage(
        environment_id=env_id,
        package_name=name,
    )
    db_session.add(pkg)
    db_session.flush()
    db_session.refresh(pkg)
    return pkg


class TestCreateVenv:
    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_creates_venv_with_uv(self, mock_run, _mock_broadcast, db_session):
        env = _make_env(db_session)
        db_session.commit()

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("src.environments.tasks.get_sync_session") as mock_gs:
            mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_gs.return_value.__exit__ = MagicMock(return_value=False)
            result = create_venv(env.id)

        assert result["status"] == "success"
        # First call: uv venv, second call: uv pip install robotframework
        assert mock_run.call_count == 2
        venv_cmd = mock_run.call_args_list[0][0][0]
        assert "venv" in venv_cmd
        install_cmd = mock_run.call_args_list[1][0][0]
        assert "install" in install_cmd
        assert "robotframework" in install_cmd

    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_env_not_found(self, mock_run, _mock_broadcast, db_session):
        db_session.commit()
        with patch("src.environments.tasks.get_sync_session") as mock_gs:
            mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_gs.return_value.__exit__ = MagicMock(return_value=False)
            result = create_venv(9999)

        assert result["status"] == "error"
        mock_run.assert_not_called()


class TestInstallPackage:
    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_install_success(self, mock_run, mock_broadcast, db_session):
        env = _make_env(db_session)
        pkg = _make_package(db_session, env.id, "robotframework")
        db_session.commit()

        # pip install succeeds, pip show returns version
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # install
            MagicMock(returncode=0, stdout="Name: robotframework\nVersion: 7.0\n", stderr=""),  # show
        ]

        with patch("src.environments.tasks.get_sync_session") as mock_gs:
            mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_gs.return_value.__exit__ = MagicMock(return_value=False)
            result = install_package(env.id, "robotframework")

        assert result["status"] == "success"
        assert result["version"] == "7.0"
        install_cmd = mock_run.call_args_list[0][0][0]
        assert "install" in install_cmd
        assert "robotframework" in install_cmd

    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_install_with_version(self, mock_run, mock_broadcast, db_session):
        env = _make_env(db_session)
        _make_package(db_session, env.id, "requests")
        db_session.commit()

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="Name: requests\nVersion: 2.31.0\n", stderr=""),
        ]

        with patch("src.environments.tasks.get_sync_session") as mock_gs:
            mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_gs.return_value.__exit__ = MagicMock(return_value=False)
            result = install_package(env.id, "requests", version="2.31.0")

        assert result["status"] == "success"
        install_cmd = mock_run.call_args_list[0][0][0]
        assert "requests==2.31.0" in install_cmd

    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_install_failure(self, mock_run, mock_broadcast, db_session):
        env = _make_env(db_session)
        pkg = _make_package(db_session, env.id, "nonexistent-pkg")
        db_session.commit()

        mock_run.side_effect = subprocess.CalledProcessError(
            1, "uv", stderr="ERROR: No matching distribution"
        )

        with patch("src.environments.tasks.get_sync_session") as mock_gs:
            mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_gs.return_value.__exit__ = MagicMock(return_value=False)
            result = install_package(env.id, "nonexistent-pkg")

        assert result["status"] == "error"


class TestUpgradePackage:
    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_upgrade_success(self, mock_run, mock_broadcast, db_session):
        env = _make_env(db_session)
        _make_package(db_session, env.id, "requests")
        db_session.commit()

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="Name: requests\nVersion: 2.32.0\n", stderr=""),
        ]

        with patch("src.environments.tasks.get_sync_session") as mock_gs:
            mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_gs.return_value.__exit__ = MagicMock(return_value=False)
            result = upgrade_package(env.id, "requests")

        assert result["status"] == "success"
        install_cmd = mock_run.call_args_list[0][0][0]
        assert "--upgrade" in install_cmd
        assert "requests" in install_cmd


class TestUninstallPackage:
    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_uninstall_success(self, mock_run, _mock_broadcast, db_session):
        env = _make_env(db_session)
        db_session.commit()

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("src.environments.tasks.get_sync_session") as mock_gs:
            mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_gs.return_value.__exit__ = MagicMock(return_value=False)
            result = uninstall_package(env.id, "requests")

        assert result["status"] == "success"
        cmd = mock_run.call_args_list[0][0][0]
        assert "uninstall" in cmd
        assert "requests" in cmd
