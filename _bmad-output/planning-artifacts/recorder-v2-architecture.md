# Recorder v2 — Architecture Decisions

**Date:** 2026-04-22
**Author:** generated pre-sprint from PRD + epic breakdown
**Scope:** resolves every `[needs-arch]` flag in `recorder-v2-epics.md`, answers the six open questions, and specifies the minimum API contract the 19 stories depend on.

## AR-0 Snapshot

- **Transport stack:** Playwright (Python) driving local Chromium via CDP. One browser per session, no pool.
- **Hosting:** in-process with the backend container. No new service.
- **Command transport:** server-sent events (SSE) from FastAPI to the browser client.
- **Datamodel:** `RecordingSession` (DB row, short-lived) + `RecordedFlow` (in-memory + JSON, never persisted as a row — serialises to .robot on save).
- **Windows desktop:** `RPA.Windows` library under the hood; recording uses raw UI Automation via `pywinauto` so we are not locked to RPA's keyword-emit shape. Flow emits RPA.Windows keywords in the .robot output.
- **macOS desktop:** feasibility spike (DM.1) gated on a 4-hour time-box; decision deferred.

---

## AR-1 — Browser: per-session, not pooled

**Decision.** One dedicated `async_playwright()` + Chromium instance per `RecordingSession`.

