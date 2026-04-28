# Story REFACTOR-1: De-duplicate the Docker client bootstrap

Status: done

Epic: REFACTOR — backlog from CLAUDE.md "Known open issues"
Story Key: `refactor-1-docker-client-dedup`

## Reported

CLAUDE.md "Known open issues" lists:

> duplicated Docker client code

The "create a Docker client with `from_env()` fallback to
`docker context inspect`" recipe lives in three places:

1. `backend/src/settings/router.py:_get_docker_client()`
2. `backend/src/execution/runners/docker_runner.py:DockerRunner._get_client()`
3. `backend/src/environments/tasks.py` (inline in
   `build_docker_image`)

The three drift apart over time. Today they already disagree on
behaviour: only `DockerRunner._get_client` does a *second*
`ping()` after the context fallback and raises a typed
`DockerNotAvailableError`; the other two silently let `from_env`'s
exception propagate up the stack as a bare `docker.errors.DockerException`.

## The fix

A new module `backend/src/docker_client.py` exposes:

- `get_docker_client() -> docker.DockerClient`
- `class DockerNotAvailableError(RuntimeError)` — moved here so
  callers can `from src.docker_client import DockerNotAvailableError`
  without pulling in the full `DockerRunner`.

The runner re-exports the exception for backwards compatibility
(`from src.docker_client import DockerNotAvailableError` is the
new canonical import; `from src.execution.runners.docker_runner
import DockerNotAvailableError` keeps working via re-export).

## Acceptance Criteria

1. **AC1 — Single source.** `src/docker_client.py` is the only
   place where `docker.from_env()` and the
   `docker context inspect` fallback are wired together.

2. **AC2 — Three call sites updated.**
   - `settings/router.py:_get_docker_client` becomes
     `from src.docker_client import get_docker_client`. The local
     helper is deleted.
   - `execution/runners/docker_runner.py:DockerRunner._get_client`
     becomes a thin caching wrapper around `get_docker_client`.
   - `environments/tasks.py` `build_docker_image` calls
     `get_docker_client` instead of inlining.

3. **AC3 — Backwards-compatible exception import.**
   `from src.execution.runners.docker_runner import DockerNotAvailableError`
   still works.

4. **AC4 — Behaviour preserved.** Every call site still:
   - Tries `from_env()` + `ping()` first.
   - Falls back to `docker context inspect` on failure.
   - Raises `DockerNotAvailableError` when both paths fail.

5. **AC5 — Tests.**
   - `test_get_docker_client_uses_from_env_when_available` — patch
     `docker.from_env` to return a stub whose `ping()` succeeds;
     assert that's what's returned and `subprocess.check_output`
     is never called.
   - `test_get_docker_client_falls_back_to_context_inspect` — patch
     `from_env` to raise; patch `subprocess.check_output` to return
     a context with a Host; assert `DockerClient(base_url=...)` is
     used.
   - `test_get_docker_client_raises_when_both_fail` — both fail;
     `DockerNotAvailableError` is raised.

## Out of scope

- **Caching the client across calls in a request scope.** Today
  each call to `_get_docker_client` creates a fresh client. Caching
  is a separate concern — could cause auth/socket leaks if the
  daemon restarts.
- **Replacing the `docker context inspect` subprocess with a
  pure-Python re-implementation.** The CLI is faster to write and
  only 50 ms.

## Risk notes

- **The runner caches the client (`self._client`).** Refactor must
  preserve the cache: `get_docker_client()` is called only when
  `self._client is None`. Tests in `tests/execution/` exercise this.
- **`docker.errors.DockerException`** is a subclass of `Exception` —
  the existing bare `try/except Exception` works. Don't narrow.
