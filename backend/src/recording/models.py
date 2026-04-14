"""Recording models: browser recording sessions."""

import sys
from datetime import datetime

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        pass

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base, TimestampMixin


class RecordingStatus(StrEnum):
    PENDING = "pending"
    RECORDING = "recording"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RecordingSource(StrEnum):
    PLAYWRIGHT = "playwright"
    EXTENSION = "extension"


class RecordingSession(Base, TimestampMixin):
    """A browser recording session that captures user interactions."""

    __tablename__ = "recording_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), index=True)
    environment_id: Mapped[int | None] = mapped_column(
        ForeignKey("environments.id"), default=None
    )
    status: Mapped[str] = mapped_column(
        String(20), default=RecordingStatus.PENDING, index=True
    )
    source: Mapped[str] = mapped_column(String(20), default=RecordingSource.PLAYWRIGHT)
    target_url: Mapped[str | None] = mapped_column(String(2000), default=None)
    target_file_path: Mapped[str | None] = mapped_column(String(500), default=None)
    target_library: Mapped[str] = mapped_column(String(50), default="Browser")
    events_json: Mapped[str | None] = mapped_column(Text, default=None)  # JSON array
    generated_robot: Mapped[str | None] = mapped_column(Text, default=None)
    rf_mcp_session_id: Mapped[str | None] = mapped_column(String(255), default=None)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    duration_seconds: Mapped[float | None] = mapped_column(Float, default=None)
    triggered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
