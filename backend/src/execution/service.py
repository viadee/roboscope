"""Execution service: run management, scheduling."""

import json
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.execution.models import ExecutionRun, RunStatus, RunType, RunnerType, Schedule
from src.execution.schemas import RunCreate, ScheduleCreate, ScheduleUpdate
from src.task_executor import TaskDispatchError, dispatch_task

logger = logging.getLogger("roboscope.execution")


# --- Execution Runs ---


def create_run(db: Session, data: RunCreate, user_id: int) -> ExecutionRun:
    """Create a new execution run."""
    run = ExecutionRun(
        repository_id=data.repository_id,
        environment_id=data.environment_id,
        run_type=data.run_type,
        runner_type=data.runner_type,
        status=RunStatus.PENDING,
        target_path=data.target_path,
        branch=data.branch,
        tags_include=data.tags_include,
        tags_exclude=data.tags_exclude,
        variables=json.dumps(data.variables) if data.variables else None,
        advanced_config=json.dumps(data.advanced_config) if data.advanced_config else None,
        parallel=data.parallel,
        max_retries=data.max_retries,
        timeout_seconds=data.timeout_seconds,
        triggered_by=user_id,
    )
    db.add(run)
    db.flush()
    db.refresh(run)
    return run


def get_run(db: Session, run_id: int) -> ExecutionRun | None:
    """Get a run by ID."""
    result = db.execute(select(ExecutionRun).where(ExecutionRun.id == run_id))
    return result.scalar_one_or_none()


def list_runs(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    repository_id: int | None = None,
    status: str | None = None,
) -> tuple[list[ExecutionRun], int]:
    """List runs with pagination and filtering."""
    query = select(ExecutionRun).order_by(ExecutionRun.created_at.desc())

    if repository_id:
        query = query.where(ExecutionRun.repository_id == repository_id)
    if status:
        query = query.where(ExecutionRun.status == status)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = db.execute(query)
    runs = list(result.scalars().all())

    return runs, total


def update_run_status(
    db: Session,
    run: ExecutionRun,
    status: RunStatus,
    error_message: str | None = None,
    duration_seconds: float | None = None,
    output_dir: str | None = None,
    task_id: str | None = None,
) -> ExecutionRun:
    """Update the status of a run."""
    run.status = status

    if status == RunStatus.RUNNING:
        run.started_at = datetime.now(timezone.utc)
    elif status in (RunStatus.PASSED, RunStatus.FAILED, RunStatus.ERROR, RunStatus.CANCELLED, RunStatus.TIMEOUT):
        run.finished_at = datetime.now(timezone.utc)

    if error_message is not None:
        run.error_message = error_message
    if duration_seconds is not None:
        run.duration_seconds = duration_seconds
    if output_dir is not None:
        run.output_dir = output_dir
    if task_id is not None:
        run.task_id = task_id

    db.flush()
    db.refresh(run)
    return run


def cancel_run(db: Session, run: ExecutionRun) -> ExecutionRun:
    """Cancel a pending or running execution."""
    if run.status not in (RunStatus.PENDING, RunStatus.RUNNING):
        raise ValueError(f"Cannot cancel run with status {run.status}")

    result = update_run_status(db, run, RunStatus.CANCELLED)

    # Kill the spawned process if the run is currently executing
    from src.execution.tasks import cancel_active_run
    cancel_active_run(run.id)

    return result


def retry_run(db: Session, run: ExecutionRun, user_id: int) -> ExecutionRun:
    """Create a new run as a retry of a failed run."""
    new_run = ExecutionRun(
        repository_id=run.repository_id,
        environment_id=run.environment_id,
        run_type=run.run_type,
        runner_type=run.runner_type,
        status=RunStatus.PENDING,
        target_path=run.target_path,
        branch=run.branch,
        tags_include=run.tags_include,
        tags_exclude=run.tags_exclude,
        variables=run.variables,
        parallel=run.parallel,
        retry_count=run.retry_count + 1,
        max_retries=run.max_retries,
        timeout_seconds=run.timeout_seconds,
        triggered_by=user_id,
    )
    db.add(new_run)
    db.flush()
    db.refresh(new_run)
    return new_run


