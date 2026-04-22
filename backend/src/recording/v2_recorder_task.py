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
    enqueue_command,
    finalize_session,
    tear_down_session,
)
from src.recording.v2_payload_translator import translate_payload

logger = logging.getLogger("roboscope.recording.v2_recorder")

# Per-session stop signal. The DELETE endpoint sets this; the recorder
# loop polls it every heartbeat.
_stop_signals: dict[int, threading.Event] = {}


def signal_stop_v2(session_id: int) -> bool:
    """Set the stop event for an active v2 recorder session. Returns True
    if a session was signalled, False if the id had no active task."""
    evt = _stop_signals.get(session_id)
    if evt is not None:
        evt.set()
        return True
    return False


def is_v2_session_active(session_id: int) -> bool:
    return session_id in _stop_signals


def run_v2_recorder_session(session_id: int, target_url: str | None = None) -> None:
    """Blocking entry point — dispatched via task_executor.dispatch_task.

    Marks the RecordingSession row RECORDING on start and CANCELLED /
    COMPLETED on stop. Any exception inside the Playwright loop flips
    the status to FAILED with the exception message captured.
    """
    stop_event = threading.Event()
    _stop_signals[session_id] = stop_event

    try:
        asyncio.run(_recorder_loop(session_id, target_url, stop_event))
    except Exception:
        logger.exception("v2 recorder session %d crashed", session_id)
        _mark_status(session_id, RecordingStatus.FAILED, message="recorder crashed")
    finally:
        _stop_signals.pop(session_id, None)
        # Ensure the SSE subscriber wakes up and the queue is cleaned.
        finalize_session(session_id)
        tear_down_session(session_id)


async def _recorder_loop(
    session_id: int,
    target_url: str | None,
    stop_event: threading.Event,
) -> None:
    # Deferred import — Playwright is a heavy optional dep.
    from playwright.async_api import async_playwright

    command_index = 0
    index_lock = threading.Lock()

    async def on_capture(source: Any, payload: dict[str, Any]) -> None:  # noqa: ARG001
        nonlocal command_index
        try:
            with index_lock:
                idx = command_index
                command_index += 1
            cmd = translate_payload(payload or {}, idx)
            if cmd is None:
                return
            enqueue_command(session_id, cmd)
        except Exception:
            # Must NEVER raise — the binding handler runs on the Playwright
            # event loop and an exception would kill the whole session.
            logger.exception("v2 recorder capture handler failed")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()

        # Inject the three IIFE scripts. `add_init_script` runs on every
        # new document, surviving SPA nav + full reload (AR-4).
        await context.add_init_script(CAPTURE_SCRIPT)
        await context.add_init_script(OVERLAY_SCRIPT)
        await context.add_init_script(CONTEXT_MENU_SCRIPT)

        # Register the binding — scripts call window.__roboscopeCapture(payload).
        await context.expose_binding("__roboscopeCapture", on_capture)

        page = await context.new_page()
        if target_url:
            try:
                await page.goto(target_url)
            except Exception:
                logger.warning("v2 recorder: initial goto(%s) failed", target_url, exc_info=True)

        # Listener on browser disconnect → flip the stop event. Same
        # safety as Story R-1.
        def _on_disconnect() -> None:
            stop_event.set()

        browser.on("disconnected", _on_disconnect)

        # Loop: wait for stop_event to be set, polling at 1 Hz.
        while not stop_event.is_set():
            await asyncio.sleep(1.0)

        try:
            await context.close()
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass

    _mark_status(session_id, RecordingStatus.COMPLETED)


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
