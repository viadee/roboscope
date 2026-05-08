"""Integration tests for rate-limiting in the SSO router (Story 2-8)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.audit.models import AuditLog
from src.auth.models import IdentityProvider
from src.auth.sso_rate_limit import _THRESHOLD, record_failure
from src.encryption import encrypt_value


@pytest.fixture
def enabled_idp(db_session: Session) -> IdentityProvider:
    idp = IdentityProvider(
        name="rate-limit-idp",
        provider_type="generic",
        issuer_url="https://idp.test/",
        client_id="rl-client",
        client_secret_encrypted=encrypt_value("secret").encode(),
        is_enabled=True,
    )
    db_session.add(idp)
    db_session.commit()
    db_session.refresh(idp)
    return idp


def _saturate(db: Session, ip: str) -> None:
    """Push the counter to threshold in the current window."""
    for _ in range(_THRESHOLD):
        record_failure(db, ip)


class TestRateLimitResponses:
    def test_init_returns_429_after_threshold(
        self,
        client: TestClient,
        db_session: Session,
        enabled_idp: IdentityProvider,
    ) -> None:
        _saturate(db_session, "testclient")
        resp = client.get(f"/api/v1/auth/sso/{enabled_idp.id}/login")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        retry = int(resp.headers["Retry-After"])
        assert retry >= 1
        body = resp.json()
        assert body["reason"] == "rate_limited"

    def test_callback_returns_429_after_threshold(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        _saturate(db_session, "testclient")
        resp = client.get(
            "/api/v1/auth/sso/callback",
            params={"code": "x", "state": "y"},
            follow_redirects=False,
        )
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_429_writes_audit_event(
        self,
        client: TestClient,
        db_session: Session,
        enabled_idp: IdentityProvider,
    ) -> None:
        _saturate(db_session, "testclient")
        client.get(f"/api/v1/auth/sso/{enabled_idp.id}/login")

        # One rate_limited audit event should be present.
        events = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "sso.login.rate_limited")
            .all()
        )
        assert len(events) >= 1


class TestFailureCounter:
    def test_return_to_invalid_increments_counter(
        self,
        client: TestClient,
        db_session: Session,
        enabled_idp: IdentityProvider,
    ) -> None:
        from src.auth.sso_rate_limit import _bucket_key
        from src.rate_limit import RateLimitCounter

        resp = client.get(
            f"/api/v1/auth/sso/{enabled_idp.id}/login",
            params={"return_to": "https://evil.example.com/"},
        )
        assert resp.status_code == 400

        rows = (
            db_session.query(RateLimitCounter)
            .filter(RateLimitCounter.bucket_key == _bucket_key("testclient"))
            .all()
        )
        assert len(rows) == 1
        assert rows[0].count == 1

    def test_idp_not_found_increments_counter(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        from src.auth.sso_rate_limit import _bucket_key
        from src.rate_limit import RateLimitCounter

        # Hit an idp_id that doesn't exist.
        resp = client.get("/api/v1/auth/sso/99999/login")
        assert resp.status_code == 404

        rows = (
            db_session.query(RateLimitCounter)
            .filter(RateLimitCounter.bucket_key == _bucket_key("testclient"))
            .all()
        )
        assert len(rows) == 1
        assert rows[0].count == 1
