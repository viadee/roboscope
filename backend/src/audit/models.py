"""Audit log model for tracking user actions."""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class AuditLog(Base):
    """Immutable log of user actions for compliance."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, default=None)
    username: Mapped[str | None] = mapped_column(String(100), default=None)
    action: Mapped[str] = mapped_column(String(50), index=True)  # create, update, delete, login, ...
    resource_type: Mapped[str] = mapped_column(String(50), index=True)  # run, report, webhook, ...
    resource_id: Mapped[int | None] = mapped_column(Integer, default=None)
    detail: Mapped[str | None] = mapped_column(Text, default=None)  # JSON extra info
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)
    timestamp: Mapped[datetime] = mapped_column(default=func.now(), server_default=func.now(), index=True)
