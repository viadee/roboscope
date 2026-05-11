# Story RECORDER-VIS-1: Recorder lifecycle visibility + restart-browser

Status: ready-for-dev

Epic: RECORDER-VIS — Make the recorder's runtime state visible
Story Key: `recorder-vis-1-lifecycle-events-and-restart`

## Reasoning

Clicking *Start Recording* today moves the user to `RecordingLiveView`
with `streamState = 'connecting'` and stays there silently — sometimes
for seconds, sometimes forever — while a background asyncio task in
`v2_recorder_task.py` boots Playwright + Chromium. If the spawn
crashes silently (missing DISPLAY on a Linux server, Playwright wheel
not initialised, blocked port), the user has zero diagnostic and
ends up reaching for the launcher's "Reset stuck recordings" button
they don't know exists.

This story adds an explicit lifecycle SSE channel and a
*Restart browser* control, so the user always knows whether the
recorder is starting, ready, idle-with-no-clicks, or crashed — and
can recover the browser without losing already-captured commands.

## Change

### Backend

`backend/src/recording/v2_command_queue.py` — generalise to carry a
heterogeneous stream of `RecordedCommand` and a new
`LifecycleEvent`:

```python
@dataclass
class LifecycleEvent:
    phase: Literal['browser_starting', 'browser_ready',
                   'browser_crashed', 'browser_restarting']
    ts: float                 # epoch seconds, captured at enqueue
    message: str | None       # short human-readable detail (errors)
```

- `enqueue_lifecycle(session_id, event)` — peer of
  `enqueue_command`, same drop-on-missing-queue contract.
- `iterate_events(session_id, ...)` replaces / supersedes
  `iterate_commands`. Yields `RecordedCommand | LifecycleEvent`. The
  old `iterate_commands` becomes a thin wrapper that filters to
  commands only, kept for tests that already mock it.

`backend/src/recording/v2_recorder_task.py` — emit lifecycle:

- Right before `pw.chromium.launch(...)` → enqueue
  `browser_starting`.
- After the initial `page.goto` (or after `context.new_page()` when
  there is no target URL) → enqueue `browser_ready`.
- In `_on_disconnect`, if `stop_event` has NOT already been set by
  user-initiated stop → enqueue `browser_crashed` before setting
  the event.
- In the `except Exception` of the outer `run_v2_recorder_session`
  → also enqueue `browser_crashed` with the exception message so
  the user sees WHY (`"NoBrowserAvailable: missing $DISPLAY"`).

`backend/src/recording/router.py`:

1. **SSE endpoint** `/recordings/sessions/{id}/commands` extended to
   emit two event types instead of one:
   - `event: command\ndata: <RecordedCommand JSON>` (unchanged)
   - `event: lifecycle\ndata: { "phase": "...", "ts": ..., "message": ... }`
   - Existing `event: end` sentinel unchanged.

2. **New endpoint** `POST /recordings/sessions/{id}/restart-browser`:
   - 200 on success, 404 / 403 / 409 on the usual errors.
   - Mechanism: set the session's `stop_event` (same mechanism the
     stop button uses), wait briefly for `_stop_signals` cleanup,
     then `dispatch_task(run_v2_recorder_session, session_id, ...)`
     again with the same target_url stashed on the session row.
   - First emits a `browser_restarting` lifecycle event so the
     frontend can switch the pill immediately. The fresh task's
     `browser_starting` / `browser_ready` events follow.
   - Captured commands stay in the queue (we don't drain it on
     restart — only on terminal status).

### Frontend

`frontend/src/views/RecordingLiveView.vue`:

- Replace the 4-state `streamState` (`connecting | live | done |
  error`) with a richer state machine driven by the new
  `event: lifecycle` payloads:
  - `connecting` — SSE handshake in flight, nothing yet from
    backend.
  - `browser_starting` — backend says Chromium is launching.
  - `browser_ready` — Chromium up; if zero commands captured,
    show the existing "Click in the browser to record" hint.
  - `browser_restarting` — restart in flight.
  - `browser_crashed` — show error banner + offer Restart.
  - `done` — user clicked Stop and Save.
  - `error` — SSE-level error (network blip, 5xx).
