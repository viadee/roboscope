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

ROBOTCODE_PACKAGE = "robotcode"
INSTALL_TIMEOUT_SECONDS = 300
LOG_TAIL_LINES = 50


class PrereqInstallFailed(RuntimeError):  # noqa: N818  # established in routers + tests
    """Raised when the RobotCode install subprocess fails or times out."""


def check_robotcode_available(venv_path: str | None) -> bool:
    """True iff the ``robotcode`` CLI binary exists inside the given venv."""
    if not venv_path:
        return False
    venv = Path(venv_path)
    if not venv.exists():
        return False
    if sys.platform == "win32":
        binary = venv / "Scripts" / "robotcode.exe"
    else:
        binary = venv / "bin" / "robotcode"
    return binary.is_file()


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
