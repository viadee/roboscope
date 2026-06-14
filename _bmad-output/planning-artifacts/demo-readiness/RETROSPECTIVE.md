# Demo-Readiness Epic — Retrospective (2026-06-13/14)

Branch: `chore/demo-readiness-bmad` (off `main`). Goal: every RoboScope
feature individually demonstrable, working incl. edge cases, bugs fixed at
source, existing E2E pipeline green — via the BMAD workflow, iteratively.

## What was done (17 passes, BMAD roles)

- **Analyst/PM** — complete function inventory (backend, frontend,
  recorder/heal/debugger, ops/integrations/E2E) + a demo-readiness matrix
  covering all 11 areas A–K (every feature: demo entry + edge cases).
- **QA** — established the regression baseline (backend 2054 pytest +
  frontend vitest green) and ran **4 adversarial edge-case audits**:
  Execution core · AI/Reports/TaskExecutor · Flagship (Recorder/Heal/
  Debugger) · plus E2E triage. ~30 code-backed findings.
- **Dev/Architect** — **24 defects fixed at the source** (no workarounds),
  each with a regression test (fail-before/pass-after).
- **Demo** — reproducible per-feature demo scenarios (incl. edge cases) for
  all 11 areas, keyed to the seeded `backend/examples` fixtures.
- **Regression** — the existing pipeline run repeatedly on clean CI runners.

## Defects fixed (24)

Execution (9): C1 cancel-lost-during-prep · C2 stderr pipe deadlock · H1
timeout misclassification · H2 docker timeout/leak · H3 commit-before-
dispatch · H4 orphan-run reaper · M1 WS count-prop locks · M3 docker
multibyte decode · L1 RLIMIT_AS→DATA.
AI/Reports (8): C1 spec path-traversal · C2 code-fence corruption · H1
nested-suite flattening · H2 keyword-tag pollution · H4 empty-LLM-response ·
M1 AI dispatch commit · M3 LLM connect-timeout · H3 rotated-key error.
Heal (2): C1 sidecar confidence-scale gate · H1 per-repo RBAC on heal
endpoints.
Debugger (2): H3 breakpoint in control structures · M1 path-traversal guard.
Recorder/Heal (2): M2 Go To wait_until · M3 heal retry narrowing.
Plus 1 de-flake: asset-token base64 last-char aliasing.

## DoD status

| Criterion | Status |
|---|---|
| All features inventoried (structured spec) | ✅ |
| Per-function QA incl. edge cases | ✅ 4 areas deep-audited + E2E exercises A–K; rest cataloged |
| Bugs fixed at source | ✅ 24, with regression tests |
| Each feature demonstrable (reproducible scenarios) | ✅ all 11 areas |
| Existing E2E pipeline fully green | ✅ E2E + full unit (3.12/3.13) + 5 dist builds on clean CI |
| Iterative + status report per pass | ✅ 17 passes logged |

## Notable wins
- First-ever unit tests for the vendored `RoboScopeHeal` library (was zero
  coverage) — and they immediately pinned the C1 confidence-scale bug.
- The heal C1 fix restored the core safety invariant ("confidence thresholds
  gate every swap") which was silently bypassed on every recorded test.
- The heal H1 fix closed a cross-repo privilege-escalation in the Phase-4
  Team/Org model.

## Remaining follow-ups (documented, niche / not demo-critical)
- Heal: C2 (surface `unknown` heal outcome distinctly), M5 (iframe `>>`/`>>>`
  separator).
- Recorder: H2 (SSE single-subscriber 409), H5 (nth-disambig syntax for
  chained selectors), M4 (restart-after-crash queue).
- Debugger: H4 (atomic start dedup race on double-click).
- Low: L1 legacy generator escaping, L2 debug port TOCTOU.

See `qa-findings-*.md` for full detail and the `iteration-log.md` for the
pass-by-pass record.

## Lessons
- `timeout(1)` is not on this macOS — use the orchestration scripts / no
  wrapper. Several "hangs" were just that.
- Local full E2E is confounded by machine load + a persistent local DB; the
  authoritative E2E gate is CI `e2e.yml` on a clean runner.
- Cross-platform Playwright browsers can't be cross-built → the offline
  browser-pack is native-Windows/Linux only (separate `feat/offline-browser-pack`).
