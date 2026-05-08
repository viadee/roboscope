"""DEBUG-4 unit tests — RobotCode prereq detection + install plumbing."""

from __future__ import annotations

import asyncio
import sys

import pytest

from src.debug.prereq import (
    PrereqInstallFailed,
    check_robotcode_available,
    install_robotcode,
)


class TestCheckRobotcodeAvailable:
    def test_returns_false_for_none_or_empty(self):
        assert check_robotcode_available(None) is False
        assert check_robotcode_available("") is False

    def test_returns_false_for_missing_path(self, tmp_path):
        assert check_robotcode_available(str(tmp_path / "nonexistent")) is False

    def test_returns_false_for_venv_without_binary(self, tmp_path):
        venv = tmp_path / "venv"
        bin_dir = venv / ("Scripts" if sys.platform == "win32" else "bin")
        bin_dir.mkdir(parents=True)
        # No `robotcode` binary written.
        assert check_robotcode_available(str(venv)) is False

    def test_returns_true_when_binary_present(self, tmp_path):
        venv = tmp_path / "venv"
        bin_dir = venv / ("Scripts" if sys.platform == "win32" else "bin")
        bin_dir.mkdir(parents=True)
        binary_name = "robotcode.exe" if sys.platform == "win32" else "robotcode"
        (bin_dir / binary_name).write_text("# placeholder", encoding="utf-8")
        assert check_robotcode_available(str(venv)) is True


class TestInstallRobotcode:
    def test_happy_path(self, tmp_path, monkeypatch):
        venv = tmp_path / "venv"
        venv.mkdir()

        class FakeProc:
            returncode = 0

            async def communicate(self):
                return (b"Resolved 1 package\nInstalled robotcode 1.2.3\n", b"")

        async def fake_create(*args, **kwargs):
            return FakeProc()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
        monkeypatch.setattr(
            "src.debug.prereq.pip_install_cmd",
            lambda venv_path, *pkgs: ["uv", "pip", "install", "--", *pkgs],
        )

        log_tail = asyncio.run(install_robotcode(str(venv)))
        assert "Installed robotcode 1.2.3" in log_tail

    def test_non_zero_exit_raises(self, tmp_path, monkeypatch):
        venv = tmp_path / "venv"
        venv.mkdir()

        class FakeProc:
            returncode = 1

            async def communicate(self):
                return (b"ERROR: Could not find robotcode\n", b"")

        async def fake_create(*args, **kwargs):
            return FakeProc()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
        monkeypatch.setattr(
            "src.debug.prereq.pip_install_cmd",
            lambda venv_path, *pkgs: ["uv", "pip", "install", *pkgs],
        )

        with pytest.raises(PrereqInstallFailed) as exc_info:
            asyncio.run(install_robotcode(str(venv)))
        assert "code 1" in str(exc_info.value)
        assert "ERROR: Could not find robotcode" in str(exc_info.value)

    def test_uv_not_found_raises_clean(self, tmp_path, monkeypatch):
        venv = tmp_path / "venv"
        venv.mkdir()

        def raise_fnf(*args, **kwargs):
            raise FileNotFoundError("uv not found")

        monkeypatch.setattr(
            "src.debug.prereq.pip_install_cmd", raise_fnf
        )

        with pytest.raises(PrereqInstallFailed, match="uv not available"):
            asyncio.run(install_robotcode(str(venv)))

    def test_timeout_raises(self, tmp_path, monkeypatch):
        venv = tmp_path / "venv"
        venv.mkdir()

        class HangingProc:
            returncode = None
            killed = False

            async def communicate(self):
                # Block forever — wait_for should fire its timeout.
                await asyncio.sleep(3600)
                return (b"", b"")

            def kill(self):
                self.killed = True

            async def wait(self):
                return 0

        async def fake_create(*args, **kwargs):
            return HangingProc()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
        monkeypatch.setattr(
            "src.debug.prereq.pip_install_cmd",
            lambda venv_path, *pkgs: ["uv", "pip", "install", *pkgs],
        )
        # Slash the timeout so the test is fast.
        monkeypatch.setattr("src.debug.prereq.INSTALL_TIMEOUT_SECONDS", 0.05)

        with pytest.raises(PrereqInstallFailed, match="timed out"):
            asyncio.run(install_robotcode(str(venv)))
