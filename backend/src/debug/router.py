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
from src.debug.prereq import (
    ROBOTCODE_PACKAGE,
    PrereqInstallFailed,
    check_robotcode_available,
    install_robotcode,
)
from src.debug.schemas import (
    DebugSessionStartResponse,
    DebugSessionState,
    InstallPrereqRequest,
    InstallPrereqResponse,
    StartDebugSessionRequest,
)
from src.debug.session_manager import DuplicateDebugSessionError, session_manager
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


def _resolve_env(db: Session, repo: Repository, run: ExecutionRun | None) -> Environment:
    """Return the project's environment for run + repo, with 422 fallbacks.

    Falls back to the repo's default environment when ``run`` is ``None``
    or doesn't pin one. 422 when there is no usable env at all.
    """
    env_id = (run.environment_id if run else None) or repo.environment_id
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
    return env


def _ensure_robotcode_or_424(env: Environment, repo: Repository) -> None:
    """DEBUG-4: bail before spawn if RobotCode isn't installed.

    The frontend catches the 424 and offers a one-click install via
    ``POST /sessions/install-prerequisites``.
    """
    if check_robotcode_available(env.venv_path):
        return
    raise HTTPException(
        status_code=424,
        detail={
            "code": "robotcode_not_installed",
            "message": "RobotCode is not installed in this project's environment",
            "repo_id": repo.id,
            "env_id": env.id,
            "package": ROBOTCODE_PACKAGE,
        },
    )


def _resolve_failing_location(run: ExecutionRun) -> FailingKeywordLocation | None:
    """Walk the run's `output.xml` for the first failing keyword.

    Returns ``None`` when the file is missing (e.g. early-failure runs).
    """
    if not run.output_dir:
        return None
    output_xml = Path(run.output_dir) / "output.xml"
    return find_first_failing_keyword(output_xml)


def _validate_step_invocation(
    repo: Repository,
    file_relative: str,
    test_name: str,
    line: int,
) -> str:
    """DEBUG-3 input validation.

    Returns the absolute path to the file. Raises 422 on any
    semantic violation:

    * file does not exist on disk under the repo
    * test_name is not present in the file
    * line is not inside the named test (or equals the test-case
      header line — RF won't break on a test-name row).
    """
    abs_path = (
        file_relative
        if os.path.isabs(file_relative)
        else str(Path(repo.local_path) / file_relative)
    )
    file_path = Path(abs_path)
    # Guard against path-traversal: the resolved file must live under
    # repo.local_path. Without this, a payload like "../../etc/passwd"
    # would route through the debug-launch path. ``resolve()`` follows
    # symlinks, but the repo root itself is administrator-controlled
    # so this is a reasonable boundary.
    try:
        repo_root = Path(repo.local_path).resolve()
        # M1: containment via relative_to, not startswith — a string prefix
        # check lets a sibling dir (/data/repo-secrets vs /data/repo) pass.
        try:
            file_path.resolve().relative_to(repo_root)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="File is not inside the repository",
            ) from None
    except OSError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Could not resolve repository root: {e}",
        ) from e

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=422,
            detail=f"Robot file does not exist on disk: {file_relative}",
        )
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Could not read robot file: {e}",
        ) from e

    # Walk the file: locate the named test, capture its header + body
    # range, then validate the requested line.
    lines = text.splitlines()
    in_tests = False
    test_header_line: int | None = None
    test_body_end: int | None = None  # inclusive last-body line
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("***"):
            if "Test Cases" in stripped or "Tasks" in stripped:
                in_tests = True
                continue
            else:
                # Hit another section: if we were inside `our` test
                # we've now passed its body.
                if test_header_line is not None and test_body_end is None:
                    test_body_end = idx - 1
                in_tests = False
                continue
        if not in_tests:
            continue
        # Test-case-name row: column-0 non-empty.
        if raw and not raw.startswith((" ", "\t")) and stripped:
            if test_header_line is not None and test_body_end is None:
                # Hit the next test name → previous test ended.
                test_body_end = idx - 1
            if stripped == test_name:
                test_header_line = idx

    if test_header_line is not None and test_body_end is None:
        # File ended while in our test → body extends to last line.
        test_body_end = len(lines)

    if test_header_line is None:
        raise HTTPException(
            status_code=422,
            detail=f"Test case '{test_name}' not found in {file_relative}",
        )

    # AC4: reject the test-case header line itself; RF won't break there.
    if line == test_header_line:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Line {line} is the test-case header for '{test_name}' — "
                "Robot Framework only stops on executable keyword lines"
            ),
        )

    if line < test_header_line or (test_body_end is not None and line > test_body_end):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Line {line} is not inside test case '{test_name}' "
                f"(test runs from line {test_header_line + 1} to "
                f"{test_body_end if test_body_end is not None else 'end-of-file'})"
            ),
        )

    return abs_path


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
    """Spawn a debug session.

    Two invocation shapes (validated by ``StartDebugSessionRequest``):

    * **DEBUG-2** — ``{run_id}``: re-run a failed run, breakpoint
      pulled from ``output.xml``.
    * **DEBUG-3** — ``{file, test_name, line, repo_id}``: run up to a
      step the user clicked in the Flow Editor.

    Dedup (AC6, both shapes):

    * Run-shape dedup by ``(user_id, run_id)`` — second start returns
      the existing session id with HTTP 409.
    * Step-shape dedup by ``(user_id, repo_id, file, line)`` — same
      file+line click while a session is paused there returns 409 with
      the same payload so the frontend can silently reconnect.
    """
    if payload.is_step_shape:
        return await _start_from_step(payload, request, user, db)
    return await _start_from_run(payload, request, user, db)


