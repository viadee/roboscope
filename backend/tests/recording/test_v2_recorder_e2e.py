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


# ──────────────────────────────────────────────────────────────────────
# RECORDER-VERIFY-FRAME — real-browser regression for the
# verifier's navigation / iframe-detach race. The fakes-based unit
# tests in test_v2_recorder_verify_wire.py cover the helper contract,
# but the production failure mode (heise.de cookie banner → click
# dismisses iframe → `evaluate_all` raises mid-verify) needs a real
# Playwright Frame to reproduce. Without these tests, the "verifier
# silently dropped every candidate" regression that shipped to users
# would have stayed undetected.
# ──────────────────────────────────────────────────────────────────────


def _http_server_for_dir(dirpath: Path):
    """Spin a small HTTP server rooted at `dirpath`. Returns the
    base URL plus a teardown callable so callers can ask for any
    fixture they want. Independent helper because the fixture-named
    `fixture_http_server` pytest fixture is hard-wired to one
    specific HTML file."""

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kw):
            super().__init__(*args, directory=str(dirpath), **kw)

        def log_message(self, *a, **kw):
            return

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    def _tear_down():
        httpd.shutdown()
        thread.join(timeout=2)

    return f"http://127.0.0.1:{port}", _tear_down


@pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="playwright not installed")
def test_click_that_navigates_preserves_selector_candidates():
    """A click that triggers full-page navigation detaches the current
    frame BEFORE the verifier's `evaluate_all` round-trip can finish.

    Pre-fix behaviour:
      - `_resolve` swallowed the exception → returned `MatchInfo(0,0,0)`
      - `verify_candidates` treated total=0 as "drop"
      - the recorded Click landed in the sidecar with ZERO selector
        candidates → emitter wrote `# RBSCOPE: dropped Click — no
        selector captured` and the user got an unrunnable .robot file.

    Post-fix:
      - `_resolve` returns `None` on exception
      - `verify_candidates` preserves the candidate at the tail
        with `verified_unique=False`
      - the click survives end-to-end with usable selectors.

    Asserts: after the recorder exits, the Click on the inter-page
    link has at least one selector candidate.
    """
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

    base_url, tear_down_server = _http_server_for_dir(FIXTURE_PATH.parent)
    try:
        target = f"{base_url}/recorder_multipage_a.html"

        session_id = 424343
        register_session(session_id)
        spy = _CommandSpy()
        spy.install()

        async def actions(page):
            await page.wait_for_selector('[data-testid="goto-page-b"]', timeout=5000)
            # Click the inter-page link. Playwright follows the
            # `href`, which forks a full navigation, which detaches
            # the frame the click came from while the recorder's
            # binding callback is still in flight.
            await page.click('[data-testid="goto-page-b"]')
            # Wait for Page B to be visible so the navigation actually
            # races the verifier.
            await page.wait_for_selector('[data-testid="page-b-heading"]', timeout=5000)
            # Settle a beat so any tail capture events drain.
            await page.wait_for_timeout(600)

        thread = threading.Thread(
            target=run_v2_recorder_session,
            args=(session_id, target),
            kwargs={"headless": True, "test_actions": actions},
            daemon=True,
        )
        thread.start()
        thread.join(timeout=30)
        assert not thread.is_alive(), "recorder thread did not exit within 30s"

        spy.uninstall()
        tear_down_session(session_id)

        payloads = list(spy.commands)
        click_cmds = [c for c in payloads if c.keyword == "Click"]
        print(
            f"\n[nav-race] captured {len(payloads)} commands, "
            f"{len(click_cmds)} Click(s); first Click has "
            f"{len(click_cmds[0].selector_candidates) if click_cmds else 0} candidates"
        )

        assert click_cmds, (
            f"expected at least one Click command, got keywords="
            f"{[c.keyword for c in payloads]!r}"
        )
        # THE assertion that the bug ships against: the captured
        # Click must have AT LEAST ONE selector candidate. Pre-fix,
        # this was empty because the verifier dropped them all.
        nav_click = next(
            (
                c for c in click_cmds
                if any("goto-page-b" in cand.value for cand in c.selector_candidates)
            ),
            None,
        )
        # If verifier kept the candidate(s), great. Even if it
        # couldn't verify (timing varies), there should be SOMETHING.
        assert nav_click is not None or (
            click_cmds[0].selector_candidates
        ), (
            "no Click command landed with selector candidates after a "
            "navigation-triggering click — verifier likely dropped them "
            f"all. Got: {[ [cand.value for cand in c.selector_candidates] for c in click_cmds]!r}"
        )
        # The CRITICAL assertion: at least one candidate exists.
        assert all(c.selector_candidates for c in click_cmds), (
            f"some Click ended up with ZERO selector candidates — "
            f"regression. Got: {[ (c.keyword, [cand.value for cand in c.selector_candidates]) for c in click_cmds]!r}"
        )
    finally:
        tear_down_server()


@pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="playwright not installed")
def test_click_inside_iframe_that_removes_itself_preserves_selectors():
    """Cookie-banner scenario (heise.de Sourcepoint flow): the user
    clicks a button INSIDE an iframe, the click handler removes the
    iframe from the parent DOM, the frame detaches, and the
    verifier's per-candidate `evaluate_all` fails with "Frame was
    detached" / "Target closed".

    Pre-fix: every candidate dropped → empty list → `# RBSCOPE:
    dropped Click — no selector captured`.
    Post-fix: candidates preserved (unverified at minimum) so the
    user has something to pick from and the test still runs.
    """
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

    base_url, tear_down_server = _http_server_for_dir(FIXTURE_PATH.parent)
    try:
        target = f"{base_url}/recorder_iframe_banner.html"

        session_id = 424344
        register_session(session_id)
        spy = _CommandSpy()
        spy.install()

        async def actions(page):
            # Wait for the iframe to be ready.
            await page.wait_for_selector('[data-testid="banner-frame"]', timeout=5000)
            iframe_locator = page.frame_locator('[data-testid="banner-frame"]')
            await iframe_locator.locator(
                '[data-testid="agree-btn"]',
            ).wait_for(state="visible", timeout=5000)
            # Click inside the iframe. The handler posts a message
            # that the parent uses to .remove() the iframe — so the
            # iframe's Frame object detaches while the binding
            # callback is still on its way back to Python.
            await iframe_locator.locator('[data-testid="agree-btn"]').click()
            # Settle so the recorder's binding handler has a chance
            # to run and the parent's `f.remove()` actually fires.
            await page.wait_for_timeout(800)

        thread = threading.Thread(
            target=run_v2_recorder_session,
            args=(session_id, target),
            kwargs={"headless": True, "test_actions": actions},
            daemon=True,
        )
        thread.start()
        thread.join(timeout=30)
        assert not thread.is_alive(), "recorder thread did not exit within 30s"

        spy.uninstall()
        tear_down_session(session_id)

        payloads = list(spy.commands)
        click_cmds = [c for c in payloads if c.keyword == "Click"]
        print(
            f"\n[iframe-detach] captured {len(payloads)} commands, "
            f"{len(click_cmds)} Click(s); cand counts="
            f"{[len(c.selector_candidates) for c in click_cmds]!r}"
        )

        assert click_cmds, (
            f"expected at least one Click on the iframe button, got "
            f"keywords={[c.keyword for c in payloads]!r}"
        )
        # The cookie-banner Click was on the iframe-internal button.
        # The recorder tags it with `frame_url` and the candidate
        # values are bare (no iframe prefix) because the emitter
        # composes the chained selector at serialise time.
        iframe_click = next(
            (c for c in click_cmds if c.frame_url is not None),
            None,
        )
        assert iframe_click is not None, (
            f"expected a Click with frame_url set (iframe origin), got "
            f"frame_urls={[c.frame_url for c in click_cmds]!r}"
        )
        # THE assertion that pins the regression: even after the
        # iframe detached mid-verify, the captured Click MUST have
        # selector candidates (verified or not).
        assert iframe_click.selector_candidates, (
            "iframe Click ended up with ZERO selector candidates — "
            "this is the heise.de cookie-banner regression. Verifier "
            "likely dropped them all because the iframe detached "
            "before evaluate_all could run."
        )
    finally:
        tear_down_server()


