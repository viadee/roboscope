# Story TEST-1: WebSocket manager test coverage

Status: done

Epic: TEST GAPS — backlog from CLAUDE.md "Test gaps (highest risk)"
Story Key: `test-1-websocket-manager-coverage`

## Reported

CLAUDE.md "Test gaps":

> WebSocket manager

`src/websocket/manager.py` is the live-update broker between the
asyncio event loop (websocket connections) and background-thread
broadcasts (called from `task_executor` jobs via
`asyncio.run_coroutine_threadsafe`). It uses a `threading.Lock` to
guard the connection lists. Until this story it had **zero
tests** — and the codepath is concurrency-sensitive enough that a
silent regression here could leak connections, deadlock, or drop
messages without anyone noticing until users reported "the page
stopped updating."

## Coverage delivered

`tests/test_websocket_manager.py` — 15 tests, four classes:

1. **TestConnectDisconnect** (4) — connect appends + accepts,
   disconnect removes, unknown-ws disconnect is a no-op, run-bucket
   lifecycle (added → cleaned up when last watcher leaves).

2. **TestBroadcast** (6) — happy path multi-recipient, dead
   connection cleanup on `send_text` failure, no-op when there are
   no connections, run-targeting isolates other runs and the general
   pool, unknown run id is a no-op, dead run-watchers also get
   cleaned up.

3. **TestConvenienceBroadcasters** (4) — shape assertions on
   `broadcast_run_status` (hits both run-watchers and general pool),
   `send_run_output` (run-watchers only), `broadcast_package_status`,
   `broadcast_recording_event`.

4. **TestThreadSafety** (1) — runs a 50-iteration spammer and a
   churn loop concurrently in two `asyncio.gather` tasks, asserts
   the manager doesn't crash. Catches "snapshot under lock, send
   outside lock" mistakes.

## Approach

The tests substitute a tiny `_StubWebSocket` for the real Starlette
WebSocket. Only `accept()` and `send_text()` are required; that
matches the manager's actual surface area and avoids hauling in a
real ASGI server. A `fail_on_send=True` flag lets each test
configure dead-client behaviour without monkeypatching.

## Verification

`uv run pytest tests/test_websocket_manager.py` → 15/15 in 0.23 s.

## Out of scope

- **End-to-end socket lifecycle** with a real Starlette TestClient
  — the manager's interface is well-isolated from the actual
  protocol; an e2e Playwright test for the WebSocket *client* in
  `frontend/src/composables/useWebSocket.ts` would round out the
  picture but is much heavier setup.
- **Property-based concurrency testing** (Hypothesis state machine)
  — the gather-based smoke test is enough to catch the realistic
  hazard categories. A hypothesis state machine would be lovely
  but adds a heavy dep.