async def _start_from_run(
    payload: StartDebugSessionRequest,
    request: Request,
    user: User,
    db: Session,
) -> DebugSessionStartResponse:
    """DEBUG-2 entry point — locate breakpoint via ``output.xml``."""
    assert payload.run_id is not None  # validator guarantees this
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

    env = _resolve_env(db, repo, run)
    _ensure_robotcode_or_424(env, repo)
    env_python = get_python_path(env.venv_path)

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
            "source": "run",
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
    except DuplicateDebugSessionError:
        # H4: a concurrent start won the race — return the same 409 as the
        # find_by_user_run pre-check above, no second subprocess spawned.
        existing = session_manager.find_by_user_run(user.id, run.id)
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A debug session for this run already exists",
                "session_id": existing.session_id if existing else None,
                "robot_file": existing.robot_file if existing else None,
                "breakpoint_line": existing.breakpoint_line if existing else None,
                "test_name": existing.test_name if existing else None,
            },
        ) from None
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


async def _start_from_step(
    payload: StartDebugSessionRequest,
    request: Request,
    user: User,
    db: Session,
) -> DebugSessionStartResponse:
    """DEBUG-3 entry point — Flow Editor "run up to selection".

    Validates the file/test_name/line semantics inline (422s are
    user-friendly), dedups on (user_id, repo_id, file, line) so a
    second click at the same step silently reconnects.
    """
    assert payload.file is not None
    assert payload.test_name is not None
    assert payload.line is not None
    assert payload.repo_id is not None

    repo = db.get(Repository, payload.repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    _ensure_runner(db, user, repo)

    # File / test / line validation (422s with descriptive detail).
    robot_file_abs = _validate_step_invocation(
        repo=repo,
        file_relative=payload.file,
        test_name=payload.test_name,
        line=payload.line,
    )

    # Dedup at file+line scope — clicking the same step twice silently
    # reconnects. A different step in the same file is NOT a dedup
    # match here; the frontend handles that via a confirm-modal that
    # stops the current session before issuing a new POST.
    existing = session_manager.find_by_user_step(
        user_id=user.id,
        repo_id=repo.id,
        robot_file=robot_file_abs,
        breakpoint_line=payload.line,
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A debug session for this step already exists",
                "session_id": existing.session_id,
                "robot_file": existing.robot_file,
                "breakpoint_line": existing.breakpoint_line,
                "test_name": existing.test_name,
            },
        )

    # The Flow-Editor path needs an environment too. Take the repo's
    # default env (the form has no per-run override yet).
    env = _resolve_env(db, repo, None)
    _ensure_robotcode_or_424(env, repo)
    env_python = get_python_path(env.venv_path)

    log_event(
        db,
        AuditEventType.DEBUG_SESSION_STARTED,
        user_id=user.id,
        username=user.username if hasattr(user, "username") else None,
        resource_id=repo.id,
        detail={
            "run_id": None,
            "repo_id": repo.id,
            "file": _make_repo_relative(repo.local_path, robot_file_abs),
            "line": payload.line,
            "test_name": payload.test_name,
            "source": "flow_editor",
        },
        ip_address=get_client_ip(request),
    )
    db.commit()

    try:
        record = await session_manager.start(
            user_id=user.id,
            run_id=None,
            repo_id=repo.id,
            robot_file=robot_file_abs,
            breakpoint_line=payload.line,
            test_name=payload.test_name,
            env_python_path=env_python,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("debug session start failed (step shape)")
        raise HTTPException(
            status_code=502,
            detail=f"Could not start debug session: {e}",
        ) from e

    return DebugSessionStartResponse(
        session_id=record.session_id,
        robot_file=_make_repo_relative(repo.local_path, robot_file_abs),
        breakpoint_line=payload.line,
        test_name=payload.test_name,
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


# ---------------------------------------------------------------------------
# DEBUG-4: Prerequisite install endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/sessions/install-prerequisites",
    response_model=InstallPrereqResponse,
)
async def install_prerequisites(
    payload: InstallPrereqRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InstallPrereqResponse:
    """Install RobotCode into the repository's project environment.

    Triggered by the frontend dialog after a 424 from ``POST /sessions``.
    Idempotent: if RobotCode is already there, returns
    ``already_installed: true`` without rerunning ``uv pip install``.
    Audited on success only.
    """
    repo = db.get(Repository, payload.repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    _ensure_runner(db, user, repo)

    env = _resolve_env(db, repo, None)
    if check_robotcode_available(env.venv_path):
        return InstallPrereqResponse(already_installed=True, log_tail=None)

    try:
        log_tail = await install_robotcode(env.venv_path)
    except PrereqInstallFailed as e:
        logger.warning("robotcode install failed for repo %s: %s", repo.id, e)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "robotcode_install_failed",
                "message": str(e),
            },
        ) from e

    log_event(
        db,
        AuditEventType.DEBUG_ROBOTCODE_INSTALLED,
        user_id=user.id,
        username=getattr(user, "username", None),
        resource_id=repo.id,
        detail={
            "repo_id": repo.id,
            "env_id": env.id,
            "package": ROBOTCODE_PACKAGE,
        },
        ip_address=get_client_ip(request),
    )
    db.commit()

    return InstallPrereqResponse(already_installed=False, log_tail=log_tail)
