# Story SH-2 — Runtime self-healing selectors (with rollback)

**Type:** BMAD story (not quick — safety-critical)
**Date:** 2026-04-24

## Background

SH-1 gave us post-hoc diagnosis: after a run fails, look up alternatives from the recorder sidecar. Valuable, but only for recorder-originated tests and only after the fact. SH-2 adds what actually matters — **heal at runtime**: intercept a selector failure, find a viable alternative, retry. Crucially, it also works for **hand-written tests** with no sidecar, by transposing the failed selector across strategies against the live page.

Self-healing is a **dual-use feature**: great when it works, catastrophic when it silently clicks the wrong thing and corrupts downstream state. This story is as much about the **rollback / safety envelope** as it is about the healing itself.

## The rollback philosophy

Browser state cannot be truly rolled back — a wrong `Click` navigates, submits, sends telemetry. So "rollback" here means:

1. **Bound the blast radius** before the swap: confidence thresholds, budget limits, opt-in at the keyword level. A user writes `Heal Click` instead of `Click` to explicitly mark "heal is OK here".
2. **Detect wrong heals after the fact** by watching whether *downstream* keywords in the same test pass. A heal that succeeds but the next keyword fails is flagged **suspect** — the patch-accept button is hidden for suspect heals and the run gets marked `⚠️ heal-suspect`.
3. **Never auto-commit a swap**. Every heal is a *suggestion* that the user explicitly accepts through the UI after review. The `.robot` file on disk is untouched during the run.
4. **Per-test escape hatch**: `[Tags] no-heal` on a test disables healing entirely for that test. For strict CI runs where flaky behaviour *is* the signal.

## Acceptance Criteria

### Runtime healing

1. **Given** a user imports `Library    RoboScopeHeal` into a `.robot` file and calls `Heal Click    id=submit`, **when** `Click    id=submit` times out, **then** the library finds alternative selectors (see AC 2 and 3), retries with the highest-confidence one, and the test call returns successfully if any candidate works.
2. **Given** the test has a sibling `<name>.rbs.json` sidecar, **when** a heal is triggered, **then** the library first consults the sidecar's candidate list for the matching line.
3. **Given** there is no sidecar OR the failing selector is not in it, **when** a heal is triggered, **then** the library generates candidates via **selector transposition** (if original is `id=X`: try `[data-testid=X]`, `text=X`, `css=input[name=X]`, `css=button#X`, etc.) against the live page. Candidates matching zero or >1 elements are rejected.
4. **Given** no candidate has confidence ≥ the configured threshold (default 0.7 for mutating keywords, 0.5 for read-only), **then** the library re-raises the original exception unchanged — no silent pass.
5. Supported keywords in first cut: `Heal Click`, `Heal Fill Text`, `Heal Type Text`, `Heal Hover`, `Heal Press Keys`, `Heal Wait For Elements State`. Follow-up story adds the long tail.

### Rollback / safety

6. **Per-test budget**: at most `max_heals_per_test` heals (default 3). Hitting the budget re-raises the original exception with a clear message — "too much drift, fix the test".
7. **Per-call retry budget**: at most 1 retry per `Heal *` call. Second failure is the real failure.
8. **Heal-audit log**: every heal writes a JSONL line to `<run_output_dir>/heal_audit.jsonl` with `timestamp`, `keyword`, `original_selector`, `healed_selector`, `confidence`, `source` (sidecar / transposition), `test_name`. Survives the run lifecycle independent of `output.xml`.
9. **Suspect-heal detection**: the run-side heal-report endpoint parses `heal_audit.jsonl` and cross-references with Robot's `output.xml` test results. A heal whose *test* ultimately failed is marked `outcome=suspect` (the wrong element likely got clicked). Heals whose test passed are marked `outcome=confirmed`.
10. **Tag-based opt-out**: if the test has tag `no-heal`, `Heal *` keywords delegate straight to the underlying Browser keyword with no retry — effectively disables the feature for that test without code changes.
11. **Never overwrite the `.robot` on disk**. No auto-commit anywhere in this story.

### Reporting + UX

12. **Endpoint** `GET /api/v1/runs/{run_id}/heal-report` returns `{total_heals, confirmed, suspect, entries: [{...}]}`. Parses `heal_audit.jsonl` from the run's output dir. 200 + empty list if no heal audit exists (tests without `Heal *` keywords).
13. **UI panel**: new `RunHealReport.vue` inside `RunDetailPanel.vue`, appears when `total_heals > 0`. Each entry shows:
    - 🩹 (confirmed) or ⚠️ (suspect) icon
    - Keyword + original selector → healed selector
    - Confidence %
    - Source badge (sidecar / transposition)
    - For **confirmed** heals only: "Copy patch" button that emits a unified diff (same format as AI-2 patches) to swap the selector.
14. **i18n**: EN/DE/FR/ES.

### Tests

15. **Unit tests** for the candidate finder: sidecar lookup, transposition for `id=`, `[data-testid=]`, `text=`, `css=`, `xpath=`, and confidence thresholds.
16. **Unit tests** for the heal library with mocked `BuiltIn.run_keyword`: happy path, no-candidates path, budget exhausted, threshold abort, tag-based opt-out, retry-per-call limit.
17. **Unit tests** for the heal-report parser: confirmed vs suspect classification, empty audit handling, malformed line skip.
18. **Integration smoke test** (guard-rail only, not blocking): load the library in a Robot Framework child process, assert it registers its keywords.

## Out of scope (future SH-3, SH-4)

- **SH-3**: DOM-walk similarity scoring (Healenium-style element-tree matching). Current transposition covers drift within strategy siblings; the tree-match catches bigger refactorings. Needs a stored element-fingerprint per step (recorder-side work).
- **SH-4**: One-click apply-patch (writes the swap into `.robot` on behalf of the user). Currently the user copies the diff and pastes manually — safer first cut, zero chance of destroying user edits.
- **SH-5**: Auto-heal the long tail of `Browser` keywords (Upload File, Mouse Button, Drag And Drop, Frame-scoped variants).
- **SH-6**: Heal-report surface on the Statistics page — which tests get healed most often, a leading indicator of upcoming test-debt.

## Critical pattern for CLAUDE.md

Any future "auto-fix test code" feature must respect the SH-2 opt-in invariant:
- **Explicit per-keyword opt-in** (the `Heal *` prefix is the user's informed consent).
- **Never mutate `.robot` files at run time** — suggestions only, review + accept happens in UI.
- **Suspect-heal detection** via downstream-test-outcome cross-reference before offering a patch.
