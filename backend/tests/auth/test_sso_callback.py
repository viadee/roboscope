"""Tests for the OIDC callback handler (Story 2-2).

All IdP HTTP traffic is intercepted via the `mock_oidc` respx fixture so these
tests are fully hermetic. Each test seeds a pre-populated discovery cache on
the test IdP to skip live discovery fetches.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from authlib.jose import JsonWebKey, jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.audit.models import AuditLog
from src.auth.constants import Role
from src.auth.models import (
    IdentityProvider,
    IdPGroupMapping,
    OidcLoginAttempt,
    User,
)
from src.encryption import encrypt_value
from src.teams.models import Team, TeamMember
from tests.fixtures.mock_oidc import ISSUER, mock_oidc  # noqa: F401 — fixture import

BASE_URL = "/api/v1/auth/sso"
_CLIENT_ID = "test-client-id"


def _make_idp(db: Session, *, name: str = "test-idp", group_claim: str = "groups") -> IdentityProvider:
    discovery_doc = {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/jwks",
    }
    idp = IdentityProvider(
        name=name,
        provider_type="oidc_generic",
        issuer_url=ISSUER,
        client_id=_CLIENT_ID,
        client_secret_encrypted=encrypt_value("test-secret").encode(),
        scopes="openid profile email",
        group_claim_name=group_claim,
        is_enabled=True,
        discovery_cache_json=json.dumps(discovery_doc),
        discovery_cached_at=datetime.now(timezone.utc),
    )
    db.add(idp)
    # Commit promotes the row to the fixture's outer SAVEPOINT so it survives
    # a handler-internal db.rollback() (P11 failure-path rollback).
    db.commit()
    db.refresh(idp)
    return idp


def _make_attempt(
    db: Session,
    idp: IdentityProvider,
    *,
    state: str = "test-state-123",
    nonce: str = "test-nonce-abc",
    pkce_verifier: str = "test-pkce-verifier-plaintext",
    return_to: str = "/",
    expires_in_seconds: int = 600,
) -> OidcLoginAttempt:
    attempt = OidcLoginAttempt(
        state=state,
        nonce=nonce,
        pkce_verifier=encrypt_value(pkce_verifier),
        idp_id=idp.id,
        return_to=return_to,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_callback_happy_path_redirects_to_return_to(
    client: TestClient, db_session: Session, mock_oidc
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp, return_to="/reports/42")
    mock_oidc.with_claims(
        iss=ISSUER, aud=_CLIENT_ID, sub="u1", email="alice@example.com", nonce=attempt.nonce
    )

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "mock-code", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/reports/42"


def test_callback_sets_access_and_refresh_token_cookies(
    client: TestClient, db_session: Session, mock_oidc
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(sub="u1", email="alice@example.com", nonce=attempt.nonce)

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "mock-code", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    # Both cookies are present
    cookies = resp.cookies
    assert cookies.get("roboscope_sso_access_token")
    assert cookies.get("roboscope_sso_refresh_token")
    # `Set-Cookie` header must not mark them HttpOnly — frontend reads them.
    set_cookie = "\n".join(
        v for k, v in resp.headers.items() if k.lower() == "set-cookie"
    )
    access_block = next(
        block for block in set_cookie.split("\n") if "roboscope_sso_access_token" in block
    )
    assert "HttpOnly" not in access_block
    assert "Max-Age=60" in access_block


def test_callback_cache_control_no_store(
    client: TestClient, db_session: Session, mock_oidc
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(sub="u1", email="alice@example.com", nonce=attempt.nonce)

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.headers.get("cache-control") == "no-store"


def test_callback_creates_new_user_with_viewer_role(
    client: TestClient, db_session: Session, mock_oidc
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(sub="u1", email="new-user@example.com", nonce=attempt.nonce)

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    user = db_session.query(User).filter_by(email="new-user@example.com").one()
    assert user.role == Role.VIEWER
    assert user.hashed_password == ""
    assert user.is_active is True
    assert user.last_login_at is not None


def test_callback_existing_user_preserves_role(
    client: TestClient, db_session: Session, mock_oidc
):
    existing = User(
        email="admin-ext@example.com",
        username="admin-ext",
        hashed_password="",
        role=Role.ADMIN,
        is_active=True,
    )
    db_session.add(existing)
    db_session.flush()

    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(sub="u1", email="admin-ext@example.com", nonce=attempt.nonce)

    client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    db_session.refresh(existing)
    assert existing.role == Role.ADMIN


def test_callback_updates_last_login_at(
    client: TestClient, db_session: Session, mock_oidc
):
    old_ts = datetime.now(timezone.utc) - timedelta(days=30)
    existing = User(
        email="returning@example.com",
        username="returning",
        hashed_password="",
        role=Role.VIEWER,
        is_active=True,
        last_login_at=old_ts,
    )
    db_session.add(existing)
    db_session.flush()

    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(sub="u1", email="returning@example.com", nonce=attempt.nonce)

    client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    db_session.refresh(existing)
    assert existing.last_login_at is not None
    # Compare without timezone to avoid SQLite naive-datetime mismatch.
    current = existing.last_login_at
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    assert current > old_ts


def test_callback_consumes_attempt_row(
    client: TestClient, db_session: Session, mock_oidc
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(sub="u1", email="a@b.c", nonce=attempt.nonce)

    client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert db_session.query(OidcLoginAttempt).filter_by(state=attempt.state).first() is None


# ---------------------------------------------------------------------------
# Error branches
# ---------------------------------------------------------------------------


def test_callback_unknown_state_redirects_to_error(
    client: TestClient, db_session: Session
):
    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": "no-such-state"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=state.unknown"

    audit = db_session.query(AuditLog).filter_by(action="sso.login.failure").one()
    detail = json.loads(audit.detail)
    assert detail["reason"] == "state.unknown"


def test_callback_expired_attempt_redirects_to_error(
    client: TestClient, db_session: Session
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp, expires_in_seconds=-5)

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=state.expired"

    # Expired rows are retained (reaper in Story 5-5 handles cleanup).
    assert db_session.query(OidcLoginAttempt).filter_by(state=attempt.state).first() is not None


def test_callback_disabled_idp_redirects_to_error(
    client: TestClient, db_session: Session
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    idp.is_enabled = False
    db_session.flush()

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=idp.unavailable"


def test_callback_token_exchange_timeout(
    client: TestClient, db_session: Session
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)

    # Custom respx mock that simulates timeout on token endpoint.
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{ISSUER}/.well-known/openid-configuration").mock(
            return_value=httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/authorize",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                },
            )
        )
        router.get(f"{ISSUER}/jwks").mock(return_value=httpx.Response(200, json={"keys": []}))
        router.post(f"{ISSUER}/token").mock(side_effect=httpx.TimeoutException("slow"))

        resp = client.get(
            f"{BASE_URL}/callback",
            params={"code": "c", "state": attempt.state},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=idp.unreachable"

    audit = db_session.query(AuditLog).filter_by(action="sso.login.failure").one()
    detail = json.loads(audit.detail)
    assert detail["reason"] == "idp.unreachable"
    # Inner service-layer reason is promoted to `sub_reason` by the router
    # to avoid a spread collision with the top-level Constraint-6 key.
    assert detail["sub_reason"] == "timeout"


def test_callback_invalid_signature_redirects_to_error(
    client: TestClient, db_session: Session
):
    """id_token signed by a key that is NOT in the IdP's published JWKS → token.invalid."""
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)

    # Mint an id_token with a foreign key.
    rogue_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rogue_jwk = JsonWebKey.import_key(rogue_private, {"kty": "RSA", "kid": "rogue-kid"})
    now = int(time.time())
    claims = {
        "iss": ISSUER, "aud": _CLIENT_ID, "sub": "u1",
        "email": "a@b.c", "nonce": attempt.nonce,
        "iat": now, "exp": now + 600,
    }
    header = {"alg": "RS256", "kid": "rogue-kid"}
    rogue_token = jwt.encode(header, claims, rogue_jwk)
    if isinstance(rogue_token, bytes):
        rogue_token = rogue_token.decode()

    with respx.mock(assert_all_called=False) as router:
        router.get(f"{ISSUER}/.well-known/openid-configuration").mock(
            return_value=httpx.Response(200, json={
                "issuer": ISSUER,
                "authorization_endpoint": f"{ISSUER}/authorize",
                "token_endpoint": f"{ISSUER}/token",
                "jwks_uri": f"{ISSUER}/jwks",
            })
        )
        # JWKS advertises a DIFFERENT key — signature verification must fail.
        legit_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        legit_jwk_pub = JsonWebKey.import_key(
            legit_private.public_key(), {"kty": "RSA", "kid": "legit-kid"}
        )
        router.get(f"{ISSUER}/jwks").mock(
            return_value=httpx.Response(200, json={"keys": [legit_jwk_pub.as_dict()]})
        )
        router.post(f"{ISSUER}/token").mock(
            return_value=httpx.Response(200, json={
                "access_token": "x", "token_type": "bearer",
                "expires_in": 600, "id_token": rogue_token,
            })
        )
        resp = client.get(
            f"{BASE_URL}/callback",
            params={"code": "c", "state": attempt.state},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=token.invalid"


def test_callback_nonce_mismatch_redirects_to_error(
    client: TestClient, db_session: Session, mock_oidc
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp, nonce="expected-nonce")
    mock_oidc.with_claims(sub="u1", email="a@b.c", nonce="wrong-nonce")

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=nonce.mismatch"


def test_callback_iss_mismatch_redirects_to_error(
    client: TestClient, db_session: Session, mock_oidc
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(
        iss="https://different-issuer.example", sub="u1",
        email="a@b.c", nonce=attempt.nonce,
    )

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=token.invalid"


def test_callback_aud_mismatch_redirects_to_error(
    client: TestClient, db_session: Session, mock_oidc
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(
        aud="some-other-client", sub="u1",
        email="a@b.c", nonce=attempt.nonce,
    )

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=token.invalid"


def test_callback_missing_email_redirects_to_error(
    client: TestClient, db_session: Session, mock_oidc
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(sub="u1", email="", nonce=attempt.nonce)

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=claims.missing_email"


def test_callback_missing_sub_redirects_to_error(
    client: TestClient, db_session: Session, mock_oidc
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(sub="", email="a@b.c", nonce=attempt.nonce)

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=claims.missing_sub"


# ---------------------------------------------------------------------------
# Group sync
# ---------------------------------------------------------------------------


def test_callback_group_sync_inserts_new_memberships(
    client: TestClient, db_session: Session, mock_oidc
):
    team = Team(name="engineering")
    db_session.add(team)
    db_session.flush()

    idp = _make_idp(db_session)
    db_session.add(
        IdPGroupMapping(
            idp_id=idp.id, group_claim_value="eng-all", team_id=team.id, role="runner"
        )
    )
    db_session.flush()
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(
        sub="u1", email="dev@example.com", nonce=attempt.nonce, groups=["eng-all"]
    )

    client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    user = db_session.query(User).filter_by(email="dev@example.com").one()
    tm = (
        db_session.query(TeamMember)
        .filter_by(team_id=team.id, user_id=user.id)
        .one()
    )
    assert tm.source == "idp_group_sync"
    assert tm.role == "runner"


def test_callback_group_sync_removes_stale_memberships(
    client: TestClient, db_session: Session, mock_oidc
):
    team_old = Team(name="old-team")
    team_new = Team(name="new-team")
    db_session.add_all([team_old, team_new])
    db_session.flush()

    user = User(
        email="returning@example.com", username="ret",
        hashed_password="", role=Role.VIEWER, is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        TeamMember(
            team_id=team_old.id, user_id=user.id,
            role="viewer", source="idp_group_sync",
        )
    )
    db_session.flush()

    idp = _make_idp(db_session)
    db_session.add(
        IdPGroupMapping(
            idp_id=idp.id, group_claim_value="new-group",
            team_id=team_new.id, role="viewer",
        )
    )
    db_session.flush()
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(
        sub="u1", email="returning@example.com",
        nonce=attempt.nonce, groups=["new-group"],
    )

    client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    # Old sync row removed, new sync row inserted.
    assert (
        db_session.query(TeamMember)
        .filter_by(team_id=team_old.id, user_id=user.id).first() is None
    )
    assert (
        db_session.query(TeamMember)
        .filter_by(team_id=team_new.id, user_id=user.id).first() is not None
    )


def test_callback_group_sync_preserves_manual_grants(
    client: TestClient, db_session: Session, mock_oidc
):
    team = Team(name="special")
    db_session.add(team)
    db_session.flush()

    user = User(
        email="manual@example.com", username="m",
        hashed_password="", role=Role.VIEWER, is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        TeamMember(
            team_id=team.id, user_id=user.id,
            role="admin", source="manual",
        )
    )
    db_session.flush()

    idp = _make_idp(db_session)
    # No mapping exists for this team — manual grant must survive.
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(
        sub="u1", email="manual@example.com",
        nonce=attempt.nonce, groups=["unrelated"],
    )

    client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    manual_tm = (
        db_session.query(TeamMember)
        .filter_by(team_id=team.id, user_id=user.id).one()
    )
    assert manual_tm.source == "manual"
    assert manual_tm.role == "admin"


def test_callback_group_sync_updates_role_when_mapping_changes(
    client: TestClient, db_session: Session, mock_oidc
):
    team = Team(name="t1")
    db_session.add(team)
    db_session.flush()

    user = User(
        email="u@example.com", username="u",
        hashed_password="", role=Role.VIEWER, is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        TeamMember(
            team_id=team.id, user_id=user.id,
            role="viewer", source="idp_group_sync",
        )
    )
    db_session.flush()

    idp = _make_idp(db_session)
    db_session.add(
        IdPGroupMapping(
            idp_id=idp.id, group_claim_value="eng",
            team_id=team.id, role="editor",
        )
    )
    db_session.flush()
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(
        sub="u1", email="u@example.com", nonce=attempt.nonce, groups=["eng"]
    )

    client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    tm = db_session.query(TeamMember).filter_by(team_id=team.id, user_id=user.id).one()
    assert tm.role == "editor"
    assert tm.source == "idp_group_sync"


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------


def test_callback_success_emits_audit_events(
    client: TestClient, db_session: Session, mock_oidc
):
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp, return_to="/dashboard")
    mock_oidc.with_claims(
        sub="u1", email="a@b.c", nonce=attempt.nonce, groups=[]
    )

    client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    success = db_session.query(AuditLog).filter_by(action="sso.login.success").one()
    synced = (
        db_session.query(AuditLog).filter_by(action="team.member.synced_from_idp").one()
    )
    assert success.resource_type == "sso"
    assert synced.resource_type == "team"
    detail = json.loads(success.detail)
    from src.auth.pii_hash import hash_email, is_email_hash
    assert "email" not in detail, "plaintext email must not leak into audit detail"
    assert is_email_hash(detail["email_hash"])
    assert detail["email_hash"] == hash_email("a@b.c")
    assert detail["return_to"] == "/dashboard"


def test_callback_failure_emits_structured_audit_event(
    client: TestClient, db_session: Session
):
    client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": "missing"},
        follow_redirects=False,
    )
    row = db_session.query(AuditLog).filter_by(action="sso.login.failure").one()
    assert row.resource_type == "sso"
    assert json.loads(row.detail)["reason"] == "state.unknown"


# ---------------------------------------------------------------------------
# Missing required query params
# ---------------------------------------------------------------------------


def test_callback_missing_code_returns_422(client: TestClient):
    resp = client.get(f"{BASE_URL}/callback", params={"state": "x"}, follow_redirects=False)
    assert resp.status_code == 422


def test_callback_missing_state_returns_422(client: TestClient):
    resp = client.get(f"{BASE_URL}/callback", params={"code": "x"}, follow_redirects=False)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Review-driven regression tests (Story 2-2 code review)
# ---------------------------------------------------------------------------


def test_callback_replay_same_state_fails_on_second_call(
    client: TestClient, db_session: Session, mock_oidc
):
    """P4 — A replay of the same state after a successful callback → state.unknown."""
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(sub="u1", email="a@b.c", nonce=attempt.nonce)

    resp1 = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c1", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp1.status_code == 302
    assert resp1.headers["location"] == "/"

    mock_oidc.with_claims(sub="u1", email="a@b.c", nonce=attempt.nonce)
    resp2 = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c2", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp2.status_code == 302
    assert resp2.headers["location"] == "/sso-error?code=state.unknown"


def test_callback_rejects_unverified_email(
    client: TestClient, db_session: Session, mock_oidc
):
    """D1 — email_verified must be True; unverified tokens are rejected."""
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(
        sub="u1", email="spoof@example.com",
        email_verified=False, nonce=attempt.nonce,
    )

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=claims.email_unverified"
    assert db_session.query(User).filter_by(email="spoof@example.com").first() is None


def test_callback_rejects_deactivated_user(
    client: TestClient, db_session: Session, mock_oidc
):
    """P6 — Deactivated local users must not be silently reactivated by SSO."""
    disabled = User(
        email="disabled@example.com", username="disabled",
        hashed_password="", role=Role.VIEWER, is_active=False,
    )
    db_session.add(disabled)
    db_session.flush()

    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(
        sub="u1", email="disabled@example.com", nonce=attempt.nonce,
    )

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=user.disabled"
    db_session.refresh(disabled)
    assert disabled.is_active is False


def test_callback_sync_failure_surfaces_sync_failed_code(
    client: TestClient, db_session: Session, mock_oidc, monkeypatch
):
    """P3 — DB failures during inline group sync surface as sync.failed."""
    from sqlalchemy.exc import SQLAlchemyError

    from src.auth import oidc_callback_service

    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(sub="u1", email="x@y.z", nonce=attempt.nonce)

    def _boom(*args, **kwargs):
        raise SQLAlchemyError("simulated DB error")

    monkeypatch.setattr(oidc_callback_service, "_sync_team_memberships", _boom)

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=sync.failed"
    audit = db_session.query(AuditLog).filter_by(action="sso.login.failure").one()
    assert json.loads(audit.detail)["reason"] == "sync.failed"


def test_callback_token_exchange_http_error_captures_status(
    client: TestClient, db_session: Session
):
    """P2 — IdP HTTP errors during token exchange include the status code in audit detail."""
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)

    with respx.mock(assert_all_called=False) as router:
        router.get(f"{ISSUER}/.well-known/openid-configuration").mock(
            return_value=httpx.Response(200, json={
                "issuer": ISSUER,
                "authorization_endpoint": f"{ISSUER}/authorize",
                "token_endpoint": f"{ISSUER}/token",
                "jwks_uri": f"{ISSUER}/jwks",
            })
        )
        router.get(f"{ISSUER}/jwks").mock(return_value=httpx.Response(200, json={"keys": []}))
        router.post(f"{ISSUER}/token").mock(
            return_value=httpx.Response(503, text="upstream unavailable")
        )

        resp = client.get(
            f"{BASE_URL}/callback",
            params={"code": "c", "state": attempt.state},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=idp.unreachable"

    audit = db_session.query(AuditLog).filter_by(action="sso.login.failure").one()
    detail = json.loads(audit.detail)
    assert detail["reason"] == "idp.unreachable"
    assert detail["http_status"] == 503


def test_callback_azp_required_for_multi_aud(
    client: TestClient, db_session: Session, mock_oidc
):
    """P10 — When aud is a multi-value array, azp MUST equal client_id (OIDC §3.1.3.7)."""
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(
        sub="u1", email="a@b.c", nonce=attempt.nonce,
        aud=[_CLIENT_ID, "other-client"],  # no azp
    )

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/sso-error?code=token.invalid"


def test_callback_azp_matching_multi_aud_succeeds(
    client: TestClient, db_session: Session, mock_oidc
):
    """P10 — Multi-aud + matching azp is OIDC-conformant and must succeed."""
    idp = _make_idp(db_session)
    attempt = _make_attempt(db_session, idp)
    mock_oidc.with_claims(
        sub="u1", email="a@b.c", nonce=attempt.nonce,
        aud=[_CLIENT_ID, "other-client"], azp=_CLIENT_ID,
    )

    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "c", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"
