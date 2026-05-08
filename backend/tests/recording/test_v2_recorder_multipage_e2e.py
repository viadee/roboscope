"""RECORDER-1A / 1B / 1C — multi-page recorder round-trip.

Drives the real Recorder v2 against a two-page local fixture:

    page-A → click "Go to Page B" link → page-B → click "Click me" button

Then asserts:

  1. The recording captures the link click (not just an inferred Go To).
  2. The recording captures the page-B button click (proving the
     post-navigation document also gets the capture script).
  3. There is **no** redundant `Go To <page-b-url>` after the link click
     — that emission is suppressed by RECORDER-1B because the click
     already implies the navigation. (Recording it would re-navigate on
     replay and wipe whatever state the click set.)

Optionally — gated on `robotframework` + `robotframework-browser` being
importable — the recorded `.robot` is rendered, written to a temp dir,
and executed via `robot` CLI. We assert exit-code 0 to confirm the
recording is a faithful, replayable representation of the user journey.

Marked `integration` so CI hosts without Chromium skip cleanly.
"""

from __future__ import annotations

import http.server
import importlib.util
import os
import shutil
import socketserver
import subprocess
import tempfile
import threading
from pathlib import Path

import pytest

from src.recording.robot_emit import emit_robot
from src.recording.selector_schema import RecordedFlow
from src.recording.v2_command_queue import register_session, tear_down_session

try:
    import playwright  # noqa: F401
    _HAS_PLAYWRIGHT = True
except Exception:
    _HAS_PLAYWRIGHT = False


pytestmark = pytest.mark.integration


FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
PAGE_A = "recorder_multipage_a.html"
PAGE_B = "recorder_multipage_b.html"


@pytest.fixture
def multipage_fixture_server():
    """Serve the two multipage fixtures over an ephemeral port.

    Yields the URL of page A; page B is reachable at the same port via
    its filename (the in-fixture link is a relative href).
    """
    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kw):
            super().__init__(*args, directory=str(FIXTURE_DIR), **kw)

        def log_message(self, *a, **kw):  # quiet stderr noise
            return

    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler) as httpd:
        httpd.daemon_threads = True
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{port}/{PAGE_A}", port
        finally:
            httpd.shutdown()
            thread.join(timeout=2)


class _CommandSpy:
    """Same pattern as test_v2_recorder_e2e — intercepts enqueue_command
    so the test sees the RecordedCommands without racing the recorder's
    own teardown."""

    def __init__(self):
        self.commands = []
        self._lock = threading.Lock()
        self._orig_q_enqueue = None
        self._orig_task_enqueue = None

    def install(self):
        from src.recording import v2_command_queue as q
        from src.recording import v2_recorder_task as t
        self._orig_q_enqueue = q.enqueue_command
        self._orig_task_enqueue = t.enqueue_command

        def _capture(session_id, command):
            with self._lock:
                self.commands.append(command)
            return self._orig_q_enqueue(session_id, command)

        q.enqueue_command = _capture
        t.enqueue_command = _capture

    def uninstall(self):
        if self._orig_q_enqueue is not None:
            from src.recording import v2_command_queue as q
            from src.recording import v2_recorder_task as t
            q.enqueue_command = self._orig_q_enqueue
            t.enqueue_command = self._orig_task_enqueue


def _chromium_available() -> bool:
    if not _HAS_PLAYWRIGHT:
        return False
    import asyncio

    from playwright.async_api import async_playwright

    async def _check():
        try:
            async with async_playwright() as pw:
                b = await pw.chromium.launch(headless=True)
                await b.close()
            return True
        except Exception:
            return False

    return asyncio.run(_check())


@pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="playwright not installed")
def test_recorder_multipage_round_trip(multipage_fixture_server):
    """Drive page-A → click link → page-B → click button.

    Proves RECORDER-1A (cross-page capture) and RECORDER-1B (no
    duplicate Go To after a click-caused navigation).
    """
    if not _chromium_available():
        pytest.skip("playwright chromium not installed — run `playwright install chromium`")

    from src.recording.v2_recorder_task import run_v2_recorder_session

    page_a_url, _port = multipage_fixture_server
    session_id = 4242420

    register_session(session_id)
    spy = _CommandSpy()
    spy.install()

    async def actions(page):
        # Wait for page A to settle and the capture script to install.
        await page.wait_for_selector('[data-testid="page-a-heading"]', timeout=5000)
        # Click the link that navigates to page B (real full nav, not hash).
        await page.click('[data-testid="goto-page-b"]')
        # Page B loads; wait for its heading + button.
        await page.wait_for_selector('[data-testid="page-b-heading"]', timeout=5000)
        await page.click('[data-testid="action-button"]')
        # Wait for the click marker to confirm the button handler ran in
        # the real browser (the recorded selector therefore has to be valid).
        await page.wait_for_selector('[data-testid="clicked-marker"].shown', timeout=2000)
        # Let the final batch flush through the binding.
        await page.wait_for_timeout(800)

    thread = threading.Thread(
        target=run_v2_recorder_session,
        args=(session_id, page_a_url),
        kwargs={"headless": True, "test_actions": actions},
        daemon=True,
    )
    thread.start()
    thread.join(timeout=30)
    assert not thread.is_alive(), "recorder thread did not exit within 30s"

    spy.uninstall()
    tear_down_session(session_id)

    payloads = list(spy.commands)
    keywords = [c.keyword for c in payloads]
    print(f"\n[multipage e2e] captured {len(payloads)} commands: {keywords!r}")

    # ----- AC1: link click captured -----
    link_clicks = [
        c for c in payloads
        if c.keyword == "Click"
        and any("goto-page-b" in cand.value for cand in c.selector_candidates)
    ]
    assert link_clicks, (
        f"expected a Click on the Page-A→B link, got keywords={keywords!r}"
    )
    link_click_idx = payloads.index(link_clicks[0])

    # ----- AC2: page-B button click captured -----
    button_clicks = [
        c for c in payloads
        if c.keyword == "Click"
        and any("action-button" in cand.value for cand in c.selector_candidates)
    ]
    assert button_clicks, (
        f"expected a Click on the Page-B action button (proves cross-page "
        f"capture survives full navigation), got keywords={keywords!r}"
    )

    # ----- AC3 (RECORDER-1B): no redundant Go To after the link click -----
    # The click caused page B to load; the post-load `Go To <page-b-url>`
    # would be the duplicate we suppressed.
    after_link = payloads[link_click_idx + 1:]
    duplicate_goto = [
        c for c in after_link
        if c.keyword == "Go To" and PAGE_B in (c.args.get("url") or "")
    ]
    assert not duplicate_goto, (
        f"expected NO Go To <page-b-url> after the link click "
        f"(click already implies the navigation), but got: "
        f"{[c.args for c in duplicate_goto]!r}\n"
        f"full sequence: {keywords!r}"
    )


