"""Background tasks for browser recording."""

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone

# Import all models so SQLAlchemy can resolve foreign keys.
import src.auth.models  # noqa: F401
import src.repos.models  # noqa: F401

from src.database import get_sync_session
from src.recording.generator import generate_robot_file
from src.recording.models import RecordingSession, RecordingStatus

logger = logging.getLogger("roboscope.recording.tasks")

# Active Playwright recorder sessions: recording_id → threading.Event (set to stop)
_stop_signals: dict[int, threading.Event] = {}


def _broadcast_recording_status(recording_id: int, status: str, **extra) -> None:
    """Broadcast a recording status change from a sync background thread."""
    from src.websocket.manager import ws_manager
    from src.main import _event_loop

    coro = ws_manager.broadcast_recording_status(recording_id, status, **extra)

    if _event_loop and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, _event_loop)
    else:
        logger.warning(
            "No event loop available to broadcast recording %d status", recording_id
        )


def _broadcast_recording_event(recording_id: int, event_data: dict) -> None:
    """Broadcast a recorded event to WebSocket listeners."""
    from src.websocket.manager import ws_manager
    from src.main import _event_loop

    coro = ws_manager.broadcast_recording_event(recording_id, event_data)

    if _event_loop and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, _event_loop)
    else:
        logger.warning(
            "No event loop available to broadcast recording %d event", recording_id
        )


def signal_stop_playwright(recording_id: int) -> bool:
    """Signal a running Playwright recorder to stop. Returns True if signal was sent."""
    evt = _stop_signals.get(recording_id)
    if evt:
        evt.set()
        return True
    return False


