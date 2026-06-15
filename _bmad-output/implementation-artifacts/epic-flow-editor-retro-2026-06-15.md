# Retrospective — Flow Editor Epic (Verification & Hardening + Follow-ups + zh + Code Review)

- **Date:** 2026-06-15
- **Branch / PR:** `chore/demo-readiness-bmad` → PR #45
- **Scope reviewed:** hardening story (round-trip fidelity, libdoc-per-environment keyword discovery, inline Variables/suite-settings panels) + 4 follow-up stories (FE-BDD, FE-ENV, FE-TPL, FE-KWSRC) + Chinese locale + 3-layer code review.
- **Participants:** Amelia (Dev, facilitator) · Winston (Architect) · Sally (UX) · John (PM) · Dana (QA) · Thomas (Project Lead)

## Delivery snapshot
- 14 epic commits (a575937..30affaa) + review/cleanup; story docs under `planning-artifacts/flow-editor-*`.
- Tests: 799 frontend vitest · 16 backend libdoc pytest (+198 env-dir) · ~12 new flow-editor e2e · vue-tsc clean · ruff/mypy clean on new code.
- 0 production incidents (unmerged). Defects fixed at source: 2 round-trip corruption (initial) + 4 ECH data-loss + 7 code-review (1 HIGH).

## What went well
- **Design-first via party mode.** Spawning independent Architect/UX/PM/Dev voices before coding produced the libdoc-per-environment direction and the "RF owns the format" round-trip invariant — decisions that held up under review.
- **Pure-module extraction.** Pulling parse/serialize out of the 3.5k-line `RobotEditor.vue` into `robotTextIO.ts` made round-trip behaviour unit-testable (golden corpus) and was the single biggest quality lever.
- **Layered adversarial review paid for itself.** The Edge Case Hunter caught 4 data-loss paths; the 3-layer code review caught a HIGH AC-B3 regression the e2e had missed.
- **Fail-before/pass-after discipline** on every fix kept regressions pinned.

## What didn't (no blame — systems)
- **e2e fixtures masked a HIGH bug.** Every flow-editor e2e seeded a SINGLE test case, so an `activeItemIndex` reset-to-0 was invisible — the AC-B3 regression (inline edits yanking the canvas to test case #1) shipped past unit + e2e and was only caught in code review.
- **Two parallel `RobotForm` type systems** (`flowConverter.ts` vs `robotTextIO.ts`/`RobotEditor.vue`) forced double-edits (e.g. `templateRows` added twice) — latent friction/footgun.
- **`git add -A` committed stray artifacts** (`.tracemind/`, `backend/results/`, `tmp.txt`) — needed a cleanup commit; gitignore was reactive, not proactive.
- **Pre-existing parser gaps surfaced** (multi-line `[Tags]`/`[Setup]` `...` continuation dropped) — carried over via the extraction, now visible.

## Lessons
1. **e2e fixtures must include plurality** — 2+ of any indexed entity (test cases, keywords) so index/selection-reset bugs can't hide. Make it the baseline for editor specs.
2. **Extract to a pure, testable module early** when logic lives in a giant component.
3. **Adversarial layers > single-pass review** for parser/round-trip/stateful-UI code.
4. **Gitignore generated artifacts proactively**; never `git add -A` on a dirty tree.

## Action items
- [ ] Add a shared multi-test-case fixture to the flow-editor e2e baseline (Owner: QA/Dev).
- [ ] Tech-debt: unify the two `RobotForm`/`RobotStep` type systems behind one source (Owner: Dev/Architect).
- [ ] Address deferred items from code review when convenient: FQN `Library.Keyword` disambiguation; multi-line `[Tags]`/`[Setup]` continuation; template-cell-equals-control-marker doc (see `deferred-work.md`).
- [ ] Decide whether to complete the zh translation long-tail (currently English fallback) or leave as-is.

## Next-epic readiness
- No hard dependencies block the roadmap (Phase 4 Auth/SSO·Teams or Phase 5 Scale/Reporting). The libdoc backend + flow-editor are additive.
- **Open before "done":** PR #45 CI green + merge to `main` (gated on Project Lead). Then `bmad-document-project` to refresh brownfield docs (Flow Editor + libdoc changed a lot).

## Significant-discovery check
None that invalidate the roadmap. The two-type-system debt and the e2e-plurality gap are process/tech-debt, not architectural reversals.
