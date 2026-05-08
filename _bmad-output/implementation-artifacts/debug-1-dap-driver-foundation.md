# Story DEBUG-1: Backend DAP driver foundation

Status: in_progress

Epic: Interactive Robot Framework Debugger
Story Key: `debug-1-dap-driver-foundation`

## Story

As a RoboScope core developer,
I want a clean async DAP-client driver that can spawn `robotcode debug-launch`, complete the protocol handshake, set breakpoints, drive run/step/continue, and surface stopped events,
so that the user-facing "Re-run to error" (DEBUG-2) and "Run up to selection" (DEBUG-3) stories share the same well-tested backend primitive instead of each reinventing subprocess + protocol plumbing.

## Acceptance Criteria

1. **AC1 — DAP wire format helpers (`backend/src/debug/dap_protocol.py`).**
   - `encode_message(msg) -> bytes` produces a `Content-Length: N\r\n\r\n<utf-8-json>` framed payload.
   - `read_message(reader) -> DapMessage` reads one framed message from an `asyncio.StreamReader`. Tolerates header-key casing variants. Raises `DapProtocolError` on missing/malformed `Content-Length`, EOF mid-header / mid-body, JSON parse failure, or non-object body. `OSError` from the underlying transport propagates unchanged so callers can distinguish protocol vs transport failures.
   - `write_message(writer, msg)` serializes + flushes.
   - Pure asyncio: no DB, no threads, no Robot Framework imports.

2. **AC2 — DapClient (`backend/src/debug/dap_client.py`).**
   - `DapClient(reader, writer, request_timeout=30.0)` with `start()` / `stop()` / `request(command, arguments) -> body` / `on_event(event, handler)`.
   - Allocates `seq` monotonically; matches responses by `request_seq`. `success=false` responses raise `DapApplicationError` with `command` + `message` attributes.
   - Single read pump loop. Cancel-safe: `stop()` cancels the task, closes the writer, rejects every pending future with `ConnectionResetError`.
   - Event handlers are sync `(body) -> None`. Multiple handlers per event allowed; firing order is registration order. A raising handler is logged and isolated; sibling handlers still run.
   - Forward-extensible: unknown message-type fields are logged at DEBUG level and dropped, NOT raised.

3. **AC3 — RobotDebugSession (`backend/src/debug/robot_debug_session.py`).**
   - `RobotDebugSession(robot_path, breakpoints, env_python_path)` async-context-manager.
   - On `__aenter__`: spawns `<env_python>/bin/robotcode debug-launch --tcp 127.0.0.1:0 -w -- <robot_path>`, parses the bound port from stdout (regex documented inline; tolerates RobotCode emitting other startup chatter), opens a TCP connection, instantiates `DapClient`, sends `initialize` → `setBreakpoints` → `configurationDone` → `launch`. Promotes any DAP error to a domain-specific `DebugSessionStartFailed` so the route layer (DEBUG-2) can return a 502 with operator-friendly detail.
   - Exposes async methods `continue_()`, `next_()`, `step_in()`, `step_out()`, `disconnect()`, `state() -> dict` (last `stopped` event body + cached `stackTrace` / `scopes` / top-level variables).
   - `__aexit__` always reaches `disconnect` and waits for subprocess exit with a 5 s grace period; on timeout, escalates to `kill()` + zombie-reap. Logs but does NOT raise from cleanup so a teardown failure can't mask the originating exception.
   - Subscribes to `stopped`, `output`, `terminated`, `exited` events; updates internal state cache and exposes a single `asyncio.Queue` for the route layer to forward to the WebSocket.

4. **AC4 — Unit tests.** `backend/tests/debug/test_dap_protocol.py` and `test_dap_client.py` use an in-process fake server (asyncio `start_server`) — no robotcode subprocess, no real Robot Framework. Coverage:
   - encode/read round-trip for request, response (success + failure), event.
   - Header casing: `content-length:` lower / `Content-LENGTH:` mixed both parse cleanly.
   - `read_message` raises `DapProtocolError` on: bytes-only header, missing `Content-Length`, non-int length, EOF mid-header, EOF mid-body, malformed JSON, JSON-array body.
   - `DapClient.request` returns body on success.
   - `DapClient.request` raises `DapApplicationError` carrying `command` + `message` on failure.
   - `DapClient.request` propagates `asyncio.TimeoutError` if the peer never responds.
   - Event handlers fire in registration order; a raising handler is contained.
   - `stop()` rejects every in-flight `request` future with `ConnectionResetError`.
   - Re-entrant `start()` is a no-op (idempotency).

5. **AC5 — RobotDebugSession tests.** `test_robot_debug_session.py` mocks the subprocess + the TCP server. Coverage: spawn-failure path (`FileNotFoundError` if robotcode binary missing in the env), port-parse failure, handshake-step failure (each of `initialize` / `setBreakpoints` / `configurationDone` / `launch` independently), clean teardown via `__aexit__`, `stop()` after spawned-but-pre-handshake (no leaked subprocess).

6. **AC6 — No new prod dependency yet.** This story does NOT add `robotcode-debugger` to `backend/pyproject.toml` — the protocol layer is self-contained Python. The dependency lands as part of DEBUG-2 (the first story that actually launches a subprocess). Rationale: keep this PR shippable / mergeable independently.

7. **AC7 — Type-hygiene.** `mypy --strict` clean across the new module. `Ruff` clean. Docstrings on every public symbol explain purpose, not signatures (signatures self-document).

## Files

- `backend/src/debug/__init__.py` — re-exports + module-level architecture comment.
- `backend/src/debug/dap_protocol.py` — wire format.
- `backend/src/debug/dap_client.py` — request/response/event router.
- `backend/src/debug/robot_debug_session.py` — high-level lifecycle wrapper.
- `backend/tests/debug/__init__.py` — empty.
- `backend/tests/debug/test_dap_protocol.py`
- `backend/tests/debug/test_dap_client.py`
- `backend/tests/debug/test_robot_debug_session.py`

## Out of scope (deferred to DEBUG-2 / DEBUG-3)

- HTTP / WebSocket router endpoints (`/debug/sessions/...`).
- Audit-log integration.
- Frontend `DebugPanel.vue`.
- Adding `robotcode-debugger` to backend deps (and the Dockerfile generator's auto-install path).
- E2E test launching real RF + Chromium.

## Dev notes

- DAP spec lives at <https://microsoft.github.io/debug-adapter-protocol/specification>. Fields we use in v1 are limited: `initialize` (advertise client capabilities), `setBreakpoints` (file + line list), `configurationDone`, `launch` (RobotCode-specific args), `continue`, `next`, `stepIn`, `stepOut`, `disconnect`, plus events `stopped`, `output`, `terminated`, `exited`.
- RobotCode's `launch` argument shape is documented at <https://robotcode.io/03_reference/cli> under `debug-launch` — the relevant keys for our story are `target` (positional `.robot` path), `args` (extra `robot` CLI args, e.g. `--test "<name>"` for DEBUG-2), and `noDebug: false`.
- Use `pytest-asyncio` (already in `pyproject.toml::dev`) for async tests.
- Logger names: `roboscope.debug.dap`, `roboscope.debug.session`. Ride the existing JSON formatter in `main.py` so per-session logs are queryable in production.
