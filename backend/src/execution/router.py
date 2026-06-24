"""Execution API endpoints: runs and schedules."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import (
    get_current_user,
    require_effective_role_for_run,
    require_role,
)
from src.auth.models import User
from src.governance.dependencies import require_feature
from src.database import get_db
from src.rate_limit import limiter
from src.task_executor import TaskDispatchError, dispatch_task
from src.execution.models import RunStatus
from pydantic import BaseModel

from src.execution.schemas import (
    RunCreate,
    RunListResponse,
    RunResponse,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
)
from src.environments.models import Environment
from src.execution.models import ExecutionRun, RunnerType
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
@limiter.limit("20/minute")
def start_run(
    request: Request,
    data: RunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Start a new test execution run."""
    # EXEC.3/EXEC.10: gate + validate + audit advanced execution config before
    # anything else. No-op unless advanced_config carries levers. The repo's
    # local path is passed so file-based levers (--pythonpath/--variablefile) are
    # repo-confined at request time (422 on escape), not only at execution.
    from src.governance.dependencies import gate_advanced_execution
    from src.repos.models import Repository

    repo_root = None
    if data.advanced_config:
        repo = db.execute(
            select(Repository).where(Repository.id == data.repository_id)
        ).scalar_one_or_none()
        repo_root = repo.local_path if repo else None
    gate_advanced_execution(db, request, current_user, data.advanced_config, repo_root)

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
        db.commit()
        db.refresh(run)
    except TaskDispatchError as e:
        logger.error("Failed to dispatch run %d: %s", run.id, e)
        # H3: commit the terminal ERROR state explicitly. The run was already
        # committed as PENDING above; a flush-only here left it stranded in
        # PENDING (no PENDING-reaper exists) if request teardown didn't commit.
        run.status = RunStatus.ERROR
        run.error_message = f"Task dispatch failed: {e}"
        db.commit()
        db.refresh(run)

    return run


@router.get("/modifiers")
def list_modifiers(
    kind: str | None = Query(default=None),
    _current_user: User = Depends(get_current_user),
    _feature: None = Depends(require_feature("executionAdvancedArgs")),
):
    """EXEC.10: curated execution modifiers (vendor + org) for the run-dialog
    picker. Gated behind ``executionAdvancedArgs`` (no point enumerating org
    modifiers — or triggering the registry import — when the feature is off).
    Returns public entries only (no internal class paths); ``kind`` filters to
    ``prerun`` / ``prerebot``."""
    from src.execution.modifiers import get_available_modifiers

    return [e.public_dict() for e in get_available_modifiers(kind)]


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


# --- Pending-run activity (Story EXEC-1) ---


class PendingBuildInfo(BaseModel):
    environment_id: int
    environment_name: str
    status: str | None
    log_tail: str


class PendingActivityResponse(BaseModel):
    status: str
    queue_position: int | None
    ahead_count: int
    active_build: PendingBuildInfo | None
    effective_runner_type: str | None


# Only the trailing slice of a (potentially multi-MB) build log is shipped
# to the browser. The full log stays available on the Environments view.
_BUILD_LOG_TAIL_CHARS = 6_000


