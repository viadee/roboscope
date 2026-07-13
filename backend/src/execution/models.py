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
    # EXEC.2: advanced robot execution config as a JSON string
    # {"args": [...], "prerun_modifiers": [...]}. Nullable; only the resolver
    # interprets it (EXEC.3+). Mirrors `variables` storage.
    advanced_config: Mapped[str | None] = mapped_column(Text, default=None)  # JSON string
    parallel: Mapped[bool] = mapped_column(Boolean, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    task_id: Mapped[str | None] = mapped_column("celery_task_id", String(255), default=None)  # DB column name kept for migration compat
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
    # EXEC.2: bring Schedule to parity with ExecutionRun so recurring runs can
    # carry variables + advanced config (previously Schedule had neither).
    #
    # Currently INERT: neither ScheduleCreate/ScheduleUpdate (schemas.py) nor
    # any scheduler job writes or reads these columns — there is no
    # schedule-trigger path yet (main.py's APScheduler jobs are retention /
    # OIDC-refresh / repo-auto-sync only, not "run this schedule's suite").
    # WHEN that trigger path is built: it MUST call
    # `governance.dependencies.gate_advanced_execution` with this schedule's
    # `advanced_config` before dispatching a run — the same gate
    # `POST /runs` uses (flag + role + deny-list). Skipping it would be a
    # code-exec bypass: a schedule is unattended, so an unaudited
    # prerun-modifier/listener would execute with no request-time review at
    # all. `test_schedule_trigger_gate_tripwire.py` fails loudly if a future
    # reader of these columns doesn't reference the gate.
    variables: Mapped[str | None] = mapped_column(Text, default=None)  # JSON string
    advanced_config: Mapped[str | None] = mapped_column(Text, default=None)  # JSON string
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(default=None)
    next_run_at: Mapped[datetime | None] = mapped_column(default=None)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