- New top-of-page status card (`<RecorderStatusCard>`) showing the
  phase as a pill, an uptime counter ticking each second once
  ready, and a *Restart browser* button enabled in
  `browser_ready` + `browser_crashed` states.
- The existing Stop-and-Save bar stays where it is at the bottom.

`frontend/src/api/recorder.api.ts` — add
`restartV2Browser(sessionId: number): Promise<void>`.

### i18n

`recorder.live.lifecycle.*` keys for each phase + the restart
confirmation modal copy. EN/DE/FR/ES.

## Out of scope

- Showing the Chromium PID — Playwright Python's stable API does
  not expose it (only via internals). Phase + uptime are the
  signal users care about; PID is debug info we'd need to extract
  via `psutil` or sidecar tracking and is fragile across
  platforms.
- A repo-wide "all stuck recordings" sweep — the existing
  launcher reset button already covers that.
- Auto-restart on crash — restart is always user-initiated, even
  on `browser_crashed`. Auto-restart would mask flaky-spawn root
  causes.

## Edge cases

| Case | Behaviour |
|---|---|
| User clicks Restart while the browser is still in `browser_starting` | The endpoint returns 409 ("Browser is still launching, please wait"). UI greys the button during the non-ready phases. |
| Browser crashes, user restarts, second crash | Second restart works. Lifecycle is `crashed → restarting → starting → ready` again. No retry limit. |
| User clicks Restart, navigates away to launcher mid-restart | The asyncio task either completes the restart or hits the `stop_event` on the original disconnect handler. Either way the session row eventually moves to `COMPLETED` or `FAILED`. SSE close on the live view is the trigger for tear-down. |
| Backend restart endpoint hit twice in quick succession | Second call is a no-op if the first hasn't reached `browser_ready` yet (409). Once ready, allow another restart. |
| ROBOSCOPE_RECORDER_DISABLED=1 environment | Original start-browser returns 202 without spawning a task. Restart endpoint returns 501 ("recorder disabled in this deployment") so the UI can hide the button when it consistently 501s. |
| Captured commands preserved across restart | Queue is NOT drained on restart — only on terminal status. Frontend's `commands.value` array is also untouched (no UI reset). |
| browser_crashed AFTER user clicked Stop and Save | Suppressed — `stop_event.is_set()` at the time of disconnect means user-initiated; no lifecycle event is emitted. |

## Verification

- Backend unit tests:
  - `test_v2_command_queue.py` — new tests for `enqueue_lifecycle`
    + `iterate_events` heterogeneous yield order.
  - `test_v2_recorder_task.py` — assert lifecycle events fire in
    the expected sequence around `test_actions`. Mocks the
    Playwright `chromium.launch` to error → `browser_crashed`
    fires with the exception message.
  - `test_router.py` — restart endpoint happy path, 404 / 403 /
    409 paths, 501 under the disabled env var.
- Frontend unit tests:
  - `RecordingLiveViewLifecycle.spec.ts` — drives synthetic SSE
    events and asserts the pill state, uptime tick, and restart
    button enabled/disabled per phase.
- E2E (deferred to follow-up — needs real Chromium to fire crash
  paths). At minimum the new `restart-browser` endpoint is hit by
  the existing reset-flow test pattern.

## Risk

- Restart re-dispatches a backend task while the SSE consumer is
  still attached to the same queue. Verified by tests that the
  consumer keeps yielding from the same queue across the
  task-restart boundary (queue is keyed by session_id, not task
  id).
- The async-to-sync signalling (stop_event → set, then
  dispatch_task on the restart) has a small race: the new task
  may try to register the same session_id queue while the old
  task is still finalising. Mitigated because
  `register_session` is idempotent (already a no-op when a queue
  exists for the id).
