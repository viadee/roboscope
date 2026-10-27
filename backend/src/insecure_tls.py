"""Opt-in ``INSECURE_TLS=true`` — ignore the whole TLS trust chain.

For corporate networks that MITM every HTTPS connection with a self-signed
CA that is not installed anywhere RoboScope's toolchain looks. Every
outbound path RoboScope owns stops verifying certificates:

* subprocesses (uv, rfbrowser init → npm + Playwright download, git) via
  the tool-specific env knobs exported by :func:`apply_insecure_tls`,
* in-process ``urllib`` (PyPI JSON) via the default-context monkeypatch,
* in-process ``httpx`` (PyPI search, LLM providers, webhooks, OIDC) via
  :func:`tls_verify`,
* the recorder's Playwright context via ``settings.INSECURE_TLS``.

The proper fix is to install the corporate CA (``SSL_CERT_FILE`` for
uv/httpx, ``NODE_EXTRA_CA_CERTS`` for node, ``GIT_SSL_CAINFO`` for git).
This switch exists for users who cannot. At their own risk.
"""

import logging
import os
import ssl
from urllib.parse import urlsplit

from src.config import settings

logger = logging.getLogger("roboscope.insecure_tls")

# Hosts uv contacts by default: PyPI + python-build-standalone downloads.
UV_DEFAULT_INSECURE_HOSTS = (
    "pypi.org files.pythonhosted.org github.com objects.githubusercontent.com"
)

# What every child process inherits. Keep in sync with the Dockerfile ENV
# line in environments/service.py::generate_dockerfile.
CHILD_ENV = {
    "UV_INSECURE_HOST": UV_DEFAULT_INSECURE_HOSTS,
    "NODE_TLS_REJECT_UNAUTHORIZED": "0",  # rfbrowser init: Playwright download
    "npm_config_strict_ssl": "false",  # rfbrowser init: npm install
    "GIT_SSL_NO_VERIFY": "true",  # git CLI + GitPython
}


def apply_insecure_tls() -> bool:
    """Export the skip-verification knobs into ``os.environ``. Idempotent.

    Returns True when the switch is on. Values already set by the operator
    win (``UV_INSECURE_HOST`` with extra hosts, for instance).
    """
    if not settings.INSECURE_TLS:
        return False
    for key, value in CHILD_ENV.items():
        os.environ.setdefault(key, value)
    ssl._create_default_https_context = ssl._create_unverified_context  # urllib
    logger.warning(
        "INSECURE_TLS is on: certificate verification is DISABLED for uv, "
        "npm/Playwright, git, PyPI, LLM, webhook and SSO connections. "
        "Use only in a trusted network."
    )
    return True


def tls_verify(default: object = True) -> object:
    """``verify=`` argument for httpx: False when the switch is on, else ``default``."""
    return False if settings.INSECURE_TLS else default


def uv_insecure_host_args(*urls: str | None) -> list[str]:
    """``--allow-insecure-host`` args for the hosts of the given index URLs."""
    if not settings.INSECURE_TLS:
        return []
    args: list[str] = []
    for url in urls:
        host = urlsplit(url or "").hostname
        if host:
            args += ["--allow-insecure-host", host]
    return args
