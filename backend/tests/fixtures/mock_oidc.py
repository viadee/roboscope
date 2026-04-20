"""Shared respx-based mock OIDC provider fixture.

Mocks the three OIDC endpoints that authlib contacts during SSO flows:
  - GET  {ISSUER}/.well-known/openid-configuration  (discovery)
  - GET  {ISSUER}/jwks                              (public key set)
  - POST {ISSUER}/token                             (token exchange)

All HTTP traffic is intercepted by respx — no outbound network calls.
Signed id_tokens use an in-process RSA-2048 test key (generated at import time).

Usage in tests::

    from backend.tests.fixtures.mock_oidc import mock_oidc  # noqa: F401

    def test_something(mock_oidc):
        mock_oidc.with_claims(email="alice@example.com", groups=["admin"])
        # ... exercise code that calls authlib / httpx
"""

from __future__ import annotations

import time
from collections.abc import Generator
from typing import Any

import httpx
import pytest
import respx
from authlib.jose import JsonWebKey, jwt
from cryptography.hazmat.primitives.asymmetric import rsa

# ---------------------------------------------------------------------------
# Module-level RSA test key (generated once per process — hermetic, offline)
# ---------------------------------------------------------------------------
ISSUER = "https://mock-idp.local"
_KID = "test-key-1"
_CLIENT_ID = "test-client-id"

_PRIVATE_KEY_RAW = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_JWK_PRIVATE = JsonWebKey.import_key(_PRIVATE_KEY_RAW, {"kty": "RSA", "kid": _KID})
_JWK_PUBLIC = JsonWebKey.import_key(_PRIVATE_KEY_RAW.public_key(), {"kty": "RSA", "kid": _KID})


def _mint_id_token(claims: dict[str, Any]) -> str:
    """Return a signed RS256 id_token string from *claims*."""
    header = {"alg": "RS256", "kid": _KID}
    token_bytes = jwt.encode(header, claims, _JWK_PRIVATE)
    return token_bytes.decode("utf-8") if isinstance(token_bytes, bytes) else token_bytes


# ---------------------------------------------------------------------------
# MockOidcProvider
# ---------------------------------------------------------------------------

class MockOidcProvider:
    """Stateful mock for a minimal OIDC provider.

    Wraps a ``respx.MockRouter`` and provides helpers to customise claims
    returned by the token endpoint on a per-call basis.
    """

    def __init__(self) -> None:
        self._pending_claims: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Static document helpers
    # ------------------------------------------------------------------

    def discovery_doc(self) -> dict[str, Any]:
        return {
            "issuer": ISSUER,
            "authorization_endpoint": f"{ISSUER}/authorize",
            "token_endpoint": f"{ISSUER}/token",
            "jwks_uri": f"{ISSUER}/jwks",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
        }

    def jwks_doc(self) -> dict[str, Any]:
        return {"keys": [_JWK_PUBLIC.as_dict()]}

    def public_jwk(self) -> Any:
        """Return the public JWK for token verification in tests."""
        return _JWK_PUBLIC

    # ------------------------------------------------------------------
    # Claims injection
    # ------------------------------------------------------------------

    def with_claims(self, **overrides: Any) -> "MockOidcProvider":
        """Override claims for the next token-endpoint response."""
        self._pending_claims.update(overrides)
        return self

    def _build_claims(self) -> dict[str, Any]:
        now = int(time.time())
        defaults: dict[str, Any] = {
            "iss": ISSUER,
            "aud": _CLIENT_ID,
            "sub": "test-user-001",
            "email": "test@example.com",
            "groups": [],
            "iat": now,
            "exp": now + 600,
        }
        defaults.update(self._pending_claims)
        self._pending_claims = {}
        return defaults

    # ------------------------------------------------------------------
    # Token endpoint handler
    # ------------------------------------------------------------------

    def handle_token(self, request: httpx.Request) -> httpx.Response:  # noqa: ARG002
        claims = self._build_claims()
        id_token = _mint_id_token(claims)
        return httpx.Response(
            200,
            json={
                "access_token": "mock-access-token",
                "token_type": "bearer",
                "expires_in": 600,
                "id_token": id_token,
            },
        )


# ---------------------------------------------------------------------------
# pytest fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_oidc() -> Generator[MockOidcProvider, None, None]:
    """Activate respx mock routes for the mock OIDC provider.

    Yields a :class:`MockOidcProvider` instance.  Tests call
    ``provider.with_claims(...)`` before exercising code that triggers
    the token endpoint.
    """
    provider = MockOidcProvider()

    with respx.mock(assert_all_called=False) as router:
        router.get(f"{ISSUER}/.well-known/openid-configuration").mock(
            return_value=httpx.Response(200, json=provider.discovery_doc())
        )
        router.get(f"{ISSUER}/jwks").mock(
            return_value=httpx.Response(200, json=provider.jwks_doc())
        )
        router.post(f"{ISSUER}/token").mock(side_effect=provider.handle_token)

        yield provider
