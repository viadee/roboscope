# Story DEBUG-3: "Run up to selection" action — Flow Editor

Status: planned

Epic: Interactive Robot Framework Debugger
Story Key: `debug-3-run-up-to-selection-action`
Depends on: DEBUG-1, DEBUG-2

## Story

As a Runner-role user authoring or reviewing a `.robot` file in the visual Flow Editor,
I want to click any keyword node and press a `▶ Bis hier ausführen` button to run the test until that step (inclusive) and pause in debug mode,
so that I can iterate on a long test by setting a "stop right here" probe without editing the source to insert a `Pause Execution` keyword.

## Acceptance Criteria

1. **AC1 — UI affordance.** Step-detail panel in `FlowEditor.vue` renders a `▶ Bis hier ausführen` button under the existing action row (`↑ ↓ × Doc-modal`). Visibility:
   - Visible iff selected node's `stepType in {keyword, assignment, control, return}` (NOT for the synthetic Start / End / setting-meta nodes).
   - Visible iff user has RUNNER+ on the file's repo AND the file has a non-empty `props.form` (i.e., it's a parseable `.robot`).
   - Visible only when the file is **saved on disk** — clicking when the form is dirty surfaces the save-prompt modal first (mirrors the existing "Save & Run" path; we don't debug an unsaved buffer).

2. **AC2 — Backend `POST /debug/sessions` extension.** The DEBUG-2 endpoint grows a second invocation shape:
   - Body `{file: <repo-relative path>, test_name: <string>, line: <int>, repo_id: <int>}` for the Flow Editor path (no `run_id` available).
   - Body `{run_id: <int>}` from DEBUG-2 stays unchanged; resolves to the same shape internally.
   - Validation: `line` must be inside the named test case in the file; `test_name` must exist; `repo_id` must be a project the user has RUNNER+ on. 422 on each violation, with a clear `detail` payload.
   - Audit-log code unchanged (`DEBUG_SESSION_STARTED`); the new payload picks up `{file, line, test_name}`.

3. **AC3 — Step-line resolution.** The Flow Editor `RobotStep` already round-trips through `RobotEditor.vue::serializeFormToRobot`. We need the line number per step at debug-launch time. Two implementation options — pick whichever is smaller:
   - **(a) Parser annotation**: extend `parseRobotToForm` to attach `step._lineNumber` (mark in `RobotStep` interface), serialize keeps lines stable, the click-handler reads the line directly.
   - **(b) Round-trip resolver**: take the canonical serializer output, re-parse with the backend's `output_xml`-walking parser to map `(test_name, step_index)` → line, on demand.
   
   **(a)** is the simpler in-frontend path; **(b)** is more robust to user edits but requires a roundtrip per click. PoC (a) first.

4. **AC4 — Test-case scoping.** The `--test "<name>"` arg passed to `robotcode debug-launch` MUST exactly match the test the user clicked into; the breakpoint MUST point at the keyword line (not the test header, which RF won't break on). If the click is on a Start node (we hide the button there per AC1, but defensive: the backend rejects `line` equal to the test-case header line with 422).

5. **AC5 — Same DebugPanel UI.** Frontend re-uses `DebugPanel.vue` from DEBUG-2. The Flow Editor's main canvas is replaced with the panel on debug-start (modal-overlay style, like the existing run-overlay) so the user can see the variable tree without losing their place in the canvas. `Stop` returns to the Flow Editor with the canvas intact (no auto-save / no auto-rebuild — debug doesn't mutate the form).

6. **AC6 — Multi-tab / multi-step rapid-fire.** Clicking `▶ Bis hier ausführen` while a debug session for the same file+line is already running is a **resume** (returns the existing session id, like DEBUG-2's 409 dedup). Clicking on a DIFFERENT step in the same file ABORTS the current session and starts a fresh one — confirm modal: "An active debug session for this file is paused at line X. Disconnect and start a new one at line Y?".

7. **AC7 — Tests.**
   - Backend: extend `tests/debug/test_router.py` with the file/line/test_name shape — line-validation 422 cases, test-name-not-found 422, RBAC, dedup behavior.
   - Frontend: extend `FlowEditor.spec.ts` to render the new button conditional on selected-node type, role, and file-clean state. Click handler dispatches the right POST.
   - E2E: `tests/e2e/debug-run-up-to-here.spec.ts` (`@integration`) — opens 09_database.robot, clicks step 2 in the first test, confirms DebugPanel renders with `Paused at` matching that line.

8. **AC8 — i18n.** New keys: `flowEditor.debug.{btnLabel,btnTitle,confirmReplace,unsavedHint}` in EN/DE/FR/ES.

9. **AC9 — Tour-of-the-feature.** The 30-tip rotation in `tipOfTheDay` gets one new tip pointing at the Flow Editor's debug button.

## Out of scope

- Step-back / step-over-the-loop semantics — DAP supports `reverse`, RobotCode does NOT yet implement it. Skip.
- Persisting the breakpoint set across sessions (if the user closes the panel and re-clicks, we re-create from scratch).
- Conditional breakpoints (epic non-goal).

## Dev notes

- The RoboScope-emit pair (`recording/robot_emit.py` and `editor/RobotEditor.vue::serializeFormToRobot`) writes deterministic line numbers, so the (a) approach in AC3 should work with at most a tiny line-tracking pass during parse. The cost of (b) is one extra parse roundtrip per click — fine if (a) becomes complex.
- The "rapid-fire on different steps" behavior in AC6 mirrors how Chrome DevTools handles "Run to here": always disconnect any running debug. Mention this in the confirm-modal copy so the user understands what's happening.
- Future enhancement: a "watchlist" pinned across step-clicks (the DAP `evaluate` request makes this trivial). Doc as a v1.5 candidate.
