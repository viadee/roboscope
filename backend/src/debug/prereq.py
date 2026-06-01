"""DEBUG-4: detect and install RobotCode (the DAP server) into a project's venv.

The DEBUG-2/3 spawn path looks for ``<venv>/bin/robotcode`` and fails
loudly when it's missing. The router calls
:func:`check_robotcode_available` *before* spawning so the missing-prereq
case becomes a clean 424 + dialog instead of a generic 502.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import suppress
from pathlib import Path

from src.environments.venv_utils import pip_install_cmd

logger = logging.getLogger("roboscope.debug.prereq")

# The umbrella ``robotcode`` package alone gives us the CLI shell but
# *not* the ``debug-launch`` subcommand — that's registered as a click
# plugin by ``robotcode-debugger``. Installing ``robotcode[debugger]``
# pulls both in (umbrella + debugger extra) and is the correct entry
# for our use case. Without the extra, RobotCode CLI exits with
# ``Error: No such command 'debug-launch'.``
ROBOTCODE_PACKAGE = "robotcode[debugger]"
INSTALL_TIMEOUT_SECONDS = 300
LOG_TAIL_LINES = 50


class PrereqInstallFailed(RuntimeError):  # noqa: N818  # established in routers + tests
    """Raised when the RobotCode install subprocess fails or times out."""


def _site_packages(venv_path: Path) -> Path | None:
    """Locate the venv's site-packages directory (cross-platform)."""
    if sys.platform == "win32":
        sp = venv_path / "Lib" / "site-packages"
        return sp if sp.is_dir() else None
    matches = list(venv_path.glob("lib/python*/site-packages"))
    return matches[0] if matches else None


def check_robotcode_available(venv_path: str | None) -> bool:
    """True iff the ``robotcode`` CLI **and** its debugger plugin are present.

    Both pieces are required to spawn ``robotcode debug-launch``: the
    umbrella registers the CLI binary, the ``robotcode-debugger`` package
    registers the actual subcommand. Checking only the binary leaves us
    open to the partial-install state where ``robotcode`` was installed
    without the debugger extra and the spawn explodes with
    ``No such command 'debug-launch'`` at runtime.
    """
    if not venv_path:
        return False
    venv = Path(venv_path)
    if not venv.exists():
        return False
    if sys.platform == "win32":
        binary = venv / "Scripts" / "robotcode.exe"
    else:
        binary = venv / "bin" / "robotcode"
    if not binary.is_file():
        return False
    sp = _site_packages(venv)
    if sp is None:
        return False
    return (sp / "robotcode" / "debugger").is_dir()


async def install_robotcode(venv_path: str) -> str:
    """Install ``robotcode`` into the given venv via ``uv pip install``.

    Returns the tail of stdout/stderr (interleaved). Raises
    :class:`PrereqInstallFailed` on non-zero exit, timeout, or missing
    uv binary. The router translates the exception into a 500 with the
    tail in ``detail``.
    """
    try:
        cmd = pip_install_cmd(venv_path, ROBOTCODE_PACKAGE)
    except FileNotFoundError as e:
        raise PrereqInstallFailed(f"uv not available: {e}") from e

    logger.info("Installing %s into %s", ROBOTCODE_PACKAGE, venv_path)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError as e:
        raise PrereqInstallFailed(f"uv not invokable: {e}") from e

    try:
        stdout_bytes, _ = await asyncio.wait_for(
            proc.communicate(), timeout=INSTALL_TIMEOUT_SECONDS,
        )
    except TimeoutError as e:
        with suppress(ProcessLookupError):
            proc.kill()
        with suppress(Exception):
            await proc.wait()
        raise PrereqInstallFailed(
            f"robotcode install timed out after {INSTALL_TIMEOUT_SECONDS}s"
        ) from e

    output = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
    tail = "\n".join(output.splitlines()[-LOG_TAIL_LINES:])
    if proc.returncode != 0:
        raise PrereqInstallFailed(
            f"uv pip install exited with code {proc.returncode}:\n{tail}"
        )
    return tail
