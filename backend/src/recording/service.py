"""Recording service: CRUD and session management."""

import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.recording.models import RecordingSession, RecordingStatus
from src.recording.schemas import RecordingCreate


def create_recording(db: Session, data: RecordingCreate, user_id: int) -> RecordingSession:
    """Create a new recording session."""
    session = RecordingSession(
        repository_id=data.repository_id,
        environment_id=data.environment_id,
        source=data.source,
        target_url=data.target_url,
        target_file_path=data.target_file_path,
        target_library=data.target_library,
        status=RecordingStatus.PENDING,
        triggered_by=user_id,
    )
    db.add(session)
    db.flush()
    db.refresh(session)
    return session


def get_recording(db: Session, recording_id: int) -> RecordingSession | None:
    """Get a recording session by ID."""
    result = db.execute(
        select(RecordingSession).where(RecordingSession.id == recording_id)
    )
    return result.scalar_one_or_none()


def list_recordings(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    repository_id: int | None = None,
    status: str | None = None,
) -> tuple[list[RecordingSession], int]:
    """List recording sessions with pagination and filtering."""
    query = select(RecordingSession).order_by(RecordingSession.created_at.desc())

    if repository_id:
        query = query.where(RecordingSession.repository_id == repository_id)
    if status:
        query = query.where(RecordingSession.status == status)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    items = list(db.execute(query.offset(offset).limit(page_size)).scalars().all())

    return items, total


def append_event(db: Session, recording: RecordingSession, event_data: dict) -> None:
    """Append a recorded event to the session's events list."""
    events = json.loads(recording.events_json) if recording.events_json else []
    events.append(event_data)
    recording.events_json = json.dumps(events)
    recording.event_count = len(events)
    db.flush()


def start_recording(db: Session, recording: RecordingSession) -> None:
    """Mark recording as actively capturing."""
    recording.status = RecordingStatus.RECORDING
    recording.started_at = datetime.now(timezone.utc)
    db.flush()


def stop_recording(db: Session, recording: RecordingSession) -> None:
    """Mark recording as stopped and calculate duration."""
    recording.status = RecordingStatus.PROCESSING
    now = datetime.now(timezone.utc)
    recording.finished_at = now
    if recording.started_at:
        started = recording.started_at
        # SQLite strips timezone info — ensure both are comparable
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        recording.duration_seconds = (now - started).total_seconds()
    db.flush()


def complete_recording(
    db: Session, recording: RecordingSession, generated_robot: str | None = None
) -> None:
    """Mark recording as completed with optional generated .robot content."""
    recording.status = RecordingStatus.COMPLETED
    if generated_robot:
        recording.generated_robot = generated_robot
    if not recording.finished_at:
        recording.finished_at = datetime.now(timezone.utc)
    db.flush()


def fail_recording(db: Session, recording: RecordingSession, error: str) -> None:
    """Mark recording as failed with an error message."""
    recording.status = RecordingStatus.FAILED
    recording.error_message = error[:2000]
    if not recording.finished_at:
        recording.finished_at = datetime.now(timezone.utc)
    db.flush()


def cancel_recording(db: Session, recording: RecordingSession) -> None:
    """Cancel a recording session."""
    recording.status = RecordingStatus.CANCELLED
    if not recording.finished_at:
        recording.finished_at = datetime.now(timezone.utc)
    db.flush()


def delete_recording(db: Session, recording: RecordingSession) -> None:
    """Delete a recording session."""
    db.delete(recording)
    db.flush()
