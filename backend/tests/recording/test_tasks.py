"""Tests for recording background tasks — browser-lifecycle event handling.

Story R-1: the recorder must no longer polled `page.evaluate("1")` as a
liveness check. Navigation-transient errors were false-positiving as
"browser closed by user", tearing down the real session under the user's
feet. These tests lock in the event-based shutdown contract.
"""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.recording.models import RecordingSession, RecordingStatus, RecordingSource
from src.recording.tasks import (
    run_playwright_recorder,
    signal_stop_playwright,
)
from src.repos.models import Repository


@pytest.fixture
def recording_id(db_session: Session, admin_user) -> int:
    """Create a PENDING recording row and return its id."""
    repo = Repository(
        name="tasks-test-repo",
        git_url="https://github.com/test/tasks-repo.git",
        default_branch="main",
        local_path="/tmp/repos/tasks-repo",
        created_by=admin_user.id,
    )
    db_session.add(repo)
    db_session.flush()

    rec = RecordingSession(
        repository_id=repo.id,
        triggered_by=admin_user.id,
        source=RecordingSource.PLAYWRIGHT,
        target_library="Browser",
        status=RecordingStatus.PENDING,
    )
    db_session.add(rec)
    db_session.commit()
    return rec.id


class _FakeListeners:
    """Collects event-listener callbacks registered via `.on(event, cb)`."""

    def __init__(self) -> None:
        self.by_event: dict[str, list[Any]] = {}

    def on(self, event: str, callback: Any) -> None:
        self.by_event.setdefault(event, []).append(callback)

    def fire(self, event: str, *args: Any) -> None:
        for cb in self.by_event.get(event, []):
            cb(*args)


def _build_fake_playwright() -> tuple[MagicMock, _FakeListeners, _FakeListeners]:
    """Construct a `sync_playwright()` mock wired with listener collectors.

    Returns (sync_playwright_mock, browser_listeners, page_listeners).
    """
    browser_listeners = _FakeListeners()
    page_listeners = _FakeListeners()

    page = MagicMock(name="page")
    page.on.side_effect = page_listeners.on
    page.main_frame = MagicMock(name="main_frame")
    page.evaluate.return_value = None
    page.goto.return_value = None

    context = MagicMock(name="context")
    context.new_page.return_value = page
    # new_cdp_session needs .on and .send to be harmless no-ops.
    cdp = MagicMock(name="cdp")
    cdp.on.return_value = None
    cdp.send.return_value = None
    context.new_cdp_session.return_value = cdp
    context.add_init_script.return_value = None

    browser = MagicMock(name="browser")
    browser.new_context.return_value = context
    browser.on.side_effect = browser_listeners.on
    browser.close.return_value = None

    chromium = MagicMock(name="chromium")
    chromium.launch.return_value = browser

    pw_instance = MagicMock(name="pw_instance")
    pw_instance.chromium = chromium
    pw_instance.stop.return_value = None

    sync_pw = MagicMock(name="sync_playwright")
    sync_pw.return_value.start.return_value = pw_instance

    return sync_pw, browser_listeners, page_listeners, browser


def _run_in_thread(recording_id: int) -> threading.Thread:
    """Start the recorder in a background thread so tests can drive events."""
    t = threading.Thread(
        target=run_playwright_recorder,
        args=(recording_id,),
        daemon=True,
    )
    t.start()
    return t


