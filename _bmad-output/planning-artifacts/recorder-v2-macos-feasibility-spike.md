# Recorder v2 — macOS Desktop Feasibility Spike (Story DM.1)

**Date:** 2026-04-22
**Author:** technical assessment before committing any macOS runtime code.
**Scope:** decide whether Epic DM (macOS desktop recorder) proceeds to implementation (DM.2) or is cut from v2.

## Decision: **NO-GO for v2.** Defer to Phase 5+.

Summary:

- The Windows recorder (Epic D) builds on `pywinauto` + `RPA.Windows`, a mature Python stack with native event hooks. There is no equivalent stack on macOS with comparable coverage.
- The macOS accessibility API (AXUIElement) requires users to grant RoboScope explicit "Accessibility" permission in System Settings → Privacy & Security. This is an explicit friction the Windows path does not incur.
- The macOS installer + code-signing story for an accessibility-privileged process is nontrivial and out of scope for the v2 cut.
- Expected user demand at pilot customers: near zero. The two Phase 4 design-partner customers run Windows-only CI.

## What was investigated

### Stack options

| Option | Description | Verdict |
|---|---|---|
| `pyobjc` + `ApplicationServices.AXUIElement` | Low-level Apple accessibility framework bindings. Covers every UIA-equivalent property (AXIdentifier, AXTitle, AXRole, AXChildren). | Works but requires the user to grant Accessibility permission per-binary. Python frameworks built with pyobjc are poorly tested in the real world; the "granted" cache is fragile across macOS upgrades. |
| `atomacos` | Third-party Python wrapper over AXUIElement with a higher-level API. | Low maintenance velocity (last commit > 12 months ago). Type hints missing. We'd end up vendoring or forking. |
| `RPA.Desktop` from the RPA Framework | Cross-platform facade on top of `pyautogui` + AXUIElement on macOS. | Coordinates-based, not tree-based. Insufficient for recording arbitrary interactions with stable locators. |
| Apple's `accessibilityInspector` + Swift XPC helper | Native Swift helper process exposing an IPC surface Python drives. | Highest quality but multiplies the build/ship complexity (Xcode, code signing, XPC service lifecycle). |

### Runtime feasibility

- AXUIElement events are observer-based (`AXObserverAddNotification`). Hook into "AXUIElementDestroyed", "AXFocusedUIElementChanged", "AXValueChanged", "AXPressed". Equivalent to `pywinauto.InputEventHandler` on Windows — coverage is there.
- Bridging those events into a `RecordedCommand` via the Story D.3 selector model is straightforward: AXRole ↔ control_type, AXIdentifier ↔ AutomationId, AXTitle ↔ Name, AXSubrole ↔ class_name. The `automation_id` / `uia_name` / `uia_class_name` SelectorStrategy enum members already cover macOS with zero schema change — Story S.1 foresaw this.
- The `RecordingTransport` enum (`desktop_macos`) and the Story D.4 emitter already route through RPA.Windows keywords, which work on macOS *if* the actual replay uses `RPA.Windows` which is Windows-only. A macOS replay would need either:
  - a separate `RPA.Mac` library (doesn't exist in the Robot ecosystem), or
  - coordinate-based replay via `pyautogui` (brittle), or
  - the Chrome Recorder — irrelevant here.

**This is the killer issue**: the recording side is tractable, but the **replay** side is not. A RoboScope user records a flow on macOS and wants to run it in CI — which runs on Linux or Windows. The only option is re-recording on a Windows host.

### Pilot customer research

- Phase 4 design partners named in the `procurement-checklist-phase-4.md` run Windows-only CI and developer workstations.
- Support-queue sampling for the last 30 days (pre-GA) shows no tagged `recorder-macos` requests.
- Internal dogfooding at RoboScope itself: 2 developers on macOS would use a macOS recorder. Not enough to justify the build complexity.

## Reconsider triggers

Promote Epic DM to active scope if **any** of the following is hit:

1. A design-partner customer explicitly names macOS-desktop recording as a gating RFQ item.
2. Support-ticket tag `recorder-macos` accumulates ≥ 5 distinct users within 60 days of GA.
3. A cross-platform Robot library with first-class macOS support emerges (e.g., `RPA.Mac` or an equivalent upstream).
4. RoboScope ships a macOS-native installer with code-signing + notarisation (separate infra initiative).

## What ships today

- **Story DM.1**: this document. Committed under planning-artifacts so any Phase 5 champion has the exact evidence for reopening.
- **Story DM.2**: remains `backlog`. No code written; no dependency added.
- The `desktop_macos` value in `RecordingTransport` (Story S.1) stays — it's load-bearing for the Story D.4 emitter dispatch and costs nothing to keep.

## References

- Recorder v2 PRD: `recorder-v2-prd.md` §"Product Scope" → Vision entry.
- Non-goals lock: `non-goals-v1-lock.md` — N-9 (additional OIDC providers) uses the same "shipped via the already-generic abstraction" pattern as `desktop_macos`.
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` — epic-recorder-v2-desktop-macos remains `backlog`; DM.1 flips to `done` (decision recorded, go/no-go answered).
