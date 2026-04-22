# Recorder v2 — Epics & Stories Breakdown

**Source:** `recorder-v2-prd.md` (2026-04-22).
**Workflow:** sprint-ready stories for the three Recorder v2 epics. Architecture decisions still pending a separate pass with `bmad-agent-architect`; stories where that blocks implementation are flagged **[needs-arch]**.

## Epic summary

| Epic | Scope | Story count | Order |
|---|---|---|---|
| **W** — Recorder Web MVP | Controlled-browser session, capture primitives, hover overlay, context menu, result-in-editor | 8 | 1 |
| **S** — Shared Selector datamodel + editor UI | Candidate model, strategy library, inline picker, uniqueness verification | 5 | 1 (parallel) |
| **D** — Desktop Recorder (Windows) | Session start, primitive capture, UI Automation tree adapter | 4 | 2 |
| **DM** — Desktop Recorder (macOS, tentative) | AX adapter if feasible | 2 | 3 (trigger-gated) |

Total: 19 stories across 4 epics.

---

## Epic W — Recorder Web MVP

### Story W.1: Controlled-browser session lifecycle (Playwright + CDP)

As a Backend engineer,
I want a controlled Chromium session I can start, stream commands from, and stop cleanly,
so that the Web Recorder has a reliable foundation.

**Acceptance Criteria:**

- **Given** the user POSTs `/api/v1/recordings/sessions` with `{transport: "web_playwright", repo_id: N}`
- **When** the endpoint runs
- **Then** a Chromium instance boots under Playwright, a `RecordingSession` row is persisted with `status=active`, and the response returns `{session_id, browser_ws_endpoint}`.
- **Given** the caller DELETEs the session
- **When** the endpoint runs
- **Then** the Chromium process terminates within 2 s and the row flips to `aborted`.
- **Given** a 30-minute idle timeout fires (no commands for that long)
- **When** the retention scheduler runs
- **Then** the session is auto-aborted and logged under `retention.recorder`.

**Dev notes:** reuse the browser-lifecycle event pattern from Story R-1. Listener-on-disconnected flips `stop_event`. Carry Playwright async API on a dedicated event-loop thread — do NOT share with the FastAPI request loop.

**[needs-arch]** confirm "browser-per-session" vs. "browser-pool" — arch-pass decides.

---

### Story W.2: Command-stream endpoint (SSE)

As a Frontend engineer,
I want to subscribe to the recorder's captured commands in near-real-time,
so that the live step list updates while the user interacts.

**Acceptance Criteria:**

- GET `/api/v1/recordings/sessions/{id}/commands` returns `text/event-stream`.
- Each event is a `RecordedCommand` JSON payload (shape per SEL epic).
- Connection drops when the session aborts / completes.
- Multiple subscribers are NOT supported in MVP (single tab per session).

---

### Story W.3: Primitive-capture injection (navigate, click, type, scroll)

As a QA tester,
I want clicks, keystrokes, scrolls, and address-bar navigations captured automatically,
so that I can focus on interacting instead of annotating.

**Acceptance Criteria:**

- The recorder injects a capture script on every new document (`page.addInitScript`).
- Script emits events over CDP Runtime.bindingCalled for: `click`, `dblclick`, `input`, `change`, `scroll`, `keypress` (Enter only; discourage keystroke-by-keystroke noise), and `navigation` (via `context.on('page')` + `frame.url` change).
- Each event maps to a Robot Framework `Browser` library keyword with the active-selector-candidate populated.
- Drag-and-drop is captured as a paired `mousedown`/`mousemove`/`mouseup` sequence and emitted as a single `Drag And Drop` keyword.

**[needs-arch]** exact mapping table from DOM event → keyword.

---

### Story W.4: DevTools-style hover overlay

As a tester evaluating an element,
I want a semi-transparent highlight around whatever I hover,
so that I can confirm my selector hits the right thing.

**Acceptance Criteria:**

- Inject a stylesheet + hover listener on every page of a recorder session.
- Overlay shows: bounding box with 2-px solid border, offsetX/Y + width/height label, element tag + leading class summary.
- Overlay never intercepts pointer events (`pointer-events: none`).
- Overlay respects `prefers-reduced-motion` (no animations).
- Overlay toggle hotkey (e.g. `Ctrl+Shift+X`) hides/shows it mid-session.

---

### Story W.5: Right-click context menu with keyword-family groups

