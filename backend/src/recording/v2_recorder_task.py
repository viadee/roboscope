"""Story W.1 full — Playwright-driven Recorder v2 session task.

Runs on a dedicated event-loop thread (R-1 pattern). Launches Chromium,
injects the three capture scripts (W.3 capture + W.4 overlay + W.5
context menu), registers the `__roboscopeCapture` binding, and drains
payloads into the v2 command queue (W.2).

The `run_v2_recorder_session(session_id)` function is the entry point
dispatched from the start-browser endpoint. It blocks until the stop
event fires or the browser disconnects.

Safe to import without Playwright installed — the actual import is
deferred to the entry point so unit tests that don't launch a browser
never trip a missing-dep error.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

# FK resolution for cross-module SQLAlchemy lookups (tasks run in
# background threads with fresh sessions — see CLAUDE.md).
import src.auth.models  # noqa: F401
import src.repos.models  # noqa: F401

from src.database import get_sync_session
from src.recording.capture_script import CAPTURE_SCRIPT
from src.recording.context_menu_script import CONTEXT_MENU_SCRIPT
from src.recording.models import RecordingSession, RecordingStatus
from src.recording.overlay_script import OVERLAY_SCRIPT
from src.recording.v2_command_queue import (
    LifecycleEvent,
    enqueue_command,
    enqueue_lifecycle,
    finalize_session,
    tear_down_session,
)
from src.recording.selector_schema import (
    FrameDescriptor,
    RecordedCommand,
    SelectorCandidate,
)
from src.recording.selector_verification import MatchInfo, verify_candidates
from src.recording.v2_payload_translator import translate_payload

logger = logging.getLogger("roboscope.recording.v2_recorder")


async def _capture_frame_chain(frame_or_page: Any) -> list[FrameDescriptor]:
    """Story RECORDER-FRAMES-2 — walk the parent-frame ancestry and
    build a `FrameDescriptor` per rung, with selector candidates for
    each `<iframe>` element synthesised against its PARENT document.

    Why: the legacy emitter rebuilt the iframe locator at serialise
    time from `frame_url` alone, hardcoded to
    `iframe[src*="<host>"]`. That broke when the host wasn't unique
    on the page (multiple CMP iframes from the same vendor) and gave
    the picker no alternative iframe selector to switch to. This
    helper produces 4-6 ranked candidates per iframe (id, testid,
    name, src exact, src host, first stable class) using Playwright's
    `frame_element()` API — works cross-origin because it's a
    CDP-level call, not a browser-DOM-level one.

    Returns an empty list when:
      - `frame_or_page` is a Page (top-frame event, no iframe wrapper
        needed),
      - any `frame_element()` raises (iframe detached mid-flight, race
        with the user's click handler — we still preserve the URL on
        the cmd, so the emitter can fall back to the legacy strategy).

    Order: index 0 is the outermost iframe in the page, last entry is
    the iframe whose document the event originated from. The emitter
    composes them with `>>>` separators in the same order.
    """
    if frame_or_page is None:
        return []
    # A Playwright Page has a `main_frame`; a Frame has `parent_frame`.
    # Top-page events arrive with `page` here → no chain.
    if not hasattr(frame_or_page, "parent_frame"):
        return []

    # Walk inner → outer, collecting one descriptor per non-root frame.
    descriptors: list[FrameDescriptor] = []
    cur: Any = frame_or_page
    try:
        while cur is not None and getattr(cur, "parent_frame", None) is not None:
            parent = cur.parent_frame
            url = cur.url if hasattr(cur, "url") else ""
            try:
                el = await asyncio.wait_for(cur.frame_element(), timeout=1.0)
                candidates = await _synthesise_iframe_candidates(el, parent, url)
            except Exception:
                # iframe element already gone (typical Sourcepoint
                # flow — banner removes itself on click). Record the
                # url-only descriptor so the emitter can fall back to
                # `iframe[src*="<host>"]`.
                candidates = []
            descriptors.append(
                FrameDescriptor(url=url, selector_candidates=candidates),
            )
            cur = parent
    except Exception:
        # Unexpected — return what we managed to collect so far.
        return list(reversed(descriptors))

    # Walked inner → outer; flip to outer → inner so emitter chains
    # `outer >>> inner >>> final`.
    return list(reversed(descriptors))


async def _synthesise_iframe_candidates(
    element_handle: Any, parent_frame: Any, frame_url: str,
) -> list[SelectorCandidate]:
    """Build a ranked list of selectors that point at one specific
    `<iframe>` element from within its parent document.

    Strategies tried, in descending quality:
      - `iframe#<id>`               (qs 90)
      - `iframe[data-testid="…"]`   (qs 95)
      - `iframe[name="…"]`          (qs 85)
      - `iframe[src="<full>"]`      (qs 75)
      - `iframe[src*="<host>"]`     (qs 65) — legacy fallback
      - `iframe.<first-class>`      (qs 40) — last resort

    Each candidate's `verified_unique` is set by a count() against
    `parent_frame` so the picker can show the green check immediately
    without a second pass through the standard verifier. Candidates
    that resolve to 0 are dropped; candidates that resolve to 1 are
    `verified_unique=True`; multi-match candidates are kept with the
    flag False so the user is at least aware.
    """
    try:
        info = await asyncio.wait_for(
            element_handle.evaluate(
                """(el) => {
                    const cls = (el.className || "").split(/\\s+/).filter(Boolean);
                    return {
                        id: el.id || "",
                        testid: el.getAttribute("data-testid") || "",
                        name: el.getAttribute("name") || "",
                        src: el.getAttribute("src") || "",
                        classes: cls,
                    };
                }""",
            ),
            timeout=1.0,
        )
    except Exception:
        return []
    if not isinstance(info, dict):
        return []

    from urllib.parse import urlparse

    raw: list[tuple[str, str, int]] = []  # (strategy, value, quality)

    if info.get("id"):
        raw.append(("css", f'iframe#{info["id"]}', 90))
    if info.get("testid"):
        raw.append(("testid", f'iframe[data-testid="{info["testid"]}"]', 95))
    if info.get("name"):
        raw.append(("css", f'iframe[name="{info["name"]}"]', 85))
    src = info.get("src") or ""
    if src:
        raw.append(("css", f'iframe[src="{src}"]', 75))
        try:
            host = urlparse(src).netloc or urlparse(frame_url).netloc
        except Exception:
            host = ""
        if host:
            raw.append(("css", f'iframe[src*="{host}"]', 65))
    elif frame_url:
        try:
            host = urlparse(frame_url).netloc
        except Exception:
            host = ""
        if host:
            raw.append(("css", f'iframe[src*="{host}"]', 65))
    classes = info.get("classes") or []
    if classes:
        raw.append(("css", f'iframe.{classes[0]}', 40))

    # Verify each candidate by counting matches in the parent frame.
    # The iframe element lives in the parent, NOT in the iframe doc, so
    # the count call goes against `parent_frame`, not `element_handle`.
    out: list[SelectorCandidate] = []
    for strategy, value, qs in raw:
        try:
            loc = parent_frame.locator(value)
            count = await asyncio.wait_for(loc.count(), timeout=1.0)
        except Exception:
            # Couldn't verify — preserve as-is, unverified.
            out.append(
                SelectorCandidate(
                    strategy=strategy, value=value,
                    quality_score=qs, verified_unique=False,
                ),
            )
            continue
        if count == 0:
            # Synthesis produced a selector that doesn't match — drop
            # rather than ship a guaranteed-wrong locator.
            continue
        out.append(
            SelectorCandidate(
                strategy=strategy, value=value,
                quality_score=qs, verified_unique=(count == 1),
            ),
        )
    # Sort by (verified_unique DESC, quality_score DESC) — same
    # contract as inner-element candidates.
    out.sort(key=lambda c: (not c.verified_unique, -c.quality_score))
    return out


def _resolve_frame_target(source: Any) -> Any:
    """Pick the locator target out of Playwright's `expose_binding`
    source argument.

    Playwright's runtime passes
    `source = dict(context=ctx, page=page, frame=frame)` — a plain
    `dict`. We previously used `getattr(source, "frame", None)`,
    which on a dict always returns `None` (dicts hold keys, not
    attributes). That silently nulled the verifier on every captured
    event in production. See the wire-up comment in `on_capture`.

    Returns:
      - For the canonical Playwright path: the originating Frame
        (iframe-aware) or, as fallback, the top Page.
      - For synthetic events (`source=None`, e.g. the recorder's
        own `_on_new_page` Switch Page emission): `None`. The
        downstream helper short-circuits on `None`.
      - For test stubs that expose `.frame` / `.page` attributes:
        the attribute, so existing unit tests don't have to be
        rewritten.
    """
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get("frame") or source.get("page")
    return getattr(source, "frame", None) or getattr(source, "page", None)


async def _verify_command_candidates(
    cmd: RecordedCommand,
    frame_or_page: Any,
) -> RecordedCommand:
    """Run `verify_candidates` against the originating frame, return
    an enriched copy with `verified_unique` flags populated.

    Extracted out of `on_capture` so a unit test can exercise it
    against a fake locator-target without mounting Playwright. The
    target only needs `.locator(value).count()` returning an
    awaitable int. In production we pass `source.frame` (the
    Playwright `BindingSource.frame`) so iframe selectors resolve
    within the iframe document — passing `.page` would search the
    top frame and falsely drop every iframe selector as 0-match.

    Returns the original command unchanged when there are no
    candidates to verify (e.g. `Go To` / `Switch Page` / payloads
    with an unknown element).
    """
    if not cmd.selector_candidates or frame_or_page is None:
        return cmd

    async def _resolve(c: SelectorCandidate) -> MatchInfo | None:
        """Return total / visible / actionable counts for one
        candidate via a single JS round-trip per candidate.

        Naive `is_visible()` / `is_enabled()` looped over every match
        does N×2 RPC calls per candidate — for a typical recording
        with ~10 candidates per click and ~50-match runaway selectors
        in there, that's ~1000 round-trips per command which blew
        through the e2e test's 30s budget. `evaluate_all` packs the
        per-element check into one CDP call.

        Visibility heuristic mirrors what Playwright's `is_visible`
        does on the JS side — `offsetParent` (covers display:none
        ancestors), computed `visibility`, computed `display`,
        non-zero box. Not perfect (no IntersectionObserver-level
        clipping check) but good enough for the recorder's intent
        of "would the user actually click this".

        Return semantics:
          - `MatchInfo(t, v, a)` — verification ran cleanly. `t > 0`
            and the candidate gets classified + ranked; `t == 0`
            means the selector resolves to nothing live and the
            caller drops it.
          - `None` — verification COULDN'T RUN (frame detached after
            a navigation-triggering click, page closed mid-flight,
            transient browser-side error). The caller preserves the
            candidate at the tail of the list as unverified rather
            than dropping it, because the failure has nothing to do
            with whether the selector is good.
        """
        try:
            loc = frame_or_page.locator(c.value)
            # Bound the JS round-trip. Without a timeout, a click on
            # a page that's mid-navigation (or an iframe that just
            # detached) can leave `evaluate_all` hanging until the
            # default Playwright timeout — which is too long for an
            # interactive recorder where the user might click 10
            # things in 1 second. 1s is generous for a same-context
            # JS call but fails fast on detached frames.
            result = await asyncio.wait_for(loc.evaluate_all(
                """(els) => {
                    let visible = 0, actionable = 0;
                    for (const el of els) {
                        if (!el || !el.ownerDocument || !el.ownerDocument.defaultView) continue;
                        const style = el.ownerDocument.defaultView.getComputedStyle(el);
                        const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
                        const inFlow = el.offsetParent !== null
                            || (style && style.position === 'fixed');
                        const notHidden = !style
                            || (style.visibility !== 'hidden'
                                && style.display !== 'none');
                        const hasSize = !rect
                            || (rect.width > 0 && rect.height > 0);
                        if (inFlow && notHidden && hasSize) {
                            visible++;
                            const disabled = el.disabled === true
                                || el.getAttribute('aria-disabled') === 'true';
                            if (!disabled) actionable++;
                        }
                    }
                    return { total: els.length, visible, actionable };
                }""",
            ), timeout=1.0)
            if not isinstance(result, dict):
                # Defensive — Playwright returned something we
                # don't recognise. Treat as "couldn't verify"
                # rather than silently dropping the candidate.
                return None
            return MatchInfo(
                total=int(result.get("total", 0)),
                visible=int(result.get("visible", 0)),
                actionable=int(result.get("actionable", 0)),
            )
        except Exception:
            # Navigation / detached frame / closed page / invalid
            # selector — couldn't decide either way. Preserve the
            # candidate as unverified so a click on a link or a
            # cookie-banner-dismiss-which-removes-the-iframe doesn't
            # nuke every candidate the synthesis layer just produced.
            # The picker shows them without a green check and the
            # user can still pick the obvious one.
            return None

    verified = await verify_candidates(cmd.selector_candidates, _resolve)
    # Story RECORDER-FRAMES-2 — capture the iframe ancestry alongside
    # the inner-element verification. Done in the same async pass so
    # the iframe still exists in the parent DOM (best chance — the
    # banner-removes-itself flow only takes effect after the user's
    # original click handler runs to completion). Empty list for
    # top-frame events.
    frame_chain = await _capture_frame_chain(frame_or_page)
    # After re-sorting, index 0 is the best (verified > non-verified, then
    # quality_score desc). The original active index is meaningless now —
    # it referred to a position in the unsorted/un-pruned list. Resetting
    # to 0 also keeps the RecordedCommand validator happy when verify
    # dropped enough candidates that the old index would be out of range.
    #
    # CRITICAL: copy `id` over from the source `cmd`. Without it the
    # default factory mints a fresh id here and the one
    # `translate_payload` assigned is silently lost. Within a single
    # session the resulting chain (SSE → /save → .robot) is still
    # internally consistent because everything downstream sees the
    # NEW id, but it wastes an id and would confuse any future logic
    # that expects translate_payload's id to be authoritative
    # (e.g. correlating across logs).
    return RecordedCommand(
        id=cmd.id,
        index=cmd.index,
        keyword=cmd.keyword,
        args=cmd.args,
        selector_candidates=verified,
        active_candidate_index=0,
        element_fingerprint=cmd.element_fingerprint,
        frame_url=cmd.frame_url,
        frame_chain=frame_chain,
    )

# Per-session stop signal. The DELETE endpoint sets this; the recorder
# loop awaits it via `_wait_for_stop_event`.
_stop_signals: dict[int, threading.Event] = {}

# Story RECORDER-VIS-1 — session ids whose current stop is a *restart*
# request (the HTTP endpoint will dispatch a fresh task right after the
# current one tears down). The wrapper checks this in its post-loop
# branch and skips the COMPLETED/finalize_session bookkeeping so the
# queue stays alive for the new task and the SSE consumer never sees
# the end sentinel.
_restart_pending: set[int] = set()


async def _wait_for_stop_event(stop_event: threading.Event) -> None:
    """Async-friendly wait for a `threading.Event` to fire.

    `stop_event.wait()` is a blocking call. Running it in the asyncio
    event loop directly would freeze every other coroutine (most
    importantly the Playwright bindings that deliver capture events).
    Hand it off to the default thread-pool executor instead — the
    coroutine awaits the executor's future without blocking the loop,
    and returns the moment the event is set.

    Returns immediately if the event was already set when called
    (the wait() call detects the prior set state). Has no timeout —
    callers that need a deadline should wrap with
    `asyncio.wait_for(..., timeout)`.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, stop_event.wait)


