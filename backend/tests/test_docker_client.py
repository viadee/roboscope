"""Story REFACTOR-1 — shared `src.docker_client.get_docker_client()`.

The three former call sites (settings/router, docker_runner,
environments/tasks) now route through this single function. These
tests pin down its three behavioural branches:

  1. `docker.from_env()` succeeds → return that client, no fallback.
  2. `from_env()` fails, `docker context inspect` returns a host →
     `DockerClient(base_url=...)` is used.
  3. Both paths fail → `DockerNotAvailableError` is raised.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.docker_client import (
    DockerNotAvailableError,
    _resolve_context_host,
    get_docker_client,
)


class TestGetDockerClient:
    def test_from_env_happy_path(self):
        """When `from_env()` returns a client whose ping succeeds,
        we return it and never touch `subprocess.check_output`.
        """
        stub_client = MagicMock(name="docker_client")
        stub_client.ping.return_value = True

        # Note: `docker` is imported *inside* `get_docker_client`, so
        # we patch through `sys.modules` indirection. The call site
        # does `import docker` → the patch on `docker.from_env`
        # applies as long as we patch the attribute on the module
        # object after import.
        import docker as docker_module

        with patch.object(docker_module, "from_env", return_value=stub_client) as mock_from_env, \
             patch("src.docker_client.subprocess.check_output") as mock_subprocess:
            client = get_docker_client()

        assert client is stub_client
        mock_from_env.assert_called_once()
        stub_client.ping.assert_called_once()
        mock_subprocess.assert_not_called()

    def test_falls_back_to_context_inspect(self):
        """`from_env()` fails → `docker context inspect` produces a
        Host → `DockerClient(base_url=Host)` is used.
        """
        import docker as docker_module
        import json

        ctx_payload = json.dumps([
            {"Endpoints": {"docker": {"Host": "unix:///custom/docker.sock"}}},
        ])

        ctx_client = MagicMock(name="ctx_client")
        ctx_client.ping.return_value = True

        with patch.object(docker_module, "from_env", side_effect=RuntimeError("no env")), \
             patch.object(docker_module, "DockerClient", return_value=ctx_client) as mock_dc, \
             patch(
                 "src.docker_client.subprocess.check_output",
                 return_value=ctx_payload,
             ):
            client = get_docker_client()

        assert client is ctx_client
        mock_dc.assert_called_once_with(base_url="unix:///custom/docker.sock")

    def test_raises_when_both_paths_fail(self):
        """`from_env()` fails AND no context Host → typed error."""
        import docker as docker_module

        with patch.object(docker_module, "from_env", side_effect=RuntimeError("no env")), \
             patch(
                 "src.docker_client.subprocess.check_output",
                 side_effect=FileNotFoundError("docker CLI not on PATH"),
             ):
            with pytest.raises(DockerNotAvailableError):
                get_docker_client()

    def test_raises_when_context_host_pings_fail(self):
        """The context fallback Host exists but pinging *that* client
        also fails → still raises `DockerNotAvailableError`.
        """
        import docker as docker_module
        import json

        ctx_payload = json.dumps([
            {"Endpoints": {"docker": {"Host": "tcp://1.2.3.4:2376"}}},
        ])

        broken_ctx_client = MagicMock(name="ctx_client")
        broken_ctx_client.ping.side_effect = RuntimeError("connection refused")

        with patch.object(docker_module, "from_env", side_effect=RuntimeError("no env")), \
             patch.object(docker_module, "DockerClient", return_value=broken_ctx_client), \
             patch(
                 "src.docker_client.subprocess.check_output",
                 return_value=ctx_payload,
             ):
            with pytest.raises(DockerNotAvailableError):
                get_docker_client()


class TestResolveContextHost:
    def test_returns_none_on_missing_cli(self):
        with patch(
            "src.docker_client.subprocess.check_output",
            side_effect=FileNotFoundError(),
        ):
            assert _resolve_context_host() is None

    def test_returns_none_on_malformed_json(self):
        with patch(
            "src.docker_client.subprocess.check_output",
            return_value="not-json{",
        ):
            assert _resolve_context_host() is None

    def test_returns_none_on_empty_endpoints(self):
        import json
        payload = json.dumps([{"Name": "default", "Endpoints": {}}])
        with patch(
            "src.docker_client.subprocess.check_output",
            return_value=payload,
        ):
            assert _resolve_context_host() is None

    def test_extracts_host(self):
        import json
        payload = json.dumps([
            {"Endpoints": {"docker": {"Host": "tcp://host:2375"}}},
        ])
        with patch(
            "src.docker_client.subprocess.check_output",
            return_value=payload,
        ):
            assert _resolve_context_host() == "tcp://host:2375"

    def test_returns_none_on_non_string_host(self):
        """Defensive: a malformed `docker context inspect` payload
        with a non-string `Host` value (could happen with custom
        plugins or future schema drift) must return None, not the
        non-string value coerced into a string. Pre-fix this leaked
        an `Any` upstream.
        """
        import json
        payload = json.dumps([
            {"Endpoints": {"docker": {"Host": 12345}}},
        ])
        with patch(
            "src.docker_client.subprocess.check_output",
            return_value=payload,
        ):
            assert _resolve_context_host() is None

    def test_returns_none_on_non_dict_first_entry(self):
        """Another malformed shape: `ctx[0]` is a string, not a dict.
        The .get() chain would crash; the isinstance guard rejects
        cleanly.
        """
        import json
        payload = json.dumps(["bogus-context-string"])
        with patch(
            "src.docker_client.subprocess.check_output",
            return_value=payload,
        ):
            assert _resolve_context_host() is None


class TestBackwardsCompat:
    def test_runner_re_exports_exception(self):
        """`from src.execution.runners.docker_runner import DockerNotAvailableError`
        must keep working — it lives in `src.docker_client` now but
        gets re-exported.
        """
        from src.execution.runners.docker_runner import (
            DockerNotAvailableError as RunnerExport,
        )
        from src.docker_client import (
            DockerNotAvailableError as Canonical,
        )
        assert RunnerExport is Canonical
