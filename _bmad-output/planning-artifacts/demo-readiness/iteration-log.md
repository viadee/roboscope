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

<!-- Append a new "## Pass N" block per iteration. -->
