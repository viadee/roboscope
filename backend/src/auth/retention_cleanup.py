"""Story 5-5: retention cleanup for Phase 4 tables.

Operational cleanup — NOT user-facing audit. Emits structured logs only.

Tables covered:
  - OidcLoginAttempt: delete rows where `expires_at < now()`. The attempt
    TTL is 10 min; stale rows only exist on the rare occurrence of an
    abandoned login flow (user closes tab before callback).
  - RateLimitCounter: delete rows where `window_start < now - 1 h`. Only
    the active 1-hour window matters for enforcement.

TeamMember tombstone cleanup (deprovision_retention_days) is deferred
until a soft-delete field lands on TeamMember (currently hard-delete
only). Tracked in deferred-work.md.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from src.auth.models import OidcLoginAttempt
from src.database import SessionLocal
from src.rate_limit import RateLimitCounter

logger = logging.getLogger("roboscope.auth.retention_cleanup")

_RATE_LIMIT_WINDOW_HOURS = 1


def cleanup_oidc_login_attempts(db: Session | None = None) -> int:
    """Delete expired OidcLoginAttempt rows. Returns number deleted."""
    own_session = db is None
    if own_session:
        db = SessionLocal()
    assert db is not None
    try:
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        result = db.execute(
            delete(OidcLoginAttempt).where(OidcLoginAttempt.expires_at < now_naive)
        )
        deleted = result.rowcount or 0
        db.commit()
        logger.info("retention.oidc_login_attempts cleaned=%d", deleted)
        return deleted
    finally:
        if own_session:
            db.close()


def cleanup_rate_limit_counters(db: Session | None = None) -> int:
    """Delete RateLimitCounter rows outside the active 1-hour window."""
    own_session = db is None
    if own_session:
        db = SessionLocal()
    assert db is not None
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            hours=_RATE_LIMIT_WINDOW_HOURS
        )
        result = db.execute(
            delete(RateLimitCounter).where(RateLimitCounter.window_start < cutoff)
        )
        deleted = result.rowcount or 0
        db.commit()
        logger.info("retention.rate_limit_counters cleaned=%d", deleted)
        return deleted
    finally:
        if own_session:
            db.close()


def run_hourly_cleanup() -> None:
    """APScheduler entry point. Runs all hourly Phase 4 retention jobs.

    Wrapped so a single job failure does not crash the scheduler for the
    others — each step logs its own exception.
    """
    for step, fn in (
        ("oidc_login_attempts", cleanup_oidc_login_attempts),
        ("rate_limit_counters", cleanup_rate_limit_counters),
    ):
        try:
            fn()
        except Exception:
            logger.warning("retention.%s failed", step, exc_info=True)
