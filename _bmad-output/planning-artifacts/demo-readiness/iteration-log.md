# Demo-Readiness Iteration Log

## Pass 1 — 2026-06-13 — Analyst/PM: Function Inventory
- **Role:** BMAD Analyst/PM (4 parallel Explore agents).
- **Did:** Produced a complete function inventory across backend, frontend, recorder/heal/debugger, and ops/integrations/E2E. Persisted `function-inventory-backend.md`; synthesized everything into the demo-readiness matrix in `README.md` (11 areas A–K, every feature with demo entry point + key edge cases).
- **Verified:** N/A (inventory phase).
- **Bugs found / fixed:** none (inventory only). Pre-existing in-flight work noted: `feat/offline-browser-pack` (offline browser-pack + heal-from-wheel) awaiting merge.
- **Next:** establish regression baseline (QA), then begin per-feature QA verification starting with Area A (Auth/RBAC) and the highest-risk untested paths (SubprocessRunner/DockerRunner, execute_test_run, WebSocket, TaskExecutor, AI client).

## Pass 2 — 2026-06-13 — QA: baseline + edge-case audit (Execution core)
- **Role:** BMAD QA.
- **Baseline:** frontend `vitest` GREEN (exit 0). Backend `pytest` baseline running (long).
- **Did:** Read-only edge-case/defect audit of the highest-risk untested paths (execution runners, `execute_test_run`, `task_executor`, websocket manager). Produced `qa-findings-execution-2026-06-13.md`: 2 CRITICAL, 4 HIGH, 3 MED, 3 LOW — all code-backed.
- **Top demo-breakers:** C1 (cancel lost during venv prep), C2 (stderr pipe deadlock), H4 (no orphan reaper).

## Pass 3 — 2026-06-13 — Dev/Architect: execution-robustness fixes
- **Role:** BMAD Dev (architecture-aligned root-cause fixes).
- **Fixed (real root causes, not workarounds):**
  - C1 — runners no longer reset `_cancelled` in `execute()`; short-circuit when a cancel landed during prepare()/sync; `tasks.py` honors `result.cancelled`. (`subprocess_runner.py`, `docker_runner.py`, `tasks.py`)
  - C2 — stderr drained in its own thread (no full-pipe deadlock). (`subprocess_runner.py`)
  - H1 — `RunResult.timed_out` flag; `tasks.py` classifies TIMEOUT from the flag, not a message substring. (`base.py`, both runners, `tasks.py`)
  - H2 — docker timeout detected by exception type → stops the container + flags timed_out (no leak/misclassification). (`docker_runner.py`)
  - H3 — explicit `db.commit()` on the `TaskDispatchError` + success paths (commit-before-dispatch contract). (`router.py`)
- **Tests:** `tests/execution/test_execution_robustness.py` — 6 new (all fail pre-fix) GREEN. Existing `tests/execution/` regression: running.
- **Deferred to Pass 4:** H4 (orphan reaper), M1 (unlocked WS count props), M3 (docker multibyte decode), L1 (RLIMIT_AS), L2/L3.
- **Next:** confirm execution-suite regression green, commit, then Pass 4 (remaining HIGH/MED) + begin Area-A (Auth) QA and demo scenarios.

## Pass 4 — 2026-06-14 — Dev: orphan-run reaper (H4)
- **Role:** BMAD Dev.
- **Fixed:** H4 — `execution/tasks.py::reconcile_interrupted_runs()` marks any PENDING/RUNNING run as ERROR on startup (the in-memory runner registry is empty after a restart, so such rows are orphans that would otherwise spin forever). Wired into `main.py` lifespan right after `create_tables()`.
- **Tests:** `test_execution_robustness.py::test_reconcile_interrupted_runs_marks_only_orphans` (orphans→ERROR, terminal rows untouched). Robustness suite: 7 passed.
- **Remaining (Pass 5):** M1 (unlocked WS count props), M3 (docker multibyte decode), L1 (RLIMIT_AS), L2/L3; then begin Area-A (Auth) QA + demo scenarios + run the Playwright E2E suite for this branch.

## Pass 5 — 2026-06-14 — Dev: remaining QA findings (M1/M3/L1)
- **Role:** BMAD Dev.
- **Fixed:** M1 (lock the WS `connection_count`/`run_connection_count` props — no more "changed size during iteration"); M3 (docker logs decoded with an incremental UTF-8 decoder + newline buffer — no multibyte corruption / partial lines on DE/FR/ES output); L1 (`RLIMIT_DATA` 4 GB instead of `RLIMIT_AS` 2 GB so Chromium/Node can reserve virtual address space).
- **Tests:** M3 incremental-decode test added; robustness suite 8 passed; docker+ws+robustness 61 passed. M2 partly mitigated by C1; L2/L3 deferred (low impact).
- **Next:** run the full Playwright E2E pipeline for this branch (DoD gate) — boots backend+frontend, exercises features A-K through the real UI — then per-area demo scenarios.

## Pass 6 — 2026-06-14 — QA + Dev: E2E pipeline triage & green-up
- **Role:** BMAD QA (run + triage) + Dev (root-cause fixes).
- **Ran:** full local Playwright E2E (servers + suite) → 296 passed / 2 failed / 6 skipped.
- **Triaged:** both failures verified NOT regressions from Passes 3-5 (POST /runs returned 201 x8, no 500s/tracebacks). One consistent (stats), one flaky (execution-run).
- **Fixed at source:** (1) stats — duplicate accessible name "Aktualisieren" on two buttons → distinct `stats.refreshNow` label in EN/DE/FR/ES (a11y + UX); (2) execution-run — flaky assertion moved from the transient toast to the persistent `.run-overlay-success`.
- **Verified:** frontend vitest 734 passed + prod build clean; targeted E2E rerun 18 passed.
- **Next:** final full E2E run for green confirmation; then per-area demo scenarios (A→K).

## Pass 7 — 2026-06-14 — QA: E2E flake hardening + authoritative CI gate
- **Role:** BMAD QA.
- **Demo scenarios:** all 11 areas (A-K) now have reproducible per-feature demo walkthroughs incl. edge cases on disk.
- **E2E hardening:** the only failing specs across repeated local full runs were the REAL-run execution tests (`execution-run.spec.ts` POST/overlay) — timing/load-sensitive: they pass in isolation, and the failures trace to the documented single-worker task queue + a heavily-loaded local machine + a persistent local `e2e.db`, NOT app regressions (POST /runs 201, runs complete, no 500s). Hardened: `pollRunToCompletion` 220 s + test budget 260 s (execution-run + heal-toggle); run-overlay wait 30 s.
- **Decision:** the authoritative E2E gate is CI `e2e.yml` on a clean isolated runner (not the contended laptop). Pushing the branch to run it there for a trustworthy green signal — same approach used to validate the offline-browser-pack branch.
- **Local full-suite high-water mark:** 296 passed / 6 skipped with only real-run timing flakes outstanding.

## Pass 8 — 2026-06-14 — QA: authoritative CI green ✅
- **Role:** BMAD QA (regression gate).
- **Result on clean CI runners:** E2E Tests (e2e.yml) = success (full Playwright suite); Build Distribution (build.yml) = success (backend pytest 3.12+3.13 + frontend vitest + all 5 dist builds).
- **Conclusion:** all changes across Passes 1-7 keep the existing pipeline fully green; the local full-run flakes were environmental, not regressions. DoD E2E/regression gate MET.

<!-- Append a new "## Pass N" block per iteration. -->
