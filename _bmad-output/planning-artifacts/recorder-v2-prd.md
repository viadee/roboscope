---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-03-success', 'step-04-journeys', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish']
completedAt: 2026-04-22
classification:
  projectType: web-application-multi-part
  domain: developer-tooling-test-automation
  complexity: medium-high
  projectContext: brownfield
  scope: recorder-v2
inputDocuments:
  - _bmad-output/planning-artifacts/recorder-vision-2026-04-22.md
  - _bmad-output/planning-artifacts/prd.md
  - CLAUDE.md
workflowType: 'prd'
---

# Product Requirements Document — RoboScope Recorder v2

**Author:** generated from user vision (2026-04-22)
**Date:** 2026-04-22
**Supersedes (for Recorder scope):** the Chrome-extension-only recorder shipped in Story R-1.
**Preserves:** the existing Chrome extension continues to work unchanged as a separate transport. v2 is additive.

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Project Classification](#project-classification)
3. [Success Criteria](#success-criteria)
4. [Product Scope](#product-scope)
5. [User Journeys](#user-journeys)
6. [Domain Model](#domain-model)
7. [Functional Requirements](#functional-requirements)
8. [Non-Functional Requirements](#non-functional-requirements)
9. [Non-Goals (Explicit)](#non-goals-explicit)
10. [Rollout & Success Metrics](#rollout--success-metrics)
11. [Glossary](#glossary)

---

## Executive Summary

The Recorder becomes a **multi-module product area** with a shared datamodel: one module captures Web interactions, another captures Desktop interactions (Windows first, macOS if feasible). Both write into the same `RecordedFlow` shape and land in the user's git repo as `.robot` files that run through the existing execution pipeline unchanged.

The Web module is the MVP. It adds four things the current Chrome extension cannot:

- **Controlled browser session.** Record starts a dedicated browser instance with deep introspection (Playwright + Chrome DevTools Protocol). No "install this extension" friction.
- **DevTools-style hover overlay** on every DOM element under the cursor.
- **Right-click context menu** grouped by Robot Framework `Browser` library keyword family — not just record-what-I-click but record-the-assertion-I-meant.
- **Multiple selector candidates per command**, swappable inline in the editor, synthesised from at least six strategies (test-id > ARIA > text > CSS > XPath > Playwright locator).

### What makes this special

Competing recorders (Selenium IDE, Playwright Codegen, Chrome Recorder, Robocorp) either (a) pick one selector and hope, (b) don't integrate with the target test framework's keyword catalog, or (c) force the user outside their test IDE to finish the job. v2 keeps the user inside RoboScope's Visual-Flow + Text editor and lets them harden selectors after recording without re-running the scenario.

---

## Project Classification

- **Project Type:** web-application-multi-part (existing RoboScope backend + frontend + new recorder transports).
- **Domain:** developer tooling — test automation / Robot Framework UI capture.
- **Complexity:** medium-high. Playwright-controlled browser is known territory; the selector-quality layer + desktop module are the novelty.
- **Project Context:** brownfield. The v1 Chrome extension continues to work; `backend/src/recording/*` is reused; `Story R-1` browser-lifecycle work is the foundation.
- **Scope:** recorder-v2.

---

## Success Criteria

### User Success

- A tester new to RoboScope can record a 6-step login-and-verify scenario, swap one locator to a stable test-id variant, and save the `.robot` file in < 5 minutes, **without leaving RoboScope**.
- A QA lead editing a flaky existing recording can open the flow, click a broken step, and pick an alternative selector from the candidate list **without re-recording**.

### Business Success

- Zero support tickets tagged `recorder-selector-broke` 30 days post-GA at a pilot customer. (Current Chrome-extension baseline: `N` tickets/month — replace with measured number once captured.)
- Adoption parity with the Chrome extension within 60 days: ≥ 50 % of recordings at pilot customers come from the v2 Web Recorder.

### Technical Success

- Recording session produces at minimum 3 candidate selectors per command (AC-FR6).
- Web Recorder uniqueness-checks every candidate at capture time — published candidates are guaranteed to match exactly one element in the captured DOM snapshot.
- Desktop Recorder's `RecordedCommand` payload is byte-compatible with the Web Recorder's payload for shared-catalog keywords.

### Measurable Outcomes

| Metric | Target | How measured |
|---|---|---|
| Time to first saved recording (Web) | ≤ 5 min | Telemetry on `record.started` → `flow.saved` at pilots |
| Selector-swap without re-record | ≥ 80 % of edit sessions | Telemetry ratio `editor.selector.swapped` / `record.retry.opened` |
| Web-Recorder crash rate | < 0.5 % of sessions | Error logs tagged `recorder.web.session.crashed` |
| Desktop-Recorder Windows coverage | 100 % of `RPA.Windows` keyword families | Integration test on every release |

---

## Product Scope

### MVP — Web Recorder v2 (Epic WEB)

- Controlled browser via Playwright + CDP.
- Captures: navigation, click, type, scroll, drag & drop (AC-FR2).
- DevTools-style hover overlay (AC-FR3).
- Right-click context menu grouped by keyword family (AC-FR4).
- Result opens in Visual-Flow + Text editor; saveable via existing FileExplorer (AC-FR5).
- SelectorCandidate datamodel shipped in the shared domain library (AC-FR6 + AC-FR7).

### Growth — Shared Selector Datamodel + Editor UI (Epic SEL)

Ships alongside the Web Recorder. Extracts the selector logic so the Desktop module can plug in without duplication:

- `SelectorCandidate { strategy, value, quality_score, verified_unique }`
- `RecordedCommand { keyword, args, selector_candidates }`
- Inline selector-picker component in FlowEditor + RobotEditor.
- Strategy library: test-id, ARIA, stable text, CSS, XPath (multiple variants), Playwright locator.

### Vision — Desktop Recorder (Epic DESKTOP)

Windows first (UI Automation API). macOS tentative (AXUIElement). Recorded flows map to `RPA.Windows` or an equivalent Robot library to be chosen by the architect.

### Explicit non-MVP

- Cross-browser recording (Firefox, Safari). Chromium-based browsers only.
- Mobile recording.
- Replay in the cloud.
- AI-assisted healing of broken selectors (future Phase).

---

## User Journeys

### Journey 1 — Web Recorder MVP, happy path

As **Maya** (tester new to Robot Framework), I want to record a login-and-verify scenario without installing anything.

1. I open RoboScope → Recorder → `[Record]`. A controlled browser window opens on `about:blank`.
2. I type the app URL in the address bar. The recorder captures a `New Page` → `Go To` step.
3. I interact with the app: click login, type email + password, submit. Each interaction appears in the live step list.
4. I hover the "Order ID" field. A DevTools-style overlay appears.
5. I right-click → `Assert / Read` → `Get Element Value`. The recorder appends a `Get Element Value` keyword.
6. I click `[Stop]`. The result opens in the standard Visual-Flow editor. Every step has a selector candidate dropdown.
7. I swap the click-login locator from the default CSS to its test-id variant. I save as `flows/login_happy.robot`.

### Journey 2 — Selector-healing, no re-record

As a **QA Lead** maintaining existing recordings, I want to fix a broken step without re-running the scenario.

1. Nightly run fails on a step `Click Element  css=.btn-submit`.
2. I open the saved flow in the Visual-Flow editor.
3. The broken step shows its selector candidates: CSS (current, red-flagged), test-id, ARIA role, XPath.
4. I click the test-id candidate. The step switches. The red flag clears.
5. I save. Next run passes.

### Journey 3 — Desktop Recorder (post-MVP)

As a **Windows automation engineer**, I want to record a native form-fill scenario.

Deferred to Desktop epic. Journey to be expanded once the architect picks the library (UI Automation raw vs. `RPA.Windows` vs. FlaUI).

---

## Domain Model

### New entities (frontend + backend)

```
RecordingSession
  id (uuid)
  transport: 'web_playwright' | 'desktop_windows' | 'desktop_macos'
  started_by_user_id
  repository_id
  started_at / ended_at
  status: 'active' | 'completed' | 'aborted'

RecordedFlow
  session_id (FK → RecordingSession)
  name  (user-provided OR generated from URL/app)
  commands: RecordedCommand[]

RecordedCommand
  index (int)
  keyword  (str, e.g. "Click" / "Get Element Value")
  args     (dict — keyword-specific non-selector args)
  selector_candidates: SelectorCandidate[]
  active_candidate_index (int, default 0)

SelectorCandidate
  strategy: 'testid' | 'aria' | 'text' | 'css' | 'xpath' | 'pw_locator'
  value     (str)
  quality_score (int 0–100 — higher = more stable)
  verified_unique (bool — was it a unique match at capture time?)
```

### Persistence

- `RecordingSession` rows persist only during the live session (purged hourly via Story-5-5 retention-cleanup pattern).
- `RecordedFlow` is never stored as its own row — it serializes to a `.robot` file the moment the user clicks Save. The in-editor state is the frontend store only.

### API surface (high-level)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/recordings/sessions` | POST | Start a session (transport + repo id) |
| `/api/v1/recordings/sessions/{id}` | DELETE | Abort |
| `/api/v1/recordings/sessions/{id}/commands` | GET (SSE) | Stream captured commands |
| `/api/v1/recordings/sessions/{id}/finalize` | POST | Stop + return the full RecordedFlow |
| `/api/v1/recordings/save` | POST | Persist a flow as `.robot` to the repo |

(Names are indicative; final contract belongs in the architecture doc.)

---

## Functional Requirements

| ID | Epic | Requirement |
|---|---|---|
| FR-R1 | WEB | Controlled browser session starts on Record click; no extension install required |
| FR-R2 | WEB | Capture nav / click / type / scroll / drag-drop at minimum |
| FR-R3 | WEB | DevTools-style hover overlay on every DOM element, non-blocking |
| FR-R4 | WEB | Right-click context menu grouped by keyword family (Assert/Read, Wait, Interact, State) |
| FR-R5 | WEB | Result opens in existing Visual-Flow + Text editor; saveable as .robot |
| FR-R6 | SEL | Every recorded command has ≥ 3 selector candidates where possible |
| FR-R7 | SEL | Inline selector-picker in the editor; swap candidate without re-recording |
| FR-R8 | SEL | Strategy library covers test-id, ARIA, text, CSS, XPath (multiple), Playwright locator |
| FR-R9 | SEL | Uniqueness check for every candidate at capture time; non-unique either parametrised (nth) or dropped |
| FR-R10 | WEB | Save flow requires EDITOR+ effective role on target repo (Story 3-7 guard) |
| FR-R11 | DESKTOP | Start a desktop recording session on Windows (UI Automation API) |
| FR-R12 | DESKTOP | Shared RecordedCommand shape with web — no divergence |
| FR-R13 | WEB | Audit events `recording.session.started` / `recording.session.completed` / `recording.flow.saved` |
| FR-R14 | SEL | Desktop-recorder generated commands reuse the same SelectorCandidate shape (quality-scored alternate paths) |

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-R1 | Zero outbound-network-at-boot invariant unchanged (existing Phase-4 NFR) |
| NFR-R2 | Controlled browser runs in the same container/host as the backend (no separate service to operate) |
| NFR-R3 | A recording session holds at most 1 Chromium process per user; auto-teardown on stop OR 30-min idle |
| NFR-R4 | All Recorder strings i18n-complete (EN/DE/FR/ES) before GA |
| NFR-R5 | Desktop recorder runs in-process with backend on Windows; no remote-agent for MVP |
| NFR-R6 | Selector-quality scoring algorithm is deterministic (same DOM → same scores) to keep tests reproducible |

---

## Non-Goals (Explicit)

- **Cross-browser recording** (Firefox / Safari) — Chromium-based only for MVP; deferred to Phase-next.
- **Mobile recording** — out of scope.
- **Replay-in-the-cloud** — recorder produces .robot files; replay uses the existing execution pipeline.
- **AI-assisted selector healing** — Phase-next candidate; ships as strategy #7 in SEL epic if demanded.
- **Chrome-extension deprecation** — the extension stays as a parallel transport; v2 does not remove it.
- **Recording-from-existing-trace** (HAR replay, etc.) — out of scope.

---

## Rollout & Success Metrics

### Release strategy

One epic per release cut:

1. **R-v2-Web** — Web Recorder MVP + minimum viable SelectorCandidate support.
2. **R-v2-Selectors** — Full selector strategy library + editor UI (may ride the Web release if ready).
3. **R-v2-Desktop** — Windows Desktop recorder; macOS tentative.

### Pre-merge gate per release

- Backend + frontend + e2e test regressions: zero.
- Fresh recording → saved .robot → executed through the existing runner → passes on the pilot app.
- axe-core accessibility gate on the Recorder view (matches Story 4-8 pattern).
- German locale completeness verified (vue-i18n prod-build).

### 30-day post-GA success metrics

(Defined in *Success Criteria* above.)

---

## Glossary

- **Controlled browser.** A Chromium instance Playwright has full CDP access to — can read the DOM, overlay annotations, and inject JS for hover tracking.
- **Selector candidate.** One of multiple locator strings that point to the same element; the recorder ships several per command so the user can swap without re-running.
- **RecordedFlow.** The JSON-serialisable shape the backend streams to the frontend; becomes a `.robot` file at Save time.
- **Transport.** A back-end module that produces commands for a RecordedFlow: `web_playwright`, `desktop_windows`, `desktop_macos`, or the legacy `chrome_extension`.
