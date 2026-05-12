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


def _make_env(db_session, name="test-env", venv_path="/tmp/test-venv", create_dir=False) -> Environment:
    """Helper to create an Environment row."""
    if create_dir:
        import os
        os.makedirs(venv_path, exist_ok=True)
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
    def test_creates_venv_with_uv(self, mock_run, _mock_broadcast, db_session, tmp_path):
        env = _make_env(db_session, venv_path=str(tmp_path / "new-venv"))
        db_session.commit()

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("src.environments.tasks.get_sync_session") as mock_gs:
            mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_gs.return_value.__exit__ = MagicMock(return_value=False)
            result = create_venv(env.id)

        assert result["status"] == "success"
        # Three subprocess calls:
        #   1) `uv venv <path>` — create the empty venv
        #   2) `uv pip install robotframework` — RF core
        #   3) `uv pip install <vendor>/robotframework-roboscopeheal`
        #      — Story HEAL-VENDORED phase-2 auto-install
        assert mock_run.call_count == 3
        venv_cmd = mock_run.call_args_list[0][0][0]
        assert "venv" in venv_cmd
        install_cmd = mock_run.call_args_list[1][0][0]
        assert "install" in install_cmd
        assert "robotframework" in install_cmd
        heal_cmd = mock_run.call_args_list[2][0][0]
        assert any(
            "vendor/robotframework-roboscopeheal" in str(arg)
            for arg in heal_cmd
        ), f"heal vendor path missing from third subprocess call: {heal_cmd!r}"

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
        env = _make_env(db_session, create_dir=True)
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
        env = _make_env(db_session, create_dir=True)
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
        env = _make_env(db_session, create_dir=True)
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

    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_shipped_no_version_installs_from_vendor_path(
        self, mock_run, mock_broadcast, db_session,
    ):
        """User clicks "install" on RoboScopeHeal in the package UI
        (no version specified). The install path resolves the name
        to the on-disk vendored source tree rather than going to
        PyPI — that's the deterministic "ship with RoboScope" path
        documented in CLAUDE.md."""
        env = _make_env(db_session, create_dir=True)
        _make_package(db_session, env.id, "robotframework-roboscopeheal")
        db_session.commit()

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(
                returncode=0,
                stdout="Name: robotframework-roboscopeheal\nVersion: 0.2.1\n",
                stderr="",
            ),
        ]

        with patch("src.environments.tasks.get_sync_session") as mock_gs:
            mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_gs.return_value.__exit__ = MagicMock(return_value=False)
            result = install_package(env.id, "robotframework-roboscopeheal")

        assert result["status"] == "success"
        install_cmd = mock_run.call_args_list[0][0][0]
        # The argv positional should be the absolute vendor path,
        # NOT the bare package name (which would trigger PyPI).
        assert any(
            "vendor/robotframework-roboscopeheal" in str(arg)
            for arg in install_cmd
        ), f"vendor path not in pip argv: {install_cmd!r}"
        assert "robotframework-roboscopeheal" not in install_cmd, (
            "bare package name leaked into argv — would resolve to PyPI"
        )

    @patch("src.environments.tasks._broadcast_package_status")
    @patch("subprocess.run")
    def test_shipped_with_version_goes_to_pypi(
        self, mock_run, mock_broadcast, db_session,
    ):
        """An EXPLICIT version request bypasses the vendor and goes
        to PyPI — that's the "I want to upgrade past what RoboScope
        ships" path. Only works once PyPI carries the package; here
        we just pin that the argv carries the `name==version` spec
        not the vendor path."""
        env = _make_env(db_session, create_dir=True)
        _make_package(db_session, env.id, "robotframework-roboscopeheal")
        db_session.commit()

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(
                returncode=0,
                stdout="Name: robotframework-roboscopeheal\nVersion: 0.4.0\n",
                stderr="",
            ),
        ]

        with patch("src.environments.tasks.get_sync_session") as mock_gs:
            mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_gs.return_value.__exit__ = MagicMock(return_value=False)
            result = install_package(
                env.id, "robotframework-roboscopeheal", version="0.4.0",
            )

        assert result["status"] == "success"
        install_cmd = mock_run.call_args_list[0][0][0]
        # PyPI-style pinned spec — no vendor path leakage.
        assert "robotframework-roboscopeheal==0.4.0" in install_cmd
        assert not any(
            "vendor/robotframework-roboscopeheal" in str(arg)
            for arg in install_cmd
        ), "vendor path leaked into versioned install argv"


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
