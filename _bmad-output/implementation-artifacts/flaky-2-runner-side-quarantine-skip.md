# Story FLAKY-2 — Runner-side skip of quarantined tests

**Type:** BMAD quick story (CI hygiene — FLAKY-1 follow-up)
**Date:** 2026-04-24

## Background

FLAKY-1 gave editors a way to mark a flaky test as quarantined — the data + the mark/unmark UI + the Stats-table badge. What FLAKY-1 deliberately did NOT do: actually skip those tests when the runner launches. FLAKY-2 fills that gap.

## Acceptance Criteria

1. **Given** the repo has any `FlakyQuarantine` rows, **when** `execute_test_run` runs for that repo, **then** a Robot Framework listener is registered via `--listener` that inspects each `start_test`'s name against the quarantine list and calls `BuiltIn().skip(...)` on matches. Skipped tests show up as `SKIP` in `output.xml` (not `FAIL`).
2. **Given** the repo has **zero** quarantine rows, **then** no listener is registered — no overhead for repos that don't use the feature.
3. **Given** a quarantined test is matched, **then** Robot Framework's native skip message is prefixed with `[roboscope-quarantine]` and contains the human-readable `reason` if one was set on the quarantine row.
4. **Given** a hand-written `Setup` or `Template` references a quarantined test name, **then** the listener logs the skip at `start_test` — not earlier — so suite-level setup runs even when the test body is skipped. Consistent with Robot's own skip semantics.
5. **Path-traversal / arbitrary-listener risk**: the listener path is computed server-side from a package-local import, NOT user input. Zero user-controlled data reaches the `--listener` argument.
6. The quarantine snapshot (`quarantine.json`) written into the run's output dir is **read-only** for the listener and discarded after the run — no persistence beyond the run lifecycle.
7. **Tests** — listener skip-matches-name, listener-no-match passes through, empty quarantine list builds no command flags, output.xml ends with SKIP status for the targeted test.

## Out of scope

- Per-run opt-out flag (`skip_quarantined=false` at run create time). Simpler first cut: skip is always-on; users who want the signal back unquarantine those specific rows. Reopen if CI teams complain.
- Auto-unquarantine after N stable runs (see FLAKY-1's out-of-scope list).
- Cross-repo quarantine (a test with the same name quarantined in repo A still runs in repo B — quarantine is always scoped to `repository_id`).

## Rollback posture

- Opt-out = unquarantine. Visible + auditable via the existing FLAKY_TEST_UNQUARANTINED audit event.
- The listener writes nothing to disk beyond the `output.xml` skip marker Robot already emits. A broken listener falls through via its wrapping `try/except` so a bug in the skip logic NEVER takes the test run down.
