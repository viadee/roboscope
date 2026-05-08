# Story SH-6 — Heal-rate KPI on the Stats page

**Type:** BMAD quick story (SH-2 follow-up)
**Date:** 2026-04-24

## Background

SH-2 emits a heal-audit per run. SH-4 lets editors commit confirmed heals. What's missing: the *leading indicator*. A team that sees "heal rate trending up over the last 14 days" knows the test suite is drifting against the app; a team that never looks at that number only finds out when the suite goes red.

SH-6 surfaces that signal: scan recent runs for heal audit files, aggregate, show a compact KPI + a trend chart on the Stats Overview tab.

## Acceptance Criteria

1. **Endpoint** `GET /api/v1/stats/heal-rate?days=30&repository_id=<opt>` returns:
   - `total_runs_in_window`: number of runs whose `output_dir` we inspected
   - `runs_with_heals`: number of those that had at least one heal
   - `total_heals`: sum of heals across all runs
   - `confirmed_heals` / `suspect_heals`: outcome breakdown
   - `trend`: `[{date: "YYYY-MM-DD", heals: N, confirmed: N, suspect: N}]` last N days, zero-filled
2. Runs without an `output_dir` OR without a `heal_audit.jsonl` are counted in `total_runs_in_window` but contribute 0 to the heal numbers.
3. **Frontend** — new compact KPI card on the Stats Overview tab directly below the existing KPI row:
   - Big number: `total_heals`
   - Sub-line: `"{runs_with_heals} of {total_runs_in_window} runs healed"`
   - Two mini-badges: `🩹 {confirmed}` `⚠️ {suspect}`
   - 14-day sparkline using the existing Chart.js setup for consistency
4. Clicking a day on the chart jumps to the Execution view filtered to that day (nice-to-have; implement via existing Execution filter if trivial, otherwise skip).
5. **Tests** — endpoint with no runs (empty response), endpoint with runs-but-no-heals (zero heal numbers, non-zero total_runs), endpoint with mixed confirmed/suspect, trend zero-fill correctness.
6. **i18n** in EN/DE/FR/ES.

## Out of scope

- Per-test heal history ("which individual tests get healed most") — future story if heal-rate surfaces genuine pain.
- Background aggregation into `kpi_records`. The scan is cheap (reads one small JSONL per recent run); pre-aggregation is premature until the run count explodes.

## Rollback posture

- Read-only endpoint. No mutations. Nothing to undo.
- On malformed heal_audit.jsonl the endpoint silently treats that run as zero heals rather than failing the whole aggregation.
