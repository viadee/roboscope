"""Pydantic schemas for browser recording."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.recording.models import RecordingSource, RecordingStatus


class RecordingCreate(BaseModel):
    repository_id: int
    environment_id: int | None = None
    source: RecordingSource = RecordingSource.PLAYWRIGHT
    target_url: str | None = Field(default=None, max_length=2000)
    target_file_path: str | None = Field(default=None, max_length=500)
    target_library: str = Field(default="Browser", pattern=r"^(Browser|SeleniumLibrary)$")


class RecordingResponse(BaseModel):
    id: int
    repository_id: int
    environment_id: int | None = None
    status: RecordingStatus
    source: RecordingSource
    target_url: str | None = None
    target_file_path: str | None = None
    target_library: str
    event_count: int
    generated_robot: str | None = None
    rf_mcp_session_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    triggered_by: int
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecordingListResponse(BaseModel):
    items: list[RecordingResponse]
    total: int
    page: int
    page_size: int


class RecordingEventIn(BaseModel):
    """An event received from the Chrome extension or Playwright recorder."""
    event_type: str  # click, input, select, navigate, scroll, wait
    selector: str | None = None
    value: str | None = None
    url: str | None = None
    tag: str | None = None
    timestamp: float | None = None


class RecordingStopRequest(BaseModel):
    """Request to stop a recording and optionally generate .robot output."""
    generate_robot: bool = True
    save_to_file: bool = False
