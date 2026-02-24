"""Unit tests for cross-platform venv utilities."""

from unittest.mock import patch

import pytest

from src.environments import venv_utils


class TestGetPythonPath:
    def test_unix(self):
        with patch.object(venv_utils.sys, "platform", "linux"):
            assert venv_utils.get_python_path("/fake/venv") == "/fake/venv/bin/python"

    def test_windows(self):
        with patch.object(venv_utils.sys, "platform", "win32"):
            result = venv_utils.get_python_path("/fake/venv")
            # Path separator may vary, check the components
            assert result.endswith("python.exe")
            assert "Scripts" in result


class TestGetVenvBinDir:
    def test_unix(self):
        with patch.object(venv_utils.sys, "platform", "linux"):
            assert venv_utils.get_venv_bin_dir("/fake/venv") == "/fake/venv/bin"

    def test_windows(self):
        with patch.object(venv_utils.sys, "platform", "win32"):
            result = venv_utils.get_venv_bin_dir("/fake/venv")
            assert "Scripts" in result


class TestCreateVenvCmd:
    def test_basic(self):
        with patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"):
            cmd = venv_utils.create_venv_cmd("/my/venv")
        assert cmd == ["/usr/bin/uv", "venv", "/my/venv"]

    def test_with_python_version(self):
        with patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"):
            cmd = venv_utils.create_venv_cmd("/my/venv", python_version="3.11")
        assert cmd == ["/usr/bin/uv", "venv", "/my/venv", "--python", "3.11"]


class TestPipInstallCmd:
    def test_single_package(self):
        with (
            patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"),
            patch.object(venv_utils.sys, "platform", "linux"),
        ):
            cmd = venv_utils.pip_install_cmd("/my/venv", "requests")
        assert cmd == [
            "/usr/bin/uv", "pip", "install",
            "--python", "/my/venv/bin/python",
            "requests",
        ]

    def test_multiple_packages(self):
        with (
            patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"),
            patch.object(venv_utils.sys, "platform", "linux"),
        ):
            cmd = venv_utils.pip_install_cmd("/my/venv", "requests", "flask")
        assert cmd == [
            "/usr/bin/uv", "pip", "install",
            "--python", "/my/venv/bin/python",
            "requests", "flask",
        ]


class TestPipUninstallCmd:
    def test_basic(self):
        with (
            patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"),
            patch.object(venv_utils.sys, "platform", "linux"),
        ):
            cmd = venv_utils.pip_uninstall_cmd("/my/venv", "requests")
        assert cmd == [
            "/usr/bin/uv", "pip", "uninstall",
            "--python", "/my/venv/bin/python",
            "requests",
        ]


class TestPipShowCmd:
    def test_basic(self):
        with (
            patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"),
            patch.object(venv_utils.sys, "platform", "linux"),
        ):
            cmd = venv_utils.pip_show_cmd("/my/venv", "requests")
        assert cmd == [
            "/usr/bin/uv", "pip", "show",
            "--python", "/my/venv/bin/python",
            "requests",
        ]


class TestPipListCmd:
    def test_basic(self):
        with (
            patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"),
            patch.object(venv_utils.sys, "platform", "linux"),
        ):
            cmd = venv_utils.pip_list_cmd("/my/venv")
        assert cmd == [
            "/usr/bin/uv", "pip", "list",
            "--python", "/my/venv/bin/python",
            "--format=json",
        ]


class TestGetUvPath:
    def test_from_settings(self):
        with patch.object(venv_utils.settings, "UV_PATH", "/custom/uv"):
            assert venv_utils.get_uv_path() == "/custom/uv"

    def test_from_which(self):
        with (
            patch.object(venv_utils.settings, "UV_PATH", ""),
            patch.object(venv_utils.shutil, "which", return_value="/usr/local/bin/uv"),
        ):
            assert venv_utils.get_uv_path() == "/usr/local/bin/uv"

    def test_not_found(self):
        with (
            patch.object(venv_utils.settings, "UV_PATH", ""),
            patch.object(venv_utils.shutil, "which", return_value=None),
        ):
            with pytest.raises(FileNotFoundError, match="uv not found"):
                venv_utils.get_uv_path()
