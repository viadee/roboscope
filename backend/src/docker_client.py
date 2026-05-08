"""Shared Docker client bootstrap.

Story REFACTOR-1 — single source of truth for "create a Docker
client, fall back via `docker context inspect`, raise a typed error
when both paths fail." Previously this recipe lived (slightly
divergent) in three places: `settings/router.py`,
`execution/runners/docker_runner.py`, and `environments/tasks.py`.

Everything that needs a Docker client should now do:

    from src.docker_client import get_docker_client, DockerNotAvailableError

`get_docker_client()` always returns a *pinged* client (or raises),
so callers can use the result directly without re-checking
connectivity.
"""

from __future__ import annotations

import json
import logging
import subprocess

logger = logging.getLogger("roboscope.docker_client")


class DockerNotAvailableError(RuntimeError):
    """Raised when the Docker daemon cannot be reached via either
    `docker.from_env()` or the socket advertised by
    `docker context inspect`.
    """

    def __init__(self) -> None:
        super().__init__("DOCKER_NOT_AVAILABLE")


def _resolve_context_host() -> str | None:
    """Inspect the active `docker context` to find a working socket.

    Returns the `Endpoints.docker.Host` from `docker context inspect`,
    or `None` if the CLI is missing / fails / the JSON is unexpected.
    Never raises.
    """
    try:
        out = subprocess.check_output(
            ["docker", "context", "inspect"], text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    except Exception:
        return None

    try:
        ctx = json.loads(out)
    except json.JSONDecodeError:
        return None

    if isinstance(ctx, list) and ctx and isinstance(ctx[0], dict):
        # `host` is `Any` at the static layer because the JSON came
        # from external CLI output; isinstance-narrow before returning
        # so a malformed `docker context inspect` payload can't
        # smuggle a non-string into our typed return contract.
        host = ctx[0].get("Endpoints", {}).get("docker", {}).get("Host")
        if isinstance(host, str) and host:
            return host
    return None


def get_docker_client():
    """Return a pinged `docker.DockerClient`.

    Order of attempts:
      1. `docker.from_env()` (honours `DOCKER_HOST`, default
         `/var/run/docker.sock`, etc.).
      2. `docker.DockerClient(base_url=<context Host>)` for installs
         where `from_env()` can't find the socket — Rancher Desktop,
         Colima, Docker Desktop on macOS without `DOCKER_HOST` set.

    Raises:
        DockerNotAvailableError — if both attempts fail or neither
        produces a client that can `ping()`. The original exception
        is chained.
    """
    import docker

    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception as orig_err:
        host = _resolve_context_host()
        if host:
            try:
                client = docker.DockerClient(base_url=host)
                client.ping()
                return client
            except Exception:
                raise DockerNotAvailableError() from orig_err
        raise DockerNotAvailableError() from orig_err