**Why.** A pool looks efficient but adds state-leak risk (cookies, localStorage, permissions from one user's session bleeding into the next) and forces synchronisation around context tear-downs. A recording session is minutes long, not milliseconds. The overhead of booting a fresh Chromium is ~600 ms; amortised over a minute-plus session, that's noise.

**Consequences.**

- Per-user rate limit: `ROBOSCOPE_RECORDER_MAX_SESSIONS_PER_USER` (default 1). The second `POST /sessions` from the same user aborts the first.
- Cleanup: 30-min idle timer in the existing hourly retention cleanup (Story 5-5 pattern) aborts any still-active session.
- Memory: one Chromium is ~250-400 MB. Shop deployments with 100+ concurrent recorders need to size accordingly. Documented in the release notes.

**Alternative considered.** Browser-pool with context-per-session. Rejected: state isolation via `browser_context.clear_cookies()` is documented as "best-effort" in Playwright. Insufficient for a privileged capture surface.

---

## AR-2 — Controlled browser runs in-process, not in a sidecar

**Decision.** The Playwright instance runs inside the FastAPI backend container / host — same process group, same file system.

**Why.** Adding a separate sidecar would:
- Introduce inter-process coordination (gRPC / another SSE hop).
- Require a new deployment artifact (Dockerfile, healthcheck, orchestration).
- Duplicate auth / RBAC plumbing.

The session is capped at 30 min, one per user. Container resource governance handles the cap.

**Consequences.**

- Playwright must run its async API on a dedicated event-loop thread. See existing `run_playwright_recorder` in `backend/src/recording/tasks.py` (Story R-1) — reuse that threading pattern. The FastAPI request loop never touches the Playwright object.
- Browser event handlers only mutate `stop_event` + queue `RecordedCommand` payloads for the SSE emitter. No sync Playwright calls inside listeners (same rule as Story R-1).

---

## AR-3 — SSE over WebSocket

**Decision.** Command stream uses Server-Sent Events. The same pattern the existing WebSocket manager uses for run status, but unidirectional.

**Why.** Commands flow server → browser only. No upstream traffic. SSE is simpler on the frontend (native `EventSource`), survives reconnects with `Last-Event-Id`, and doesn't need the `/ws/` auth-upgrade dance. The existing WebSocket manager stays for execution status.

**Consequences.**

- New endpoint `GET /api/v1/recordings/sessions/{id}/commands` returns `text/event-stream`.
- Each event is `data: <json>\n\n` with `event: command`.
- Single subscriber only. Multiple tabs open on the same session: first wins, second gets 409.

---

## AR-4 — Hover overlay injection survives soft-navigation

**Decision.** Overlay is injected via `page.add_init_script()` so every new document the frame loads gets the same init script. For History-API navigations (pushState/replaceState without a full document load), we additionally set up a `popstate`+`pushState` proxy inside the init script that re-attaches the overlay listener.

**Why.** The classic bug: a SPA does `history.pushState(...)` to navigate without a new page load, and scripts added by `page.add_script_tag()` miss the transition. `addInitScript` runs *before* page scripts on every navigation including iframes; combined with a history-proxy inside the script for the SPA case, coverage is complete.

**Script lifecycle.**

```
page.add_init_script(OVERLAY_JS)  // runs on every navigation
OVERLAY_JS:
  mountOverlay()
  wrap(history, 'pushState')      // reinstall if SPA nav
  wrap(history, 'replaceState')
  addEventListener('popstate', mountOverlay)
```

---

## AR-5 — Right-click context menu: in-page DOM, not browser-chrome

**Decision.** The right-click menu is rendered as an overlay DIV inside the captured page (styled so it's unmistakably a RoboScope UI — amber left-accent, fixed font). The browser's native menu is suppressed via `contextmenu` event `preventDefault` on the overlay layer only.

**Why.** Injecting into the browser chrome requires an extension — same friction we're moving away from. In-page overlay + preventDefault gets us 95 % of the UX with zero install.

**Consequences.** The menu itself is a small Vue component rendered by the Playwright-injected `<iframe>` overlay layer. Styled to match RoboScope's brand so users don't confuse it with a fake.

---

## AR-6 — Keyword-family catalog (for Story W.5)

**Decision.** MVP menu groups. Pulled from the `Browser` library's keyword reference. Frozen list for v2; extensible via settings later.

```
Assert / Read:
  - Get Element Value
  - Get Text
  - Get Attribute
  - Should Be Equal
  - Should Contain

Wait:
  - Wait For Elements State
  - Wait Until Network Is Idle
  - Wait For Condition

Interact:
  - Double Click
  - Hover
  - Focus
  - Press Keys

State:
  - Scroll To Element
  - Take Screenshot
  - Highlight Elements
```

15 keywords total. Each menu item is a typed entry (`keyword`, `args_schema`). Extra args (e.g. expected-value for Should Be Equal) are captured via a compact inline mini-dialog in the overlay layer.

---

## AR-7 — Selector synthesis priority + scoring

**Decision.** The quality_score is an integer 0-100. Scoring rubric:

| Strategy | Base | Quality deductions |
|---|---|---|
| `testid` (configurable attr) | 95 | − 25 if value looks auto-generated (UUID shape, > 20 chars, mixed-case hash) |
| `aria` (role + name) | 80 | − 15 if name is dynamic (contains numbers / time) |
| `text` | 70 | − 20 if text is longer than 40 chars, − 30 if numeric-only |
| `css` | 50 | − 10 per structural step (`>`, `~`), − 20 if `:nth-child` needed |
| `xpath-absolute` | 25 | fixed low — always fragile |
| `xpath-relative-anchored` | 55 | − 10 if anchor is generic (`div`, `span`) |
| `xpath-text-anchored` | 65 | inherits text penalties |
| `pw_locator` (getByRole / getByText) | 75 | − 10 if derived from a generic role |

Uniqueness verification (Story S.3) runs after scoring. A candidate that's non-unique is either parameterised to `:nth-match(N)` or dropped. Candidates dropping below 20 post-deduction are omitted entirely.

**Ordering.** Final sorted order = `(verified_unique DESC, quality_score DESC)`. The first candidate becomes the active one; editor UI exposes the rest.

---

## AR-8 — Windows desktop transport

**Decision.** Raw UI Automation via `pywinauto` for capture; `RPA.Windows` keywords for emit. Recorder does NOT use `RPA.Windows` for capture — its event-loop shape is inside-out for our needs.

**Why.** `RPA.Windows` is great at driving (it wraps UIA well) but offers no introspection primitives for "record user's click". `pywinauto.InputEventHandler` gives raw mouse / keyboard hooks with element-under-pointer resolution.

**Emit mapping (AR-8.1).**

| Captured event | RPA.Windows keyword |
|---|---|
| Mouse-click on focusable control | `Click` |
| Text input into edit field | `Type Text` |
| Combo-box selection | `Select From Combobox` |
| Menu selection | `Select From Menu` |
| Window focus change | `Control Window` |

---

## AR-9 — Chrome extension transport stays untouched

**Decision.** The existing Chrome extension (Story R-1) remains a parallel, unchanged transport. v2 adds `web_playwright` + `desktop_windows` (+ optional `desktop_macos`) alongside it.

**Transport enum values.**

```python
class RecordingTransport(StrEnum):
    CHROME_EXTENSION = "chrome_extension"    # v1, unchanged
    WEB_PLAYWRIGHT   = "web_playwright"      # v2 MVP
    DESKTOP_WINDOWS  = "desktop_windows"     # v2 Epic D
    DESKTOP_MACOS    = "desktop_macos"       # v2 Epic DM (tentative)
```

No deprecation. No breaking changes to the v1 extension API.

---

## AR-10 — Rate limiting on recording sessions

**Decision.** Per-user cap: 1 active session at a time. Exceeding the cap aborts the older session and issues a toast in the newer tab.

**Why.** Prevents a runaway loop from spawning a Chromium army. Avoids conflicting capture streams on the same URL.

**Enforcement.** In `POST /recordings/sessions`: query for active sessions by `started_by_user_id`, abort any found, proceed with the new one.

---

## Minimum API contract (normative for the 19 stories)

```
POST   /api/v1/recordings/sessions
       Body: {transport, repo_id}
       Returns: {session_id, transport, status}
       Requires: effective_role(repo) >= EDITOR

GET    /api/v1/recordings/sessions/{id}/commands
       Content-Type: text/event-stream
       Events: event: command / data: <RecordedCommand JSON>
       Requires: same user as session starter

POST   /api/v1/recordings/sessions/{id}/finalize
       Returns: RecordedFlow (full JSON)

DELETE /api/v1/recordings/sessions/{id}
       Aborts the session; 204

POST   /api/v1/recordings/save
       Body: {flow: RecordedFlow, repo_id, path}
       Returns: {saved_path}
       Requires: effective_role(repo) >= EDITOR
```

---

## Test surface (estimate)

| Area | New unit | New integration | New e2e |
|---|---|---|---|
| Session lifecycle + retention | 10 | 2 | 1 |
| SSE stream + reconnect | 4 | 2 | 1 |
| Capture script emits correct commands | 12 | 4 | 2 (Chromium-driven Playwright test against a fixture app) |
| Selector synthesis + scoring | 25 | — | — |
| Uniqueness verification | 8 | 2 | — |
| Hover overlay + context menu | — | — | 3 |
| Desktop Windows (when epic lands) | 6 | 3 | 1 |

Est. 83 new tests total. phase4-gates.yml adds a new gate for Recorder: record-a-known-fixture-app + run the .robot + assert it passes.

---

## Rollout impact

- No migrations (RecordingSession already exists from Story R-1; we only add new rows).
- One new env var: `ROBOSCOPE_RECORDER_MAX_SESSIONS_PER_USER` (default 1).
- One new Docker-image dependency: Playwright's Chromium deb (~200 MB). Already part of existing e2e image; copy layer to the main backend image or split into a `roboscope-recorder` image variant. **Decision pending sprint planning** — both options have trade-offs (image size vs. deployment complexity).

---

## Open items tracked to implementation

- [ ] AR-1 per-session vs pool — *resolved, per-session*
- [ ] AR-2 in-process vs sidecar — *resolved, in-process*
- [ ] AR-3 SSE vs WebSocket — *resolved, SSE*
- [ ] AR-4 overlay-survive-SPA — *resolved, init-script + history proxy*
- [ ] AR-5 right-click menu — *resolved, in-page overlay*
- [ ] AR-6 keyword family list — *resolved, 15 keywords frozen for MVP*
- [ ] AR-7 selector scoring — *resolved, rubric above*
- [ ] AR-8 Windows transport — *resolved, pywinauto capture → RPA.Windows emit*
- [ ] AR-9 Chrome extension future — *resolved, parallel transport, no deprecation*
- [ ] AR-10 rate limiting — *resolved, 1/user*
- [ ] Playwright-image shipping strategy — *pending sprint planning call*
- [ ] Feasibility of macOS transport — *spike scheduled in DM.1, 4-hour time-box*
