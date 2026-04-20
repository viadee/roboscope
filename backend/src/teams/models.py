"""Team and TeamMember ORM models — Phase 4 Enterprise Identity."""

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

import src.auth.models  # noqa: F401 — FK resolution (team_members.user_id -> users.id)
from src.database import Base, TimestampMixin


class Team(Base, TimestampMixin):
    """A team groups users for repo-scoped role inheritance."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    external_id: Mapped[str | None] = mapped_column(
        String(255), index=True, default=None, nullable=True
    )


class TeamMember(Base, TimestampMixin):
    """Membership of a user in a team with a specific role."""

    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    source: Mapped[str] = mapped_column(String(20), default="manual")
    external_id: Mapped[str | None] = mapped_column(String(255), default=None, nullable=True)
