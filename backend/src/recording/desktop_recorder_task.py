"""Story D.1 + D.2 — Windows desktop recorder task (skeleton).

Mirrors the web `v2_recorder_task.py` shape: a dedicated thread entry
point that drives the Windows UI Automation capture via pywinauto. The
pure-Python translator `translate_uia_event` is isolated so it can be
unit-tested on any host; the pywinauto import is deferred into the
entry point so macOS / Linux dev machines can still import this module.

Epic D implementation status (as of this commit):
  D.1 session adapter  — skeleton + threading + import guard.
  D.2 primitive capture — translator pure fn tested; the actual
                          pywinauto event hook wiring lives in
                          `_desktop_loop` and requires a Windows host
                          to be exercised.
  D.3 selector synthesis — shipped separately (desktop_selector_synthesis).
  D.4 RPA.Windows emit   — shipped separately (robot_emit dispatch).
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Any

# FK resolution for fresh background-thread DB sessions (CLAUDE.md).
import src.auth.models  # noqa: F401
import src.repos.models  # noqa: F401

from src.recording.desktop_selector_synthesis import (
    DesktopAncestor,
    DesktopElementSnapshot,
    synthesise_desktop_selectors,
)
from src.recording.models import RecordingSession, RecordingStatus
from src.recording.selector_schema import RecordedCommand
from src.recording.v2_command_queue import (
    enqueue_command,
    finalize_session,
    tear_down_session,
)

logger = logging.getLogger("roboscope.recording.desktop_recorder")

# Per-session stop signal — same registry shape as the web task.
_stop_signals: dict[int, threading.Event] = {}


def signal_stop_desktop(session_id: int) -> bool:
    evt = _stop_signals.get(session_id)
    if evt is not None:
        evt.set()
        return True
    return False


def is_desktop_session_active(session_id: int) -> bool:
    return session_id in _stop_signals


# ---------------------------------------------------------------------------
# Translator — pure function, testable on any OS.
# ---------------------------------------------------------------------------


_UIA_KIND_TO_KEYWORD: dict[str, str] = {
    "click": "Click",
    "dblclick": "Double Click",
    "type": "Type Text",
    "combobox_select": "Select From Combobox",
    "menu_select": "Select From Menu",
    "window_focus": "Control Window",
}


def _element_from_uia_payload(raw: dict[str, Any] | None) -> DesktopElementSnapshot | None:
    if not raw:
        return None
    ancestors = [
        DesktopAncestor(
            control_type=a.get("control_type", ""),
            automation_id=a.get("automation_id"),
            name=a.get("name"),
        )
        for a in (raw.get("ancestors") or [])
    ]
    return DesktopElementSnapshot(
        control_type=raw.get("control_type", ""),
        automation_id=raw.get("automation_id"),
        name=raw.get("name"),
        class_name=raw.get("class_name"),
        ancestors=ancestors,
    )


def translate_uia_event(payload: dict[str, Any], index: int) -> RecordedCommand | None:
    """Return a RecordedCommand for a captured UIA event, or None.

    Payload shape (produced by the hook in `_desktop_loop`):

        {
          "kind": "click" | "type" | "combobox_select" | ...,
          "element": {control_type, automation_id, name, class_name,
                      ancestors: [{control_type, automation_id, name}]},
          "text" | "value": <str>   # keyword-specific
        }
    """
    kind = payload.get("kind")
    if not isinstance(kind, str) or kind not in _UIA_KIND_TO_KEYWORD:
        return None

    keyword = _UIA_KIND_TO_KEYWORD[kind]
    el = _element_from_uia_payload(payload.get("element"))
    candidates = synthesise_desktop_selectors(el) if el else []

    args: dict[str, Any] = {}
    if kind == "type":
        text = payload.get("text")
        if isinstance(text, str):
            args["text"] = text
    elif kind in ("combobox_select", "menu_select"):
        value = payload.get("value")
        if isinstance(value, str):
            args["value"] = value

    return RecordedCommand(
        index=index,
        keyword=keyword,
        args=args,
        selector_candidates=candidates,
        active_candidate_index=0,
    )


# ---------------------------------------------------------------------------
# Entry point — blocking, dispatched via task_executor.
# ---------------------------------------------------------------------------


def run_desktop_recorder_session(session_id: int) -> None:
    """Start the Windows recorder for a session. No-ops on non-Windows
    hosts so this codepath is importable everywhere."""
    if not sys.platform.startswith("win"):
        logger.warning(
            "desktop_windows recorder dispatched on non-Windows host — "
            "no-op for session %d", session_id,
        )
        _mark_status(session_id, RecordingStatus.FAILED, "desktop recorder requires Windows")
        finalize_session(session_id)
        tear_down_session(session_id)
        return

    stop_event = threading.Event()
    _stop_signals[session_id] = stop_event

    try:
        _desktop_loop(session_id, stop_event)
    except Exception:
        logger.exception("desktop recorder session %d crashed", session_id)
        _mark_status(session_id, RecordingStatus.FAILED, "recorder crashed")
    finally:
        _stop_signals.pop(session_id, None)
        finalize_session(session_id)
        tear_down_session(session_id)


def _desktop_loop(session_id: int, stop_event: threading.Event) -> None:
    """Windows UIA capture loop. Deferred pywinauto import — lives here so
    the module can be imported on non-Windows hosts (unit tests).

    The actual event-hook wiring is a D.1 full follow-up — this skeleton
    polls the stop event and emits nothing so the session ends cleanly.
    """
    # Deferred import — raises only when actually called on Windows.
    try:
        import pywinauto  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "pywinauto is not installed; add it to the Windows-optional "
            "dependency group before dispatching the desktop recorder"
        ) from exc

    command_index = 0

    def enqueue(payload: dict[str, Any]) -> None:
        nonlocal command_index
        try:
            cmd = translate_uia_event(payload, command_index)
            if cmd is None:
                return
            command_index += 1
            enqueue_command(session_id, cmd)
        except Exception:
            logger.exception("desktop recorder translate failed")

    # TODO(D.1 full): attach pywinauto InputEventHandler hooks that call
    # `enqueue(...)`. Until then, the loop just waits for the stop event.
    # This keeps the thread lifecycle correct (create/destroy) while the
    # hook wiring is a separate PR that needs a Windows dev host.

    while not stop_event.is_set():
        stop_event.wait(timeout=0.5)

    _mark_status(session_id, RecordingStatus.COMPLETED)


def _mark_status(session_id: int, status: str, message: str | None = None) -> None:
    from datetime import datetime, timezone

    from src.database import get_sync_session

    try:
        with get_sync_session() as db:
            row = db.get(RecordingSession, session_id)
            if row is None:
                return
            row.status = status
            if message:
                row.error_message = message[:2000]
            row.finished_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        logger.exception(
            "desktop recorder: failed to mark session %d as %s", session_id, status
        )
