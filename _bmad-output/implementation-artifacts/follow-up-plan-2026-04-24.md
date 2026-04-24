# Follow-up Stories — Plan

**Date:** 2026-04-24
**Context:** all explicitly-deferred items from recent stories, prioritised by effort → value.

## Open follow-ups (in planned order)

| # | Story       | Origin           | Effort | Priority | Notes |
|---|-------------|------------------|--------|----------|-------|
| 1 | **SH-4**    | SH-2             | S      | 1        | One-click apply-patch writes the swap into `.robot`. Reuses AI-2 diff infra. |
| 2 | **FLAKY-2** | flaky-1          | S–M    | 2        | Runner-side skip of quarantined tests via Robot Framework `--exclude-tag`. |
| 3 | **SH-6**    | SH-2             | S      | 3        | Heal-rate KPI + mini chart on Stats page. |
| 4 | **SH-5**    | SH-2             | S–M    | 4        | Long-tail Browser keywords (Upload File, Drag And Drop, Mouse Button, frame-scoped Click). |
| 5 | **SH-3**    | SH-2             | M–L    | 5        | DOM-walk similarity scoring. Needs Recorder to emit element fingerprints, then runtime compares. |
| 6 | **E2E-SH**  | SH-2 / SH-3 / SH-4 | M    | 6        | Real Playwright + Robot Framework end-to-end test that exercises heal on a drifted fixture page. |
| 7 | **D-5**     | recorder-D-2     | blocked | n/a     | Windows native-hook wiring. Needs a Windows host; unavailable on this macOS machine. Stays in deferred-work.md. |

## Non-goals for this follow-up pass

- DB migrations for any of the above. Everything should ride on existing tables.
- Wiring the heal library into the default runner launch path. Users explicitly opt in via `Library    RoboScopeHeal` in their `.robot` files; implicit global enablement would break the SH-2 opt-in contract codified in CLAUDE.md.
- Refactoring the pre-existing flaky-detection service — FLAKY-2 only adds a filter on top, doesn't touch the ranking logic.

## Rollback invariants per follow-up

- **SH-4**: server-side writes must be atomic and guarded by the same editor-role check as `/recordings/save`. Reject any patch target outside the repo root (same path-traversal guard as save). Never overwrite without the patch's source heal being `confirmed` in the audit.
- **FLAKY-2**: per-run opt-out (`skip_quarantined=false` query param) so CI teams who want the signal back can disable it without un-quarantining every row. Default is apply-quarantine.
- **SH-3**: element fingerprints are recorder-side; a test without a sidecar still heals via the SH-2 transposition fallback — SH-3 never regresses SH-2.

## Test coverage target

- **Unit tests** for every new endpoint / parser / library function.
- **Frontend type-check** delta ≤ 0 new errors each commit.
- **Real e2e** (story E2E-SH): one pytest that drives a real Chromium via Playwright against a local HTML fixture where `id=submit` fails but `[data-testid=submit]` works, runs the heal library in-process (not via RF subprocess — to keep CI portable), asserts the heal record appears in the audit.
