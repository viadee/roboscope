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


from fastapi.responses import PlainTextResponse


@router.get("/recordings/{recording_id}/robot", response_class=PlainTextResponse)
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


# ---------------------------------------------------------------------------
# Recorder v2 — Session endpoint family (Story W.1 stub + W.8 audit)
# ---------------------------------------------------------------------------

from pydantic import BaseModel

from src.audit.event_types import AuditEventType
from src.audit.service import log_event
from src.auth.constants import ERR_INSUFFICIENT_PERMISSIONS, ROLE_HIERARCHY
from src.auth.permissions import effective_role
from src.recording.models import RecordingSession, RecordingSource
from src.recording.selector_schema import RecordingTransport
from src.repos.models import Repository


class V2CapabilitiesResponse(BaseModel):
    web_playwright_viable: bool
    desktop_windows_viable: bool
    desktop_macos_viable: bool


def _web_playwright_viable() -> bool:
    """Is a backend-launched, user-visible Chromium feasible on this host?

    Heuristic:
      * `ROBOSCOPE_HEADED_BROWSER=true|false` overrides everything.
      * Linux: requires $DISPLAY or $WAYLAND_DISPLAY. No desktop → no
        window the remote user could see.
      * macOS / Windows: assume yes (no cheap remote-detection heuristic
        — admins of a headless Windows Server SKU set the override).

    Story DEPLOY-1 (2026-04-23).
    """
    import os as _os
    import sys as _sys
    override = _os.environ.get("ROBOSCOPE_HEADED_BROWSER", "auto").strip().lower()
    if override in ("1", "true", "yes", "on"):
        return True
    if override in ("0", "false", "no", "off"):
        return False
    if _sys.platform.startswith("linux"):
        return bool(_os.environ.get("DISPLAY") or _os.environ.get("WAYLAND_DISPLAY"))
    return True


@router.get("/recordings/sessions/capabilities", response_model=V2CapabilitiesResponse)
def v2_recorder_capabilities(
    _current_user: User = Depends(get_current_user),
) -> V2CapabilitiesResponse:
    """Tell the frontend which v2 recorder transports the *backend host*
    can actually drive. Drives the launcher's transport radio group so
    remote deployments don't silently offer "Web (Playwright)" when the
    backend has no display to render Chromium into.
    """
    import sys as _sys
    return V2CapabilitiesResponse(
        web_playwright_viable=_web_playwright_viable(),
        desktop_windows_viable=_sys.platform.startswith("win"),
        desktop_macos_viable=False,  # DM.1 NO-GO lock.
    )


class V2SessionCreateRequest(BaseModel):
    transport: RecordingTransport
    repo_id: int


class V2SessionResponse(BaseModel):
    session_id: int
    transport: RecordingTransport
    status: str


def _transport_to_source(t: RecordingTransport) -> str:
    """Map the v2 transport enum to the existing RecordingSource column.
    chrome_extension → extension; everything else uses the playwright
    storage path. Desktop transports temporarily co-locate; a dedicated
    `desktop_*` source value is a follow-up schema-migration story."""
    if t == "chrome_extension":
        return RecordingSource.EXTENSION
    return RecordingSource.PLAYWRIGHT


