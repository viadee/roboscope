# Story DEBUG-2: "Re-run to terminating error" action — Executions view

Status: planned

Epic: Interactive Robot Framework Debugger
Story Key: `debug-2-rerun-failed-test-action`
Depends on: DEBUG-1

## Story

As a Runner-role user looking at a failed test in the run-detail panel,
I want a `🐞 Debug` button that re-launches the failing test and pauses execution at the line that originally failed,
so that I can inspect the live variable scope and figure out *why* the assertion fired without running the test, reading the log, editing, re-running, repeat.

## Acceptance Criteria

1. **AC1 — UI affordance.** Run-detail panel renders a `🐞 Debug` button next to the existing `🔁 Retry` button. Visibility:
   - Visible iff `run.status === 'failed'` AND user has `RUNNER+` role for the run's repository.
   - Tooltip in 4 locales: `runDetail.debugBtn.tooltip` = "Re-run this test and pause at the failing line".
   - Clicking dispatches `POST /api/v1/debug/sessions` with `{run_id: <id>}`. Response is `{session_id: <uuid>, robot_file: <path>, breakpoint_line: <int>}`. On success the run-detail tabs are replaced by `<DebugPanel session-id="...">`. On 4xx / 5xx we show a toast and stay on the run-detail view.

2. **AC2 — Backend `POST /debug/sessions`.** New router `backend/src/debug/router.py` mounted at `/api/v1/debug` (RUNNER+). Handler:
   - Looks up the run; 404 if missing, 403 if user has no RUNNER+ on the repo.
   - Parses `output.xml` (existing `report_parser`) to find the FIRST failing keyword's `source` (file path, repo-relative) + `line`. If the run has no `output.xml` (early-failure), uses the test's first executable line as the breakpoint.
   - Resolves the project's Python environment via `environments.service.get_environment_python(repo)`.
   - Spawns `RobotDebugSession(robot_path, [{file, line}], env_python_path)` from DEBUG-1 inside a per-session async task; stores the session in an in-process `_active_sessions: dict[str, RobotDebugSession]` keyed by UUID.
   - Audits `DEBUG_SESSION_STARTED` (new audit code, DEBUG-2 adds it) with `{run_id, repo_id, file, line}`.
   - Returns the session metadata. The session is reaped automatically on `terminated` event or `disconnect`.

3. **AC3 — WebSocket stream.** Existing `/ws/notifications` connection grows a new topic: `debug:session:<uuid>`. Backend forwards every event the `RobotDebugSession`'s queue emits to all subscribers. Event payloads are JSON-serializable mirrors of DAP's `stopped` / `output` / `terminated` events plus a synthetic `state` event whenever the cached scope/variable tree refreshes (after every `stopped`).

4. **AC4 — REST control endpoints.** `POST /debug/sessions/<id>/{continue,next,stepIn,stepOut,disconnect}` — RUNNER+ scoped to the session-owning user. `disconnect` is idempotent and always 204s. Each control request issues the corresponding DAP request via the active `RobotDebugSession` and returns 204 on success.

5. **AC5 — Variable inspection endpoint.** `GET /debug/sessions/<id>/state` returns `{paused_at: {file, line, keyword}, scopes: [{name, variables: [{name, value, type}]}], call_stack: [{name, file, line}]}`. Frontend uses this to render the panel; the WebSocket `state` event delivers the same payload pushed.

6. **AC6 — Session lifecycle gates.**
   - Session auto-disconnects on the `terminated` DAP event; cleanup must NOT leak the subprocess (Chromium / rfbrowser-init Node processes alike). Existing `RunOverlay`-style timeout: 30 s grace from `terminated` to subprocess `wait()`, then `kill()`.
   - Frontend tab-close should call `disconnect` via `navigator.sendBeacon` so an unloaded tab doesn't keep a paused subprocess alive forever. Backend has a 5 min idle-timeout fallback (no control commands received).
   - One concurrent debug session per (user, run) pair — second `POST /debug/sessions` for the same run+user returns 409 with the existing session id so the user can resume.

7. **AC7 — Frontend `DebugPanel.vue`.** New component, ~400 LOC, lives at `frontend/src/components/debug/DebugPanel.vue`. Renders:
   - Header: paused-at file:line + keyword name; toolbar with `Continue` / `Step Over` / `Step Into` / `Step Out` / `Stop` buttons.
   - Left side: collapsed call-stack list (`paused_at` highlighted).
   - Right side: scope tree — `Local` / `Suite` / `Global` collapsible; each scope shows variable name + value (formatted) + type. Long values truncate with a "Show more" affordance.
   - Bottom: `output` event log (the running `Run logging` from RF, streamed live).
   - Pinia store `frontend/src/stores/debug.store.ts` keys per session-id; clears on `terminated`.

8. **AC8 — i18n.** All new user-facing strings have entries in EN/DE/FR/ES under `debug.*`. Required keys: `debug.btn.label`, `debug.btn.tooltip`, `debug.panel.{header,toolbar.*,scope.*,output.empty}`, `debug.error.*`. Tour gate: when DEBUG-2 ships, the existing default-tour gets a step on the new button; existing tour-completed users see a small "New" pill the first time they open a failed run-detail.

9. **AC9 — Tests.**
   - Backend: `tests/debug/test_router.py` with mocked `RobotDebugSession` (test the routing + RBAC + audit-log assertion + 409 dedup, NOT the real DAP path).
   - Frontend: component test for `DebugPanel.vue` (`@vue/test-utils`) wiring fake WebSocket + fake REST.
   - E2E gated optional: `tests/e2e/debug-rerun-failed.spec.ts` with `pytest.mark.integration` because it needs a real chromium subprocess. Skip in default CI.

10. **AC10 — Audit log.** New constant `DEBUG_SESSION_STARTED` + `DEBUG_SESSION_ENDED` in `audit/constants.py`. Backend writes both. Existing audit middleware does NOT auto-log GET/control endpoints (they're not state-changing in our auditable sense), but `disconnect` is logged because it captures user intent.

## Out of scope

- Conditional breakpoints / watch expressions (epic non-goal).
- Multi-test / multi-suite debug — v1 starts a single test case.

## Dev notes

- `robotcode debug-launch` accepts `--test "<name>"` via the trailing `-- ...` args; we use this to ensure ONLY the failing test runs (saves time and keeps stack frames clean).
- Audit-code formatting follows the existing `RUN_*` pattern (uppercase snake, ≤ 32 chars).
- 5 min idle-timeout: re-evaluate after first user feedback; ops may want this higher / configurable.