def _wait_for_registration(listeners: _FakeListeners, event: str, timeout: float = 2.0) -> None:
    """Spin-wait until the recorder thread has registered the given listener."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if event in listeners.by_event:
            return
        time.sleep(0.01)
    raise AssertionError(f"Listener for {event!r} was never registered")


class TestBrowserLifecycle:

    def test_browser_disconnect_event_stops_recorder(self, recording_id: int) -> None:
        """AC4: browser 'disconnected' → stop event set → loop exits cleanly."""
        sync_pw, browser_listeners, _page_listeners, browser = _build_fake_playwright()

        with (
            patch("playwright.sync_api.sync_playwright", sync_pw),
            patch("src.recording.tasks._broadcast_recording_status"),
            patch("src.recording.tasks._broadcast_recording_event"),
            patch(
                "src.recording.tasks.generate_robot_for_recording"
            ) as mock_generate,
        ):
            thread = _run_in_thread(recording_id)
            _wait_for_registration(browser_listeners, "disconnected")

            # Simulate the user closing the Chromium window.
            browser_listeners.fire("disconnected")

            thread.join(timeout=5.0)
            assert not thread.is_alive(), "recorder thread did not exit after disconnect"

            # finally-block closed the browser exactly once.
            browser.close.assert_called_once()
            # Post-loop: generate_robot_for_recording is invoked.
            mock_generate.assert_called_once_with(recording_id)

    def test_page_close_event_stops_recorder(self, recording_id: int) -> None:
        """AC2: page 'close' listener fires → stop event set → loop exits."""
        sync_pw, _browser_listeners, page_listeners, browser = _build_fake_playwright()

        with (
            patch("playwright.sync_api.sync_playwright", sync_pw),
            patch("src.recording.tasks._broadcast_recording_status"),
            patch("src.recording.tasks._broadcast_recording_event"),
            patch("src.recording.tasks.generate_robot_for_recording"),
        ):
            thread = _run_in_thread(recording_id)
            _wait_for_registration(page_listeners, "close")

            # Simulate the user clicking the tab's X button.
            page_listeners.fire("close", MagicMock(name="page_arg"))

            thread.join(timeout=5.0)
            assert not thread.is_alive()
            browser.close.assert_called_once()

    def test_signal_stop_still_works(self, recording_id: int) -> None:
        """AC3: signal_stop_playwright sets the same event and exits cleanly."""
        sync_pw, browser_listeners, _page_listeners, browser = _build_fake_playwright()

        with (
            patch("playwright.sync_api.sync_playwright", sync_pw),
            patch("src.recording.tasks._broadcast_recording_status"),
            patch("src.recording.tasks._broadcast_recording_event"),
            patch("src.recording.tasks.generate_robot_for_recording"),
        ):
            thread = _run_in_thread(recording_id)
            # Wait until the recorder is fully initialized (listeners registered).
            _wait_for_registration(browser_listeners, "disconnected")

            assert signal_stop_playwright(recording_id) is True

            thread.join(timeout=5.0)
            assert not thread.is_alive()
            browser.close.assert_called_once()

    def test_navigation_transient_does_not_stop_recorder(
        self, recording_id: int
    ) -> None:
        """AC1: transient navigation errors no longer tear down the session.

        The old code polled `page.evaluate("1")` every 500 ms and treated
        *any* exception as "browser closed". We assert the new implementation
        never calls `page.evaluate()` in the wait loop — there is nothing
        that could false-positive on a navigation transient.
        """
        sync_pw, browser_listeners, _page_listeners, browser = _build_fake_playwright()

        # Poison page.evaluate so that any call after setup raises. If the
        # shutdown loop still touches it, the test fails with that error.
        call_log: list[str] = []

        def _evaluate_side_effect(*_args: Any, **_kwargs: Any) -> None:
            call_log.append("evaluate")
            return None

        # Extract page off the chain so we can control its behavior.
        pw_instance = sync_pw.return_value.start.return_value
        page = pw_instance.chromium.launch.return_value.new_context.return_value.new_page.return_value
        page.evaluate.side_effect = _evaluate_side_effect

        with (
            patch("playwright.sync_api.sync_playwright", sync_pw),
            patch("src.recording.tasks._broadcast_recording_status"),
            patch("src.recording.tasks._broadcast_recording_event"),
            patch("src.recording.tasks.generate_robot_for_recording"),
        ):
            thread = _run_in_thread(recording_id)
            _wait_for_registration(browser_listeners, "disconnected")

            # Count evaluate calls after startup, then sleep longer than the
            # old 500 ms poll cadence. If the new loop still polls, more
            # calls will accumulate.
            baseline = len(call_log)
            time.sleep(1.5)
            after_idle = len(call_log)

            # Tear down via the disconnect listener so the thread can join.
            browser_listeners.fire("disconnected")
            thread.join(timeout=5.0)

        assert after_idle == baseline, (
            f"page.evaluate was called {after_idle - baseline} times during "
            "idle wait — the shutdown loop must not poll."
        )
