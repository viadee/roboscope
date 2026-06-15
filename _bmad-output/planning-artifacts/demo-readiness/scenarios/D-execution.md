# Demo Scenarios — Area D: Execution & Scheduling

Seed: the auto-seeded **Examples** repo (`backend/examples/tests/`), admin
login. All paths assume a freshly-installed RoboScope.

---

### Run a test (subprocess runner) + live output — D
Seed: Examples repo → `calculator/basic_math.robot`.
Happy path:
  1. Explorer → Examples → `calculator` → `basic_math.robot` → **▶ Run**.
  2. Dismiss any pre-run dialog (env setup / library check).
  → expected: run-overlay-success appears naming `basic_math.robot`; live
     output streams in the Run panel; status → PASSED.
Edge cases:
  - **Cancel during venv prep** (C1): create a *new* environment, start a run
    that triggers venv creation, click **Cancel** during "preparing". →
    expected: run ends **CANCELLED**, the suite does NOT run to completion
    (regression `test_subprocess_cancel_before_execute_does_not_launch`).
  - **Inactivity / timeout** (H1): a hung run is reported as **TIMEOUT**
    (not FAILED) — status derived from `RunResult.timed_out`, not message text.
  - **stderr-heavy run** (C2): a test emitting >64 KB stderr completes
    cleanly (no false "hung") — stderr drained concurrently.
  - **Backend restart mid-run** (H4): restart the backend while a run is
    RUNNING → on restart the run is reconciled to **ERROR** ("interrupted by
    a backend restart"), never left spinning.
Capture: `execution-run.spec.ts` (overlay), `execution.spec.ts`.

### Docker runner — D
Seed: env with a `docker_image`; `DOCKER_AVAILABLE=true`.
Happy path: start a run with runner_type=docker → container runs, logs stream.
Edge cases:
  - **Docker daemon down** → graceful error, not a crash.
  - **Container timeout** (H2): the container is stopped (not leaked) and the
    run flagged TIMEOUT.
  - **Multibyte log output** (M3): DE/FR/ES test names render intact in the
    live stream (incremental UTF-8 decode).

### Cancel / retry — D
  - Cancel a RUNNING run → status CANCELLED, process killed.
  - Retry a FAILED run from the Run panel → new run starts.

### Schedules (cron) — D
Seed: Examples repo.
Happy path: Runs → Schedules → **+ New Schedule** → preset "Daily 08:00" →
  human-readable preview "Täglich um 08:00" → save → appears with next-run.
Edge cases:
  - **Invalid cron** (`not-a-cron`) → inline validation error, save blocked.
  - Timezone change → preview updates.
  - Enable/disable toggle persists.

### Retention — D (admin)
  - `POST /audit/retention/run` (ADMIN) → reports/runs older than
    `report_retention_days` deleted; APScheduler also runs it every 24h.