# --- Schedules ---


def compute_next_run(cron_expression: str, now: datetime | None = None) -> datetime:
    """Next fire time strictly after `now`, as naive UTC (the DB convention).

    The cron fields are read in the server's local time zone (APScheduler's
    default), so "0 2 * * *" means 02:00 server time.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    # +1s: CronTrigger returns a time >= now; a tick landing exactly on a
    # match must not compute the same slot again.
    trigger = CronTrigger.from_crontab(cron_expression)
    nxt = trigger.get_next_fire_time(None, now + timedelta(seconds=1))
    return nxt.astimezone(timezone.utc).replace(tzinfo=None)


def _refresh_next_run(schedule: Schedule) -> None:
    schedule.next_run_at = (
        compute_next_run(schedule.cron_expression) if schedule.is_active else None
    )


def create_run_from_schedule(
    db: Session, schedule: Schedule, user_id: int, now: datetime | None = None
) -> ExecutionRun:
    """Create, commit and dispatch a run from a schedule's plain run fields.

    Deliberately never copies the schedule's variables / advanced config:
    those columns are inert and any reader must go through
    `gate_advanced_execution` (see the Schedule model + tripwire test).
    Sets `last_run_at`; the caller owns `next_run_at`.
    """
    now = now or datetime.now(timezone.utc)
    run = ExecutionRun(
        repository_id=schedule.repository_id,
        environment_id=schedule.environment_id,
        run_type=RunType.SCHEDULED,
        runner_type=schedule.runner_type,
        status=RunStatus.PENDING,
        target_path=schedule.target_path,
        branch=schedule.branch,
        tags_include=schedule.tags_include,
        tags_exclude=schedule.tags_exclude,
        triggered_by=user_id,
        schedule_id=schedule.id,
    )
    db.add(run)
    schedule.last_run_at = now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo else now
    # Commit so the background thread (separate session) sees the run.
    db.commit()

    from src.execution.tasks import execute_test_run

    try:
        run.task_id = dispatch_task(execute_test_run, run.id).id
    except TaskDispatchError as e:
        logger.error("Failed to dispatch scheduled run %d: %s", run.id, e)
        run.status = RunStatus.ERROR
        run.error_message = f"Task dispatch failed: {e}"
    db.commit()
    db.refresh(run)
    return run


def create_schedule(db: Session, data: ScheduleCreate, user_id: int) -> Schedule:
    """Create a new schedule."""
    schedule = Schedule(
        name=data.name,
        cron_expression=data.cron_expression,
        repository_id=data.repository_id,
        environment_id=data.environment_id,
        target_path=data.target_path,
        branch=data.branch,
        runner_type=data.runner_type,
        tags_include=data.tags_include,
        tags_exclude=data.tags_exclude,
        created_by=user_id,
        is_active=True,
    )
    _refresh_next_run(schedule)
    db.add(schedule)
    db.flush()
    db.refresh(schedule)
    return schedule


def get_schedule(db: Session, schedule_id: int) -> Schedule | None:
    """Get a schedule by ID."""
    result = db.execute(select(Schedule).where(Schedule.id == schedule_id))
    return result.scalar_one_or_none()


def list_schedules(db: Session) -> list[Schedule]:
    """List all schedules."""
    result = db.execute(select(Schedule).order_by(Schedule.name))
    return list(result.scalars().all())


def update_schedule(db: Session, schedule: Schedule, data: ScheduleUpdate) -> Schedule:
    """Update a schedule."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(schedule, key, value)
    _refresh_next_run(schedule)
    db.flush()
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule: Schedule) -> None:
    """Delete a schedule. Its past runs stay, detached from it."""
    db.execute(
        update(ExecutionRun)
        .where(ExecutionRun.schedule_id == schedule.id)
        .values(schedule_id=None)
    )
    db.delete(schedule)
    db.flush()


def toggle_schedule(db: Session, schedule: Schedule) -> Schedule:
    """Toggle a schedule's active status."""
    schedule.is_active = not schedule.is_active
    _refresh_next_run(schedule)
    db.flush()
    db.refresh(schedule)
    return schedule
