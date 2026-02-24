"""Cross-platform venv path utilities + uv command builders."""

import os
import shutil
import sys
from pathlib import Path

from src.config import settings


def get_uv_path() -> str:
    """Return path to uv binary. Checks settings.UV_PATH first, then PATH."""
    if settings.UV_PATH:
        return settings.UV_PATH
    uv = shutil.which("uv")
    if uv:
        return uv
    raise FileNotFoundError(
        "uv not found. Install via: curl -LsSf https://astral.sh/uv/install.sh | sh"
    )


def get_python_path(venv_path: str) -> str:
    """Cross-platform Python path inside a venv."""
    venv = Path(venv_path)
    if sys.platform == "win32":
        return str(venv / "Scripts" / "python.exe")
    return str(venv / "bin" / "python")


def get_venv_bin_dir(venv_path: str) -> str:
    """Cross-platform bin/Scripts directory."""
    if sys.platform == "win32":
        return str(Path(venv_path) / "Scripts")
    return str(Path(venv_path) / "bin")


def create_venv_cmd(venv_path: str, python_version: str | None = None) -> list[str]:
    """Build command to create a venv with uv."""
    uv = get_uv_path()
    cmd = [uv, "venv", str(venv_path)]
    if python_version:
        cmd += ["--python", python_version]
    return cmd


def pip_install_cmd(venv_path: str, *packages: str) -> list[str]:
    """Build uv pip install command targeting a venv."""
    uv = get_uv_path()
    return [uv, "pip", "install", "--python", get_python_path(venv_path), *packages]


def pip_uninstall_cmd(venv_path: str, *packages: str) -> list[str]:
    """Build uv pip uninstall command targeting a venv."""
    uv = get_uv_path()
    return [uv, "pip", "uninstall", "--python", get_python_path(venv_path), *packages]


def pip_show_cmd(venv_path: str, package: str) -> list[str]:
    """Build uv pip show command targeting a venv."""
    uv = get_uv_path()
    return [uv, "pip", "show", "--python", get_python_path(venv_path), package]


def pip_list_cmd(venv_path: str) -> list[str]:
    """Build uv pip list command targeting a venv."""
    uv = get_uv_path()
    return [uv, "pip", "list", "--python", get_python_path(venv_path), "--format=json"]
