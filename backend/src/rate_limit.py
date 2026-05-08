"""Global API rate limiter (slowapi) + DB-persistent counter model for SSO attempts."""

from datetime import datetime

from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base

limiter = Limiter(key_func=get_remote_address, default_limits=["1000/minute"])


class RateLimitCounter(Base):
    """Persistent per-bucket counter for rate-limited operations (e.g. SSO attempts).

    Used by Story 2.8 (SSO rate limiting) to enforce limits across a single-instance
    deployment without requiring Redis. APScheduler cleans up stale rows.
    """

    __tablename__ = "rate_limit_counters"
    __table_args__ = (
        UniqueConstraint(
            "bucket_key", "window_start", name="uq_rate_limit_counters_bucket_window"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bucket_key: Mapped[str] = mapped_column(String(255), nullable=False)
    window_start: Mapped[datetime] = mapped_column(index=True, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0)
