"""TLS context hardening for outbound IdP calls (NFR13 — TLS 1.2+)."""

from __future__ import annotations

import ssl


def test_tls_context_minimum_version_is_1_2():
    """Outbound httpx calls must refuse TLS 1.0 / 1.1 at the client."""
    from src.auth.oidc_discovery import _TLS_CONTEXT

    assert _TLS_CONTEXT.minimum_version == ssl.TLSVersion.TLSv1_2


def test_tls_context_verifies_certificates():
    """Default production context must verify server certs (not CERT_NONE)."""
    from src.auth.oidc_discovery import _TLS_CONTEXT

    assert _TLS_CONTEXT.verify_mode == ssl.CERT_REQUIRED
    assert _TLS_CONTEXT.check_hostname is True
