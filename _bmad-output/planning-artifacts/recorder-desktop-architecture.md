---
workflowType: 'architecture'
project_name: 'roboscope'
scope: 'recorder-desktop-windows'
author: 'Winston (Architect)'
date: 2026-06-25
inputDocuments:
  - _bmad-output/planning-artifacts/recorder-v2-prd.md
  - _bmad-output/planning-artifacts/recorder-v2-epics.md
  - _bmad-output/implementation-artifacts/deferred-work.md
  - backend/src/recording/desktop_recorder_task.py
  - backend/src/recording/desktop_selector_synthesis.py
  - backend/src/recording/robot_emit.py
  - CLAUDE.md
status: 'complete'
---

# Architecture Decision — Windows Desktop Recorder (Epic D, completion)

**Decision owner:** Winston (Architect persona)
**Status:** Accepted · 2026-06-25
**Supersedes:** the open question #3 in `recorder-v2-epics.md` ("`RPA.Windows` vs. raw `pywinauto`?") and closes the D-5 follow-up ("Windows native event-hook wiring").

## 1. Context

Recorder v2 shipped the Web Recorder (Epic W) and the shared SelectorCandidate
datamodel (Epic S). Epic D (Windows Desktop Recorder) was **scaffolded but not
finished**:

- `desktop_recorder_task.py` — thread lifecycle + pure `translate_uia_event`
  translator (unit-tested) + stop-signal registry. **The actual event-hook
  wiring inside `_desktop_loop` is a TODO** — the loop just blocks on the stop
  event and captures nothing.
- `desktop_selector_synthesis.py` — UIA locator scoring
  (`AutomationId > Name > ClassName > XPath`) — **done**.
- `robot_emit.py` — emits `RPA.Windows` keywords with `id:`/`name:`/`class:`/
  `xpath:` locator syntax — **done**.
- Router: `POST /recordings/sessions` + `/start-browser` dispatch
  `run_desktop_recorder_session`; `desktop_windows_viable` gating; `DELETE`
  calls `signal_stop_desktop`. SSE `/commands` + `/save` (with `emit_robot`)
  are transport-agnostic — **done**.
- Frontend: transport picker, live view, stop-and-save, capabilities gating,
  i18n EN/DE/FR/ES — **done** (with two transport-plumbing bugs noted in §6).

The only missing core is **capture**: turning real Windows mouse/keyboard
activity into `RecordedCommand`s.

A new option entered the conversation: **`platynui`** (`d-biehl` / `imbus`), an
emerging Rust-core desktop automation lib for Robot Framework.

## 2. Decision

> **Ship the Windows Desktop Recorder on the existing `pywinauto` + `RPA.Windows`
> stack now. Keep the emit layer pluggable so a `platynui` backend can be added
> later — when (and if) `platynui` reaches a stable release.**

### 2.1 Why not platynui (yet)

| Factor | platynui | pywinauto + RPA.Windows |
|---|---|---|
| Maturity | **Preview/Alpha** (`0.0.9` / `0.2.0.dev1`); explicit "APIs may change" warning | Mature, widely deployed (`rpaframework`) |
| Python floor | **3.12+** (our backend is `>=3.11` → a cross-cutting bump) | 3.11 OK |
| Build/offline | Rust 1.95+ toolchain; **per-platform/cp312 wheels** to vendor offline (cf. the roboheal wheel) | Pure-Python deps (`comtypes`, `pywin32`); simpler offline story |
| **Recording API** | **None** — platynui *drives* and *inspects*, it does not capture user input | None either — but irrelevant, see §3 |
| Effort to GA | High (stack rebuild + py bump + wheel pipeline) | Low (~the missing `_desktop_loop` only) |

Decisive point: **platynui does not solve the capture problem** (the actual hard
part). It is only an alternative for (a) the emitted keyword set / locator format
and (b) live inspection/highlight. Adopting it now would mean rebuilding a
nearly-complete stack and taking on alpha + py3.12 + Rust-wheel risk for **zero**
capture benefit. platynui is a strong **Phase-2** candidate, not a Phase-1
foundation.

### 2.2 Keeping the door open for platynui

