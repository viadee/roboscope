"""Per-IP rate-limiter for SSO login attempts (Story 2-8).

Uses the `rate_limit_counters` table (Story 1-1) so we don't need Redis.

Tradeoffs vs Redis:
  - Single-instance only (counters don't sync across replicas). Acceptable
    for the brownfield deployment story we're shipping.
  - Per-5-min windows aligned to wall-clock, not sliding. Simpler logic
    and acceptable cliff at the configured threshold (20 / 5 min).
  - Successful login clears ALL windows for the bucket (not just the
    current one) so a user who legitimately authenticates is fully
    cleared.

Callers MUST pass the client IP as the `ip` parameter. The module does
not inspect `X-Forwarded-For` — that's the caller's responsibility, so
we don't leak the misconfigured-proxy pitfall into multiple locations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database import get_sync_session
from src.rate_limit import RateLimitCounter

# Window and threshold. Tuning knobs for future sensitivity changes —
# e.g. a reduced threshold for high-value deployments can be applied
# without touching the router.
_WINDOW_SECONDS = 300  # 5 min
_THRESHOLD = 20
_STALE_AFTER = timedelta(hours=1)
_BUCKET_PREFIX = "sso:login:"


def _bucket_key(ip: str) -> str:
    """Namespace the IP so multiple rate-limited operations can coexist."""
    return f"{_BUCKET_PREFIX}{ip}"


def _window_start(now: datetime) -> datetime:
    """Return the floor of `now` to the nearest `_WINDOW_SECONDS` boundary.

    Stored in the DB with timezone=UTC. The RateLimitCounter.window_start
    column is a naive TIMESTAMP in SQLite but a TIMESTAMPTZ in Postgres;
    we normalize to UTC-naive here to be dialect-agnostic.
    """
    epoch = int(now.timestamp())
    floored = (epoch // _WINDOW_SECONDS) * _WINDOW_SECONDS
    return datetime.fromtimestamp(floored, tz=timezone.utc).replace(tzinfo=None)


def record_failure(db: Session, ip: str, *, now: datetime | None = None) -> int:
    """Increment the failure counter for `ip` in the current window.

    Returns the new count. Commits to DB.
    """
    when = now or datetime.now(timezone.utc)
    bucket = _bucket_key(ip)
    window = _window_start(when)

    # Try INSERT first; on unique-violation, fall back to UPDATE. Works
    # portably across SQLite and Postgres without needing ON CONFLICT
    # syntax differences.
    row = db.execute(
        select(RateLimitCounter).where(
            RateLimitCounter.bucket_key == bucket,
            RateLimitCounter.window_start == window,
        )
    ).scalar_one_or_none()

    if row is None:
        row = RateLimitCounter(bucket_key=bucket, window_start=window, count=1)
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            # Another request inserted concurrently — re-read and update.
            db.rollback()
            row = db.execute(
                select(RateLimitCounter).where(
                    RateLimitCounter.bucket_key == bucket,
                    RateLimitCounter.window_start == window,
                )
            ).scalar_one()
            row.count = (row.count or 0) + 1
            db.flush()
    else:
        row.count = (row.count or 0) + 1
        db.flush()

    db.commit()
    return row.count


def is_rate_limited(
    db: Session, ip: str, *, now: datetime | None = None
) -> tuple[bool, int]:
    """Return (limited, retry_after_seconds) for `ip` in the current window.

    `retry_after_seconds` is the time until the current window ends; clients
    should wait at least that long before retrying.
    """
    when = now or datetime.now(timezone.utc)
    bucket = _bucket_key(ip)
    window = _window_start(when)

    row = db.execute(
        select(RateLimitCounter).where(
            RateLimitCounter.bucket_key == bucket,
            RateLimitCounter.window_start == window,
        )
    ).scalar_one_or_none()

    count = row.count if row else 0
    limited = count >= _THRESHOLD

    # Seconds until the next window boundary.
    next_window = window + timedelta(seconds=_WINDOW_SECONDS)
    # naive -> aware for correct subtraction
    next_window_utc = next_window.replace(tzinfo=timezone.utc)
    retry_after = max(1, int((next_window_utc - when).total_seconds()))
    return limited, retry_after


def reset_failures(db: Session, ip: str) -> int:
    """Delete all counter rows for the bucket. Returns deleted row count."""
    bucket = _bucket_key(ip)
    result = db.execute(
        delete(RateLimitCounter).where(RateLimitCounter.bucket_key == bucket)
    )
    db.commit()
    return result.rowcount or 0


def cleanup_stale_counters(
    now: datetime | None = None, db: Session | None = None
) -> int:
    """APScheduler job: delete counter rows older than 1 hour.

    In production (`db=None`) opens its own session via `get_sync_session`.
    Tests can inject a `db` session to observe side-effects from the same
    connection.
    """
    when = now or datetime.now(timezone.utc)
    cutoff = (when - _STALE_AFTER).replace(tzinfo=None)
    stmt = delete(RateLimitCounter).where(RateLimitCounter.window_start < cutoff)

    if db is not None:
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0

    with get_sync_session() as owned:
        result = owned.execute(stmt)
        owned.commit()
        return result.rowcount or 0
