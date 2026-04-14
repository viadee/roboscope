"""Recording API endpoints: browser recording sessions."""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from src.database import get_db
from src.rate_limit import limiter
from src.task_executor import TaskDispatchError, dispatch_task
from src.recording.models import RecordingStatus
from src.recording.schemas import (
    RecordingCreate,
    RecordingEventIn,
    RecordingListResponse,
    RecordingResponse,
    RecordingStopRequest,
)
from src.recording.service import (
    append_event,
    cancel_recording,
    complete_recording,
    create_recording,
    delete_recording,
    fail_recording,
    get_recording,
    list_recordings,
    start_recording,
    stop_recording,
)

logger = logging.getLogger("roboscope.recording")

router = APIRouter()


# --- CRUD ---


@router.post(
    "/recordings",
    response_model=RecordingResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def create_recording_endpoint(
    request: Request,
    data: RecordingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Create a new recording session."""
    recording = create_recording(db, data, current_user.id)
    return recording


@router.get("/recordings", response_model=RecordingListResponse)
def list_recordings_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repository_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
):
    """List recording sessions with pagination."""
    items, total = list_recordings(
        db, page=page, page_size=page_size,
        repository_id=repository_id, status=status_filter,
    )
    return RecordingListResponse(
        items=[RecordingResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/recordings/{recording_id}", response_model=RecordingResponse)
def get_recording_endpoint(
    recording_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a recording session by ID."""
    recording = get_recording(db, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    return recording


@router.delete("/recordings/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recording_endpoint(
    recording_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Delete a recording session."""
    recording = get_recording(db, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    delete_recording(db, recording)


# --- Recording lifecycle ---


@router.post("/recordings/{recording_id}/start", response_model=RecordingResponse)
def start_recording_endpoint(
    recording_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Start capturing events for a recording session."""
    recording = get_recording(db, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    if recording.status != RecordingStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start recording in '{recording.status}' status",
        )
    start_recording(db, recording)
    return recording


@router.post("/recordings/{recording_id}/start-browser", response_model=RecordingResponse)
def start_browser_recording_endpoint(
    recording_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Start a Playwright browser for in-app recording.

    Opens a headed Chromium browser that captures user interactions.
    Events are streamed via WebSocket in real time.
    """
    recording = get_recording(db, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    if recording.status != RecordingStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start browser in '{recording.status}' status",
        )

    db.commit()  # Must commit before dispatch_task

    try:
        from src.recording.tasks import run_playwright_recorder
        dispatch_task(run_playwright_recorder, recording_id, recording.target_url)
    except TaskDispatchError as e:
        logger.error("Failed to dispatch Playwright recorder: %s", e)
        fail_recording(db, recording, f"Browser launch failed: {e}")
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

    db.refresh(recording)
    return recording


@router.post("/recordings/{recording_id}/event", response_model=RecordingResponse)
def append_event_endpoint(
    recording_id: int,
    event: RecordingEventIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Append a recorded browser event to the session."""
    recording = get_recording(db, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    if recording.status != RecordingStatus.RECORDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot append events in '{recording.status}' status",
        )

    event_data = event.model_dump(exclude_none=True)
    append_event(db, recording, event_data)

    # Broadcast event via WebSocket (best-effort, don't block)
    try:
        from src.recording.tasks import _broadcast_recording_event
        _broadcast_recording_event(recording_id, event_data)
    except Exception:
        pass  # Non-critical

    return recording


@router.post("/recordings/{recording_id}/stop", response_model=RecordingResponse)
def stop_recording_endpoint(
    recording_id: int,
    data: RecordingStopRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Stop a recording session and optionally generate .robot output."""
    recording = get_recording(db, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    if recording.status != RecordingStatus.RECORDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot stop recording in '{recording.status}' status",
        )

    stop_data = data or RecordingStopRequest()

    # Signal Playwright recorder to stop (if running)
    from src.recording.tasks import signal_stop_playwright
    signalled = signal_stop_playwright(recording_id)

    if signalled:
        # Playwright task handles status transitions and .robot generation on exit
        logger.info("Recording %d: stop signal sent to Playwright", recording_id)
    else:
        # Extension-based recording — handle directly
        stop_recording(db, recording)
        db.commit()

        if stop_data.generate_robot:
            try:
                from src.recording.tasks import generate_robot_for_recording
                dispatch_task(generate_robot_for_recording, recording_id)
            except TaskDispatchError as e:
                logger.error("Failed to dispatch robot generation: %s", e)
                fail_recording(db, recording, f"Generation dispatch failed: {e}")
        else:
            complete_recording(db, recording)

    db.refresh(recording)
    return recording


@router.post(
    "/recordings/{recording_id}/cancel", response_model=RecordingResponse
)
def cancel_recording_endpoint(
    recording_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Cancel a recording session."""
    recording = get_recording(db, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    if recording.status in (RecordingStatus.COMPLETED, RecordingStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel recording in '{recording.status}' status",
        )
    # Signal Playwright to stop if running
    from src.recording.tasks import signal_stop_playwright
    signal_stop_playwright(recording_id)
    cancel_recording(db, recording)
    return recording


@router.get("/recordings/{recording_id}/robot", response_class=None)
def get_generated_robot(
    recording_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the generated .robot file content for a completed recording."""
    recording = get_recording(db, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    if not recording.generated_robot:
        raise HTTPException(
            status_code=404,
            detail="No generated .robot content available",
        )
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=recording.generated_robot,
        media_type="text/plain",
    )


@router.get("/recordings/{recording_id}/events")
def get_recording_events(
    recording_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the list of recorded events for a session."""
    recording = get_recording(db, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    events = json.loads(recording.events_json) if recording.events_json else []
    return {"recording_id": recording_id, "events": events, "count": len(events)}
