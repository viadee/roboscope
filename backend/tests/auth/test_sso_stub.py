"""Tests for the SSO login stub route (/api/v1/auth/sso/{idp_id}/login)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import IdentityProvider
from src.encryption import encrypt_value

BASE_URL = "/api/v1/auth/sso"


@pytest.fixture
def enabled_idp(db_session: Session) -> IdentityProvider:
    """Seed an enabled IdP for the SSO endpoint to resolve."""
    idp = IdentityProvider(
        name="test-idp-sso",
        provider_type="generic",
        issuer_url="https://idp.test/",
        client_id="sso-client",
        client_secret_encrypted=encrypt_value("secret").encode(),
        is_enabled=True,
    )
    db_session.add(idp)
    db_session.flush()
    db_session.refresh(idp)
    return idp


@pytest.fixture
def disabled_idp(db_session: Session) -> IdentityProvider:
    idp = IdentityProvider(
        name="test-idp-disabled",
        provider_type="generic",
        issuer_url="https://idp.test/",
        client_id="sso-client-disabled",
        client_secret_encrypted=encrypt_value("secret").encode(),
        is_enabled=False,
    )
    db_session.add(idp)
    db_session.flush()
    db_session.refresh(idp)
    return idp


# ---------------------------------------------------------------------------
# return_to validation
# ---------------------------------------------------------------------------


def test_invalid_external_return_to_rejected(client: TestClient, enabled_idp: IdentityProvider):
    res = client.get(
        f"{BASE_URL}/{enabled_idp.id}/login",
        params={"return_to": "https://evil.com/phish"},
    )
    assert res.status_code == 400


def test_invalid_return_to_has_error_code(client: TestClient, enabled_idp: IdentityProvider):
    res = client.get(
        f"{BASE_URL}/{enabled_idp.id}/login",
        params={"return_to": "https://evil.com/phish"},
    )
    body = res.json()
    assert body["detail"]["code"] == "return_to.invalid"
    assert "message" in body["detail"]
    assert body["detail"]["localization_key"] == "auth.error.returnToInvalid"


def test_protocol_relative_return_to_rejected(client: TestClient, enabled_idp: IdentityProvider):
    res = client.get(
        f"{BASE_URL}/{enabled_idp.id}/login",
        params={"return_to": "//evil.com/"},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "return_to.invalid"


def test_valid_relative_return_to_not_rejected(client: TestClient, enabled_idp: IdentityProvider):
    # Key invariant: valid return_to must not be rejected with 400.
    # Story 2-1 replaced 501 stub; expects 302 (cached discovery) or 503 (no cache).
    res = client.get(
        f"{BASE_URL}/{enabled_idp.id}/login",
        params={"return_to": "/dashboard"},
        follow_redirects=False,
    )
    assert res.status_code != 400


def test_no_return_to_not_rejected(client: TestClient, enabled_idp: IdentityProvider):
    res = client.get(
        f"{BASE_URL}/{enabled_idp.id}/login",
        follow_redirects=False,
    )
    assert res.status_code != 400


# ---------------------------------------------------------------------------
# IdP resolution
# ---------------------------------------------------------------------------


def test_unknown_idp_returns_404(client: TestClient):
    res = client.get(f"{BASE_URL}/99999/login", params={"return_to": "/"})
    assert res.status_code == 404


def test_disabled_idp_returns_404(client: TestClient, disabled_idp: IdentityProvider):
    res = client.get(
        f"{BASE_URL}/{disabled_idp.id}/login", params={"return_to": "/"}
    )
    assert res.status_code == 404


def test_idp_lookup_precedes_return_to_validation(client: TestClient):
    """Unknown-IdP 404 is raised BEFORE return_to validation.

    Anti-probing guard from the Phase 4 security review: the previous
    order exposed an IdP-existence oracle via 400 (valid return_to,
    invalid idp) vs 302 (valid return_to, valid idp). With the check
    order flipped, an anon caller cannot distinguish valid from
    invalid idp_id — every request with an unknown idp returns 404
    regardless of return_to shape.
    """
    res = client.get(
        f"{BASE_URL}/99999/login", params={"return_to": "https://evil.com"}
    )
    assert res.status_code == 404