@router.get("/runs/{run_id}/pending-activity", response_model=PendingActivityResponse)
def get_run_pending_activity(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> PendingActivityResponse:
    """Tell the caller *why* a pending run has not started yet.

    - How many earlier runs are still ahead of it in the single-worker
      queue (``ahead_count`` / ``queue_position``).
    - Whether the run's environment is currently building a Docker image
      (``active_build``), and if so, the tail of the live build log so
      the detail panel can render it inline without a separate request.

    Emits the full response on any run state (pending / running /
    terminal); the frontend relies on ``status`` to decide whether to
    render the pending box at all. Returning the shape universally keeps
    the polling contract simple (the consumer can stop polling the
    moment it sees a non-pending status).
    """
    run = db.get(ExecutionRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )

    # Queue position — only meaningful while pending. Runs created before
    # this one that are still in pending / running contend for the single
    # executor slot. We count the running one too so "queued behind 1"
    # correctly describes the common "one running, this one next" state.
    ahead_count = 0
    queue_position: int | None = None
    if run.status == RunStatus.PENDING:
        ahead_count = (
            db.query(ExecutionRun)
            .filter(
                ExecutionRun.id != run.id,
                ExecutionRun.status.in_([RunStatus.PENDING, RunStatus.RUNNING]),
                ExecutionRun.created_at < run.created_at,
            )
            .count()
        )
        queue_position = ahead_count + 1

    # Effective runner type mirrors the fallback logic in
    # execute_test_run: a run created with subprocess inherits docker if
    # the bound environment's default is docker.
    effective_runner_type: str | None = run.runner_type
    env: Environment | None = (
        db.get(Environment, run.environment_id) if run.environment_id else None
    )
    if env is not None and env.default_runner_type == RunnerType.DOCKER and run.runner_type == RunnerType.SUBPROCESS:
        effective_runner_type = RunnerType.DOCKER

    # Active build detection — any env row whose `docker_build_status`
    # is currently "building" qualifies. `docker_build_log` is the
    # consolidated log the env's build task appends to.
    active_build: PendingBuildInfo | None = None
    if env is not None and env.docker_build_status == "building":
        full_log = env.docker_build_log or ""
        active_build = PendingBuildInfo(
            environment_id=env.id,
            environment_name=env.name,
            status=env.docker_build_status,
            log_tail=full_log[-_BUILD_LOG_TAIL_CHARS:],
        )

    return PendingActivityResponse(
        status=run.status,
        queue_position=queue_position,
        ahead_count=ahead_count,
        active_build=active_build,
        effective_runner_type=effective_runner_type,
    )


# --- Selector-health diagnosis (Story SH-1) ---


class SelectorCandidateSnippet(BaseModel):
    strategy: str
    value: str
    quality_score: float | None = None


class SelectorHealthHit(BaseModel):
    raw_locator: str
    candidates: list[SelectorCandidateSnippet]


class SelectorHealthResponse(BaseModel):
    has_sidecar: bool
    sidecar_path: str | None
    failed_locators: list[SelectorHealthHit]


# Robot / Browser / Playwright "element not found" / "timeout on locator"
# signatures we recognise. Deliberately permissive — one-shot patterns,
# not a full log parser. Falls back to empty list on anything we don't
# understand rather than hallucinating.
_LOCATOR_FAILURE_PATTERNS: tuple[str, ...] = (
    # Robot Framework `Element '<locator>' not found`
    r"Element\s+'([^']+)'\s+(?:not\s+found|did\s+not\s+appear)",
    # Browser library `locator('<locator>').click: Timeout`
    r"locator\([\"']([^\"']+)[\"']\)\.[\w_]+:\s*Timeout",
    # Browser library `Locator '<locator>' ...`
    r"Locator\s+['\"]([^'\"]+)['\"]",
    # Playwright `TimeoutError: ... waiting for selector "<locator>"`
    r"waiting\s+for\s+selector\s+[\"']([^\"']+)[\"']",
)


def _extract_failed_locators(output_text: str) -> list[str]:
    import re as _re

    hits: list[str] = []
    seen: set[str] = set()
    for pattern in _LOCATOR_FAILURE_PATTERNS:
        for m in _re.finditer(pattern, output_text, flags=_re.IGNORECASE):
            loc = m.group(1).strip()
            if loc and loc not in seen:
                seen.add(loc)
                hits.append(loc)
    return hits


@router.get(
    "/runs/{run_id}/selector-health",
    response_model=SelectorHealthResponse,
)
def get_run_selector_health(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> SelectorHealthResponse:
    """Story SH-1 — cross-reference a run's failed selectors with the
    recording's sidecar `.rbs.json` and return the ranked alternative
    candidates for each failure.

    Returns `has_sidecar=False` when the run wasn't produced from a v2
    recording (no sidecar alongside the .robot file) or when the file
    has simply been moved — not a failure, just nothing to suggest.
    """
    import json as _json
    from pathlib import Path

    run = db.get(ExecutionRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )

    # Locate the .robot file in its repository; the sidecar sits next to it.
    from src.repos.models import Repository
    repo = db.get(Repository, run.repository_id) if run.repository_id else None
    if repo is None or not run.target_path:
        return SelectorHealthResponse(
            has_sidecar=False, sidecar_path=None, failed_locators=[]
        )
    repo_root = Path(repo.local_path).resolve()
    robot_path = (repo_root / run.target_path).resolve()
    try:
        robot_path.relative_to(repo_root)
    except ValueError:
        return SelectorHealthResponse(
            has_sidecar=False, sidecar_path=None, failed_locators=[]
        )
    sidecar_path = robot_path.with_suffix(".rbs.json")
    if not sidecar_path.is_file():
        return SelectorHealthResponse(
            has_sidecar=False, sidecar_path=None, failed_locators=[]
        )

    # Load sidecar — build a locator → candidate-list index.
    try:
        flow_data = _json.loads(sidecar_path.read_text(encoding="utf-8"))
    except Exception:
        return SelectorHealthResponse(
            has_sidecar=False, sidecar_path=str(sidecar_path.relative_to(repo_root)),
            failed_locators=[],
        )
    commands = flow_data.get("commands") or []
    # Build lookup: raw candidate string (e.g. "id=submit") → full command.
    locator_to_command: dict[str, dict] = {}
    for cmd in commands:
        for cand in (cmd.get("selector_candidates") or []):
            value = cand.get("value")
            if value:
                locator_to_command.setdefault(value, cmd)

    # Pull failed locators out of the run output.
    output_text_parts: list[str] = []
    if run.output_dir:
        for name in ("stdout.log", "stderr.log", "output.xml"):
            p = Path(run.output_dir) / name
            if p.is_file():
                try:
                    output_text_parts.append(p.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
    if run.error_message:
        output_text_parts.append(run.error_message)
    combined = "\n".join(output_text_parts)
    failed_locators = _extract_failed_locators(combined)

    hits: list[SelectorHealthHit] = []
    for loc in failed_locators:
        cmd = locator_to_command.get(loc)
        if cmd is None:
            # Not a recorder-originated selector — still surface it so
            # the user sees "this failed but we can't offer alternatives".
            hits.append(SelectorHealthHit(raw_locator=loc, candidates=[]))
            continue
        cands = cmd.get("selector_candidates") or []
        active_idx = cmd.get("active_candidate_index", 0)
        # Present the other candidates ordered by quality_score desc,
        # excluding the one that was active (the one that just failed).
        others = [
            SelectorCandidateSnippet(
                strategy=c.get("strategy", ""),
                value=c.get("value", ""),
                quality_score=c.get("quality_score"),
            )
            for i, c in enumerate(cands)
            if i != active_idx
        ]
        others.sort(key=lambda c: c.quality_score or 0.0, reverse=True)
        hits.append(SelectorHealthHit(raw_locator=loc, candidates=others))

    return SelectorHealthResponse(
        has_sidecar=True,
        sidecar_path=str(sidecar_path.relative_to(repo_root)),
        failed_locators=hits,
    )


class HealAuditEntryOut(BaseModel):
    timestamp: str
    test_name: str
    keyword: str
    original_selector: str
    healed_selector: str
    confidence: float
    source: str
    outcome: str
    # RECORDER-IDMAP — id of the recorded command this heal applied
    # to (resolved by the heal library at audit-write time via
    # sidecar matching). None for legacy / no-sidecar runs.
    command_id: str | None = None


class HealReportOut(BaseModel):
    total_heals: int
    confirmed: int
    suspect: int
    entries: list[HealAuditEntryOut]


@router.get("/runs/{run_id}/heal-report", response_model=HealReportOut)
def get_run_heal_report(
    run_id: int,
    db: Session = Depends(get_db),
    # H1: gate on the user's effective role on THIS run's repo, not just any
    # authenticated user — heal data is repo-scoped (Phase-4 Team/Org model).
    _current_user: User = Depends(require_effective_role_for_run(Role.VIEWER)),
) -> HealReportOut:
    """Story SH-2 — return the structured heal report for a run.

    Reads `<output_dir>/heal_audit.jsonl` and cross-references the
    heal's `test_name` with Robot Framework's `output.xml`:
      - test passed → heal `outcome=confirmed`
      - test failed → `outcome=suspect` (heal may have swapped to the
        wrong element, which is why the downstream test failed)
      - no output.xml → `outcome=unknown`

    Returns all-zero totals for runs that have no heal audit file
    (tests without any `Heal *` keywords).
    """
    from pathlib import Path
    from RoboScopeHeal.heal_report import parse_heal_audit

    run = db.get(ExecutionRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )
    if not run.output_dir:
        return HealReportOut(total_heals=0, confirmed=0, suspect=0, entries=[])

    audit_path = Path(run.output_dir) / "heal_audit.jsonl"
    output_xml = Path(run.output_dir) / "output.xml"
    report = parse_heal_audit(
        audit_path,
        output_xml=output_xml if output_xml.is_file() else None,
    )
    return HealReportOut(
        total_heals=report.total_heals,
        confirmed=report.confirmed,
        suspect=report.suspect,
        entries=[HealAuditEntryOut(**e.to_dict()) for e in report.entries],
    )


class HealPatchApplyResponse(BaseModel):
    file_path: str
    line_number: int
    applied: bool
    reason: str | None = None


@router.post(
    "/runs/{run_id}/heal-report/{heal_index}/apply",
    response_model=HealPatchApplyResponse,
)
def apply_heal_patch(
    run_id: int,
    heal_index: int,
    request: Request,
    db: Session = Depends(get_db),
    # H1: heal-apply WRITES to .robot files in the run's repo — gate on the
    # effective EDITOR role for that repo (mirrors cancel/retry), not a global
    # role, so a global EDITOR without a grant on the repo can't write to it.
    current_user: User = Depends(require_effective_role_for_run(Role.EDITOR)),
) -> HealPatchApplyResponse:
    """Story SH-4 — write a single confirmed heal swap into the .robot.

    Safety gates (must ALL pass or the write is aborted):
      * index in bounds
      * heal outcome == "confirmed"
      * target .robot file is inside the run's repo root (path-traversal)
      * original selector appears on *exactly one* line (no guessing)

    Re-application is idempotent — if the line already carries the
    healed selector, returns 200 with `applied=false`.
    """
    import os
    import tempfile
    from pathlib import Path

    from src.audit.event_types import AuditEventType
    from src.audit.service import log_event
    from RoboScopeHeal.heal_report import parse_heal_audit
    from src.repos.models import Repository

    run = db.get(ExecutionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.output_dir:
        raise HTTPException(status_code=404, detail="Run has no output directory")

    audit_path = Path(run.output_dir) / "heal_audit.jsonl"
    output_xml = Path(run.output_dir) / "output.xml"
    report = parse_heal_audit(
        audit_path,
        output_xml=output_xml if output_xml.is_file() else None,
    )
    if not (0 <= heal_index < len(report.entries)):
        raise HTTPException(status_code=404, detail="Heal index out of bounds")
    entry = report.entries[heal_index]
    if entry.outcome != "confirmed":
        raise HTTPException(
            status_code=400,
            detail=f"Only confirmed heals can be applied (outcome={entry.outcome})",
        )

    # Resolve the target .robot file. We prefer the run's `target_path`
    # because that's the file Robot Framework actually executed; if
    # it's a directory (run-the-whole-folder case), we fall back to a
    # per-test-name match inside the directory — but only if unique.
    repo = db.get(Repository, run.repository_id) if run.repository_id else None
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    repo_root = Path(repo.local_path).resolve()
    if not repo_root.exists():
        raise HTTPException(status_code=500, detail="Repository path missing")

    target_candidates: list[Path] = []
    if run.target_path:
        tp = (repo_root / run.target_path).resolve()
        try:
            tp.relative_to(repo_root)
        except ValueError:
            raise HTTPException(status_code=400, detail="Target path escapes repo")
        if tp.is_file() and tp.suffix == ".robot":
            target_candidates = [tp]
        elif tp.is_dir():
            # Find all .robot files in the dir that contain the original
            # selector on a line with the matching keyword. Must be unique.
            target_candidates = list(tp.rglob("*.robot"))

    # RECORDER-IDMAP — recorded lines now carry a trailing
    # `    # rbs:<id>` comment. Strip it before line matching so a
    # heal apply can find lines from fresh recordings, AND preserve
    # the comment when rewriting so the FlowEditor's id-based
    # selector matcher keeps working after the patch lands.
    import re as _re_idmap
    _RBS_TAIL = _re_idmap.compile(r"(\s+# rbs:[A-Za-z0-9-]+)\s*$")
    _RBS_TAIL_ID = _re_idmap.compile(r"\s+# rbs:([A-Za-z0-9-]+)\s*$")

    def _strip_rbs(line: str) -> str:
        """Return the line without a trailing `# rbs:<id>` comment."""
        return _RBS_TAIL.sub("", line)

    def _extract_rbs_tail(line: str) -> str:
        """Return the rstripped trailing `    # rbs:<id>` slice (with
        leading whitespace) if present, else empty string. Used to
        glue the comment back onto the rewritten line."""
        m = _RBS_TAIL.search(line)
        return m.group(1) if m else ""

    def _extract_rbs_id(line: str) -> str | None:
        """Return just the id portion of a trailing `# rbs:<id>` cell."""
        m = _RBS_TAIL_ID.search(line)
        return m.group(1) if m else None

    # RECORDER-RF-ESCAPE — the on-disk line carries the RF-escaped
    # form of the selector (`\#login-form`) but the audit captures
    # the runtime-resolved value (`#login-form`, RF lexer consumes
    # the leading `\` before Browser library sees it). Build the
    # needle with the same escape applied so heals against
    # `#`-prefixed selectors actually find their line.
    from src.recording.robot_emit import _escape_rf_token
    needle_original = (
        f"    {entry.keyword}    {_escape_rf_token(entry.original_selector)}"
    )

    candidates_with_match: list[tuple[Path, int, list[str]]] = []

    # RECORDER-IDMAP step 2 — when the audit carries a `command_id`,
    # use it to disambiguate among lines that share the same
    # selector text. Without this, two consecutive `Click id=submit`
    # rows (a confirm-dialog pattern is enough to trip it) would
    # 409-ambiguous even though the id makes the target unique.
    #
    # The id phase still requires the line's selector text to match
    # `needle_original` — otherwise a user hand-edit of a recorded
    # row (different selector kept the rbs comment) would be
    # silently overwritten when the apply runs. Drifted lines fall
    # through to the selector-text path, which won't find them
    # either, and the regular 409 fires — that's the safe outcome.
    if entry.command_id:
        id_matches: list[tuple[Path, int, list[str]]] = []
        for path in target_candidates:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for i, ln in enumerate(lines):
                if _extract_rbs_id(ln) != entry.command_id:
                    continue
                if _strip_rbs(ln.rstrip()) != needle_original:
                    # ID matches but selector text doesn't — drift.
                    # Skip; the selector-text fallback will report
                    # the appropriate "missing/already-patched/etc"
                    # outcome.
                    continue
                id_matches.append((path, i, lines))
                break  # ids are unique within one file
        if len(id_matches) >= 1:
            # 1 hit → unambiguous; 2+ hits is a cross-file id
            # collision (someone copy-pasted a recording into two
            # .robot files in the same repo), which the existing
            # multi-file ambiguity guard below will reject.
            candidates_with_match = id_matches

    if not candidates_with_match:
        for path in target_candidates:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            hits = [
                i for i, ln in enumerate(lines)
                if _strip_rbs(ln.rstrip()) == needle_original
            ]
            if len(hits) == 1:
                candidates_with_match.append((path, hits[0], lines))

    if not candidates_with_match:
        # Is it already applied? Idempotent check — if exactly one file
        # already carries the healed line, report applied=false.
        needle_healed = (
            f"    {entry.keyword}    {_escape_rf_token(entry.healed_selector)}"
        )
        for path in target_candidates:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            healed_hits = [
                i for i, ln in enumerate(lines)
                if _strip_rbs(ln.rstrip()) == needle_healed
            ]
            if len(healed_hits) == 1:
                return HealPatchApplyResponse(
                    file_path=str(path.relative_to(repo_root)),
                    line_number=healed_hits[0] + 1,
                    applied=False,
                    reason="already_patched",
                )
        raise HTTPException(
            status_code=409,
            detail="Original selector line not found (ambiguous or missing) — aborting write",
        )

    if len(candidates_with_match) > 1:
        raise HTTPException(
            status_code=409,
            detail=f"Original selector line found in {len(candidates_with_match)} files — ambiguous, aborting",
        )

    target, line_idx, lines = candidates_with_match[0]
    # Preserve any `# rbs:<id>` comment from the original line so the
    # FlowEditor's id-based matcher keeps working after the patch.
    rbs_tail = _extract_rbs_tail(lines[line_idx])
    # RF-token escape — a healed `#login-form` selector would
    # otherwise be parsed as a comment by Robot Framework. (The
    # importer is hoisted near the matcher above so we share it.)
    healed_escaped = _escape_rf_token(entry.healed_selector)
    new_line = f"    {entry.keyword}    {healed_escaped}{rbs_tail}"
    lines[line_idx] = new_line
    content = "\n".join(lines)
    # Preserve trailing newline if the original file had one.
    if not content.endswith("\n"):
        content += "\n"

    # Atomic write via temp-file-and-rename so a crash mid-write leaves
    # either the old file or the new one, never a truncated hybrid.
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp",
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, str(target))
    except Exception:
        # Best-effort cleanup; re-raise the original exception.
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise

    log_event(
        db,
        AuditEventType.HEAL_PATCH_APPLIED,
        user_id=current_user.id,
        resource_id=repo.id,
        detail={
            "run_id": run.id,
            "heal_index": heal_index,
            "file_path": str(target.relative_to(repo_root)),
            "line_number": line_idx + 1,
            "keyword": entry.keyword,
            "original_selector": entry.original_selector,
            "healed_selector": entry.healed_selector,
        },
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return HealPatchApplyResponse(
        file_path=str(target.relative_to(repo_root)),
        line_number=line_idx + 1,
        applied=True,
    )


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
def cancel_run_endpoint(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_effective_role_for_run(Role.RUNNER)),
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

    # Kill active runner processes
    from src.execution.tasks import cancel_active_run
    for run in runs:
        cancel_active_run(run.id)

    logger.info("Cancelled %d runs", cancelled)
    return {"cancelled": cancelled}


@router.post("/runs/{run_id}/retry", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def retry_run_endpoint(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_effective_role_for_run(Role.RUNNER)),
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