def _find_replay_venv() -> tuple[Path, Path] | None:
    """Locate a venv that has both `robot` and `Browser` importable.

    Looks at:
      1. The current process's interpreter (rare — the backend venv
         doesn't ship rfbrowser by default).
      2. `~/.roboscope/venvs/roboscope-default` — the venv the project's
         own environments system creates with rfbrowser pre-installed.
      3. Any venv path supplied via the `ROBOSCOPE_REPLAY_VENV` env var.

    Returns `(python_bin, robot_bin)` or None when none qualify.
    """
    candidates: list[Path] = []
    env_override = os.environ.get("ROBOSCOPE_REPLAY_VENV")
    if env_override:
        candidates.append(Path(env_override))
    candidates.append(Path.home() / ".roboscope" / "venvs" / "roboscope-default")

    for venv in candidates:
        py = venv / "bin" / "python"
        rb = venv / "bin" / "robot"
        if not py.exists() or not rb.exists():
            continue
        try:
            check = subprocess.run(
                [str(py), "-c", "import robot, Browser"],
                capture_output=True, timeout=10,
            )
            if check.returncode == 0:
                return py, rb
        except Exception:
            continue

    # Fallback: the current interpreter, if it has both modules.
    if importlib.util.find_spec("robot") and importlib.util.find_spec("Browser"):
        bin_dir = Path(__import__("sys").executable).parent
        rb = bin_dir / "robot"
        if rb.exists():
            return Path(__import__("sys").executable), rb
    return None


@pytest.mark.skipif(
    not _HAS_PLAYWRIGHT,
    reason="needs playwright to drive the recorder",
)
def test_recorded_robot_replays_successfully(multipage_fixture_server):
    """End-to-end: record the journey, render to .robot, replay via the
    `robot` CLI, assert exit 0.

    This is the strongest possible regression — if the recorder ever
    captures unreplayable selectors or emits redundant `Go To`s that
    break replay, this test goes red.
    """
    if not _chromium_available():
        pytest.skip("playwright chromium not installed")
    replay_venv = _find_replay_venv()
    if replay_venv is None:
        pytest.skip(
            "no venv with robotframework + robotframework-browser found "
            "(set ROBOSCOPE_REPLAY_VENV to a path that has both)"
        )

    from src.recording.v2_recorder_task import run_v2_recorder_session

    page_a_url, _port = multipage_fixture_server
    session_id = 4242421

    register_session(session_id)
    spy = _CommandSpy()
    spy.install()

    async def actions(page):
        await page.wait_for_selector('[data-testid="page-a-heading"]', timeout=5000)
        await page.click('[data-testid="goto-page-b"]')
        await page.wait_for_selector('[data-testid="page-b-heading"]', timeout=5000)
        await page.click('[data-testid="action-button"]')
        await page.wait_for_selector('[data-testid="clicked-marker"].shown', timeout=2000)
        await page.wait_for_timeout(800)

    thread = threading.Thread(
        target=run_v2_recorder_session,
        args=(session_id, page_a_url),
        kwargs={"headless": True, "test_actions": actions},
        daemon=True,
    )
    thread.start()
    thread.join(timeout=30)
    assert not thread.is_alive()

    spy.uninstall()
    tear_down_session(session_id)

    flow = RecordedFlow(
        schema_version=1,
        transport="web_playwright",
        session_id=str(session_id),
        name="MultipageReplay",
        commands=list(spy.commands),
    )
    robot_source = emit_robot(flow)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        robot_file = tmp_path / "multipage_replay.robot"
        robot_file.write_text(robot_source, encoding="utf-8")

        py_bin, robot_bin = replay_venv
        result = subprocess.run(
            [str(robot_bin),
             "--variable", "BROWSER:chromium",
             "--variable", "HEADLESS:True",
             "--outputdir", str(tmp_path),
             str(robot_file)],
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ},
        )

        assert result.returncode == 0, (
            f"recorded test failed on replay (exit {result.returncode})\n"
            f"--- robot source ---\n{robot_source}\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
