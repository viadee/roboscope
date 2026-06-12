"""End-to-end proof for the offline Playwright browser-pack.

Unlike `test_offline_browser_pack.py` (which mocks subprocess + builds
fake `.local-browsers` trees), this exercises the REAL chain that the
original "browserType.launch: Executable doesn't exist" bug lived in:

    install robotframework-browser-batteries
      → harvest its browsers via a real `rfbrowser init`   (the "build" side)
      → wipe them, then lay the pack back down by COPY      (the offline path,
        through the real `_run_rfbrowser_init`, asserting NO network init runs)
      → run a tiny `New Browser` Robot test and assert PASS (the binaries
        actually launch)

Marked `integration` (deselected by the default `-m 'not integration'`):
it needs Node.js + network for the one-time harvest and takes a couple of
minutes. It skips cleanly when uv/Node/Chromium aren't available or the
Playwright CDN is unreachable — the point is that when it CAN run, only a
real browser launch can prove the harvested pack is functional.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.environments import tasks
from src.environments.venv_utils import (
    browser_local_browsers_dir,
    bundled_browsers_present,
    get_python_path,
    get_uv_path,
)

pytestmark = pytest.mark.integration


def _uv() -> str:
    try:
        return get_uv_path()
    except Exception:
        pytest.skip("uv not available")


def _require_node() -> None:
    if shutil.which("node") is None or shutil.which("npm") is None:
        pytest.skip("Node.js/npm not available — rfbrowser init can't harvest browsers")


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="venv layout assertions use the Unix wrapper path",
)
def test_pack_laydown_launches_real_browser(tmp_path: Path) -> None:
    _require_node()
    uv = _uv()

    venv = tmp_path / "venv"
    assert _run([uv, "venv", str(venv)]).returncode == 0, "venv create failed"
    py = get_python_path(str(venv))

    # 1. Install the batteries variant (ships the Node wrapper, no browsers).
    inst = _run([uv, "pip", "install", "--python", py, "robotframework-browser-batteries"])
    if inst.returncode != 0:
        pytest.skip(f"batteries install failed (offline build host?): {inst.stderr[-300:]}")

    # 2. Harvest browsers via a real rfbrowser init (the "build host" step).
    #    chromium only — matches what the build scripts ship (Firefox/WebKit
    #    would balloon the pack), and the smoke test below launches chromium.
    rfbrowser = venv / "bin" / "rfbrowser"
    init = _run([str(rfbrowser), "init", "chromium"], timeout=600)
    target = browser_local_browsers_dir(str(venv))
    if init.returncode != 0 or target is None or not bundled_browsers_present(str(venv)):
        pytest.skip(
            "rfbrowser init did not produce browsers (no network / CDN blocked): "
            f"{(init.stderr or init.stdout)[-300:]}"
        )

    # Copy them into a pack dir, then wipe the venv's copy so the venv is
    # back to the "batteries installed, no browsers" state a fresh install
    # leaves behind.
    pack = tmp_path / "browser-pack"
    (pack / ".local-browsers").parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(target, pack / ".local-browsers", symlinks=True)
    shutil.rmtree(target)
    assert not bundled_browsers_present(str(venv))

    # 3. Lay the pack down through the REAL _run_rfbrowser_init, with the
    #    network init guarded: subprocess.run must NOT be called.
    with patch.object(tasks, "resolve_browser_pack_dir", return_value=pack), \
         patch.object(tasks, "_broadcast_package_status"), \
         patch("src.environments.tasks.subprocess.run") as guard:
        tasks._run_rfbrowser_init(
            str(venv), env_id=1,
            package_name="robotframework-browser-batteries",
            pkg=None, session=MagicMock(),
        )
        guard.assert_not_called()  # offline copy path, never the network init

    assert bundled_browsers_present(str(venv)), "pack lay-down left no browsers"

    # 4. Run a trivial Browser test — only a working binary launches Chromium.
    suite = tmp_path / "smoke.robot"
    suite.write_text(
        "*** Settings ***\n"
        "Library    Browser\n\n"
        "*** Test Cases ***\n"
        "Launch Offline Chromium\n"
        "    New Browser    chromium    headless=True\n"
        "    New Page    about:blank\n"
        "    Get Title\n"
        "    Close Browser\n"
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    run = _run(
        [py, "-m", "robot", "--outputdir", str(out_dir), str(suite)],
        timeout=180,
    )
    assert run.returncode == 0, (
        "Robot run failed — laid-down pack browser did not launch.\n"
        f"STDOUT:\n{run.stdout[-1500:]}\nSTDERR:\n{run.stderr[-800:]}"
    )
