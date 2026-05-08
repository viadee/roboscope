# Recorder Enhancement — Vision & Raw Acceptance Criteria

**Status:** input for upcoming PRD / epic / story planning. Captured verbatim from the user on 2026-04-22 during a /loop session. Not yet architecture-reviewed.

**Source:** conversation notes — to be hardened by `bmad-agent-pm` (John) via `bmad-create-prd` and then decomposed with `bmad-create-epics-and-stories`.

---

## Product Vision

The Recorder is no longer a single Chrome extension. Long-term it becomes a **multi-module product area** with shared concepts (selectors, commands, keyword library) but independent entry points:

- **Web Recorder** — opens a controlled browser session; captures human interactions and converts them into Robot Framework keywords.
- **Desktop Recorder** — records interactions with native apps (Windows first; macOS on the roadmap if feasible).

Future modules are possible (mobile, API trace replay, etc.), but the architecture must make the first two clean without over-designing for the rest.

---

## Web Recorder — Acceptance Criteria (raw, to be refined)

### AC-W1: Recording start

- **Given** a logged-in user on the Recorder view
- **When** they click `[Record]`
- **Then** a dedicated browser session opens (controlled — must allow programmatic introspection; Playwright / CDP attach is the obvious candidate)
- **And** all captured commands are streamed to the frontend in near-real-time

### AC-W2: Supported commands

The Web Recorder must capture at minimum:

- **Navigation** to a new URL (address-bar change)
- **Click** on elements
- **Type** into text fields (input, textarea, contenteditable)
- **Scroll** (page and inner-container)
- **Drag & drop**
- (Stretch) hover, keypress, file upload

> Approach decision pending: the PM/architect should survey Selenium IDE, Playwright Codegen, Chrome Recorder, Robocorp's recorder and pick a sensible pattern. Decision recorded in PRD §"Approach".

### AC-W3: Element-hover overlay

- **Given** the Recorder browser is attached to a page
- **When** the user hovers any DOM element
- **Then** a semi-transparent highlight overlay appears around it, equivalent to Chrome DevTools' "Inspect element" hover state (box model, offset, classes summary)
- **And** the overlay does not interfere with the page's own hit-testing (so clicks still flow through to the underlying element)

### AC-W4: Context menu with additional actions

- **Given** a user right-clicks on a highlighted element
- **When** the context menu opens
- **Then** they see additional Recorder actions grouped by category — the groups map to Robot Framework Browser library keyword families, e.g.:
  - *Assert / Read* (Get Element Value, Get Text, Get Attribute, …)
  - *Wait* (Wait For Elements State, Wait Until Network Is Idle, Wait For Condition, …)
  - *Interact* (Double-click, Hover, Right-click, Tap, …)
  - *State* (Scroll To, Take Screenshot of Element, Highlight, …)
- **And** picking an action appends a corresponding keyword to the recorded flow with the right locator pre-filled

### AC-W5: Result view uses the standard editor

- **Given** the user stops the recording
- **When** the result view renders
- **Then** it uses the same Visual-Flow + Text editor components the rest of RoboScope uses (FlowEditor + RobotEditor + FileExplorer)
- **And** every existing feature of those editors is available (cut/paste nodes, text-mode toggle, keyword search, etc.)
- **And** the result can be saved as a `.robot` file in the user's repo

### AC-W6: Multiple selectors per command

- **Given** a recorded command targets an element
- **When** the command is rendered in the editor
- **Then** every command stores **multiple candidate selectors**, not just the one picked at record time. The editor shows a selector-picker menu inline with the command.
- **And** the user can swap the active selector at any time without re-recording

### AC-W7: Selector strategies

The Recorder must synthesise candidate selectors from at least these strategies, in priority order:

1. **Test-id attributes** (`data-test-id`, `data-testid`, `data-test`, `data-qa` — configurable)
2. **ARIA / accessibility roles** (`role=…`, `aria-label=…`)
3. **Stable text content** for elements where text is the natural identifier (buttons, links, labels)
4. **CSS selector** — shortest-unique path using `id`, classes, structural selectors
5. **XPath** — multiple variants: absolute, relative-anchored, text-anchored
6. **Playwright locator** (`getByRole`, `getByText`, `getByLabel`) where applicable

> Each synthesised selector is verified for uniqueness at capture time; non-unique candidates are either parameterised (nth-match) or dropped.

---

## Desktop Recorder — open questions

The user has asked for Windows support (macOS tentative). Concrete AC to be defined in the PRD. Open questions to put to John:

- Which accessibility API is the backbone? UI Automation on Windows; AXUIElement on macOS.
- Does the desktop recorder reuse the same command-model + selector-list shape as the web recorder, or does it model things like coordinate-based events?
- How is the recorded desktop flow represented in Robot? Existing Robot libraries (`WhitelibraryN`, `Robot Framework AutoItLibrary`, `RPA.Windows`) give different trade-offs.
- Is there a mandatory module-selector UI ("Record Web" vs "Record Desktop") or can a session switch mid-recording?

---

## Cross-cutting architectural asks

- **Shared selector datamodel.** `SelectorCandidate { strategy, value, quality_score }` and `RecordedCommand { keyword, args, selector_candidates }` — used by both modules.
- **Persistence.** Recorded flows land in the user's git repo via the existing FileExplorer save path; no new storage tier.
- **Extension model.** The Chrome-extension transport that exists today (Story R-1) becomes one of several recorder transports; the Web Recorder described here is the canonical UX going forward. The Chrome extension is explicitly NOT required to change for MVP.
- **Security / audit.** A recording session counts as privileged repo access; the user must be EDITOR+ on the target repo (per Story 3-7 effective-role). Session metadata audit-logged as `recording.started` / `recording.stopped`.

---

## Intentional non-goals (to be confirmed in PRD)

- Cross-browser recording. Target Chromium-based browsers only for MVP.
- Mobile recording. Out of scope until Desktop lands.
- Replay-in-the-cloud. Recorder produces `.robot` files that run through the existing execution pipeline; no parallel replay engine.
- AI-assisted healing of broken selectors. Interesting, but belongs in Phase-next. Selector strategy #7 candidate.

---

## Next steps (recommended BMAD flow)

1. **`bmad-agent-pm` → `bmad-create-prd`** using this document as the raw input. Result: full PRD with journeys, NFRs, success metrics.
2. **`bmad-agent-architect` → `bmad-create-architecture`** to pick the controlled-browser tech (Playwright + CDP is the leading candidate), the selector-scoring algorithm, the desktop-module surface.
3. **`bmad-create-epics-and-stories`** to decompose into sprint-ready stories — likely three epics: (E-Web) Web Recorder MVP, (E-Desktop) Desktop Recorder, (E-Selector) Shared selector datamodel + UI.
4. **`bmad-check-implementation-readiness`** gate.
5. **`bmad-create-story`** → **`bmad-dev-story`** per story.

---

## Change log

- **2026-04-22** — Captured raw requirements from the user's /loop session. Planning-ready, not yet PRD-hardened.