As a tester capturing an assertion,
I want to right-click an element and pick an action like "Get Element Value",
so that assertions make it into the recording without me typing anything.

**Acceptance Criteria:**

- Right-click on a hovered element preempts the native context menu.
- Menu groups the Robot Framework `Browser` library keyword catalog into: `Assert / Read`, `Wait`, `Interact`, `State`.
- Per-group items are the concrete keywords (MVP: ~15 keywords total covering the most-used).
- Selecting a menu item emits a `RecordedCommand` with that keyword + the element's selector candidates. Extra args (e.g. expected-value for `Should Be Equal`) are captured via an inline mini-dialog.

**[needs-arch]** exact keyword list — pull from `Browser` library keyword export.

---

### Story W.6: Result view uses standard editor components

As a tester who finished recording,
I want the captured flow to open in the same Visual-Flow + Text editor I already know,
so that I can refine without learning a new UI.

**Acceptance Criteria:**

- Clicking `[Stop]` calls `/finalize` and receives a full `RecordedFlow` payload.
- The frontend routes to `/recordings/result/{session_id}` which mounts `RobotEditor.vue` + `FlowEditor.vue` (tabbed like the existing ExplorerView).
- The loaded flow is **unsaved** — leaving the route without Save prompts a "discard?" dialog.
- Save dispatches `/api/v1/recordings/save` which writes the .robot file into the user's repo. Uses existing FileExplorer save path (no new storage tier).

---

### Story W.7: Recording view route + launcher button

As a user,
I want a dedicated `Record` button in the nav that opens the recording view,
so that discovery is obvious.

**Acceptance Criteria:**

- New route `/recordings/new` with a `RecordingLauncherView.vue` (transport picker: Web / Desktop-Windows / Desktop-macOS) + the Record CTA.
- Sidebar gets a "Recorder" entry (EDITOR+ only).
- After successful recording, the save dialog prompts for a path under `flows/` and defaults the file name to the top-level URL slug.

---

### Story W.8: Audit + retention for recording sessions

As a Security admin,
I want every recording session to produce structured audit entries,
so that I can reconstruct who recorded what against which repo.

**Acceptance Criteria:**

- `AuditEventType.RECORDING_SESSION_STARTED` + `RECORDING_SESSION_COMPLETED` + `RECORDING_FLOW_SAVED` enum entries.
- Each emission site uses `log_event` with `user_id`, `resource_id=repo_id`, detail including transport + duration + command count.
- `RecordingSession` rows honour the Story 5-5 hourly cleanup: anything older than 30 min that's still `active` is auto-aborted.

---

## Epic S — Shared Selector datamodel + editor UI

### Story S.1: Selector-candidate datamodel & API shape

As a Frontend / Backend engineer,
I want a shared, versioned shape for `SelectorCandidate` and `RecordedCommand`,
so that Web and Desktop transports produce consumable-by-the-same-editor flows.

**Acceptance Criteria:**

- TypeScript + Pydantic types for `SelectorCandidate { strategy, value, quality_score, verified_unique }` and `RecordedCommand { keyword, args, selector_candidates, active_candidate_index }`.
- Shapes round-trip losslessly through JSON.
- Schema version bump: `schema_version: 1` on the flow root; serialisation guard raises on unknown versions.

---

### Story S.2: Strategy library (test-id, ARIA, text, CSS, XPath, Playwright locator)

As a recorder backend,
I want every capture to synthesise candidates from the six configured strategies,
so that the user has real alternatives.

**Acceptance Criteria:**

- Strategy module exports `synthesise_selectors(element_snapshot) -> list[SelectorCandidate]`.
- Strategies: `testid` (configurable attr names), `aria` (role + name), `text`, `css`, `xpath` (absolute / relative-anchored / text-anchored variants), `pw_locator` (Playwright getByRole / getByText).
- Quality-scoring heuristic: testid > aria-with-name > text > short-css > xpath > pw_locator, with per-strategy penalties for fragile anchors (auto-generated class names, nth-of-type).

---

### Story S.3: Uniqueness verification at capture time

As a recorder,
I want to verify each candidate points to exactly one element in the live DOM,
so that we don't ship broken selectors in the saved flow.

**Acceptance Criteria:**

- Every candidate runs against the captured DOM snapshot via Playwright's `$$` match count.
- Non-unique candidates are either parameterised (`:nth-match(2)`) or dropped.
- Candidates that match zero elements (edge case of DOM mutating mid-capture) are logged + dropped.

---

