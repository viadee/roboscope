# Story TEST-2: DockerRunner unit coverage

Status: done

Epic: TEST GAPS — backlog from CLAUDE.md "Test gaps (highest risk)"
Story Key: `test-2-docker-runner-coverage`

## Reported

CLAUDE.md "Test gaps":

> SubprocessRunner / DockerRunner

`SubprocessRunner` has tests; `DockerRunner` had none. The runner
spawns containers, streams logs, handles cancel + cleanup, and
translates docker-py exceptions into typed errors — exactly the
kind of code where a subtle regression silently breaks every
Docker-mode run.

## Coverage delivered

`tests/execution/test_docker_runner.py` — **24 tests** in four
classes, all using a mocked docker-py client (no daemon needed):

1. **TestBuildRobotCommand** (7) — pure command-string building:
   minimal, loglevel + color flag, single/multi-CSV `--include`
   tags with whitespace stripping, `--exclude`, variables (each
   becomes its own `--variable K:V`), and a kitchen-sink combination.

2. **TestPrepare** (4) — image-resolution path:
   - image already local → skips `images.pull`
   - image missing → triggers `images.pull`
   - pull failure → typed `DockerImageNotFoundError`
   - `env_config["docker_image"]` overrides the constructor image

3. **TestExecute** (6) — control flow around the container:
   - happy path (exit 0) returns RunResult with all output paths
   - non-zero exit → `success=False`, `exit_code` preserved
   - `containers.run` raises → `success=False, exit_code=-1`,
     error_message captured
   - `on_output` callback receives every log line
     (chunks split on `\n`, no double-emit)
   - `listeners` param logs a WARNING, doesn't break (FLAKY-3 follow-up)
   - `_cancelled` mid-stream breaks the log loop early

4. **TestCancelAndCleanup** (7) — defensive paths:
   - cancel with no container just sets the flag
   - cancel with container → `stop(timeout=10)`, kill not called
   - stop fails → falls back to `kill()`
   - kill also fails → swallowed (no raise)
   - cleanup removes with `force=True`, nulls `_container`
   - cleanup with no container is idempotent
   - cleanup with `remove()` failure swallowed

## Verification

`uv run pytest tests/execution/test_docker_runner.py` → 24/24 in
0.26 s. No daemon involvement; runs anywhere.

## Out of scope

- **End-to-end with a real Docker daemon.** Out of scope for unit
  tests; the existing integration coverage in
  `tests/execution/test_runner_interface_parity.py` exercises
  a real daemon when one is available.
- **Listener wiring (FLAKY-3).** The runner currently drops listeners
  with a warning; mounting them into the container is tracked
  separately. The test pins down the warning so the future fix
  flips one assertion.
- **Resource limits** (`mem_limit`, `cpu_quota`). These are static
  config; testing them would require introspecting the kwargs
  passed to `containers.run` — would catch regressions but adds
  noise without revealing real bugs.
