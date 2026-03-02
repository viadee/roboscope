"""Execution API endpoints: runs and schedules."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from src.task_executor import TaskDispatchError, dispatch_task
from src.database import get_db
from src.execution.models import RunStatus
from src.execution.schemas import (
    RunCreate,
    RunListResponse,
    RunResponse,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
)
from src.execution.service import (
    cancel_run,
    create_run,
    create_schedule,
    delete_schedule,
    get_run,
    get_schedule,
    list_runs,
    list_schedules,
    retry_run,
    toggle_schedule,
    update_schedule,
)
from src.reports.models import Report

logger = logging.getLogger("roboscope.execution")

router = APIRouter()


# --- Runs ---


@router.post("/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def start_run(
    data: RunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Start a new test execution run."""
    # Override runner_type from environment's default if an environment is set
    if data.environment_id:
        from src.environments.models import Environment
        env = db.execute(
            select(Environment).where(Environment.id == data.environment_id)
        ).scalar_one_or_none()
        if env and env.default_runner_type and data.runner_type == "subprocess":
            data.runner_type = env.default_runner_type

    run = create_run(db, data, current_user.id)
    # Commit so background thread can see the run in a separate DB session
    db.commit()

    # Dispatch to background executor
    try:
        from src.execution.tasks import execute_test_run

        result = dispatch_task(execute_test_run, run.id)
        run.task_id = result.id
        db.flush()
        db.refresh(run)
    except TaskDispatchError as e:
        logger.error("Failed to dispatch run %d: %s", run.id, e)
        run.status = RunStatus.ERROR
        run.error_message = f"Task dispatch failed: {e}"
        db.flush()
        db.refresh(run)

    return run


@router.get("/runs", response_model=RunListResponse)
def get_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repository_id: int | None = Query(default=None),
    run_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List execution runs with pagination and filtering."""
    runs, total = list_runs(db, page, page_size, repository_id, run_status)
    return RunListResponse(
        items=[RunResponse.model_validate(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run_detail(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get execution run details."""
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
def cancel_run_endpoint(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Cancel a pending or running execution."""
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    try:
        return cancel_run(db, run)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/runs/cancel-all")
def cancel_all_runs(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Cancel all pending and running executions."""
    from src.execution.models import ExecutionRun
    result = db.execute(
        select(ExecutionRun).where(
            ExecutionRun.status.in_([RunStatus.PENDING, RunStatus.RUNNING])
        )
    )
    runs = list(result.scalars().all())
    cancelled = 0
    for run in runs:
        run.status = RunStatus.CANCELLED
        run.finished_at = datetime.now(timezone.utc)
        cancelled += 1
    db.flush()
    logger.info("Cancelled %d runs", cancelled)
    return {"cancelled": cancelled}


@router.post("/runs/{run_id}/retry", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def retry_run_endpoint(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Retry a failed or errored run."""
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status not in (RunStatus.FAILED, RunStatus.ERROR, RunStatus.TIMEOUT):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only retry failed, errored, or timed-out runs",
        )
    new_run = retry_run(db, run, current_user.id)
    db.commit()

    # Dispatch to background executor
    try:
        from src.execution.tasks import execute_test_run

        result = dispatch_task(execute_test_run, new_run.id)
        new_run.task_id = result.id
        db.flush()
        db.refresh(new_run)
    except TaskDispatchError as e:
        logger.error("Failed to dispatch retry run %d: %s", new_run.id, e)
        new_run.status = RunStatus.ERROR
        new_run.error_message = f"Task dispatch failed: {e}"
        db.flush()
        db.refresh(new_run)

    return new_run


@router.get("/runs/{run_id}/output")
def get_run_output(
    run_id: int,
    stream: str = Query(default="stdout", description="stdout or stderr"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get stdout or stderr output of a run."""
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if not run.output_dir:
        return PlainTextResponse("")

    log_file = Path(run.output_dir) / f"{stream}.log"
    if not log_file.exists():
        return PlainTextResponse("")

    content = log_file.read_text(encoding="utf-8", errors="replace")
    return PlainTextResponse(content)


@router.get("/runs/{run_id}/report")
def get_run_report(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get the report ID linked to a run (if parsed)."""
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    result = db.execute(
        select(Report).where(Report.execution_run_id == run_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        return {"report_id": None}
    return {"report_id": report.id}


# --- Schedules ---


@router.get("/schedules", response_model=list[ScheduleResponse])
def get_schedules(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all schedules."""
    return list_schedules(db)


@router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def add_schedule(
    data: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Create a new schedule."""
    return create_schedule(db, data, current_user.id)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
def patch_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Update a schedule."""
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return update_schedule(db, schedule, data)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Delete a schedule."""
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    delete_schedule(db, schedule)


@router.post("/schedules/{schedule_id}/toggle", response_model=ScheduleResponse)
def toggle_schedule_endpoint(
    schedule_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Toggle a schedule's active status."""
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return toggle_schedule(db, schedule)
