"""Execution models: runs, schedules."""

import sys
from datetime import datetime

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        pass

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base, TimestampMixin


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class RunType(StrEnum):
    SINGLE = "single"
    FOLDER = "folder"
    BATCH = "batch"
    SCHEDULED = "scheduled"


class RunnerType(StrEnum):
    SUBPROCESS = "subprocess"
    DOCKER = "docker"


class ExecutionRun(Base, TimestampMixin):
    """A single test execution run."""

    __tablename__ = "execution_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), index=True)
    environment_id: Mapped[int | None] = mapped_column(ForeignKey("environments.id"), default=None)
    run_type: Mapped[str] = mapped_column(String(20), default=RunType.SINGLE)
    runner_type: Mapped[str] = mapped_column(String(20), default=RunnerType.SUBPROCESS)
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.PENDING, index=True)
    target_path: Mapped[str] = mapped_column(String(500))
    branch: Mapped[str] = mapped_column(String(100), default="main")
    tags_include: Mapped[str | None] = mapped_column(String(500), default=None)
    tags_exclude: Mapped[str | None] = mapped_column(String(500), default=None)
    variables: Mapped[str | None] = mapped_column(Text, default=None)  # JSON string
    parallel: Mapped[bool] = mapped_column(Boolean, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    task_id: Mapped[str | None] = mapped_column("celery_task_id", String(255), default=None)
    output_dir: Mapped[str | None] = mapped_column(String(500), default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    duration_seconds: Mapped[float | None] = mapped_column(Float, default=None)
    triggered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("schedules.id"), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)


class Schedule(Base, TimestampMixin):
    """Scheduled test execution."""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    cron_expression: Mapped[str] = mapped_column(String(100))
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"))
    environment_id: Mapped[int | None] = mapped_column(ForeignKey("environments.id"), default=None)
    target_path: Mapped[str] = mapped_column(String(500))
    branch: Mapped[str] = mapped_column(String(100), default="main")
    runner_type: Mapped[str] = mapped_column(String(20), default=RunnerType.SUBPROCESS)
    tags_include: Mapped[str | None] = mapped_column(String(500), default=None)
    tags_exclude: Mapped[str | None] = mapped_column(String(500), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(default=None)
    next_run_at: Mapped[datetime | None] = mapped_column(default=None)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
