"""Pydantic schemas for test execution."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.execution.models import RunnerType, RunStatus, RunType


class RunCreate(BaseModel):
    repository_id: int
    environment_id: int | None = None
    run_type: RunType = RunType.SINGLE
    runner_type: RunnerType = RunnerType.SUBPROCESS
    target_path: str = Field(..., min_length=1, max_length=500)
    branch: str = "main"
    tags_include: str | None = None
    tags_exclude: str | None = None
    variables: dict | None = None
    parallel: bool = False
    max_retries: int = Field(default=0, ge=0, le=5)
    timeout_seconds: int = Field(default=3600, ge=30, le=86400)


class RunResponse(BaseModel):
    id: int
    repository_id: int
    environment_id: int | None = None
    run_type: RunType
    runner_type: RunnerType
    status: RunStatus
    target_path: str
    branch: str
    tags_include: str | None = None
    tags_exclude: str | None = None
    parallel: bool
    retry_count: int
    max_retries: int
    timeout_seconds: int
    celery_task_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    triggered_by: int
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunListResponse(BaseModel):
    items: list[RunResponse]
    total: int
    page: int
    page_size: int


class ScheduleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    cron_expression: str = Field(..., min_length=5, max_length=100)
    repository_id: int
    environment_id: int | None = None
    target_path: str
    branch: str = "main"
    runner_type: RunnerType = RunnerType.SUBPROCESS
    tags_include: str | None = None
    tags_exclude: str | None = None


class ScheduleUpdate(BaseModel):
    name: str | None = None
    cron_expression: str | None = None
    target_path: str | None = None
    branch: str | None = None
    runner_type: RunnerType | None = None
    tags_include: str | None = None
    tags_exclude: str | None = None
    is_active: bool | None = None


class ScheduleResponse(BaseModel):
    id: int
    name: str
    cron_expression: str
    repository_id: int
    environment_id: int | None = None
    target_path: str
    branch: str
    runner_type: RunnerType
    tags_include: str | None = None
    tags_exclude: str | None = None
    is_active: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}
