# QA Findings — Execution core (2026-06-13)

BMAD QA edge-case audit of the highest-risk, least-tested backend paths
(`execution/`, `task_executor.py`, `websocket/manager.py`). Read-only audit;
all findings code-backed. Fix status tracked below.

| ID | Sev | Finding | Fix status |
|---|---|---|---|
| C1 | CRITICAL | Cancel during `prepare()`/sync silently lost — `execute()` reset `_cancelled=False`, suite ran to completion despite CANCELLED. | ✅ fixed (subprocess+docker short-circuit; tasks honors `result.cancelled`) |
| C2 | CRITICAL | SubprocessRunner read stderr only after `wait()` → full-pipe deadlock → false hang on stderr-heavy runs. | ✅ fixed (concurrent stderr drain thread) |
| H1 | HIGH | Inactivity-timeout mis-classified FAILED (status sniffed from "timeout" substring; message says "hung"). | ✅ fixed (`RunResult.timed_out` flag; tasks maps on flag) |
| H2 | HIGH | Docker `wait(timeout=)` = HTTP read timeout, doesn't stop container → leak + misclassification. | ✅ fixed (type-based timeout detect → stop container + flag) |
| H3 | HIGH | `commit-before-dispatch` violated on `TaskDispatchError` (flush-only) → run can strand in PENDING. | ✅ fixed (explicit `db.commit()` both paths) |
| H4 | HIGH | No orphan-run reaper → runs stuck RUNNING forever after backend restart. | ✅ fixed (Pass 4: `reconcile_interrupted_runs()` in lifespan startup) |
| M1 | MED | `connection_count`/`run_connection_count` iterate unlocked → `RuntimeError` under concurrent mutation. | ⏳ Pass 4 |
| M2 | MED | Cancel-during-execute correctness depends on commit-vs-refresh timing. | ⚠️ partly mitigated by C1 (`result.cancelled`); revisit Pass 4 |
| M3 | MED | Docker stdout decoded per-chunk → garbled multibyte (DE/FR/ES output). | ⏳ Pass 4 (incremental decoder) |
| L1 | LOW | `RLIMIT_AS` 2 GB can stop Chromium/Node from starting (virtual-mem cap). | ⏳ Pass 4 (use RLIMIT_DATA/cgroups or drop) |
| L2 | LOW | cancel-all ignores `cancel_active_run` return (orphans). | ⏳ Pass 4 |
| L3 | LOW | `output_dir` written before repo-exists check. | ⏳ Pass 4 |

## Coverage gaps confirmed (demo risk)
- `subprocess_runner.py`: existing tests fully mock `Popen` — real pipe/stderr/signals untested → C2 test now uses a real subprocess.
- `docker_runner.py`: existing tests mock the client; real `wait(timeout=)` untested → H2 test added.
- `execute_test_run()`: only the 3 early-exit branches tested (per the test file's own docstring); happy path + cancel race + retries uncovered.
- End-to-end run cancellation: untested → C1 tests added.

New regression tests: `backend/tests/execution/test_execution_robustness.py` (6 tests, all would fail pre-fix).