### Story S.4: Inline selector-picker component

As a tester refining a recording,
I want an inline picker next to each step's locator that shows candidates with quality badges,
so that I can swap without re-recording.

**Acceptance Criteria:**

- New `SelectorPicker.vue` mounts inside each flow-editor step node + text-editor line.
- Shows candidates sorted by quality_score, with a colored dot + tooltip (`testid` green, `aria` green, `text` amber, `css` amber, `xpath` red, `pw_locator` green).
- Clicking a candidate sets `active_candidate_index` and regenerates the serialized Robot line.
- The text-editor mode keeps the picker as a code-lens-style gutter annotation — not a blocking dialog.

---

### Story S.5: i18n — selector-picker + strategy names in 4 locales

Catches the "i18n-complete before GA" invariant (NFR-R4). Strategy labels + picker CTA strings shipped in EN/DE/FR/ES.

---

## Epic D — Desktop Recorder (Windows)

### Story D.1: UI Automation session adapter

**[needs-arch]** The architect decides between `RPA.Windows` (ships with a mature test library but heavier) and raw `pywinauto` / `pyautogui` (smaller, less opinionated). Decision captured in the architecture doc.

As a Backend engineer,
I want a Windows desktop transport that can start / stop / stream commands like the Web transport,
so that the Desktop Recorder plugs into the same session UX.

**Acceptance Criteria:**

- POST `/recordings/sessions` with `transport=desktop_windows` spawns the capture process.
- Only runs on Windows hosts — other OSes return 501.
- Capture stream uses the same SSE endpoint shape as Web.

---

### Story D.2: Primitive capture — click, type, select

**Acceptance Criteria:**

- Mouse click on any focusable control → `Click` keyword.
- Keyboard input into text fields → `Type Text` keyword.
- Combo-box selection → `Select From Combobox` keyword.
- All commands carry `SelectorCandidate[]` synthesised from the UI Automation tree (see S.2 for web; D.1 ships the desktop equivalent).

---

### Story D.3: Desktop-specific selector strategies

**Acceptance Criteria:**

- Strategies: `AutomationId` (analogue of testid), `Name` (analogue of aria-label), `ClassName`, `XPath-over-UIA-tree`, `Ancestor + nth child`.
- Quality order: AutomationId > Name > ClassName > XPath > ancestor-chain.

---

### Story D.4: Robot library mapping + .robot emit

**[needs-arch]** Mapping table from recorded command → Robot keyword. Likely target library: `RPA.Windows`.

**Acceptance Criteria:**

- `finalize` on a desktop session returns a flow the Robot runner can execute.
- The emitted `.robot` runs end-to-end through the existing execution pipeline.

---

## Epic DM — Desktop Recorder (macOS, tentative)

### Story DM.1: AXUIElement feasibility spike

Go / no-go decision based on accessibility API richness and RoboScope macOS runtime support.

### Story DM.2: macOS session adapter + primitive capture

Only starts if DM.1 returns "go".

---

## Rollout sequence

1. **Sprint N**: W.1 + S.1 + S.2 in parallel. Establishes the foundation — you cannot demo anything yet but no other epic can proceed without these.
2. **Sprint N+1**: W.2 + W.3 + S.3 + S.4. Demo-able end-to-end: record a scenario, watch steps stream in, stop, swap a selector, save.
3. **Sprint N+2**: W.4 + W.5 + W.6 + W.7 + S.5. Polish + discoverability; GA-ready Web Recorder.
4. **Sprint N+3**: D.1 + D.2.
5. **Sprint N+4**: D.3 + D.4 (+ DM.1 spike).
6. **Sprint N+5 (optional)**: DM.2 if spike passed.

Each story ends with a commit; each sprint ends with a tag + a release-gate CI run (Phase-4 `phase4-gates.yml` pattern).

---

## Open questions for the architect

1. Browser-per-session vs. pool?
2. Should the controlled browser run in a Docker sidecar or in-process with the backend?
3. `RPA.Windows` vs. raw `pywinauto`?
4. How do we inject the hover-overlay script in a way that survives soft navigations (History API)?
5. Do we expose the Chrome extension transport as a first-class `transport` enum value, or keep it as a separate code path?
6. Do we rate-limit recording sessions per user (blast radius if a user opens 100 tabs)?

---

## Change log

- **2026-04-22** — First cut, derived from recorder-v2-prd.md. 19 stories across 3 main epics + 1 tentative. Architecture pass pending.
