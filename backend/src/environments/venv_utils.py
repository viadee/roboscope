"""Cross-platform venv path utilities + uv command builders."""

import logging
import os
import re
import shutil
import sys
from pathlib import Path

from src.config import settings

logger = logging.getLogger("roboscope.environments.venv_utils")

# Python versions known to work well with uv and the RF ecosystem
KNOWN_STABLE_VERSIONS = {"3.9", "3.10", "3.11", "3.12", "3.13"}
# Versions that exist but may have limited package availability
KNOWN_PRERELEASE_VERSIONS = {"3.14"}

_VERSION_RE = re.compile(r"^3\.(\d{1,2})(\.\d+)?$")


class PythonVersionError(ValueError):
    """Raised when a Python version string is invalid."""


class PythonVersionWarning:
    """Warning info about a Python version choice."""

    def __init__(self, version: str, message: str):
        self.version = version
        self.message = message


def validate_python_version(version: str) -> str:
    """Validate and normalize a Python version string.

    Accepts formats like "3.12", "3.12.0", "3.14".
    Returns the normalized major.minor form (e.g. "3.12").
    Raises PythonVersionError for invalid formats.
    """
    version = version.strip()
    match = _VERSION_RE.match(version)
    if not match:
        raise PythonVersionError(
            f"Invalid Python version '{version}'. Expected format: 3.X or 3.X.Y (e.g. 3.12, 3.13.1)"
        )
    minor = int(match.group(1))
    if minor < 9:
        raise PythonVersionError(
            f"Python 3.{minor} is not supported. Minimum supported version is 3.9."
        )
    # Return normalized major.minor
    return f"3.{minor}"


def check_python_version_compatibility(version: str) -> PythonVersionWarning | None:
    """Check if a Python version may have compatibility issues.

    Returns a warning object if there are potential issues, None otherwise.
    """
    normalized = validate_python_version(version)
    if normalized in KNOWN_PRERELEASE_VERSIONS:
        return PythonVersionWarning(
            normalized,
            f"Python {normalized} is very new and many packages (including some Robot Framework "
            f"libraries) may not have pre-built wheels available yet. Package installations may "
            f"fail or require compilation. Consider using Python 3.12 or 3.13 for best compatibility.",
        )
    if normalized not in KNOWN_STABLE_VERSIONS and normalized not in KNOWN_PRERELEASE_VERSIONS:
        return PythonVersionWarning(
            normalized,
            f"Python {normalized} is not a recognized version. If this is a future release, "
            f"package availability may be limited.",
        )
    return None


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
    """Build command to create a venv with uv.

    If python_version is provided, it is validated and normalized.
    """
    uv = get_uv_path()
    cmd = [uv, "venv", str(venv_path)]
    if python_version:
        normalized = validate_python_version(python_version)
        cmd += ["--python", normalized]
    return cmd


def pip_install_cmd(
    venv_path: str,
    *packages: str,
    index_url: str | None = None,
    extra_index_url: str | None = None,
) -> list[str]:
    """Build uv pip install command targeting a venv.

    Args:
        venv_path: Path to the virtual environment.
        packages: Package specifiers to install.
        index_url: Custom primary PyPI index URL (replaces default).
        extra_index_url: Additional index URL to search (e.g. private registry).
    """
    uv = get_uv_path()
    cmd = [uv, "pip", "install", "--python", get_python_path(venv_path)]
    if index_url:
        cmd += ["--index-url", index_url]
    if extra_index_url:
        cmd += ["--extra-index-url", extra_index_url]
    cmd += list(packages)
    return cmd


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


def rfbrowser_init_cmd(venv_path: str) -> list[str]:
    """Build command to run 'rfbrowser init' from a venv."""
    bin_dir = Path(get_venv_bin_dir(venv_path))
    if sys.platform == "win32":
        rfbrowser = str(bin_dir / "rfbrowser.exe")
    else:
        rfbrowser = str(bin_dir / "rfbrowser")
    return [rfbrowser, "init"]
