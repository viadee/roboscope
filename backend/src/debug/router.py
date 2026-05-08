"""DEBUG-2: HTTP API for the interactive Robot Framework debug session.

Endpoints (mounted at ``/api/v1/debug``):

* ``POST /sessions``                    — start a session, return its id
* ``POST /sessions/{id}/continue``      — DAP continue
* ``POST /sessions/{id}/next``          — DAP step-over
* ``POST /sessions/{id}/stepIn``        — DAP step-in
* ``POST /sessions/{id}/stepOut``       — DAP step-out
* ``POST /sessions/{id}/disconnect``    — DAP disconnect (idempotent)
* ``GET  /sessions/{id}/state``         — current state snapshot

All gated on RUNNER+ effective role for the run's repository, plus
session-ownership for the per-session endpoints.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from src.audit.event_types import AuditEventType
from src.audit.service import log_event
from src.auth.client_ip import get_client_ip
from src.auth.constants import ROLE_HIERARCHY, Role
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.auth.permissions import effective_role
from src.database import get_db
from src.debug.output_xml_walker import (
    FailingKeywordLocation,
    find_first_failing_keyword,
)
from src.debug.schemas import (
    DebugSessionStartResponse,
    DebugSessionState,
    StartDebugSessionRequest,
)
from src.debug.session_manager import session_manager
from src.environments.models import Environment
from src.environments.venv_utils import get_python_path
from src.execution.models import ExecutionRun
from src.repos.models import Repository

logger = logging.getLogger("roboscope.debug.router")

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_runner(db: Session, user: User, repo: Repository) -> None:
    """Raise 403 unless ``user`` has RUNNER+ effective role on ``repo``.

    API tokens stay capped at their scoped role (see auth/dependencies
    rationale). For DEBUG-2 — a long-lived interactive session that
    can spawn arbitrary Playwright/Chromium subprocesses — we do not
    want token-driven CI pipelines to be able to start sessions; gate
    on the underlying role only.
    """
    if getattr(user, "_auth_via_api_token", False):
        user_level = ROLE_HIERARCHY.get(Role(user.role), -1)
        if user_level < ROLE_HIERARCHY.get(Role.RUNNER, 999):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return
    er = effective_role(db, user, repo)
    if ROLE_HIERARCHY.get(er, -1) < ROLE_HIERARCHY.get(Role.RUNNER, 999):
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def _resolve_env_python(db: Session, repo: Repository, run: ExecutionRun) -> str:
    """Return the python executable for the run's project environment.

    Falls back to the repo's default environment when the run doesn't
    pin one. 422 if there is no usable env (the test obviously needs
    a Python to run in).
    """
    env_id = run.environment_id or repo.environment_id
    if env_id is None:
        raise HTTPException(
            status_code=422,
            detail="No environment configured for this run/repository — "
            "debug needs a Python environment",
        )
    env = db.get(Environment, env_id)
    if env is None or not env.venv_path:
        raise HTTPException(
            status_code=422,
            detail="Project environment has no venv yet — install packages first",
        )
    return get_python_path(env.venv_path)


def _resolve_failing_location(run: ExecutionRun) -> FailingKeywordLocation | None:
    """Walk the run's `output.xml` for the first failing keyword.

    Returns ``None`` when the file is missing (e.g. early-failure runs).
    """
    if not run.output_dir:
        return None
    output_xml = Path(run.output_dir) / "output.xml"
    return find_first_failing_keyword(output_xml)


def _fallback_first_executable_line(robot_file: str) -> int:
    """When ``output.xml`` doesn't carry a keyword line, point the
    breakpoint at the first non-blank, non-comment line under the
    first ``*** Test Cases ***`` block.

    Cheap text scan — the editor parses the same file with a real
    parser, but a debug-launch only needs *some* line inside the
    target test for the user to land near the failure.
    """
    try:
        text = Path(robot_file).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 1
    lines = text.splitlines()
    in_tests = False
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("***") and "Test Cases" in stripped:
            in_tests = True
            continue
        if not in_tests:
            continue
        if stripped.startswith("***") and "Test Cases" not in stripped:
            # Hit the next section header without finding any executable
            # line — give up and point at the section header.
            return idx
        if not stripped or stripped.startswith("#"):
            continue
        # Skip the test name (no leading whitespace) — we want the
        # first indented body line.
        if not raw.startswith((" ", "\t")):
            continue
        return idx
    return 1


# ---------------------------------------------------------------------------
# POST /sessions — start
# ---------------------------------------------------------------------------


@router.post(
    "/sessions",
    response_model=DebugSessionStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_session(
    payload: StartDebugSessionRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DebugSessionStartResponse:
    """Spawn a debug session for a previously-failed run.

    AC2 + AC6: dedup on ``(user_id, run_id)`` returns the existing
    session id with HTTP 409 so the user can reconnect instead of
    spawning a redundant subprocess.
    """
    run = db.get(ExecutionRun, payload.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    repo = db.get(Repository, run.repository_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    _ensure_runner(db, user, repo)

    # Dedup BEFORE we audit: returning the existing session means the
    # user is reconnecting, not starting a new one. We already audited
    # the original START.
    existing = session_manager.find_by_user_run(user.id, payload.run_id)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A debug session for this run already exists",
                "session_id": existing.session_id,
                "robot_file": existing.robot_file,
                "breakpoint_line": existing.breakpoint_line,
                "test_name": existing.test_name,
            },
        )

    # Resolve where the breakpoint goes.
    location = _resolve_failing_location(run)
    if location is not None:
        # AC2 wants repo-relative paths in audit/UX; absolute path goes
        # to RobotDebugSession (RF needs absolute for setBreakpoints).
        robot_file_abs = location.source
        if not os.path.isabs(robot_file_abs):
            robot_file_abs = str(Path(repo.local_path) / robot_file_abs)
        bp_line = location.line
        test_name: str | None = location.test_name
    else:
        # Fall back to the run's target file + first executable line.
        target = run.target_path or ""
        robot_file_abs = (
            target if os.path.isabs(target) else str(Path(repo.local_path) / target)
        )
        bp_line = _fallback_first_executable_line(robot_file_abs)
        test_name = None

    if not Path(robot_file_abs).exists():
        raise HTTPException(
            status_code=422,
            detail=f"Robot file does not exist on disk: {robot_file_abs}",
        )

    env_python = _resolve_env_python(db, repo, run)

    # Audit BEFORE the spawn — if spawn fails the audit still records
    # that the user attempted to start a session, which matches the
    # canonical RUN_* audit pattern (we audit intent, not outcome).
    log_event(
        db,
        AuditEventType.DEBUG_SESSION_STARTED,
        user_id=user.id,
        username=user.username if hasattr(user, "username") else None,
        resource_id=run.id,
        detail={
            "run_id": run.id,
            "repo_id": repo.id,
            "file": _make_repo_relative(repo.local_path, robot_file_abs),
            "line": bp_line,
            "test_name": test_name,
        },
        ip_address=get_client_ip(request),
    )
    db.commit()

    try:
        record = await session_manager.start(
            user_id=user.id,
            run_id=run.id,
            repo_id=repo.id,
            robot_file=robot_file_abs,
            breakpoint_line=bp_line,
            test_name=test_name,
            env_python_path=env_python,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("debug session start failed")
        raise HTTPException(
            status_code=502,
            detail=f"Could not start debug session: {e}",
        ) from e

    return DebugSessionStartResponse(
        session_id=record.session_id,
        robot_file=_make_repo_relative(repo.local_path, robot_file_abs),
        breakpoint_line=bp_line,
        test_name=test_name,
    )


def _make_repo_relative(repo_path: str, abs_path: str) -> str:
    try:
        return str(Path(abs_path).relative_to(repo_path))
    except ValueError:
        return abs_path


# ---------------------------------------------------------------------------
# Session-scoped helpers
# ---------------------------------------------------------------------------


def _get_owned_session(
    session_id: str, user: User, db: Session
) -> Any:
    rec = session_manager.get(session_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Debug session not found")
    if rec.user_id != user.id:
        # Session-ownership gate — even ADMIN can't drive someone
        # else's paused subprocess, that's a confusing UX.
        raise HTTPException(status_code=403, detail="Not your debug session")
    return rec


# ---------------------------------------------------------------------------
# Control endpoints
# ---------------------------------------------------------------------------


def _control_endpoint(method_name: str) -> Any:
    """Factory for the four step-control endpoints."""

    async def handler(
        session_id: str,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Response:
        rec = _get_owned_session(session_id, user, db)
        method = getattr(rec.session, method_name)
        await method()
        await session_manager.touch(session_id)
        return Response(status_code=204)

    return handler


router.add_api_route(
    "/sessions/{session_id}/continue",
    _control_endpoint("continue_"),
    methods=["POST"],
    status_code=204,
)
router.add_api_route(
    "/sessions/{session_id}/next",
    _control_endpoint("next_"),
    methods=["POST"],
    status_code=204,
)
router.add_api_route(
    "/sessions/{session_id}/stepIn",
    _control_endpoint("step_in"),
    methods=["POST"],
    status_code=204,
)
router.add_api_route(
    "/sessions/{session_id}/stepOut",
    _control_endpoint("step_out"),
    methods=["POST"],
    status_code=204,
)


@router.post("/sessions/{session_id}/disconnect", status_code=204)
async def disconnect(
    session_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Idempotent disconnect — always returns 204 even if the session
    no longer exists (e.g. tab was closed twice in a row, or the
    DAP terminated event already cleaned it up)."""
    rec = session_manager.get(session_id)
    if rec is None:
        return Response(status_code=204)
    if rec.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your debug session")

    log_event(
        db,
        AuditEventType.DEBUG_SESSION_ENDED,
        user_id=user.id,
        username=getattr(user, "username", None),
        resource_id=rec.run_id,
        detail={
            "run_id": rec.run_id,
            "session_id": rec.session_id,
            "ended_by": "user",
        },
        ip_address=get_client_ip(request),
    )
    db.commit()
    await session_manager.stop(session_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# State endpoint
# ---------------------------------------------------------------------------


@router.get("/sessions/{session_id}/state", response_model=DebugSessionState)
async def get_state(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DebugSessionState:
    """Return the cached state snapshot. Refreshed on every DAP
    `stopped` event by the manager — this endpoint never triggers
    its own DAP roundtrip, so it stays cheap on rapid polling."""
    rec = _get_owned_session(session_id, user, db)
    if rec.state_cache is not None:
        # Patch the session_id (state_fetcher leaves it blank).
        snap: DebugSessionState = rec.state_cache.model_copy(
            update={"session_id": session_id}
        )
        return snap
    return DebugSessionState(session_id=session_id)
