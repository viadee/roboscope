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

    def test_whitespace_only_index_url_ignored(self):
        """Whitespace-only registry URLs must not be passed to uv."""
        with (
            patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"),
            patch.object(venv_utils.sys, "platform", "linux"),
        ):
            cmd = venv_utils.pip_install_cmd(
                "/my/venv", "requests", index_url="   ", extra_index_url="\t"
            )
        assert cmd == [
            "/usr/bin/uv", "pip", "install",
            "--python", "/my/venv/bin/python",
            "requests",
        ]

    def test_whitespace_trimmed_from_index_url(self):
        """Leading/trailing whitespace is stripped from registry URLs."""
        with (
            patch.object(venv_utils, "get_uv_path", return_value="/usr/bin/uv"),
            patch.object(venv_utils.sys, "platform", "linux"),
        ):
            cmd = venv_utils.pip_install_cmd(
                "/my/venv", "requests",
                index_url="  https://my-registry.example.com/simple/  ",
                extra_index_url="  https://extra.example.com/simple/  ",
            )
        assert cmd == [
            "/usr/bin/uv", "pip", "install",
            "--python", "/my/venv/bin/python",
            "--index-url", "https://my-registry.example.com/simple/",
            "--extra-index-url", "https://extra.example.com/simple/",
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



class TestMaskUrlCredentials:
    def test_masks_password(self):
        url = "https://user:secret@registry.example.com/simple/"
        assert venv_utils.mask_url_credentials(url) == "https://user:***@registry.example.com/simple/"

    def test_masks_token_without_username(self):
        url = "https://:mytoken@registry.example.com/simple/"
        result = venv_utils.mask_url_credentials(url)
        assert "mytoken" not in result
        assert "***" in result

    def test_no_credentials_unchanged(self):
        url = "https://registry.example.com/simple/"
        assert venv_utils.mask_url_credentials(url) == url

    def test_none_returns_none(self):
        assert venv_utils.mask_url_credentials(None) is None

    def test_preserves_port(self):
        url = "https://user:pass@registry.example.com:8080/simple/"
        result = venv_utils.mask_url_credentials(url)
        assert "pass" not in result
        assert "8080" in result
        assert "user:***" in result


class TestSanitizeTextCredentials:
    def test_redacts_embedded_url_password(self):
        text = "Error: could not connect to https://user:secret@registry.example.com/simple/"
        result = venv_utils.sanitize_text_credentials(text)
        assert "secret" not in result
        assert "https://user:***@registry.example.com/simple/" in result

    def test_no_credentials_unchanged(self):
        text = "Error: could not connect to https://registry.example.com/simple/"
        assert venv_utils.sanitize_text_credentials(text) == text

    def test_multiple_urls_all_redacted(self):
        text = (
            "https://user1:pass1@host1.example.com/simple/ "
            "and https://user2:pass2@host2.example.com/simple/"
        )
        result = venv_utils.sanitize_text_credentials(text)
        assert "pass1" not in result
        assert "pass2" not in result
        assert "user1:***" in result
        assert "user2:***" in result
