"""Execution service: run management, scheduling."""

import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.execution.models import ExecutionRun, RunStatus, RunType, RunnerType, Schedule
from src.execution.schemas import RunCreate, ScheduleCreate, ScheduleUpdate


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

    # Note: in-process executor doesn't support cancellation of running tasks.
    # The run will be marked as cancelled in the DB.

    return update_run_status(db, run, RunStatus.CANCELLED)


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
    )
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
    db.flush()
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule: Schedule) -> None:
    """Delete a schedule."""
    db.delete(schedule)
    db.flush()


def toggle_schedule(db: Session, schedule: Schedule) -> Schedule:
    """Toggle a schedule's active status."""
    schedule.is_active = not schedule.is_active
    db.flush()
    db.refresh(schedule)
    return schedule
