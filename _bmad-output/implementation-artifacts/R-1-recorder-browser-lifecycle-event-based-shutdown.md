# Story R.1: Recorder — event-based browser lifecycle (stop false-positives on navigation)

Status: review

Epic: R — Recorder Stability (out-of-band, not part of Phase 4)
Story Key: `R-1-recorder-browser-lifecycle-event-based-shutdown`

## Problem statement

`run_playwright_recorder()` in `backend/src/recording/tasks.py:201-209` polls the
headed Chromium session by calling `page.evaluate("1")` every 500 ms to detect
whether the user closed the window:

```python
while not stop_event.is_set():
    try:
        page.evaluate("1")
    except Exception:                                # too broad
        logger.info("... browser window closed by user")
        break
    stop_event.wait(timeout=0.5)
```

`page.evaluate()` **raises transiently** while a page is navigating — Playwright
throws `Error: Execution context was destroyed, most likely because of a
navigation`, `Target closed`, or `frame was detached` during the short window
between `framenavigated` and the new execution context being ready.

Because the `except Exception` clause does not differentiate, **any
navigation-triggered transient is interpreted as "user closed the browser"**.
The loop breaks, `finally` calls `browser.close()`, and the real browser
window is torn down under the user's feet. Observed symptoms match exactly:

> *"Der Browser schließt sich nach einer gewissen Zeit. Manchmal nach der
>  URL-Eingabe, manchmal auch später."*

— i.e., whenever the 500 ms tick happens to fall inside a navigation window.

## Story

As a QA engineer recording a Robot-Framework test,
I want the recorder browser to stay open while I navigate between pages,
so that I can record multi-page flows without the window closing on me mid-recording.

## Acceptance Criteria

1. **AC1 — Navigation does not trigger shutdown.** When `page.goto(url)` or a
   user-initiated URL entry in the address bar fires a `framenavigated` event,
   the recorder MUST continue running. No `browser.close()` is called in
   response to navigation transients. Verified by a unit test that
   simulates a transient `Error: Execution context was destroyed, most likely
   because of a navigation` raised from the liveness probe and asserts the
   loop does not exit.

2. **AC2 — Event-based shutdown detection.** The 500 ms `page.evaluate("1")`
   polling loop is replaced by event listeners on the browser and the page:
   - `browser.on("disconnected", …)` sets the stop event.
   - `page.on("close", …)` sets the stop event.

   The main loop becomes a pure `stop_event.wait(timeout=…)` with no liveness
   probe at all. The `except Exception → break` construct is removed.

3. **AC3 — Explicit stop signal still works.** `signal_stop_playwright(id)`
   continues to work exactly as before: sets the `threading.Event`, the loop
   exits, `finally` closes the browser. Existing callers of the stop API are
   unchanged. Verified by a unit test that signals stop and asserts the
   recorder shuts down cleanly.

4. **AC4 — Clean shutdown when user really does close the window.** When the
   user clicks the red close button on the Chromium window, the
   `browser.on("disconnected")` listener fires, the stop event is set, the
   loop exits, and the recorder transitions to status `COMPLETED` (followed
   by `generate_robot_for_recording()`). No `FAILED` status, no traceback
   logged at `ERROR` level — only an `INFO` "browser window closed by user"
   line. Verified by a unit test that triggers the disconnect listener and
   asserts the final DB row status.

5. **AC5 — Navigation event capture is robust.** The existing
   `page.on("framenavigated", _on_navigate)` handler re-evaluates the
   capture script on the new frame context via `frame.evaluate(_CAPTURE_JS)`.
   This call is already wrapped in `try/except` (good) — the story adds a
   log line at `DEBUG` level when re-injection fails, so future navigation
   issues can be debugged without raising log verbosity globally.

6. **AC6 — No regression of existing recording-module tests.** All tests in
   `backend/tests/recording/` continue to pass (`pytest backend/tests/recording/`).

## Tasks / Subtasks

### Task 1: Replace polling with event listeners (AC1, AC2, AC4)

- [x] MOD `backend/src/recording/tasks.py` — in `run_playwright_recorder`:
  - After `browser = pw.chromium.launch(headless=False)` and
    `page = context.new_page()`, register two listeners that both set the
    same `stop_event`:
    ```python
    browser.on("disconnected", lambda: stop_event.set())
    page.on("close", lambda _page: stop_event.set())
    ```
  - Replace the `while not stop_event.is_set(): try: page.evaluate("1") …`
    block with a single `stop_event.wait()` (no timeout — the listeners
    guarantee the event will be set; an optional timeout arg is acceptable
    if we want to keep the loop responsive to future extensions).
  - Remove the `except Exception → break` construct entirely. Transient
    navigation errors now never reach this code path.
  - Keep the existing `try / except Exception as e: logger.exception(...)`
    outer block — it still handles genuine launch failures (Playwright
    install missing, Chromium binary not found, etc.).

### Task 2: Logging cleanup (AC5)

- [x] MOD `backend/src/recording/tasks.py` — in the `_on_navigate` handler:
  - Replace the bare `except Exception: pass` with
    `except Exception: logger.debug("Recording %d: capture re-injection after navigation failed", recording_id, exc_info=True)`.
  - Add an INFO log at the `disconnected` listener firing path to preserve
    the existing "browser window closed by user" signal.

### Task 3: Unit tests (AC1, AC3, AC4, AC6)

- [x] NEW `backend/tests/recording/test_tasks.py` — unit tests that patch
  `playwright.sync_api.sync_playwright` with a `MagicMock` to drive the
  listener callbacks synchronously:
  - `test_navigation_transient_does_not_stop_recorder`: simulate a
    `framenavigated` event; assert the recorder is still running (stop
    event not set, browser.close not yet called).
  - `test_browser_disconnect_event_stops_recorder`: fire the
    `"disconnected"` listener; assert the loop exits, recording is
    marked COMPLETED, and `browser.close()` is called exactly once.
  - `test_page_close_event_stops_recorder`: fire the `"close"` listener;
    assert the loop exits.
  - `test_signal_stop_playwright_still_works`: call
    `signal_stop_playwright(id)` while the recorder thread is running;
    assert the loop exits.
  - Use `threading.Thread(target=run_playwright_recorder, ...)` with a
    short join timeout; drive the lifecycle via the mocked listeners.

### Task 4: Smoke regression (AC6)

- [x] Run `.venv/bin/python -m pytest backend/tests/recording/ -v` —
  all 49 tests pass (45 pre-existing + 4 new).

## Non-goals

- Re-architecting the recorder to use async Playwright (the
  ThreadPoolExecutor + sync_playwright pattern is intentional for Phase 3).
- Any change to the event-capture JS or the CDP binding mechanism.
- Any frontend change — the WebSocket status broadcasts are unchanged.

## Dev Notes

- **Playwright sync-API threading caveat**: `browser.on("disconnected", …)`
  callbacks are dispatched on the Playwright event thread, **not** on the
  thread that created the browser. Setting a `threading.Event` from a
  listener is safe (threading.Event is thread-safe); calling any other
  Playwright sync API from the listener is NOT safe and would deadlock.
  Keep listeners to `stop_event.set()` + optional `logger.info`.

- **No `await` needed**: the listeners are fire-and-forget; the main thread
  simply waits on the event.

- **Why `stop_event.wait(timeout=...)` instead of `stop_event.wait()`**:
  keeping a small timeout (e.g. 5 s) lets us add future periodic hooks
  (heartbeat broadcasts, memory-pressure checks) without another refactor.
  Not load-bearing for the fix itself.