def run_playwright_recorder(recording_id: int, target_url: str | None = None) -> None:
    """Background task: open a headed Playwright browser and capture interactions.

    Runs in the ThreadPoolExecutor. Blocks until the user closes the browser
    or stop is signalled via signal_stop_playwright().
    """
    from playwright.sync_api import sync_playwright

    stop_event = threading.Event()
    _stop_signals[recording_id] = stop_event

    with get_sync_session() as session:
        recording = session.get(RecordingSession, recording_id)
        if not recording:
            logger.error("Recording %d not found", recording_id)
            _stop_signals.pop(recording_id, None)
            return

        recording.status = RecordingStatus.RECORDING
        recording.started_at = datetime.now(timezone.utc)
        session.commit()
        _broadcast_recording_status(recording_id, RecordingStatus.RECORDING)

    pw = None
    browser = None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        def _store_event(event_data: dict) -> None:
            """Append event to DB and broadcast via WebSocket."""
            with get_sync_session() as s:
                rec = s.get(RecordingSession, recording_id)
                if not rec or rec.status != RecordingStatus.RECORDING:
                    return
                events = json.loads(rec.events_json) if rec.events_json else []
                events.append(event_data)
                rec.events_json = json.dumps(events)
                rec.event_count = len(events)
                s.commit()
            _broadcast_recording_event(recording_id, event_data)

        # --- Hook CDP events for click/input capture ---
        client = context.new_cdp_session(page)

        def _on_dom_event(params: dict) -> None:
            """Handle DOM events from CDP Runtime.bindingCalled."""
            try:
                payload = json.loads(params.get("payload", "{}"))
                _store_event(payload)
            except Exception:
                logger.debug("Failed to parse CDP binding payload", exc_info=True)

        client.on("Runtime.bindingCalled", _on_dom_event)
        client.send("Runtime.addBinding", {"name": "__roboscope_event"})

        # Inject event capture script into every frame
        _CAPTURE_JS = """
        (() => {
            if (window.__roboscope_attached) return;
            window.__roboscope_attached = true;

            function selector(el) {
                if (el.id) return '#' + CSS.escape(el.id);
                if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
                if (el.getAttribute && el.getAttribute('data-testid'))
                    return '[data-testid="' + el.getAttribute('data-testid') + '"]';
                const tag = el.tagName.toLowerCase();
                const text = (el.textContent || '').trim().slice(0, 30);
                if (text && ['button', 'a', 'label'].includes(tag))
                    return tag + ':has-text("' + text.replace(/"/g, '\\\\"') + '")';
                return tag;
            }

            document.addEventListener('click', (e) => {
                const el = e.target;
                window.__roboscope_event(JSON.stringify({
                    event_type: 'click',
                    selector: selector(el),
                    tag: el.tagName.toLowerCase(),
                    url: location.href,
                    timestamp: Date.now() / 1000
                }));
            }, true);

            document.addEventListener('change', (e) => {
                const el = e.target;
                const isPassword = el.type === 'password';
                const isCheckbox = el.type === 'checkbox' || el.type === 'radio';
                const isSelect = el.tagName.toLowerCase() === 'select';
                let eventType = 'input';
                if (isPassword) eventType = 'password';
                else if (isCheckbox) eventType = 'checkbox';
                else if (isSelect) eventType = 'select';

                window.__roboscope_event(JSON.stringify({
                    event_type: eventType,
                    selector: selector(el),
                    value: isPassword ? '' : (el.value || ''),
                    tag: el.tagName.toLowerCase(),
                    url: location.href,
                    timestamp: Date.now() / 1000
                }));
            }, true);
        })();
        """

        context.add_init_script(_CAPTURE_JS)
        page.evaluate(_CAPTURE_JS)

        # Hook navigation events
        def _on_navigate(frame) -> None:
            if frame == page.main_frame:
                _store_event({
                    "event_type": "navigate",
                    "url": frame.url,
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                })
                # Re-inject capture script after navigation
                try:
                    frame.evaluate(_CAPTURE_JS)
                except Exception:
                    pass

        page.on("framenavigated", _on_navigate)

        # Navigate to target URL if provided
        if target_url:
            page.goto(target_url)
            _store_event({
                "event_type": "navigate",
                "url": target_url,
                "timestamp": datetime.now(timezone.utc).timestamp(),
            })

        logger.info("Recording %d: Playwright browser opened", recording_id)

        # Block until stop signal or browser closed
        while not stop_event.is_set():
            try:
                # Check if browser is still open (page.url throws if closed)
                page.evaluate("1")
            except Exception:
                logger.info("Recording %d: browser window closed by user", recording_id)
                break
            stop_event.wait(timeout=0.5)

    except Exception as e:
        logger.exception("Recording %d: Playwright recorder failed", recording_id)
        with get_sync_session() as session:
            recording = session.get(RecordingSession, recording_id)
            if recording:
                recording.status = RecordingStatus.FAILED
                recording.error_message = str(e)[:2000]
                recording.finished_at = datetime.now(timezone.utc)
                session.commit()
        _broadcast_recording_status(recording_id, RecordingStatus.FAILED)
        return
    finally:
        _stop_signals.pop(recording_id, None)
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if pw:
            try:
                pw.stop()
            except Exception:
                pass

    # Recording finished — generate .robot file
    generate_robot_for_recording(recording_id)


def generate_robot_for_recording(recording_id: int) -> None:
    """Background task: generate .robot file from recorded events.

    This runs in the ThreadPoolExecutor after a recording is stopped.
    """
    with get_sync_session() as session:
        recording = session.get(RecordingSession, recording_id)
        if not recording:
            logger.error("Recording %d not found", recording_id)
            return

        try:
            recording.status = RecordingStatus.PROCESSING
            session.commit()
            _broadcast_recording_status(recording_id, RecordingStatus.PROCESSING)

            # Generate .robot file
            robot_content = generate_robot_file(
                events_json=recording.events_json or "[]",
                target_library=recording.target_library,
                target_url=recording.target_url,
            )

            recording.generated_robot = robot_content
            recording.status = RecordingStatus.COMPLETED
            if not recording.finished_at:
                recording.finished_at = datetime.now(timezone.utc)
            session.commit()

            _broadcast_recording_status(recording_id, RecordingStatus.COMPLETED)
            logger.info(
                "Recording %d: generated .robot (%d lines)",
                recording_id,
                robot_content.count("\n") + 1,
            )

        except Exception as e:
            logger.exception("Recording %d: generation failed", recording_id)
            recording.status = RecordingStatus.FAILED
            recording.error_message = str(e)[:2000]
            if not recording.finished_at:
                recording.finished_at = datetime.now(timezone.utc)
            session.commit()
            _broadcast_recording_status(recording_id, RecordingStatus.FAILED)
