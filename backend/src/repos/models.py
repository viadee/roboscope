"""Repository models."""

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

import src.environments.models  # noqa: F401 — FK resolution
from src.database import Base, TimestampMixin


class Repository(Base, TimestampMixin):
    """Repository configuration — git remote or local folder."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    repo_type: Mapped[str] = mapped_column(String(20), default="git")
    git_url: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    local_path: Mapped[str] = mapped_column(String(500))
    last_synced_at: Mapped[datetime | None] = mapped_column(default=None)
    auto_sync: Mapped[bool] = mapped_column(Boolean, default=True)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    sync_status: Mapped[str | None] = mapped_column(String(20), nullable=True, default="idle")
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    environment_id: Mapped[int | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"), nullable=True, default=None
    )


class ProjectMember(Base, TimestampMixin):
    """User membership in a project (repository) with per-project role."""

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("user_id", "repository_id", name="uq_project_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="viewer")
