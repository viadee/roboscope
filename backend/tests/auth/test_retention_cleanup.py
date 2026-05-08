"""Story 5-5: retention cleanup jobs for Phase 4 tables."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.auth.models import IdentityProvider, OidcLoginAttempt
from src.auth.retention_cleanup import (
    cleanup_oidc_login_attempts,
    cleanup_rate_limit_counters,
)
from src.encryption import encrypt_value
from src.rate_limit import RateLimitCounter


def _mk_idp(db: Session) -> IdentityProvider:
    idp = IdentityProvider(
        name="ret-test-idp",
        provider_type="oidc_generic",
        issuer_url="https://idp.test",
        client_id="c",
        client_secret_encrypted=encrypt_value("s").encode(),
        scopes="openid profile email",
        group_claim_name="groups",
        is_enabled=True,
    )
    db.add(idp)
    db.commit()
    db.refresh(idp)
    return idp


class TestOidcLoginAttemptCleanup:
    def test_deletes_expired_rows(self, db_session: Session) -> None:
        idp = _mk_idp(db_session)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        expired = OidcLoginAttempt(
            state="expired-state",
            nonce="n1",
            pkce_verifier=encrypt_value("v1"),
            idp_id=idp.id,
            return_to="/",
            expires_at=now - timedelta(minutes=5),
        )
        fresh = OidcLoginAttempt(
            state="fresh-state",
            nonce="n2",
            pkce_verifier=encrypt_value("v2"),
            idp_id=idp.id,
            return_to="/",
            expires_at=now + timedelta(minutes=5),
        )
        db_session.add_all([expired, fresh])
        db_session.commit()

        deleted = cleanup_oidc_login_attempts(db_session)
        assert deleted == 1

        remaining = db_session.query(OidcLoginAttempt).all()
        states = {a.state for a in remaining}
        assert states == {"fresh-state"}

    def test_no_expired_rows_returns_zero(self, db_session: Session) -> None:
        idp = _mk_idp(db_session)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.add(
            OidcLoginAttempt(
                state="only-fresh",
                nonce="n",
                pkce_verifier=encrypt_value("v"),
                idp_id=idp.id,
                return_to="/",
                expires_at=now + timedelta(minutes=5),
            )
        )
        db_session.commit()

        assert cleanup_oidc_login_attempts(db_session) == 0


class TestRateLimitCounterCleanup:
    def test_deletes_old_windows(self, db_session: Session) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stale = RateLimitCounter(
            bucket_key="stale-bucket",
            window_start=now - timedelta(hours=2),
            count=5,
        )
        fresh = RateLimitCounter(
            bucket_key="fresh-bucket",
            window_start=now - timedelta(minutes=15),
            count=3,
        )
        db_session.add_all([stale, fresh])
        db_session.commit()

        deleted = cleanup_rate_limit_counters(db_session)
        assert deleted == 1

        remaining = {r.bucket_key for r in db_session.query(RateLimitCounter).all()}
        assert remaining == {"fresh-bucket"}

    def test_boundary_exact_hour_keeps_row(self, db_session: Session) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Row with window_start === cutoff should NOT be deleted (strict <).
        on_boundary = RateLimitCounter(
            bucket_key="on-boundary",
            window_start=now - timedelta(minutes=59),
            count=1,
        )
        db_session.add(on_boundary)
        db_session.commit()

        assert cleanup_rate_limit_counters(db_session) == 0
        assert db_session.query(RateLimitCounter).count() == 1
