"""Recorder v2 end-to-end capture test.

Launches the REAL v2 Playwright recorder (headless) against a local
HTML fixture, drives scripted user actions through the capture
pipeline, then asserts on the emitted RecordedCommand payloads.

The test is marked `integration` so CI environments without Chromium
(e.g. offline Windows ZIP builder) can skip it. On any dev / CI host
that has `playwright install chromium`, the test runs in < 10 s and
provides the regression signal that the capture script + the
__roboscopeCapture binding + the selector synthesis are wired
end-to-end.

If this test ever red, **do not** mock around the failure — the whole
point of the fixture is that only a real browser can catch a broken
binding or injection.
"""

from __future__ import annotations

import http.server
import socketserver
import threading
import time
from pathlib import Path

import pytest

from src.recording.v2_command_queue import (
    register_session,
    tear_down_session,
)

try:
    import playwright  # noqa: F401
    _HAS_PLAYWRIGHT = True
except Exception:
    _HAS_PLAYWRIGHT = False


pytestmark = pytest.mark.integration


FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "recorder_fixture.html"


@pytest.fixture
def fixture_http_server():
    """Serve `backend/tests/fixtures/` over an ephemeral port."""
    fixture_dir = FIXTURE_PATH.parent

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kw):
            super().__init__(*args, directory=str(fixture_dir), **kw)

        def log_message(self, *a, **kw):  # quiet the stderr noise
            return

    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler) as httpd:
        httpd.daemon_threads = True
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{port}/recorder_fixture.html"
        finally:
            httpd.shutdown()
            thread.join(timeout=2)


class _CommandSpy:
    """Intercepts `enqueue_command` so the test can observe emitted
    RecordedCommands without racing the recorder's `tear_down_session`
    in the thread's finally-block."""

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
        # v2_recorder_task imports enqueue_command by name at module load —
        # patch the reference in that module too.
        t.enqueue_command = _capture

    def uninstall(self):
        if self._orig_q_enqueue is not None:
            from src.recording import v2_command_queue as q
            from src.recording import v2_recorder_task as t
            q.enqueue_command = self._orig_q_enqueue
            t.enqueue_command = self._orig_task_enqueue


@pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="playwright not installed")
def test_recorder_captures_click_type_navigate(fixture_http_server):
    """Real-browser capture test — the whole pipeline end to end.

    1. Start the v2 recorder in a background thread.
    2. `test_actions` drives the fixture page: fill email, click submit,
       follow the #next link.
    3. After the recorder exits, drain the queue and assert the
       keyword + selector shapes of the emitted RecordedCommands.
    """
    # Probe Chromium binary up-front so the skip reason is clear.
    from playwright.async_api import async_playwright

    async def _chromium_available():
        try:
            async with async_playwright() as pw:
                b = await pw.chromium.launch(headless=True)
                await b.close()
            return True
        except Exception:
            return False

    import asyncio
    if not asyncio.run(_chromium_available()):
        pytest.skip("playwright chromium not installed — run `playwright install chromium`")

    from src.recording.v2_recorder_task import run_v2_recorder_session

    session_id = 424242
    register_session(session_id)

    spy = _CommandSpy()
    spy.install()

    async def actions(page):
        # Give the injected capture script a beat to install listeners.
        await page.wait_for_selector('[data-testid="submit-button"]', timeout=5000)
        # Focus the input then trigger a change event so the `type`
        # handler fires. Playwright `page.fill` issues a clear+type+blur
        # sequence — the blur produces the DOM `change` event.
        await page.fill('[data-testid="email-input"]', "alice@example.com")
        # Move focus elsewhere to fire the change event on the input.
        await page.click('[data-testid="submit-button"]')
        # Follow the in-page link — triggers either a `navigate` event
        # (hash change) or a `click` event on the anchor.
        await page.click('[data-testid="next-link"]')
        # Let the final batch of events flush through the binding.
        await page.wait_for_timeout(800)

    thread = threading.Thread(
        target=run_v2_recorder_session,
        args=(session_id, fixture_http_server),
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
    print(f"\n[e2e] captured {len(payloads)} commands: {keywords!r}")

    # The capture script emits a `navigate` event for the initial load
    # too — translated to `Go To`. We only require the real user actions
    # to land.
    click_cmds = [c for c in payloads if c.keyword == "Click"]
    type_cmds = [c for c in payloads if c.keyword == "Type Text"]

    # AC3 assertions.
    assert len(click_cmds) >= 1, (
        f"expected at least one Click command, got keywords={keywords!r}"
    )
    submit_clicks = [
        c for c in click_cmds
        if any("submit-button" in cand.value for cand in c.selector_candidates)
    ]
    assert submit_clicks, (
        f"expected a Click command targeting the submit-button testid, "
        f"got click_cmds={[ [cand.value for cand in c.selector_candidates] for c in click_cmds]!r}"
    )

    assert len(type_cmds) >= 1, f"expected at least one Type Text, got keywords={keywords!r}"
    assert any(
        c.args.get("text") == "alice@example.com" for c in type_cmds
    ), f"expected Type Text with 'alice@example.com', got {[c.args for c in type_cmds]!r}"

    # Either a `Go To` (full nav) OR a second Click on the next-link is
    # acceptable — both prove the navigation path is captured.
    nav_or_link_click = [
        c for c in payloads
        if c.keyword == "Go To"
        or (
            c.keyword == "Click"
            and any("next-link" in cand.value for cand in c.selector_candidates)
        )
    ]
    assert nav_or_link_click, (
        f"expected a Go To or Click on next-link after the link click, "
        f"got keywords={keywords!r}"
    )