# ──────────────────────────────────────────────────────────────────────
# Story RECORDER-FRAMES-2 — iframe-element selectors live in
# `cmd.frame_chain`, not just `cmd.frame_url`. These tests record a
# click inside a real cross-document iframe and assert that:
#   1. The sidecar payload (RecordedCommand on the queue) carries a
#      populated `frame_chain` with selector candidates for the
#      iframe element itself, NOT just the inner selectors.
#   2. The emitter prefers a high-quality iframe candidate (id-based)
#      over the legacy URL-derived `iframe[src*="<host>"]` fallback
#      when serialising to .robot.
#   3. When the iframe detaches mid-flight (Sourcepoint flow), the
#      chain may be empty — the emitter still produces a valid line
#      via the URL-derived legacy strategy AND the inner click is
#      preserved with at least one candidate (the regression chain).
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="playwright not installed")
def test_iframe_click_records_frame_chain_with_id_candidate_in_sidecar():
    """Records a click inside a STABLE iframe (no detach on click).

    Asserts the captured Click ends up with:
      - non-empty `frame_chain` (the structural fix)
      - at least one rung whose `selector_candidates` includes the
        id-based `iframe#consent-banner` strategy (the strongest
        synthesis output)
      - the emitted .robot line uses an id/testid/name-based iframe
        locator, NOT the legacy `iframe[src*="<host>"]` fallback.

    This is the post-FRAMES-2 happy path the user asked us to pin
    in real-browser E2E.
    """
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
        pytest.skip("playwright chromium not installed")

    from src.recording.v2_recorder_task import run_v2_recorder_session
    from src.recording.robot_emit import _emit_command

    base_url, tear_down_server = _http_server_for_dir(FIXTURE_PATH.parent)
    try:
        target = f"{base_url}/recorder_iframe_stable.html"
        session_id = 424345
        register_session(session_id)
        spy = _CommandSpy()
        spy.install()

        async def actions(page):
            await page.wait_for_selector(
                '[data-testid="consent-banner"]', timeout=5000,
            )
            iframe_locator = page.frame_locator('[data-testid="consent-banner"]')
            await iframe_locator.locator(
                '[data-testid="agree-btn"]',
            ).wait_for(state="visible", timeout=5000)
            await iframe_locator.locator('[data-testid="agree-btn"]').click()
            await page.wait_for_timeout(800)

        thread = threading.Thread(
            target=run_v2_recorder_session,
            args=(session_id, target),
            kwargs={"headless": True, "test_actions": actions},
            daemon=True,
        )
        thread.start()
        thread.join(timeout=30)
        assert not thread.is_alive()

        spy.uninstall()
        tear_down_session(session_id)

        click_cmds = [c for c in spy.commands if c.keyword == "Click"]
        iframe_clicks = [c for c in click_cmds if c.frame_url is not None]
        assert iframe_clicks, (
            f"expected an iframe click, got "
            f"frame_urls={[c.frame_url for c in click_cmds]!r}"
        )
        cmd = iframe_clicks[0]

        # (1) The sidecar payload itself carries the chain.
        assert cmd.frame_chain, (
            f"frame_chain is empty on an iframe click — RECORDER-FRAMES-2 "
            f"regression. Got: {cmd}"
        )
        assert len(cmd.frame_chain) == 1, (
            f"expected 1 rung (no nesting), got "
            f"{len(cmd.frame_chain)}: {cmd.frame_chain!r}"
        )
        rung = cmd.frame_chain[0]
        cand_values = [c.value for c in rung.selector_candidates]
        print(f"\n[frames-2] frame_chain rung candidates: {cand_values!r}")
        assert rung.selector_candidates, (
            f"frame_chain rung has no candidates — synthesis failed. "
            f"rung={rung}"
        )
        first = rung.selector_candidates[0]
        assert any(
            s in first.value for s in [
                "iframe#consent-banner",
                'iframe[data-testid="consent-banner"]',
                'iframe[name="consent"]',
            ]
        ), (
            f"best iframe candidate isn't id/testid/name strategy: "
            f"{first.value!r}"
        )
        assert first.verified_unique is True, (
            f"best iframe candidate not verified_unique on a "
            f"single-iframe fixture: {first!r}"
        )

        # (2) Emitter uses the chain, NOT the legacy URL-host pattern.
        line = _emit_command(cmd)
        print(f"[frames-2] emitted line: {line}")
        assert 'iframe[src*="127.0.0.1"]' not in line
        assert any(
            s in line for s in [
                "iframe#consent-banner >>>",
                'iframe[data-testid="consent-banner"] >>>',
                'iframe[name="consent"] >>>',
            ]
        ), (
            f"emitted line doesn't use a high-quality iframe candidate: "
            f"{line!r}"
        )
    finally:
        tear_down_server()


@pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="playwright not installed")
def test_iframe_click_when_iframe_detaches_falls_back_to_url_strategy():
    """Click inside the SELF-REMOVING iframe (Sourcepoint flow). The
    iframe is gone by verify time, so `frame_element()` fails and
    `frame_chain` may be empty. Asserts the emitter still produces a
    valid line via the URL-derived legacy strategy."""
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
        pytest.skip("playwright chromium not installed")

    from src.recording.v2_recorder_task import run_v2_recorder_session
    from src.recording.robot_emit import _emit_command

    base_url, tear_down_server = _http_server_for_dir(FIXTURE_PATH.parent)
    try:
        target = f"{base_url}/recorder_iframe_banner.html"
        session_id = 424346
        register_session(session_id)
        spy = _CommandSpy()
        spy.install()

        async def actions(page):
            await page.wait_for_selector(
                '[data-testid="banner-frame"]', timeout=5000,
            )
            iframe_locator = page.frame_locator('[data-testid="banner-frame"]')
            await iframe_locator.locator(
                '[data-testid="agree-btn"]',
            ).wait_for(state="visible", timeout=5000)
            await iframe_locator.locator('[data-testid="agree-btn"]').click()
            await page.wait_for_timeout(800)

        thread = threading.Thread(
            target=run_v2_recorder_session,
            args=(session_id, target),
            kwargs={"headless": True, "test_actions": actions},
            daemon=True,
        )
        thread.start()
        thread.join(timeout=30)
        assert not thread.is_alive()

        spy.uninstall()
        tear_down_session(session_id)

        click_cmds = [c for c in spy.commands if c.keyword == "Click"]
        iframe_clicks = [c for c in click_cmds if c.frame_url is not None]
        assert iframe_clicks, "no iframe click was captured"
        cmd = iframe_clicks[0]
        assert cmd.frame_url is not None
        assert cmd.selector_candidates, (
            "iframe click lost all inner selectors — preserve-on-exception "
            "regression"
        )
        # RECORDER-FRAMES-2 — the proactive inventory should have
        # registered the iframe BEFORE the user click detached it, so
        # the chain MUST carry id-based selectors even though
        # `frame_element()` would now fail. Pre-inventory behaviour
        # left this empty.
        assert cmd.frame_chain, (
            "frame_chain empty after iframe detach — proactive "
            "inventory didn't fire in time. Got: " + repr(cmd)
        )
        rung = cmd.frame_chain[0]
        assert rung.selector_candidates, (
            "frame_chain rung has no candidates — inventory entry "
            "missing for url=" + repr(rung.url)
        )
        cand_values = [c.value for c in rung.selector_candidates]
        print(
            f"\n[frames-2-detach] frame_chain candidates (post-detach): "
            f"{cand_values!r}"
        )
        line = _emit_command(cmd)
        print(f"[frames-2-detach] emitted line: {line}")
        # Now the chain has a high-quality iframe selector, so the
        # emitted line MUST use one of those — NOT just the URL host
        # fallback (which used to be the only option pre-inventory).
        assert "iframe" in line and ">>>" in line, (
            f"emitted line lost its iframe wrapper: {line!r}"
        )
        assert any(
            s in line for s in [
                "iframe#banner-frame",
                'iframe[data-testid="banner-frame"]',
            ]
        ), (
            f"emitted line uses neither id nor testid iframe locator "
            f"despite proactive inventory: {line!r}"
        )
    finally:
        tear_down_server()


@pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="playwright not installed")
def test_iframe_loaded_after_DOMContentLoaded_still_registered():
    """heise.de / Sourcepoint shape: the CMP iframe is INJECTED via
    JS after the parent's DOMContentLoaded. A single ready-time scan
    misses it. The retry-loop (100/300/700/1500/3000/5000 ms +
    iframe load events) is supposed to catch it before the user
    clicks, which the recorder doesn't until at least ~2 s into the
    session.

    Asserts:
      - The captured iframe click has `frame_url` set.
      - `frame_chain[0].selector_candidates` is NON-EMPTY — proving
        the late-load was caught by the retry-scan.
      - The emitted line uses an id/testid/name iframe locator (the
        synthesised candidates), NOT the legacy URL-host fallback.
    """
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
        pytest.skip("playwright chromium not installed")

    from src.recording.v2_recorder_task import run_v2_recorder_session
    from src.recording.robot_emit import _emit_command

    base_url, tear_down_server = _http_server_for_dir(FIXTURE_PATH.parent)
    try:
        target = f"{base_url}/recorder_iframe_late_load.html"
        session_id = 424347
        register_session(session_id)
        spy = _CommandSpy()
        spy.install()

        async def actions(page):
            # Give the injection setTimeout(600ms) PLUS our retry scan
            # at 700ms time to register the iframe. The retry loop
            # covers 100/300/700/1500/3000/5000ms — by 1500ms we're
            # safely past the injection.
            await page.wait_for_selector(
                '[data-testid="cmp-banner"]', timeout=5000,
            )
            iframe_locator = page.frame_locator('[data-testid="cmp-banner"]')
            await iframe_locator.locator(
                '[data-testid="agree-btn"]',
            ).wait_for(state="visible", timeout=5000)
            await iframe_locator.locator('[data-testid="agree-btn"]').click()
            await page.wait_for_timeout(800)

        thread = threading.Thread(
            target=run_v2_recorder_session,
            args=(session_id, target),
            kwargs={"headless": True, "test_actions": actions},
            daemon=True,
        )
        thread.start()
        thread.join(timeout=30)
        assert not thread.is_alive()

        spy.uninstall()
        tear_down_session(session_id)

        click_cmds = [c for c in spy.commands if c.keyword == "Click"]
        iframe_clicks = [c for c in click_cmds if c.frame_url is not None]
        assert iframe_clicks, "no iframe click was captured"
        cmd = iframe_clicks[0]

        # The critical assertion — the retry-scan caught the
        # late-injected iframe BEFORE the user clicked, so the chain
        # has real candidates.
        assert cmd.frame_chain, (
            "frame_chain is empty — retry-scan didn't catch the "
            "late-loaded iframe in time"
        )
        rung = cmd.frame_chain[0]
        assert rung.selector_candidates, (
            "frame_chain rung is empty — retry-scan didn't register "
            "the iframe (URL match miss?)"
        )
        cand_values = [c.value for c in rung.selector_candidates]
        print(
            f"\n[frames-2-late-load] frame_chain candidates: "
            f"{cand_values!r}"
        )

        line = _emit_command(cmd)
        print(f"[frames-2-late-load] emitted line: {line}")
        assert any(
            s in line for s in [
                "iframe#sp_message_iframe_1234567",
                'iframe[data-testid="cmp-banner"]',
                'iframe[name="consent"]',
            ]
        ), (
            f"emitted line doesn't use an id/testid/name iframe "
            f"locator despite retry-scan catching the late load: {line!r}"
        )
    finally:
        tear_down_server()
