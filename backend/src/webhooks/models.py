"""Models for API tokens and webhooks."""

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base, TimestampMixin


class ApiToken(Base, TimestampMixin):
    """Long-lived API token for programmatic access (CI/CD)."""

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    prefix: Mapped[str] = mapped_column(String(16))  # First 8 chars for display: rbs_xxxx
    role: Mapped[str] = mapped_column(String(20), default="runner")  # scoped role
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(default=None)
    last_used_at: Mapped[datetime | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Webhook(Base, TimestampMixin):
    """Outbound webhook for event notifications."""

    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(1000))
    secret: Mapped[str | None] = mapped_column(String(255), default=None)  # HMAC secret
    events: Mapped[str] = mapped_column(Text, default="[]")  # JSON array of event names
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), default=None, index=True,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    last_triggered_at: Mapped[datetime | None] = mapped_column(default=None)
    last_status_code: Mapped[int | None] = mapped_column(Integer, default=None)


class WebhookDelivery(Base):
    """Log of individual webhook delivery attempts."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    webhook_id: Mapped[int] = mapped_column(
        ForeignKey("webhooks.id", ondelete="CASCADE"), index=True,
    )
    event: Mapped[str] = mapped_column(String(100))
    payload: Mapped[str] = mapped_column(Text)  # JSON
    status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    response_body: Mapped[str | None] = mapped_column(Text, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
    )
