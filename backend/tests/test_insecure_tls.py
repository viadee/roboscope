"""INSECURE_TLS switch — every outbound path must flip together."""

import os
import ssl

import pytest

from src import insecure_tls
from src.config import settings
from src.environments.service import generate_dockerfile
from src.environments.venv_utils import pip_install_cmd


@pytest.fixture
def insecure(monkeypatch):
    monkeypatch.setattr(settings, "INSECURE_TLS", True)
    for key in insecure_tls.CHILD_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(ssl, "_create_default_https_context", ssl.create_default_context)


def test_off_by_default_changes_nothing(monkeypatch):
    monkeypatch.setattr(settings, "INSECURE_TLS", False)
    for key in insecure_tls.CHILD_ENV:
        monkeypatch.delenv(key, raising=False)
    assert insecure_tls.apply_insecure_tls() is False
    assert not any(k in os.environ for k in insecure_tls.CHILD_ENV)
    assert insecure_tls.tls_verify() is True
    assert insecure_tls.uv_insecure_host_args("https://pypi.corp/simple") == []
    assert "--allow-insecure-host" not in pip_install_cmd("/v", "robotframework")
    assert "INSECURE_TLS" not in generate_dockerfile("3.12", ["robotframework"])


def test_on_exports_child_env_and_patches_urllib(insecure):
    assert insecure_tls.apply_insecure_tls() is True
    assert os.environ["NODE_TLS_REJECT_UNAUTHORIZED"] == "0"
    assert os.environ["GIT_SSL_NO_VERIFY"] == "true"
    assert os.environ["npm_config_strict_ssl"] == "false"  # noqa: SIM112
    assert "pypi.org" in os.environ["UV_INSECURE_HOST"]
    assert ssl._create_default_https_context is ssl._create_unverified_context


def test_on_keeps_operator_override(insecure, monkeypatch):
    monkeypatch.setenv("UV_INSECURE_HOST", "pypi.corp")
    insecure_tls.apply_insecure_tls()
    assert os.environ["UV_INSECURE_HOST"] == "pypi.corp"


def test_on_httpx_verify_false_whatever_the_default(insecure):
    ctx = ssl.create_default_context()
    assert insecure_tls.tls_verify() is False
    assert insecure_tls.tls_verify(ctx) is False


def test_on_uv_allows_index_hosts(insecure):
    cmd = pip_install_cmd(
        "/v", "pkg", index_url="https://pypi.corp:8443/simple", extra_index_url="https://x.corp/s"
    )
    assert cmd[-5:] == [
        "--allow-insecure-host",
        "pypi.corp",
        "--allow-insecure-host",
        "x.corp",
        "pkg",
    ]
    assert insecure_tls.uv_insecure_host_args(None, "", "not a url") == []


def test_on_dockerfile_carries_env(insecure):
    df = generate_dockerfile("3.12", ["robotframework"])
    env_line = next(line for line in df.splitlines() if line.startswith("ENV "))
    assert 'NODE_TLS_REJECT_UNAUTHORIZED="0"' in env_line
    assert 'GIT_SSL_NO_VERIFY="true"' in env_line
    assert df.index(env_line) < df.index("RUN uv pip install")