@router.post(
    "/recordings/sessions",
    response_model=V2SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def v2_create_session(
    request: Request,
    data: V2SessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Story W.1 (stub): create a v2 RecordingSession row + emit audit.

    Does NOT yet launch a Chromium instance — that's a follow-up commit
    that wires Playwright on a dedicated event-loop thread per AR-2.
    The session row is marked RECORDING immediately so the retention
    cleanup (W.8) can auto-abort if nothing ever starts streaming.

    Effective-role check is done inline because the repo id arrives in
    the JSON body, not the URL path (so `require_effective_role` isn't
    usable here — it reads `path_params["repo_id"]`).
    """
    repo = db.get(Repository, data.repo_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
        )
    if getattr(current_user, "_auth_via_api_token", False):
        # Story 3-15: API tokens stay capped at scoped role; no team/project grant.
        role_level = ROLE_HIERARCHY.get(Role(current_user.role), -1)
    else:
        er = effective_role(db, current_user, repo)
        role_level = ROLE_HIERARCHY.get(er, -1)
    if role_level < ROLE_HIERARCHY.get(Role.EDITOR, 999):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERR_INSUFFICIENT_PERMISSIONS,
        )

    # Per-user session cap (AR-10): abort any other active session owned
    # by the caller before creating the new one.
    existing = (
        db.query(RecordingSession)
        .filter(
            RecordingSession.triggered_by == current_user.id,
            RecordingSession.status == RecordingStatus.RECORDING,
        )
        .all()
    )
    for row in existing:
        row.status = RecordingStatus.CANCELLED
        row.finished_at = datetime.now(timezone.utc)
        log_event(
            db,
            AuditEventType.RECORDING_SESSION_ABORTED,
            user_id=current_user.id,
            resource_id=row.repository_id,
            detail={"session_id": row.id, "reason": "superseded"},
        )

    session = RecordingSession(
        repository_id=data.repo_id,
        status=RecordingStatus.RECORDING,
        source=_transport_to_source(data.transport),
        triggered_by=current_user.id,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.flush()
    db.refresh(session)

    # Story W.2 — register the in-memory FIFO so the SSE endpoint and
    # the capture producer (future W.1 full) share it.
    from src.recording.v2_command_queue import register_session
    register_session(session.id)

    log_event(
        db,
        AuditEventType.RECORDING_SESSION_STARTED,
        user_id=current_user.id,
        resource_id=data.repo_id,
        detail={"session_id": session.id, "transport": data.transport},
    )
    db.commit()
    return V2SessionResponse(
        session_id=session.id,
        transport=data.transport,
        status=session.status,
    )


class V2SaveRequest(BaseModel):
    flow: dict  # Validated against RecordedFlow inside the handler.
    repo_id: int
    path: str


class V2SaveResponse(BaseModel):
    saved_path: str
    bytes_written: int


@router.post(
    "/recordings/save",
    response_model=V2SaveResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/minute")
def v2_save_flow(
    request: Request,
    data: V2SaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Story W.6 — serialise a RecordedFlow to `.robot` in the target repo.

    Effective-role check is inline for the same body-vs-path reason as
    the session-create endpoint. Path validation blocks `..` escape and
    absolute paths — the flow lands strictly under `<repo local_path>/<path>`.
    """
    import os
    from pathlib import Path

    from src.recording.robot_emit import emit_robot
    from src.recording.selector_schema import (
        RecordedFlow,
        validate_schema_version,
    )

    repo = db.get(Repository, data.repo_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
        )
    if getattr(current_user, "_auth_via_api_token", False):
        role_level = ROLE_HIERARCHY.get(Role(current_user.role), -1)
    else:
        er = effective_role(db, current_user, repo)
        role_level = ROLE_HIERARCHY.get(er, -1)
    if role_level < ROLE_HIERARCHY.get(Role.EDITOR, 999):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERR_INSUFFICIENT_PERMISSIONS,
        )

    # Validate flow JSON against the v2 schema before touching disk.
    try:
        validate_schema_version(data.flow)
        parsed = RecordedFlow.model_validate(data.flow)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid flow shape") from exc

    # Path-traversal guard: reject absolute paths, `..` segments, and
    # anything that resolves outside the repo's local_path tree.
    repo_root = Path(repo.local_path).resolve()
    if not repo_root.exists():
        raise HTTPException(
            status_code=500,
            detail="Repository filesystem path missing — server misconfiguration",
        )
    raw_path = data.path.strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="path must not be empty")
    if raw_path.startswith("/") or raw_path.startswith("\\") or ".." in Path(raw_path).parts:
        raise HTTPException(status_code=400, detail="path must be a repo-relative subpath")
    target = (repo_root / raw_path).resolve()
    try:
        target.relative_to(repo_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="path resolves outside the repository")

    # Auto-suffix .robot if missing for a smoother UX.
    if target.suffix != ".robot":
        target = target.with_suffix(".robot")

    target.parent.mkdir(parents=True, exist_ok=True)

    content = emit_robot(parsed)
    blob = content.encode("utf-8")
    target.write_bytes(blob)

    log_event(
        db,
        AuditEventType.RECORDING_FLOW_SAVED,
        user_id=current_user.id,
        resource_id=repo.id,
        detail={
            "session_id": parsed.session_id,
            "path": str(target.relative_to(repo_root)),
            "command_count": len(parsed.commands),
            "bytes": len(blob),
        },
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return V2SaveResponse(
        saved_path=str(target.relative_to(repo_root)),
        bytes_written=len(blob),
    )


class V2StartBrowserRequest(BaseModel):
    target_url: str | None = None
    # Optional per-call transport override. When omitted we dispatch the
    # web recorder (backward-compatible with all existing callers). The
    # desktop transport spawns a different background task; see D.1.
    transport: RecordingTransport | None = None


class V2StartBrowserResponse(BaseModel):
    session_id: int
    task_id: str | None  # None if the browser wasn't actually launched (disabled)


@router.post(
    "/recordings/sessions/{session_id}/start-browser",
    response_model=V2StartBrowserResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def v2_start_browser(
    session_id: int,
    data: V2StartBrowserRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Story W.1 full — launch the controlled Chromium for this session.

    Explicit opt-in endpoint (not part of session create) so unit tests
    and air-gapped environments never open a browser. The frontend
    launcher calls this straight after receiving the session id.
    """
    import os

    session = db.get(RecordingSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.triggered_by != current_user.id and current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only the session owner or an admin can start the browser",
        )
    if session.status != RecordingStatus.RECORDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start browser in '{session.status}' status",
        )

    # Env-var kill switch for deployments that don't ship Chromium
    # (the Windows offline ZIP currently does not).
    if os.environ.get("ROBOSCOPE_RECORDER_DISABLED", "").lower() in ("1", "true"):
        return V2StartBrowserResponse(session_id=session_id, task_id=None)

    target_url = (data.target_url if data else None) or None
    transport: RecordingTransport = (data.transport if data else None) or "web_playwright"

    # Transport dispatch (D.1 AC): the Windows desktop recorder lives on
    # its own thread-entry; macOS was NO-GO per the DM.1 feasibility
    # spike; the chrome_extension transport is not a v2 Playwright-based
    # session. Non-Windows hosts asking for desktop_windows get a 501 so
    # the UI can surface a "this host cannot record desktop flows"
    # message instead of silently FAILing the session row.
    import sys as _sys
    if transport == "desktop_windows":
        if not _sys.platform.startswith("win"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Desktop (Windows) recording requires a Windows host.",
            )
        try:
            from src.recording.desktop_recorder_task import run_desktop_recorder_session
            result = dispatch_task(run_desktop_recorder_session, session_id)
            task_id = result.id
        except TaskDispatchError as exc:
            logger.error(
                "desktop recorder dispatch failed for session %d: %s", session_id, exc
            )
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return V2StartBrowserResponse(session_id=session_id, task_id=task_id)
    if transport == "desktop_macos":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Desktop (macOS) recording is not implemented in v2 (DM.1 NO-GO).",
        )
    if transport == "chrome_extension":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="chrome_extension sessions do not use /start-browser.",
        )

    try:
        from src.recording.v2_recorder_task import run_v2_recorder_session
        result = dispatch_task(run_v2_recorder_session, session_id, target_url)
        task_id = result.id
    except TaskDispatchError as exc:
        logger.error("v2 recorder dispatch failed for session %d: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return V2StartBrowserResponse(session_id=session_id, task_id=task_id)


@router.delete(
    "/recordings/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def v2_abort_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Abort an active v2 recording session."""
    session = db.get(RecordingSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.triggered_by != current_user.id and current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only the session owner or an admin can abort",
        )
    if session.status != RecordingStatus.RECORDING:
        # Already terminal — idempotent.
        return
    session.status = RecordingStatus.CANCELLED
    session.finished_at = datetime.now(timezone.utc)
    # Story W.2 — tell any live SSE subscriber to close cleanly.
    from src.recording.desktop_recorder_task import signal_stop_desktop
    from src.recording.v2_command_queue import finalize_session, tear_down_session
    from src.recording.v2_recorder_task import signal_stop_v2
    # Story W.1 full / D.1 — signal whichever task owns this session to
    # tear down its backend (Chromium or UIA). The other registry is a
    # no-op when the session isn't registered, so calling both is safe
    # regardless of transport.
    signal_stop_v2(session.id)
    signal_stop_desktop(session.id)
    finalize_session(session.id)
    tear_down_session(session.id)
    log_event(
        db,
        AuditEventType.RECORDING_SESSION_ABORTED,
        user_id=current_user.id,
        resource_id=session.repository_id,
        detail={"session_id": session.id, "reason": "user_abort"},
    )
    db.commit()


# ---------------------------------------------------------------------------
# Recorder v2 — Story W.2: SSE command stream
# ---------------------------------------------------------------------------

import json as _json


@router.get("/recordings/sessions/{session_id}/commands")
def v2_command_stream(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    token: str | None = Query(None),
):
    """Story W.2 — single-subscriber SSE stream of RecordedCommand events.

    Returns text/event-stream. Events are `event: command` with the
    RecordedCommand JSON as `data`. Stream terminates when the session
    finalizes (end sentinel) OR the session row transitions to a
    terminal status out-of-band.

    Auth: EventSource cannot set Authorization headers, so this endpoint
    ALSO accepts a `?token=<jwt>` query param (same pattern as the
    existing WebSocket notifications endpoint). Bearer header is still
    honoured for programmatic clients.

    Single-subscriber per AR-3 — a second concurrent GET returns 409.
    """
    from fastapi.responses import StreamingResponse
    from src.auth.service import decode_token, get_user_by_id
    from src.recording.v2_command_queue import iterate_commands

    # Resolve current user: Authorization header wins, ?token= falls back.
    # Duplicates a little logic from get_current_user because EventSource
    # has no way to send custom headers and we can't bolt a query-param
    # path onto the shared Depends() without changing every endpoint.
    raw_token: str | None = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        raw_token = auth_header[len("Bearer "):]
    elif token:
        raw_token = token
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing credentials")
    try:
        payload = decode_token(raw_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token")
    user = get_user_by_id(db, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive user")
    current_user = user

    session = db.get(RecordingSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if (
        session.triggered_by != current_user.id
        and current_user.role != Role.ADMIN
    ):
        raise HTTPException(
            status_code=403,
            detail="Only the session owner or an admin can subscribe",
        )

    def event_gen():
        for cmd in iterate_commands(session_id, poll_timeout_s=0.5):
            payload = _json.dumps(cmd.model_dump(mode="json"), default=str)
            yield f"event: command\ndata: {payload}\n\n"
        # End of stream — SSE clients close on connection end; emit a
        # final explicit `event: end` so the browser-side EventSource
        # handler can distinguish "done" from "network blip".
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # nginx: disable response buffering
        },
    )