def signal_stop_v2(session_id: int) -> bool:
    """Set the stop event for an active v2 recorder session. Returns True
    if a session was signalled, False if the id had no active task."""
    evt = _stop_signals.get(session_id)
    if evt is not None:
        evt.set()
        return True
    return False


def signal_restart_v2(session_id: int) -> bool:
    """Signal a restart: mark the session for a graceful tear-down WITHOUT
    finalisation (the queue + DB row stay live), then set the stop event.

    Returns False if no task is active for this session id — callers
    should then 409 or treat it as already-torn-down.
    """
    if session_id not in _stop_signals:
        return False
    _restart_pending.add(session_id)
    return signal_stop_v2(session_id)


def is_v2_session_active(session_id: int) -> bool:
    return session_id in _stop_signals


def run_v2_recorder_session(
    session_id: int,
    target_url: str | None = None,
    *,
    headless: bool = False,
    test_actions: Any = None,
) -> None:
    """Blocking entry point — dispatched via task_executor.dispatch_task.

    Marks the RecordingSession row RECORDING on start and CANCELLED /
    COMPLETED on stop. Any exception inside the Playwright loop flips
    the status to FAILED with the exception message captured.

    Test hooks (only used from the e2e integration test — production
    dispatch never passes them):
      headless     — launch Chromium headless (no window). Default False
                     so interactive recording keeps the visible window.
      test_actions — optional `async (page) -> None`. When given, runs
                     once right after the initial goto, then sets
                     stop_event so the task exits cleanly. Lets a pytest
                     drive scripted interactions through the real
                     capture pipeline.
    """
    stop_event = threading.Event()
    _stop_signals[session_id] = stop_event

    crashed = False
    try:
        asyncio.run(
            _recorder_loop(
                session_id, target_url, stop_event,
                headless=headless, test_actions=test_actions,
            )
        )
    except Exception as exc:
        crashed = True
        logger.exception("v2 recorder session %d crashed", session_id)
        # RECORDER-VIS-1 — surface the crash on the SSE stream so the
        # live view can render an error banner + Restart button before
        # the queue is torn down.
        enqueue_lifecycle(
            session_id,
            LifecycleEvent(phase="browser_crashed", message=str(exc) or None),
        )
        _mark_status(session_id, RecordingStatus.FAILED, message="recorder crashed")
    finally:
        _stop_signals.pop(session_id, None)
        # RECORDER-VIS-1 — if this stop was a restart request AND the
        # task exited cleanly, keep the queue + DB row alive so the
        # new task can resume seamlessly. Otherwise finalise normally
        # (existing W.2 contract). Always clear the restart flag so a
        # late call doesn't leak the entry.
        was_restart = session_id in _restart_pending
        _restart_pending.discard(session_id)
        if was_restart and not crashed:
            # Do NOT mark COMPLETED, do NOT push end-sentinel, do NOT
            # tear down the queue — the restart endpoint dispatches a
            # fresh task that will reuse all three.
            pass
        else:
            if not crashed:
                # Loop exited cleanly via user stop.
                _mark_status(session_id, RecordingStatus.COMPLETED)
            # The crash branch above already pushed `browser_crashed`
            # onto the queue; the end sentinel below then closes the
            # SSE stream cleanly.
            finalize_session(session_id)
            tear_down_session(session_id)


