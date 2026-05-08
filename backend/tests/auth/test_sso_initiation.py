"""Tests for SSO provider listing and OIDC login initiation (Story 2-1)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.audit.models import AuditLog
from src.auth.models import IdentityProvider, OidcLoginAttempt
from src.encryption import decrypt_value, encrypt_value, is_encrypted

BASE_URL = "/api/v1/auth/sso"
_MOCK_ISSUER = "https://mock-idp.local"
_DISCOVERY_DOC = {
    "issuer": _MOCK_ISSUER,
    "authorization_endpoint": f"{_MOCK_ISSUER}/authorize",
    "token_endpoint": f"{_MOCK_ISSUER}/token",
    "jwks_uri": f"{_MOCK_ISSUER}/jwks",
}


def _make_idp(
    db: Session,
    *,
    name: str = "test-idp",
    is_enabled: bool = True,
    with_cache: bool = True,
) -> IdentityProvider:
    idp = IdentityProvider(
        name=name,
        provider_type="oidc_generic",
        issuer_url=_MOCK_ISSUER,
        client_id="test-client-id",
        client_secret_encrypted=encrypt_value("test-secret").encode(),
        scopes="openid profile email",
        group_claim_name="groups",
        is_enabled=is_enabled,
    )
    if with_cache:
        idp.discovery_cache_json = json.dumps(_DISCOVERY_DOC)
        idp.discovery_cached_at = datetime.now(timezone.utc)
    db.add(idp)
    db.flush()
    db.refresh(idp)
    return idp


# ---------------------------------------------------------------------------
# GET /sso/providers
# ---------------------------------------------------------------------------


def test_list_providers_returns_enabled_only(client: TestClient, db_session: Session):
    _make_idp(db_session, name="enabled-idp", is_enabled=True)
    _make_idp(db_session, name="disabled-idp", is_enabled=False)
    resp = client.get(f"{BASE_URL}/providers")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "enabled-idp" in names
    assert "disabled-idp" not in names


def test_list_providers_no_auth_required(client: TestClient, db_session: Session):
    resp = client.get(f"{BASE_URL}/providers")
    assert resp.status_code == 200


def test_list_providers_public_fields_only(client: TestClient, db_session: Session):
    _make_idp(db_session)
    resp = client.get(f"{BASE_URL}/providers")
    assert resp.status_code == 200
    provider = resp.json()[0]
    assert set(provider.keys()) == {"id", "name", "provider_type"}
    assert "issuer_url" not in provider
    assert "client_id" not in provider
    assert "client_secret_encrypted" not in provider


def test_list_providers_empty_when_none_enabled(client: TestClient, db_session: Session):
    resp = client.get(f"{BASE_URL}/providers")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /sso/{idp_id}/login — happy path
# ---------------------------------------------------------------------------


def test_login_redirect_302(client: TestClient, db_session: Session):
    idp = _make_idp(db_session)
    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    assert resp.status_code == 302


def test_login_redirect_targets_authorization_endpoint(
    client: TestClient, db_session: Session
):
    idp = _make_idp(db_session)
    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    location = resp.headers["location"]
    assert location.startswith(f"{_MOCK_ISSUER}/authorize")


def test_login_pkce_params_present(client: TestClient, db_session: Session):
    idp = _make_idp(db_session)
    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    location = resp.headers["location"]
    params = parse_qs(urlparse(location).query)
    assert params["response_type"] == ["code"]
    assert params["code_challenge_method"] == ["S256"]
    assert "code_challenge" in params
    assert "state" in params
    assert "nonce" in params
    assert params["client_id"] == ["test-client-id"]
    assert "openid" in params["scope"][0].split()
    assert params["redirect_uri"][0].endswith("/api/v1/auth/sso/callback")


def test_login_persists_attempt_row(client: TestClient, db_session: Session):
    idp = _make_idp(db_session)
    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    location = resp.headers["location"]
    state = parse_qs(urlparse(location).query)["state"][0]

    attempt = db_session.query(OidcLoginAttempt).filter_by(state=state).first()
    assert attempt is not None
    assert attempt.idp_id == idp.id
    assert attempt.pkce_verifier != ""
    assert attempt.nonce != ""
    assert attempt.return_to == "/"


def test_login_pkce_verifier_encrypted_at_rest(
    client: TestClient, db_session: Session
):
    """pkce_verifier must be Fernet-encrypted on disk (D1 hardening)."""
    idp = _make_idp(db_session)
    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]

    attempt = db_session.query(OidcLoginAttempt).filter_by(state=state).first()
    assert attempt is not None
    assert is_encrypted(attempt.pkce_verifier)
    decrypted = decrypt_value(attempt.pkce_verifier)
    assert len(decrypted) >= 43  # token_urlsafe(32) ≥ 43 chars


def test_login_attempt_ttl_is_ten_minutes(
    client: TestClient, db_session: Session
):
    """AC2: expires_at must be ~10 minutes after created_at."""
    idp = _make_idp(db_session)
    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]

    attempt = db_session.query(OidcLoginAttempt).filter_by(state=state).first()
    assert attempt is not None
    created = attempt.created_at
    expires = attempt.expires_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    delta_s = (expires - created).total_seconds()
    assert 550 < delta_s < 650, f"expected ~600s TTL, got {delta_s}s"


def test_login_state_and_nonce_entropy(client: TestClient, db_session: Session):
    """NFR6: state/nonce/pkce_verifier must carry ≥128 bits entropy."""
    idp = _make_idp(db_session)
    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    params = parse_qs(urlparse(resp.headers["location"]).query)

    state = params["state"][0]
    nonce = params["nonce"][0]
    # token_urlsafe(32) produces ≥43-char base64url strings = 256 bits entropy.
    assert len(state) >= 43
    assert len(nonce) >= 43

    attempt = db_session.query(OidcLoginAttempt).filter_by(state=state).first()
    assert attempt is not None
    assert len(decrypt_value(attempt.pkce_verifier)) >= 43


def test_login_return_to_stored_in_attempt(client: TestClient, db_session: Session):
    idp = _make_idp(db_session)
    resp = client.get(
        f"{BASE_URL}/{idp.id}/login",
        params={"return_to": "/dashboard"},
        follow_redirects=False,
    )
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]
    attempt = db_session.query(OidcLoginAttempt).filter_by(state=state).first()
    assert attempt is not None
    assert attempt.return_to == "/dashboard"


# ---------------------------------------------------------------------------
# GET /sso/{idp_id}/login — error cases
# ---------------------------------------------------------------------------


def test_login_unknown_idp_returns_404(client: TestClient, db_session: Session):
    resp = client.get(f"{BASE_URL}/9999/login", follow_redirects=False)
    assert resp.status_code == 404


def test_login_disabled_idp_returns_404(client: TestClient, db_session: Session):
    idp = _make_idp(db_session, is_enabled=False)
    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    assert resp.status_code == 404


def test_login_invalid_return_to_returns_400(client: TestClient, db_session: Session):
    idp = _make_idp(db_session)
    resp = client.get(
        f"{BASE_URL}/{idp.id}/login",
        params={"return_to": "https://evil.com/steal"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "return_to.invalid"


def test_login_no_discovery_cache_returns_503(client: TestClient, db_session: Session):
    idp = _make_idp(db_session, with_cache=False)
    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "idp.unreachable"


# ---------------------------------------------------------------------------
# State uniqueness
# ---------------------------------------------------------------------------


def test_each_login_request_gets_unique_state(client: TestClient, db_session: Session):
    idp = _make_idp(db_session)
    states = set()
    for _ in range(3):
        r = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
        state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
        states.add(state)
    assert len(states) == 3


# ---------------------------------------------------------------------------
# AC4: no audit log entry for SSO initiation
# ---------------------------------------------------------------------------


def test_login_does_not_write_audit_log(client: TestClient, db_session: Session):
    """AC4: GET /sso/{id}/login is not audited (audit middleware skips GET)."""
    idp = _make_idp(db_session)
    before = db_session.query(AuditLog).count()
    client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    after = db_session.query(AuditLog).count()
    assert after == before


# ---------------------------------------------------------------------------
# Cache-Control hardening on redirect
# ---------------------------------------------------------------------------


def test_login_redirect_has_no_store_cache_control(
    client: TestClient, db_session: Session
):
    """state/nonce in Location header must not be cached."""
    idp = _make_idp(db_session)
    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    assert resp.headers.get("cache-control") == "no-store"


# ---------------------------------------------------------------------------
# Discovery doc edge cases
# ---------------------------------------------------------------------------


def test_authorization_endpoint_with_existing_query_string(
    client: TestClient, db_session: Session
):
    """IdPs like Azure AD B2C ship `authorization_endpoint` with query params.

    The auth URL must join with `&`, not `?` (which would produce a second `?`
    and break parameter parsing at the IdP).
    """
    doc = {**_DISCOVERY_DOC, "authorization_endpoint": f"{_MOCK_ISSUER}/authorize?p=B2C_1A_SIGNIN"}
    idp = IdentityProvider(
        name="b2c-idp",
        provider_type="oidc_generic",
        issuer_url=_MOCK_ISSUER,
        client_id="test-client-id",
        client_secret_encrypted=encrypt_value("s").encode(),
        scopes="openid profile email",
        group_claim_name="groups",
        is_enabled=True,
        discovery_cache_json=json.dumps(doc),
        discovery_cached_at=datetime.now(timezone.utc),
    )
    db_session.add(idp)
    db_session.flush()
    db_session.refresh(idp)

    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    location = resp.headers["location"]
    # Exactly one "?" — the rest of the params after the existing query string
    # must be joined with "&".
    assert location.count("?") == 1
    assert "p=B2C_1A_SIGNIN" in location
    assert "response_type=code" in location


def test_missing_authorization_endpoint_returns_503(
    client: TestClient, db_session: Session
):
    """Malformed discovery cache (no authorization_endpoint) yields idp.unreachable."""
    bad_doc = {k: v for k, v in _DISCOVERY_DOC.items() if k != "authorization_endpoint"}
    idp = IdentityProvider(
        name="broken-idp",
        provider_type="oidc_generic",
        issuer_url=_MOCK_ISSUER,
        client_id="test-client-id",
        client_secret_encrypted=encrypt_value("s").encode(),
        scopes="openid profile email",
        group_claim_name="groups",
        is_enabled=True,
        discovery_cache_json=json.dumps(bad_doc),
        discovery_cached_at=datetime.now(timezone.utc),
    )
    db_session.add(idp)
    db_session.flush()
    db_session.refresh(idp)

    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    # The cache is invalid so get_or_fetch_discovery may try a live refresh, which
    # we don't want to stub here. Accept either 503 (cache rejected) or 503 (refresh
    # also yields the malformed doc). Either way: status must be 503, not 500.
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "idp.unreachable"


# ---------------------------------------------------------------------------
# return_to length cap + scope normalization
# ---------------------------------------------------------------------------


def test_oversize_return_to_rejected(client: TestClient, db_session: Session):
    """return_to longer than column capacity must be rejected with 400, not truncated."""
    idp = _make_idp(db_session)
    long_path = "/" + ("a" * 500)
    resp = client.get(
        f"{BASE_URL}/{idp.id}/login",
        params={"return_to": long_path},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "return_to.invalid"


def test_scope_without_openid_gets_openid_added(
    client: TestClient, db_session: Session
):
    """Admin misconfiguration: scopes missing 'openid' must still produce an OIDC request."""
    idp = _make_idp(db_session, name="no-openid")
    idp.scopes = "profile email"
    db_session.flush()
    db_session.refresh(idp)

    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    scope = parse_qs(urlparse(resp.headers["location"]).query)["scope"][0]
    assert "openid" in scope.split()


def test_scope_whitespace_normalized(client: TestClient, db_session: Session):
    """Newlines/tabs in scopes collapse to single-space separators."""
    idp = _make_idp(db_session, name="weird-scope")
    idp.scopes = "openid\nprofile\temail"
    db_session.flush()
    db_session.refresh(idp)

    resp = client.get(f"{BASE_URL}/{idp.id}/login", follow_redirects=False)
    scope = parse_qs(urlparse(resp.headers["location"]).query)["scope"][0]
    # No newlines or tabs survive normalization.
    assert "\n" not in scope
    assert "\t" not in scope
    assert set(scope.split()) == {"openid", "profile", "email"}
