# Story SH-5 — Heal long-tail Browser keywords

**Type:** BMAD quick story (SH-2 follow-up)
**Date:** 2026-04-24

## Background

SH-2 shipped with six headline keywords (Click, Fill Text, Type Text,
Hover, Press Keys, Wait For Elements State). Real .robot files have a
long tail: Upload File, Check Checkbox, Select Options By, Drag And
Drop (two-selector), Get Text, Get Element Count. SH-5 extends
`RoboScopeHeal` so those cases heal too.

## Acceptance Criteria

1. New heal keywords, each wraps the same-named Browser keyword:
   - `Heal Upload File`
   - `Heal Check Checkbox`
   - `Heal Uncheck Checkbox`
   - `Heal Select Options By`
   - `Heal Get Text`         (read-only threshold)
   - `Heal Get Element Count` (read-only threshold)
   - `Heal Drag And Drop`    (two selectors — source + target)
2. `Heal Drag And Drop` heals the **source** selector first. If the
   source heals but the *target* then times out, a second round of
   healing applies to the target with the same safety envelope. No
   nested retry (one heal per call still applies, but across both
   selectors = at most two heals for one Heal Drag And Drop call).
3. Read-only keywords (`Get Text`, `Get Element Count`,
   `Wait For Elements State`) pass through the library's read-only
   confidence threshold (default 0.5). Mutating keywords keep the 0.7
   default.
4. Checkbox / Upload / Select keywords classify as **mutating**
   (threshold 0.7) — they change page state.
5. All new keywords honour the `no-heal` tag opt-out, the per-test
   budget, and the audit writer without duplication.
6. **Tests** — per new keyword: happy-path heal succeeds, no-heal
   budget path, source-then-target heal sequence for Drag And Drop.

## Out of scope

- Frame-scoped selectors (`iframe >>> …` pattern). Works by accident
  today because the selector string is opaque to the heal library;
  explicit frame support is a follow-up if real drift in frames shows
  up.
- Keyboard-only interactions (`Keyboard Key`, `Keyboard Input`) that
  don't take a selector — nothing to heal.
- Variants like `Click With Options` — the plain variant is the 90%.

## Rollback posture

- Identical to SH-2. Same opt-in contract (`Heal *` prefix), same
  budget limits, same suspect-classification at the report level.
  Adding keywords does not change any invariant.