async def _recorder_loop(
    session_id: int,
    target_url: str | None,
    stop_event: threading.Event,
    *,
    headless: bool = False,
    test_actions: Any = None,
) -> None:
    # Deferred import — Playwright is a heavy optional dep.
    from playwright.async_api import async_playwright

    command_index = 0
    index_lock = threading.Lock()

    async def on_capture(source: Any, payload: dict[str, Any]) -> None:
        nonlocal command_index
        try:
            with index_lock:
                idx = command_index
                command_index += 1
            cmd = translate_payload(payload or {}, idx)
            if cmd is None:
                return
            # Story S.3 wire-up — verify candidate uniqueness against the
            # ORIGINATING FRAME, not the top page. iframe selectors only
            # resolve within their own document; using `source.page`
            # would falsely drop every iframe selector as 0-match.
            # The helper sorts by `(verified_unique desc, quality_score
            # desc)`, so the picker's first option is the best verified
            # candidate (or the best unverified one if none is unique).
            #
            # BUG-FIX (RECORDER-VERIFY-FRAME): Playwright's
            # `expose_binding` callback passes `source` as a
            # `dict(context=..., page=..., frame=...)` — NOT as an
            # object with `.frame`/`.page` attributes. The previous
            # `getattr(source, "frame", None)` therefore ALWAYS
            # returned None on production captures (dicts have keys,
            # not attributes), `_verify_command_candidates` then
            # short-circuited on `frame_or_page is None`, and every
            # recorded command landed with `verified_unique=False`
            # on every candidate — so the picker defaulted to
            # whatever ranked first by static heuristic, even when
            # it was non-unique against the live DOM. Use dict
            # access for the canonical case, keep getattr as a
            # fallback so legacy unit tests that pass fake objects
            # with `.frame` still work.
            frame = _resolve_frame_target(source)
            cmd = await _verify_command_candidates(cmd, frame)
            enqueue_command(session_id, cmd)
        except Exception:
            # Must NEVER raise — the binding handler runs on the Playwright
            # event loop and an exception would kill the whole session.
            logger.exception("v2 recorder capture handler failed")

    # RECORDER-VIS-1 — tell the live view we're spawning so the pill
    # leaves "connecting" before Chromium boot completes. Emitted from
    # the same thread as the wrapper so there is no race with the
    # consumer-side iterator already attached to this session id.
    enqueue_lifecycle(session_id, LifecycleEvent(phase="browser_starting"))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context()

        # Inject the three IIFE scripts. `add_init_script` runs on every
        # new document, surviving SPA nav + full reload (AR-4).
        await context.add_init_script(CAPTURE_SCRIPT)
        await context.add_init_script(OVERLAY_SCRIPT)
        await context.add_init_script(CONTEXT_MENU_SCRIPT)

        # Register the binding — scripts call window.__roboscopeCapture(payload).
        await context.expose_binding("__roboscopeCapture", on_capture)

        # RECORDER-1A: emit a `Switch Page    NEW` command whenever the
        # context acquires a new page (popup, target=_blank link,
        # `window.open`). The first page (created explicitly below) is
        # skipped — we don't want to record a Switch right after the
        # initial Go To.
        seen_first_page = {"value": False}

        async def _on_new_page(new_page: Any) -> None:
            if not seen_first_page["value"]:
                seen_first_page["value"] = True
                return
            try:
                # Wait briefly for the popup to start loading so the URL
                # we capture is meaningful (it usually starts as
                # about:blank and then navigates).
                try:
                    await new_page.wait_for_load_state("domcontentloaded", timeout=2000)
                except Exception:
                    pass
                url = new_page.url if hasattr(new_page, "url") else None
                await on_capture(None, {"kind": "switch_page", "url": url or ""})
            except Exception:
                logger.exception("v2 recorder: switch_page handler failed")

        context.on("page", lambda p: asyncio.create_task(_on_new_page(p)))

        page = await context.new_page()
        if target_url:
            try:
                await page.goto(target_url)
            except Exception:
                logger.warning("v2 recorder: initial goto(%s) failed", target_url, exc_info=True)

        # RECORDER-VIS-1 — at this point Chromium is up, the capture
        # scripts are injected, the binding is registered, and the
        # initial page is rendered. The user can click and see events
        # arrive. Flip the live-view pill to "browser ready".
        enqueue_lifecycle(session_id, LifecycleEvent(phase="browser_ready"))

        # Listener on browser disconnect → flip the stop event. Same
        # safety as Story R-1. If the disconnect is unexpected (user
        # closed the window, OS killed the process, …) the stop_event
        # wasn't set yet — RECORDER-VIS-1 turns that into an explicit
        # `browser_crashed` lifecycle event so the live view can offer
        # a Restart button.
        def _on_disconnect() -> None:
            if not stop_event.is_set():
                enqueue_lifecycle(
                    session_id,
                    LifecycleEvent(
                        phase="browser_crashed",
                        message="browser disconnected unexpectedly",
                    ),
                )
            stop_event.set()

        browser.on("disconnected", _on_disconnect)

        # Test hook — run scripted user actions through the real
        # capture pipeline, then signal stop so the loop exits cleanly.
        if test_actions is not None:
            try:
                await test_actions(page)
            except Exception:
                logger.exception("v2 recorder: test_actions raised")
            # Give the final batch of events a moment to flush through
            # the binding before we tear down.
            await asyncio.sleep(0.4)
            stop_event.set()

        # Block until `stop_event` fires (set by the user clicking
        # Stop, by the test hook, or by the browser-disconnect
        # listener above). The threading.Event.wait() runs in a
        # worker thread via `run_in_executor`, so it doesn't block
        # the asyncio event loop — Playwright bindings keep
        # delivering events while we wait. A previous version
        # busy-polled at 1 Hz, which made stop latency up to a full
        # second after the click; for an interactive recorder
        # that's "did my click register?" UX. Event-driven wait is
        # instantaneous (the executor returns the moment the event
        # is set).
        await _wait_for_stop_event(stop_event)

        try:
            await context.close()
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass

    # NOTE: terminal status update (COMPLETED) moved to the wrapper
    # `run_v2_recorder_session` so it can distinguish stop-for-restart
    # from real stop. See the RECORDER-VIS-1 changes above.


def _mark_status(session_id: int, status: str, message: str | None = None) -> None:
    """Flip the RecordingSession row to a terminal status from the task
    thread. Fresh DB session — must never reuse the caller's."""
    try:
        with get_sync_session() as db:
            row = db.get(RecordingSession, session_id)
            if row is None:
                return
            row.status = status
            if message:
                row.error_message = message[:2000]
            from datetime import datetime, timezone
            row.finished_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        logger.exception("v2 recorder: failed to mark session %d as %s", session_id, status)
