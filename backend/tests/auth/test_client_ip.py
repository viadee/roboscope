"""Tests for proxy-aware client IP extraction.

Covers the leftmost-trusted algorithm: peer must be in the trusted
proxies set before we honor X-Forwarded-For; a hostile direct client
that sends its own XFF header is ignored.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.auth.client_ip import get_client_ip


def _app_returning_client_ip() -> FastAPI:
    app = FastAPI()

    @app.get("/probe")
    def probe(request: Request) -> dict:
        return {"ip": get_client_ip(request)}

    return app


class TestNoTrustedProxies:
    """Default: no trusted proxies → always use peer IP, ignore XFF."""

    def test_uses_peer_ip_when_no_xff(self):
        client = TestClient(_app_returning_client_ip())
        resp = client.get("/probe")
        # TestClient's default peer is "testclient"; absent proxy-trust
        # we return the peer verbatim.
        assert resp.status_code == 200
        assert resp.json()["ip"] == "testclient"

    def test_ignores_xff_when_no_proxies_configured(self):
        client = TestClient(_app_returning_client_ip())
        resp = client.get(
            "/probe", headers={"X-Forwarded-For": "203.0.113.7"}
        )
        assert resp.json()["ip"] == "testclient"


class TestTrustedProxy:
    """With the peer in the trusted set, honor XFF."""

    def test_returns_leftmost_entry_when_peer_is_trusted(self):
        # testclient IP is "testclient" (a literal, not a dotted quad).
        # We patch the trusted-proxy list to include a catch-all so
        # the test client is treated as trusted. Cover the algorithm.
        with patch("src.auth.client_ip._trusted_proxies") as trust:
            import ipaddress
            trust.return_value = [ipaddress.ip_network("0.0.0.0/0")]

            # Since peer must pass _is_trusted(peer_str, nets) and
            # peer_str is "testclient" (not an IP), we additionally
            # patch _is_trusted to return True for "testclient".
            with patch("src.auth.client_ip._is_trusted") as is_trusted:
                def _trust_peer_and_real_ips(ip_str, _nets):
                    if ip_str == "testclient":
                        return True
                    # Trust anything in 10.0.0.0/8 (proxy chain)
                    return ip_str.startswith("10.")

                is_trusted.side_effect = _trust_peer_and_real_ips
                client = TestClient(_app_returning_client_ip())
                resp = client.get(
                    "/probe",
                    headers={"X-Forwarded-For": "203.0.113.5, 10.0.0.1"},
                )
                # Rightmost (10.0.0.1) is trusted → skip → leftmost
                # (203.0.113.5) is untrusted → return it as client.
                assert resp.json()["ip"] == "203.0.113.5"

    def test_returns_peer_when_xff_missing_even_if_peer_trusted(self):
        with patch("src.auth.client_ip._trusted_proxies") as trust:
            import ipaddress
            trust.return_value = [ipaddress.ip_network("0.0.0.0/0")]
            with patch("src.auth.client_ip._is_trusted", return_value=True):
                client = TestClient(_app_returning_client_ip())
                resp = client.get("/probe")
                # No XFF → we fall back to the peer.
                assert resp.json()["ip"] == "testclient"
