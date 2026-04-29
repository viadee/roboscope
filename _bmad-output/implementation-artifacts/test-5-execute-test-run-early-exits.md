# Story TEST-5: `execute_test_run` early-exit branch coverage

Status: done

Epic: TEST GAPS — backlog from CLAUDE.md "Test gaps (highest risk)"
Story Key: `test-5-execute-test-run-early-exits`

## Reported

CLAUDE.md "Test gaps":

> `execute_test_run()`

The orchestrator at the heart of every test run is ~200 lines that
threads through env-config resolution, runner selection, listener
setup, retries, and report parsing. End-to-end test coverage requires
real subprocess + venv + parser plumbing — not feasible in a unit
test. Until this story the function had **partial coverage** through
adjacent integration tests but **zero direct tests on the
early-exit branches**.

## Coverage delivered

`tests/execution/test_execute_test_run_branches.py` — 3 tests
covering the three early-exit branches that have shipped to
production at least once with this exact wording:

1. **`TestRunNotFound`** — `run_id=99999` (no row matches) returns
   `{"status": "error", "message": "Run not found"}` and emits no
   broadcast (no run id to scope to).

2. **`TestEnvironmentMissing`** — run with `environment_id=99999`
   (deleted env) → ERROR + "no longer exists" guidance + RUNNING +
   ERROR broadcasts in order. Pins the user-facing message text so
   future log-consumers / error-banner code can grep for it.

3. **`TestDockerRunnerMissingImage`** — Docker runner requested but
   `env_config.docker_image` is None → ERROR + "no Docker image"
   guidance, names the misconfigured env, never invokes the docker
   SDK. Regression guard for the
   "build a Docker image first" UX hint.

For each: assert (a) the run row's terminal status is ERROR (not
just the return-dict, since orchestrators sometimes fork before
reading), (b) the broadcast was emitted, (c) `finished_at` is set
so the UI clears the spinner.

## Approach

`execute_test_run` opens its own `get_sync_session()`, so the test
patches it to re-yield the test's transactional session — same
trick used in `tests/repos/test_auto_sync.py`.
`_broadcast_run_status` is patched to record arguments instead of
trying to schedule a coroutine without an event loop.

## Out of scope

- **Happy path (PASSED / FAILED / TIMEOUT)** — needs a fully mocked
  runner returning a `RunResult` plus filesystem stubs for
  `output.xml` parsing. Doable but ~80 lines of boilerplate per
  branch; deferred unless a real regression hits.
- **Cancellation race** — needs orchestrating two threads (the test
  thread sets status=CANCELLED while the runner thread is mid-execute).
  Already covered indirectly by `tests/execution/test_tasks.py::TestCancelActiveRun`.
- **rfbrowser-init missing** — early-exit branch but requires
  patching `check_rfbrowser_initialized` plus a venv-bearing
  env_config; defer.
- **Full retry loop** — the runner's retry behaviour lives inside
  `runner.execute`, not the orchestrator.

## Verification

`uv run pytest tests/execution/test_execute_test_run_branches.py` →
3/3 in 0.82 s.
