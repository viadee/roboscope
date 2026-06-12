"""Cross-platform venv path utilities + uv command builders."""

import logging
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
    find_links: str | None = None,
) -> list[str]:
    """Build uv pip install command targeting a venv.

    Args:
        venv_path: Path to the virtual environment.
        packages: Package specifiers to install.
        index_url: Custom primary PyPI index URL (replaces default).
        extra_index_url: Additional index URL to search (e.g. private registry).
        find_links: Additional local directory to resolve wheels from. Used
            for shipped-with-RoboScope packages that aren't on PyPI (the
            vendored heal library) in offline / online distributions — uv
            searches this dir AND the index, so deps still resolve from the
            bundled wheels offline while online installs fall through to PyPI.
    """
    uv = get_uv_path()
    cmd = [uv, "pip", "install", "--python", get_python_path(venv_path)]
    if index_url:
        cmd += ["--index-url", index_url]
    if extra_index_url:
        cmd += ["--extra-index-url", extra_index_url]
    if find_links:
        cmd += ["--find-links", find_links]
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


def check_rfbrowser_initialized(venv_path: str) -> bool:
    """Check if rfbrowser init has been run successfully.

    Verifies that the Browser wrapper's node_modules directory exists,
    which is created by 'rfbrowser init'.
    """
    venv = Path(venv_path)
    # Unix: lib/python3.X/site-packages/Browser/wrapper/node_modules
    # Windows: Lib/site-packages/Browser/wrapper/node_modules
    if sys.platform == "win32":
        wrapper = venv / "Lib" / "site-packages" / "Browser" / "wrapper" / "node_modules"
        return wrapper.is_dir()
    # Unix — python version in path varies, use glob
    matches = list(venv.glob("lib/python*/site-packages/Browser/wrapper/node_modules"))
    return len(matches) > 0


def browser_wrapper_node_modules(venv_path: str) -> Path | None:
    """Return the Browser wrapper's `node_modules` dir if present, else None.

    The Robot Framework Browser library (and its `-batteries` variant)
    keeps its Node-side gRPC wrapper + `playwright-core` under
    `…/site-packages/Browser/wrapper/node_modules`. `-batteries` ships
    this tree inside the wheel; the standard variant lays it down via
    `rfbrowser init` (npm). Either way the browser binaries live below
    `playwright-core/.local-browsers/`.
    """
    venv = Path(venv_path)
    if sys.platform == "win32":
        candidate = (
            venv / "Lib" / "site-packages" / "Browser" / "wrapper" / "node_modules"
        )
        return candidate if candidate.is_dir() else None
    matches = list(
        venv.glob("lib/python*/site-packages/Browser/wrapper/node_modules")
    )
    return matches[0] if matches else None


def browser_local_browsers_dir(venv_path: str) -> Path | None:
    """Return the `playwright-core/.local-browsers` target dir for this
    venv's Browser library, or None when `playwright-core` isn't present
    (i.e. node_modules wasn't laid down yet — standard variant without a
    completed `rfbrowser init`). The `.local-browsers` dir itself need not
    exist yet; the caller creates it when copying bundled browsers in.
    """
    node_modules = browser_wrapper_node_modules(venv_path)
    if node_modules is None:
        return None
    playwright_core = node_modules / "playwright-core"
    if not playwright_core.is_dir():
        return None
    return playwright_core / ".local-browsers"


def bundled_browsers_present(venv_path: str) -> bool:
    """True when the Browser library's `.local-browsers` dir holds at least
    one actual browser build (a `chromium*`/`chrome*`/`ffmpeg*` subdir).

    Stricter than `check_rfbrowser_initialized` (which only checks that
    `node_modules` exists): the `-batteries` wheel creates `node_modules`
    but NOT the browser binaries, so node_modules-presence alone does not
    mean Chromium can launch.
    """
    target = browser_local_browsers_dir(venv_path)
    if target is None or not target.is_dir():
        return False
    return any(
        child.is_dir() and child.name[0] != "."
        for child in target.iterdir()
    )


def _remove_path(p: Path) -> None:
    """Delete a file, directory, or (possibly broken) symlink at `p`."""
    if p.is_symlink() or p.is_file():
        p.unlink(missing_ok=True)
    elif p.is_dir():
        shutil.rmtree(p, ignore_errors=True)


def _link_browser_dir(source: Path, target: Path) -> bool:
    """Make `target` a directory link to `source` so every env SHARES one
    on-disk browser copy instead of duplicating ~700 MB per venv.

    Uses a junction on Windows (no admin needed, unlike symlinks) and a
    directory symlink elsewhere. Returns False when the OS / filesystem
    refuses the link, so the caller can fall back to a plain copy.
    """
    import os

    try:
        if sys.platform == "win32":
            import subprocess

            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                capture_output=True, text=True,
            )
            return result.returncode == 0 and target.is_dir()
        os.symlink(source, target, target_is_directory=True)
        return target.is_dir()
    except OSError:
        return False


def lay_down_bundled_browsers(venv_path: str, pack_dir: str) -> bool:
    """Point this venv's `playwright-core/.local-browsers` at the bundled
    browser-pack so the Browser library can launch Chromium WITHOUT a
    network `rfbrowser init` (the offline-distribution path).

    `pack_dir` is the `browser-pack/` directory whose `.local-browsers/`
    subtree was harvested at build time from a real `rfbrowser init`. To
    avoid duplicating ~700 MB into every environment, the venv's
    `.local-browsers` is created as a LINK (junction on Windows, symlink
    elsewhere) to the single shared pack; a plain copy is the fallback when
    the filesystem won't allow a link. Variant-safe either way: only the
    browser binaries are shared — the gRPC server binary (which differs
    between the standard and `-batteries` variants, and lives elsewhere
    under node_modules) is never touched.

    Returns True when browsers ended up in place (already present, linked,
    or copied), False when there's nothing to lay down or the target
    wrapper (`playwright-core`) is missing.
    """
    pack = Path(pack_dir)
    source = (pack / ".local-browsers").resolve()
    if not source.is_dir():
        return False

    target = browser_local_browsers_dir(venv_path)
    if target is None:
        # playwright-core not laid down (standard variant, no node_modules):
        # nothing to link into — caller falls back to network rfbrowser init.
        return False

    if bundled_browsers_present(venv_path):
        return True  # already linked/copied (idempotent re-run)

    # Clear a stale or broken target (empty dir, dangling symlink) first.
    if target.is_symlink() or target.exists():
        _remove_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    if not _link_browser_dir(source, target):
        # Filesystem won't link (e.g. cross-device, restricted Windows) —
        # fall back to a full copy so offline Browser tests still work.
        shutil.copytree(source, target, symlinks=True)

    return bundled_browsers_present(venv_path)
