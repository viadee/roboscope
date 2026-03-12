"""Unit tests for cross-platform venv utilities."""

from unittest.mock import patch

import pytest

from src.environments import venv_utils
from src.environments.venv_utils import (
    PythonVersionError,
    check_python_version_compatibility,
    validate_python_version,
)


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


    def test_with_index_url(self):
        with (
            patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"),
            patch.object(venv_utils.sys, "platform", "linux"),
        ):
            cmd = venv_utils.pip_install_cmd(
                "/my/venv", "requests", index_url="https://my-registry.example.com/simple/"
            )
        assert cmd == [
            "/usr/bin/uv", "pip", "install",
            "--python", "/my/venv/bin/python",
            "--index-url", "https://my-registry.example.com/simple/",
            "requests",
        ]

    def test_with_extra_index_url(self):
        with (
            patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"),
            patch.object(venv_utils.sys, "platform", "linux"),
        ):
            cmd = venv_utils.pip_install_cmd(
                "/my/venv", "requests", extra_index_url="https://extra.example.com/simple/"
            )
        assert cmd == [
            "/usr/bin/uv", "pip", "install",
            "--python", "/my/venv/bin/python",
            "--extra-index-url", "https://extra.example.com/simple/",
            "requests",
        ]

    def test_with_both_index_urls(self):
        with (
            patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"),
            patch.object(venv_utils.sys, "platform", "linux"),
        ):
            cmd = venv_utils.pip_install_cmd(
                "/my/venv", "requests",
                index_url="https://main.example.com/simple/",
                extra_index_url="https://extra.example.com/simple/",
            )
        assert cmd == [
            "/usr/bin/uv", "pip", "install",
            "--python", "/my/venv/bin/python",
            "--index-url", "https://main.example.com/simple/",
            "--extra-index-url", "https://extra.example.com/simple/",
            "requests",
        ]

    def test_none_index_urls_ignored(self):
        with (
            patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"),
            patch.object(venv_utils.sys, "platform", "linux"),
        ):
            cmd = venv_utils.pip_install_cmd(
                "/my/venv", "requests", index_url=None, extra_index_url=None
            )
        assert cmd == [
            "/usr/bin/uv", "pip", "install",
            "--python", "/my/venv/bin/python",
            "requests",
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


class TestValidatePythonVersion:
    def test_valid_major_minor(self):
        assert validate_python_version("3.12") == "3.12"

    def test_valid_major_minor_patch(self):
        assert validate_python_version("3.12.0") == "3.12"
        assert validate_python_version("3.13.1") == "3.13"

    def test_normalizes_to_major_minor(self):
        assert validate_python_version("3.14.0") == "3.14"

    def test_strips_whitespace(self):
        assert validate_python_version("  3.12  ") == "3.12"

    def test_invalid_format_no_dot(self):
        with pytest.raises(PythonVersionError, match="Invalid Python version"):
            validate_python_version("312")

    def test_invalid_format_python2(self):
        with pytest.raises(PythonVersionError, match="Invalid Python version"):
            validate_python_version("2.7")

    def test_too_old_version(self):
        with pytest.raises(PythonVersionError, match="not supported"):
            validate_python_version("3.8")

    def test_invalid_empty_string(self):
        with pytest.raises(PythonVersionError, match="Invalid Python version"):
            validate_python_version("")

    def test_invalid_non_numeric(self):
        with pytest.raises(PythonVersionError, match="Invalid Python version"):
            validate_python_version("latest")

    def test_valid_3_9(self):
        assert validate_python_version("3.9") == "3.9"

    def test_valid_3_14(self):
        assert validate_python_version("3.14") == "3.14"


class TestCheckRfbrowserInitialized:
    def test_unix_initialized(self, tmp_path):
        """Returns True when node_modules exists under Browser/wrapper."""
        venv = tmp_path / "venv"
        node_modules = venv / "lib" / "python3.12" / "site-packages" / "Browser" / "wrapper" / "node_modules"
        node_modules.mkdir(parents=True)
        with patch.object(venv_utils.sys, "platform", "linux"):
            assert venv_utils.check_rfbrowser_initialized(str(venv)) is True

    def test_unix_not_initialized(self, tmp_path):
        """Returns False when node_modules does not exist."""
        venv = tmp_path / "venv"
        venv.mkdir()
        with patch.object(venv_utils.sys, "platform", "linux"):
            assert venv_utils.check_rfbrowser_initialized(str(venv)) is False

    def test_windows_initialized(self, tmp_path):
        """Returns True on Windows path layout."""
        venv = tmp_path / "venv"
        node_modules = venv / "Lib" / "site-packages" / "Browser" / "wrapper" / "node_modules"
        node_modules.mkdir(parents=True)
        with patch.object(venv_utils.sys, "platform", "win32"):
            assert venv_utils.check_rfbrowser_initialized(str(venv)) is True

    def test_windows_not_initialized(self, tmp_path):
        """Returns False on Windows when node_modules missing."""
        venv = tmp_path / "venv"
        venv.mkdir()
        with patch.object(venv_utils.sys, "platform", "win32"):
            assert venv_utils.check_rfbrowser_initialized(str(venv)) is False

    def test_unix_different_python_version(self, tmp_path):
        """Glob matches any python3.X version."""
        venv = tmp_path / "venv"
        node_modules = venv / "lib" / "python3.13" / "site-packages" / "Browser" / "wrapper" / "node_modules"
        node_modules.mkdir(parents=True)
        with patch.object(venv_utils.sys, "platform", "linux"):
            assert venv_utils.check_rfbrowser_initialized(str(venv)) is True


class TestCheckPythonVersionCompatibility:
    def test_stable_version_no_warning(self):
        assert check_python_version_compatibility("3.12") is None
        assert check_python_version_compatibility("3.13") is None

    def test_prerelease_version_warns(self):
        warning = check_python_version_compatibility("3.14")
        assert warning is not None
        assert "very new" in warning.message
        assert "3.12 or 3.13" in warning.message

    def test_unknown_future_version_warns(self):
        warning = check_python_version_compatibility("3.20")
        assert warning is not None
        assert "not a recognized version" in warning.message

    def test_create_venv_cmd_validates_version(self):
        with patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"):
            with pytest.raises(PythonVersionError):
                venv_utils.create_venv_cmd("/my/venv", python_version="3.8")

    def test_create_venv_cmd_normalizes_version(self):
        with patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"):
            cmd = venv_utils.create_venv_cmd("/my/venv", python_version="3.12.5")
        assert cmd == ["/usr/bin/uv", "venv", "/my/venv", "--python", "3.12"]
