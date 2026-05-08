# Interactive Robot Framework Debugger — Epic + Stories

**Status**: Planning
**Date**: 2026-05-08
**Owner**: RoboScope core team

## Headline

Add an interactive **debug-and-pause** mode to RoboScope so the user can:

- Re-run a failed test from the Executions view and stop on the line that originally failed, then inspect state.
- Click a step in the Flow Editor and run the test case up to that step ("Run up to here"), then drop into the same debug surface.

Both flows surface the same web-UI debug panel: paused-at location, current variable scope tree, step / continue / abort controls.

## Why this, why now

Today RoboScope can only run tests "to the end" — the user gets a pass/fail report. When a test fails, the only debug affordance is reading `output.xml` after the fact. There is no way to **freeze** the runner at the failing line, inspect what `${response_body}` actually contains at that point, then either step further or abort.

For Browser-library tests against real-world pages, this gap is especially painful: a `Click` failure could be a stale selector, a timing race, or a page-state bug, and post-mortem log diffing rarely tells the three apart. An interactive pause-and-inspect surface is the single biggest force multiplier the project can ship to RUNNER-role users.

## Architecture decision

Use **RobotCode's DAP server** (`pip install robotcode-debugger`, Apache-2.0, last release 2026-04). It speaks the standard Microsoft Debug Adapter Protocol over TCP, supports breakpoints / step-in/over/out / scopes / variables / evaluate / disconnect, and is the most actively maintained debugger in the Robot Framework ecosystem.

RoboScope's FastAPI backend implements a thin DAP client (~300 LOC) that:

- Spawns `<env>/bin/robotcode debug-launch --tcp 127.0.0.1:0 -w -- <robot_file>` in the project's resolved Python environment.
- Connects, sends `initialize` → `setBreakpoints` → `configurationDone` → `launch`.
- Streams `stopped` / `terminated` / `output` events to the frontend over the existing per-run WebSocket.
- Exposes REST endpoints for `continue` / `next` / `stepIn` / `disconnect` / `evaluate`.

A custom RF Listener V3 fallback (Apache, in-tree) stays documented in the architecture so a future RobotCode-pin issue doesn't block us. **Not built unless we need it.**

See the research note in [CLAUDE.md release-publish checklist] and the parent SECURITY.md disclosure section for licensing rationale.

## Stories

The work splits into three sequential, independently-shippable stories:

### Story DEBUG-1 — Backend DAP driver foundation
Apache-2.0 dependency + DAP wire format + `RobotDebugSession` lifecycle (spawn / handshake / tear-down) + unit tests with a fake DAP server. **No router, no UI** — purely the driver primitives DEBUG-2 and DEBUG-3 build on. Lives in `backend/src/debug/`.

### Story DEBUG-2 — "Re-run to terminating error" action (Executions view)
Run-detail panel gets a `🐞 Debug` button next to the existing `🔁 Retry` button (visible only on FAILED runs, RUNNER+ role). Click → backend extracts the (file, line) of the first failing keyword from `output.xml`, calls `dap_driver.start(file, [{file, line}])`, returns a `debug_session_id`. Frontend opens a new `DebugPanel` view in place of the run-detail tabs, subscribes to the WebSocket, renders `Paused at file:line` + scope/variable tree + toolbar.

### Story DEBUG-3 — "Run up to selection" action (Flow Editor)
Step-detail panel gets a `▶ Bis hier ausführen` button (visible to RUNNER+, when a `keyword` step is selected and the file has a saved sidecar). Same backend path as DEBUG-2 but the breakpoint is taken from `step.line` (which the parser-emit pair already round-trips). Same `DebugPanel` UI surface — the two stories converge on a single component.

## Acceptance gates (epic-level)

Beyond each story's own ACs, the epic ships only when:

1. RobotCode DAP subprocess survives the same Browser-library + rfbrowser-init bootstrap that subprocess-runner already navigates (no version drift between the project's `playwright` and the debugger's expected version).
2. Pause / resume cycles do NOT leak Chromium processes or rf-browser node-side gRPC servers — every `disconnect` MUST tear the underlying RF run down cleanly.
3. The new `/debug/sessions/<id>/state` endpoint is RBAC-gated to RUNNER+ for the project that owns the file (Audit-log entry per session start, per project, per user, mirroring the existing `RUN_*` audit codes).
4. The new dependency is documented in `SECURITY.md` and `CLAUDE.md` — it inherits Apache-2.0 cleanly, but operators upgrading from 0.9.x will see a fresh audit-log code and a new `debug` module.
5. CI: at minimum a backend unit test that mocks the DAP server + a frontend component test for `DebugPanel`. A real-Chromium e2e is desirable but gated on Phase-4 Gate 5's existing Playwright-install step (Story DEBUG-2 will piggy-back).

## Non-goals

- **Conditional breakpoints** — out of scope for v1, though the protocol supports `condition`. Re-evaluate after the basic pause/resume flow ships.
- **Watch expressions** — same; DAP `evaluate` makes them cheap to add later, but the v1 panel ships with scope/variable inspection only.
- **Multi-session debugging** — backend supports it (each session keys off a UUID), but frontend ships with single-active-debug per browser tab to keep the WebSocket multiplex simple.
- **Edit-and-continue** — the user can change values via DAP `setVariable` in v1.5 if requested; out of scope for v1.

## Cross-references

- Research note: see CLAUDE.md `release-publish checklist` summarizing the ecosystem survey.
- Listener-V3 fallback architecture sketch: stays in this doc only; if we ever swap from RobotCode, that's a fresh story spec.
- Existing audit-code constants: `backend/src/audit/constants.py` — DEBUG-2 will add `DEBUG_SESSION_STARTED` / `DEBUG_SESSION_ENDED`.
