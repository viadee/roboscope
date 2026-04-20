"""Smoke tests for the mock_oidc pytest fixture (AC 8)."""

from __future__ import annotations

import httpx
import pytest
from authlib.jose import jwt

from tests.fixtures.mock_oidc import (
    ISSUER,
    MockOidcProvider,
    _CLIENT_ID,
    mock_oidc,  # noqa: F401
)


def test_discovery_endpoint(mock_oidc: MockOidcProvider) -> None:
    """AC1 — discovery doc is served with correct issuer."""
    resp = httpx.get(f"{ISSUER}/.well-known/openid-configuration")
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["issuer"] == ISSUER
    assert "authorization_endpoint" in doc
    assert "token_endpoint" in doc
    assert "jwks_uri" in doc


def test_jwks_endpoint(mock_oidc: MockOidcProvider) -> None:
    """AC2 — JWKS returns test public key with expected kid."""
    resp = httpx.get(f"{ISSUER}/jwks")
    assert resp.status_code == 200
    keys = resp.json()["keys"]
    assert len(keys) >= 1
    assert keys[0]["kid"] == "test-key-1"
    assert keys[0]["kty"] == "RSA"


def test_token_exchange_with_custom_claims(mock_oidc: MockOidcProvider) -> None:
    """AC3/AC6 — token endpoint returns signed id_token with injected claims."""
    mock_oidc.with_claims(email="alice@example.com", groups=["admin"])

    resp = httpx.post(
        f"{ISSUER}/token",
        data={"grant_type": "authorization_code", "code": "dummy"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "id_token" in body

    pub_jwk = mock_oidc.public_jwk()
    claims = jwt.decode(
        body["id_token"],
        pub_jwk,
        claims_options={
            "iss": {"essential": True, "values": [ISSUER]},
            "aud": {"essential": True, "values": [_CLIENT_ID]},
        },
    )
    claims.validate()

    assert claims["email"] == "alice@example.com"
    assert "admin" in claims["groups"]
    assert claims["sub"] == "test-user-001"


def test_authlib_oauth2_client(mock_oidc: MockOidcProvider) -> None:
    """AC4 — authlib OAuth2Client can exchange a code via httpx transport."""
    from authlib.integrations.httpx_client import OAuth2Client

    client = OAuth2Client(
        client_id=_CLIENT_ID,
        client_secret="test-secret",
        token_endpoint=f"{ISSUER}/token",
    )
    mock_oidc.with_claims(email="bob@example.com", sub="bob-001")

    token = client.fetch_token(
        url=f"{ISSUER}/token",
        grant_type="authorization_code",
        code="dummy-auth-code",
    )
    assert "access_token" in token
    assert "id_token" in token

    pub_jwk = mock_oidc.public_jwk()
    claims = jwt.decode(token["id_token"], pub_jwk)
    assert claims["email"] == "bob@example.com"
    assert claims["sub"] == "bob-001"


def test_network_isolation(mock_oidc: MockOidcProvider) -> None:
    """AC5 — unmatched URLs raise under the active mock_oidc fixture."""
    from respx.models import AllMockedAssertionError

    with pytest.raises(AllMockedAssertionError, match="not mocked"):
        httpx.get("https://real-external-site.example.com/api")