The capture layer and the datamodel (`RecordedCommand` / `SelectorCandidate`)
are already **transport-agnostic**. The library coupling lives entirely in
`robot_emit._library_for_transport` + `_render_desktop_selector`. A future
`platynui` backend is therefore a localized change: a new emit branch +
locator-format mapping (AutomationId/Name/Class/XPath all map cleanly onto
platynui's XPath model), gated behind a transport/setting — no recorder rewrite.

## 3. Capture architecture (the missing core)

Capture is **our** responsibility regardless of automation lib. On Windows the
mechanism is OS-level, not library-level:

```
 Win32 low-level hooks (WH_MOUSE_LL / WH_KEYBOARD_LL, ctypes)
        │  raw mouse-up (x,y) / key events, on a thread with a message pump
        ▼
 UIA element resolution (pywinauto: ElementFromPoint + GetFocusedElement)
        │  → UIAElementInfo → ancestor walk
        ▼
 ElementSnapshot dict  {control_type, automation_id, name, class_name, ancestors[]}
        ▼
 DesktopEventAccumulator (PURE)  — buffers typed text, coalesces double-clicks,
        │                          classifies combobox/menu, flushes on focus/click/stop
        ▼  translator payload {kind, element, text|value}
 translate_uia_event()  →  RecordedCommand  →  enqueue_command()  →  SSE  →  Live view
```

### 3.1 Module split (testability-first)

The hard constraint from `desktop_recorder_task.py` is **"importable on every OS"**
(macOS/Linux dev boxes + CI run the unit tests). So OS glue and logic are split:

- **`desktop_capture.py` — PURE, no OS imports.** Holds:
  - `ElementInfoLike` protocol + `extract_snapshot(info, max_ancestors)` →
    payload dict (walks `.parent`, caps ancestor depth).
  - Raw-event dataclasses (`RawMouse`, `RawKey`, `RawFocus`).
  - `DesktopEventAccumulator` — the stateful classifier. Consumes raw events,
    yields translator payloads. **No `time`, no OS, no threads** → 100 %
    unit-testable on any host. Double-click is a flag set by the OS layer (which
    owns the timing); the accumulator only trusts it.
  - `pump_raw_events(events, emit, stop_event)` — drains a raw-event iterator
    through the accumulator into an `emit(payload)` callback. Testable with a
    fake iterator; this is the e2e seam for the backend integration test.
- **`win32_input.py` — Windows-only, import-guarded inside `_desktop_loop`.**
  Installs the `ctypes` LL hooks, runs the `GetMessage` pump, resolves elements
  via pywinauto, and pushes `RawMouse`/`RawKey`/`RawFocus` onto a thread-safe
  queue that `pump_raw_events` consumes. Never imported on non-Windows.
- **`desktop_recorder_task._desktop_loop`** — wires the two together; accepts an
  injectable `event_source` (default: build the real Win32 source on Windows) so
  the loop's command-emission path is exercised in tests without the OS.

### 3.2 Event → keyword mapping (extends the existing translator)

| Raw signal | Detected as | Keyword (RPA.Windows) |
|---|---|---|
| Left mouse-up on a control | `click` | `Click` |
| Two left-ups within `GetDoubleClickTime()` + drag rect | `dblclick` | `Double Click` |
| Buffered text committed (focus leaves / click / stop) | `type` | `Type Text  <text>` |
| Click on `ListItem` whose ancestor is `ComboBox` | `combobox_select` | `Select From Combobox  <value>` |
| Click on `MenuItem` | `menu_select` | `Select From Menu  <value>` |
| Top-level window focus change | `window_focus` | `Control Window` |

(`_UIA_KIND_TO_KEYWORD` already declares all six — no translator change needed.)

## 4. Deployment & viability (unchanged invariants)

- **Windows-host-only, interactive session required.** A desktop recorder can
  only capture apps on the machine running the backend, with a real interactive
  desktop. `desktop_windows_viable = sys.platform.startswith("win")` already
  gates the launcher; the `/start-browser` dispatch returns **501** elsewhere.
  This mirrors the `web_playwright_viable` pattern (CLAUDE.md: backend-launched
  capture is not remote-friendly). Realistic deployment target: the **offline
  Windows install** on a tester's machine.
- **Offline-only (NFR-R1).** `pywinauto` (+ `comtypes`, `pywin32`) are
  pure-Python wheels → vendor into the offline Windows bundle like any other
  dependency. No Rust toolchain, no per-arch native build (the platynui cost we
  are deliberately avoiding).
- **One capture thread per user** (NFR-R3 analogue): the existing per-user
  session cap + `_stop_signals` registry already enforce this.

## 5. Dependencies

- Add `pywinauto` to a **Windows-only optional dependency group** in
  `backend/pyproject.toml` (`[project.optional-dependencies] windows`), guarded
  with `sys_platform == 'win32'`. The deferred import in `_desktop_loop` already
  raises a clear install hint if it is missing. LL hooks use **`ctypes`** (stdlib)
  — no extra dependency for the hook layer itself.

## 6. Frontend transport-plumbing fixes (required for correctness)

Two bugs make the desktop path silently behave like web — fixed as part of this work:

1. `RecordingLiveView.ensureBrowserStarted` calls `startV2Browser(sessionId, url)`
   **without a transport**, and `/start-browser` defaults to `web_playwright` →
   a desktop session dispatches the **web** recorder. Fix: stash the transport in
   the launcher, thread it through `startV2Browser(sessionId, url, transport)`.
2. `RecordingLiveView.stopAndSave` hardcodes `transport: 'web_playwright'` in the
   saved `RecordedFlow` → desktop recordings would emit `Browser` library, not
   `RPA.Windows`. Fix: use the session's real transport in the flow.

## 7. Test strategy

- **Unit (any OS):** `extract_snapshot`, `DesktopEventAccumulator` (click,
  dblclick, type-buffering/flush, combobox/menu heuristics, window focus),
  `pump_raw_events`. Plus the existing translator/synthesis tests stay green.
- **Backend integration (any OS):** drive the **real** `_desktop_loop` via the
  injected `event_source` seam with synthetic raw events → assert
  `RecordedCommand`s enqueued → `emit_robot` produces a valid `RPA.Windows`
  `.robot`. This covers the real pipeline minus the OS hook.
- **E2E (real RoboScope UI, Playwright):** launcher → pick **Desktop (Windows)**
  → live view → command stream → **Stop & Save** → assert `.robot` carries
  `Library    RPA.Windows`. Native desktop input cannot be generated from a web
  e2e in CI, so the captured-command stream is served deterministically over the
  SSE route (consistent with `recorder-lifecycle.spec.ts`); the *real* capture
  pipeline is covered by the backend integration test above. This is logged as
  an explicit coverage boundary — not silent truncation.

## 8. Consequences

- ✅ Desktop Recorder reaches GA with minimal new surface — only the capture loop
  + two frontend fixes + tests.
- ✅ No Python bump, no Rust pipeline, no alpha-API exposure.
- ✅ `platynui` remains a clean, localized Phase-2 swap behind the pluggable emit.
- ⚠️ Capture relies on Win32 LL hooks + UIA, which can only be exercised
  end-to-end on a Windows host with an interactive desktop. The injectable
  `event_source` seam keeps everything below that boundary deterministically
  testable.
