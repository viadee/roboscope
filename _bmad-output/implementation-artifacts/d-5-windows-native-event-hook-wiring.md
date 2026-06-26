# Story D-5 — Windows native event-hook wiring (Desktop Recorder capture)

**Epic:** D — Desktop Recorder (Windows)
**Status:** ready-for-dev → in-progress (2026-06-25)
**Depends on:** D.1 (session adapter, done), D.2 (translator, done), D.3 (selector
synthesis, done), D.4 (RPA.Windows emit, done)
**Architecture:** `_bmad-output/planning-artifacts/recorder-desktop-architecture.md`

## Story

As a **Windows automation engineer**,
I want my real clicks, double-clicks, typed text, combobox/menu selections and
window focus changes captured automatically while recording,
so that I get a runnable `RPA.Windows` `.robot` flow without annotating anything.

## Why this was deferred

D.1/D.2 closed at "Python skeleton + pure translator + dispatch + selector
synthesis + .robot emit". The native event-hook subscription inside
`_desktop_loop` was deferred because it can only be validated on a Windows host
and would have blocked the v2 milestone on a macOS dev box. This story completes
it on the Windows CI/dev host, with everything below the OS boundary made
deterministically testable via an injectable event source.

## Acceptance Criteria

1. **Capture wiring.** `_desktop_loop` installs Win32 low-level mouse + keyboard
   hooks (via `ctypes`), runs a message pump, and on each interaction resolves
   the UIA element (pywinauto `ElementFromPoint` / focused element) into an
   `ElementSnapshot`, producing translator payloads that flow through
   `translate_uia_event` → `enqueue_command`.
   - **Given** a recording desktop session on Windows
   - **When** the user left-clicks a control / double-clicks / types into a field /
     picks a combobox item / picks a menu item / switches the active window
   - **Then** a `Click` / `Double Click` / `Type Text` / `Select From Combobox` /
     `Select From Menu` / `Control Window` command appears on the live SSE stream
     with synthesised `SelectorCandidate[]`.
2. **Typed-text buffering.** Consecutive keystrokes into one focused field
   coalesce into a single `Type Text` command, flushed when focus leaves, a click
   occurs, or the session stops.
3. **Cross-OS import safety.** `desktop_recorder_task` + `desktop_capture` import
   cleanly on macOS/Linux; the pywinauto/ctypes Win32 code is imported only inside
   the Windows branch. Unit tests run on any host.
4. **Clean teardown.** `signal_stop_desktop` (wired to `DELETE /sessions/{id}`)
   uninstalls the hooks, exits the message pump, marks the session COMPLETED, and
   finalizes the SSE stream.
5. **Emit.** `Stop & Save` produces a `.robot` whose `*** Settings ***` is
   `Library    RPA.Windows` and whose targeted keywords carry `id:`/`name:`/
   `class:`/`xpath:` locators.
6. **Frontend transport correctness.** The desktop session actually dispatches the
   desktop task (transport threaded through `/start-browser`) and the saved flow's
   `transport` is `desktop_windows` (not the hardcoded `web_playwright`).

## Test plan

- **Unit (any OS):** `extract_snapshot`, `DesktopEventAccumulator`
  (click/dblclick/type-flush/combobox/menu/window-focus), `pump_raw_events`.
- **Integration (any OS):** real `_desktop_loop` via injected `event_source` of
  synthetic raw events → assert enqueued commands → `emit_robot` → valid
  `RPA.Windows` `.robot`.
- **E2E (Playwright, real UI):** desktop transport launcher → live stream → Stop &
  Save → saved `.robot` asserted to import `RPA.Windows`. Native OS input is out
  of web-e2e scope (logged boundary); the real capture path is covered by the
  integration test.

## Out of scope (future)

- platynui emit backend (Phase 2 — see architecture §2.2).
- macOS desktop capture (Epic DM — DM.1 NO-GO).
- Rich UIA event subscriptions beyond LL-hook-derived heuristics (e.g. native
  `SelectionItem_ElementSelected`); the click-on-ListItem heuristic covers the
  common combobox case for v1.

## Change log

- **2026-06-25** — Story opened from the recorder-v2 D-5 deferral; architecture
  decision (RPA.Windows now, platynui later) accepted; implementation begun.
