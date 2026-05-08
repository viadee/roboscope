"""Story 4-7: SSO link-consent flow.

Covers:
  - Callback redirects to /sso-link-consent?token=... when the email
    matches an existing local-account user (non-empty hashed_password).
  - POST /sso/link-consent with approve=true: detaches the password,
    syncs teams, returns tokens + return_to, emits user.account_linked.
  - POST /sso/link-consent with approve=false: emits
    user.account_link_cancelled, returns status=cancelled.
  - Invalid / expired / tampered token: 400.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.audit.models import AuditLog
from src.auth.models import IdentityProvider, OidcLoginAttempt, User
from src.auth.service import hash_password
from src.auth.sso_link_consent import encode_consent_token
from src.config import settings
from src.encryption import encrypt_value
from tests.fixtures.mock_oidc import ISSUER, mock_oidc  # noqa: F401


ENDPOINT = "/api/v1/auth/sso/link-consent"


def _mk_idp(db: Session, *, name: str = "link-idp") -> IdentityProvider:
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
        client_id="test-client-id",
        client_secret_encrypted=encrypt_value("s").encode(),
        scopes="openid profile email",
        group_claim_name="groups",
        is_enabled=True,
        discovery_cache_json=json.dumps(discovery_doc),
        discovery_cached_at=datetime.now(timezone.utc),
    )
    db.add(idp)
    db.commit()
    db.refresh(idp)
    return idp


def _mk_local_user(db: Session, email: str) -> User:
    u = User(
        email=email,
        username=email,
        hashed_password=hash_password("localpw"),
        role="viewer",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _mk_attempt(db: Session, idp: IdentityProvider) -> OidcLoginAttempt:
    attempt = OidcLoginAttempt(
        state="link-state",
        nonce="link-nonce",
        pkce_verifier=encrypt_value("v"),
        idp_id=idp.id,
        return_to="/reports/7",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=600),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


class TestCallbackInterception:
    def test_local_account_sso_callback_redirects_to_consent(
        self, client: TestClient, db_session: Session, mock_oidc  # noqa: F811
    ) -> None:
        idp = _mk_idp(db_session)
        _mk_local_user(db_session, "link@example.com")
        attempt = _mk_attempt(db_session, idp)
        mock_oidc.with_claims(
            sub="link-sub", email="link@example.com", nonce=attempt.nonce
        )

        resp = client.get(
            "/api/v1/auth/sso/callback",
            params={"code": "x", "state": attempt.state},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        location = resp.headers["location"]
        parsed = urlparse(location)
        assert parsed.path == "/sso-link-consent"
        qs = parse_qs(parsed.query)
        assert "token" in qs and qs["token"][0]

        audits = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "sso.login.failure")
            .all()
        )
        assert len(audits) == 0  # not a failure — no audit

    def test_sso_only_user_bypasses_consent(
        self, client: TestClient, db_session: Session, mock_oidc  # noqa: F811
    ) -> None:
        """Users with hashed_password='' are SSO-linked already; no consent."""
        idp = _mk_idp(db_session, name="link-idp-2")
        existing = User(
            email="ssoonly@example.com",
            username="ssoonly",
            hashed_password="",  # already SSO-linked
            role="viewer",
        )
        db_session.add(existing)
        db_session.commit()
        attempt = _mk_attempt(db_session, idp)
        mock_oidc.with_claims(
            sub="sso-sub", email="ssoonly@example.com", nonce=attempt.nonce
        )

        resp = client.get(
            "/api/v1/auth/sso/callback",
            params={"code": "x", "state": attempt.state},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["location"] == "/reports/7"


class TestApprove:
    def test_approve_detaches_password_and_issues_tokens(
        self, client: TestClient, db_session: Session
    ) -> None:
        idp = _mk_idp(db_session)
        user = _mk_local_user(db_session, "approve@example.com")
        token = encode_consent_token(
            user_id=user.id, idp_id=idp.id, sub="s",
            email=user.email, groups=[], return_to="/reports/42",
        )

        resp = client.post(ENDPOINT, json={"consent_token": token, "approve": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "linked"
        assert body["return_to"] == "/reports/42"
        assert body["access_token"]
        assert body["refresh_token"]

        db_session.expire_all()
        refreshed = db_session.get(User, user.id)
        assert refreshed is not None
        assert refreshed.hashed_password == ""

        audits = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "user.account_linked")
            .all()
        )
        assert len(audits) == 1


class TestCancel:
    def test_decline_emits_cancelled_audit(
        self, client: TestClient, db_session: Session
    ) -> None:
        idp = _mk_idp(db_session, name="cancel-idp")
        user = _mk_local_user(db_session, "cancel@example.com")
        token = encode_consent_token(
            user_id=user.id, idp_id=idp.id, sub="s",
            email=user.email, groups=[], return_to="/",
        )

        resp = client.post(ENDPOINT, json={"consent_token": token, "approve": False})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cancelled"
        assert body["access_token"] is None

        audits = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "user.account_link_cancelled")
            .all()
        )
        assert len(audits) == 1


class TestTokenValidation:
    def test_invalid_token_is_rejected(
        self, client: TestClient, db_session: Session
    ) -> None:
        resp = client.post(
            ENDPOINT, json={"consent_token": "not-a-jwt", "approve": True}
        )
        assert resp.status_code == 400

    def test_expired_token_is_rejected(
        self, client: TestClient, db_session: Session
    ) -> None:
        idp = _mk_idp(db_session, name="expired-idp")
        user = _mk_local_user(db_session, "expired@example.com")

        # Mint an already-expired token directly.
        now = int(time.time())
        expired = jwt.encode(
            {
                "type": "sso_link_consent",
                "user_id": user.id, "idp_id": idp.id, "sub": "s",
                "email": user.email, "groups": [], "return_to": "/",
                "iat": now - 3600, "exp": now - 10,
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        resp = client.post(
            ENDPOINT, json={"consent_token": expired, "approve": True}
        )
        assert resp.status_code == 400

    def test_email_mismatch_is_rejected(
        self, client: TestClient, db_session: Session
    ) -> None:
        idp = _mk_idp(db_session, name="mismatch-idp")
        user = _mk_local_user(db_session, "original@example.com")
        # Mint a token with the right user_id but a different email.
        token = encode_consent_token(
            user_id=user.id, idp_id=idp.id, sub="s",
            email="tampered@example.com", groups=[], return_to="/",
        )
        resp = client.post(ENDPOINT, json={"consent_token": token, "approve": True})
        assert resp.status_code == 400
