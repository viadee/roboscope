"""Unit tests for the per-IP SSO rate-limit service (Story 2-8)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from src.auth.sso_rate_limit import (
    _THRESHOLD,
    _WINDOW_SECONDS,
    _bucket_key,
    _window_start,
    cleanup_stale_counters,
    is_rate_limited,
    record_failure,
    reset_failures,
)
from src.rate_limit import RateLimitCounter


def _count_rows(db: Session, ip: str) -> int:
    return (
        db.query(RateLimitCounter)
        .filter(RateLimitCounter.bucket_key == _bucket_key(ip))
        .count()
    )


class TestRecordFailure:
    def test_increments_counter_in_current_window(self, db_session: Session) -> None:
        now = datetime(2026, 4, 22, 10, 0, 30, tzinfo=timezone.utc)

        assert record_failure(db_session, "1.2.3.4", now=now) == 1
        assert record_failure(db_session, "1.2.3.4", now=now) == 2
        assert record_failure(db_session, "1.2.3.4", now=now) == 3

        assert _count_rows(db_session, "1.2.3.4") == 1  # same window, one row

    def test_uses_separate_rows_per_window(self, db_session: Session) -> None:
        t0 = datetime(2026, 4, 22, 10, 0, 30, tzinfo=timezone.utc)
        t1 = t0 + timedelta(seconds=_WINDOW_SECONDS + 1)  # next window

        assert record_failure(db_session, "1.2.3.4", now=t0) == 1
        assert record_failure(db_session, "1.2.3.4", now=t0) == 2
        # Rolls into a new window — counter resets to 1 for the new row.
        assert record_failure(db_session, "1.2.3.4", now=t1) == 1

        assert _count_rows(db_session, "1.2.3.4") == 2  # two windows, two rows

    def test_distinct_ips_have_distinct_counters(self, db_session: Session) -> None:
        now = datetime(2026, 4, 22, 10, 0, 30, tzinfo=timezone.utc)
        record_failure(db_session, "1.1.1.1", now=now)
        record_failure(db_session, "2.2.2.2", now=now)
        assert _count_rows(db_session, "1.1.1.1") == 1
        assert _count_rows(db_session, "2.2.2.2") == 1


class TestIsRateLimited:
    def test_below_threshold_returns_false(self, db_session: Session) -> None:
        now = datetime(2026, 4, 22, 10, 0, 30, tzinfo=timezone.utc)
        for _ in range(_THRESHOLD - 1):
            record_failure(db_session, "1.2.3.4", now=now)
        limited, retry_after = is_rate_limited(db_session, "1.2.3.4", now=now)
        assert limited is False
        assert retry_after > 0

    def test_at_threshold_returns_true(self, db_session: Session) -> None:
        now = datetime(2026, 4, 22, 10, 0, 30, tzinfo=timezone.utc)
        for _ in range(_THRESHOLD):
            record_failure(db_session, "1.2.3.4", now=now)
        limited, retry_after = is_rate_limited(db_session, "1.2.3.4", now=now)
        assert limited is True
        assert retry_after >= 1

    def test_no_rows_returns_false(self, db_session: Session) -> None:
        limited, _ = is_rate_limited(db_session, "unseen")
        assert limited is False

    def test_retry_after_decreases_through_window(
        self, db_session: Session
    ) -> None:
        window_floor = _window_start(
            datetime(2026, 4, 22, 10, 0, 0, tzinfo=timezone.utc)
        )
        early = window_floor.replace(tzinfo=timezone.utc) + timedelta(seconds=10)
        late = window_floor.replace(tzinfo=timezone.utc) + timedelta(
            seconds=_WINDOW_SECONDS - 5
        )
        for _ in range(_THRESHOLD):
            record_failure(db_session, "1.2.3.4", now=early)
        _, retry_early = is_rate_limited(db_session, "1.2.3.4", now=early)
        _, retry_late = is_rate_limited(db_session, "1.2.3.4", now=late)
        assert retry_early > retry_late >= 1


class TestResetFailures:
    def test_clears_all_windows_for_ip(self, db_session: Session) -> None:
        t0 = datetime(2026, 4, 22, 10, 0, 30, tzinfo=timezone.utc)
        t1 = t0 + timedelta(seconds=_WINDOW_SECONDS + 1)
        record_failure(db_session, "1.2.3.4", now=t0)
        record_failure(db_session, "1.2.3.4", now=t1)
        assert _count_rows(db_session, "1.2.3.4") == 2

        deleted = reset_failures(db_session, "1.2.3.4")
        assert deleted == 2
        assert _count_rows(db_session, "1.2.3.4") == 0

    def test_does_not_affect_other_ips(self, db_session: Session) -> None:
        now = datetime(2026, 4, 22, 10, 0, 30, tzinfo=timezone.utc)
        record_failure(db_session, "1.1.1.1", now=now)
        record_failure(db_session, "2.2.2.2", now=now)

        reset_failures(db_session, "1.1.1.1")
        assert _count_rows(db_session, "1.1.1.1") == 0
        assert _count_rows(db_session, "2.2.2.2") == 1


class TestCleanupStaleCounters:
    def test_removes_rows_older_than_one_hour(self, db_session: Session) -> None:
        t_now = datetime(2026, 4, 22, 10, 0, 30, tzinfo=timezone.utc)
        t_stale = t_now - timedelta(hours=2)
        t_fresh = t_now - timedelta(minutes=5)

        record_failure(db_session, "stale", now=t_stale)
        record_failure(db_session, "fresh", now=t_fresh)

        # Inject the test session so the cleanup is visible to assertions.
        deleted = cleanup_stale_counters(now=t_now, db=db_session)
        assert deleted == 1
        assert _count_rows(db_session, "stale") == 0
        assert _count_rows(db_session, "fresh") == 1
