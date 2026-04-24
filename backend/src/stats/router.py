"""Statistics and KPI API endpoints."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from src.database import get_db
from src.rate_limit import limiter
from src.task_executor import dispatch_task
from src.stats.analysis import run_analysis
from src.stats.schemas import (
    AVAILABLE_KPIS,
    AnalysisCreate,
    AnalysisListResponse,
    AnalysisResponse,
    DurationStat,
    FlakyQuarantineCreate,
    FlakyQuarantineResponse,
    FlakyTest,
    HeatmapCell,
    OverviewKpi,
    SuccessRatePoint,
    TrendPoint,
)
from src.stats.service import (
    create_analysis,
    get_analysis,
    get_duration_stats,
    get_flaky_tests,
    get_heatmap_data,
    get_overview,
    get_success_rate_trend,
    get_trends,
    list_analyses,
)
from src.stats.tasks import aggregate_daily_kpis, get_data_status

router = APIRouter()


@router.get("/overview", response_model=OverviewKpi)
def overview(
    days: int = Query(default=30, ge=1, le=365),
    repository_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get dashboard overview KPIs."""
    return get_overview(db, repository_id, days)


@router.get("/success-rate", response_model=list[SuccessRatePoint])
def success_rate(
    days: int = Query(default=30, ge=1, le=365),
    repository_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get success rate trend over time."""
    return get_success_rate_trend(db, days, repository_id)


@router.get("/trends", response_model=list[TrendPoint])
def trends(
    days: int = Query(default=30, ge=1, le=365),
    repository_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get pass/fail/error trends over time."""
    return get_trends(db, days, repository_id)


@router.get("/flaky", response_model=list[FlakyTest])
def flaky_tests(
    days: int = Query(default=30, ge=1, le=365),
    min_runs: int = Query(default=3, ge=2),
    repository_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get flaky test analysis, with quarantine state merged in (Story FLAKY-1)."""
    return get_flaky_tests(db, days, min_runs, repository_id)


# --- Flaky-test quarantine (Story FLAKY-1) ---


@router.get("/quarantine", response_model=list[FlakyQuarantineResponse])
def list_flaky_quarantine(
    repository_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all quarantined flaky tests. Optional `repository_id` filter."""
    from src.stats.models import FlakyQuarantine
    from sqlalchemy import select

    stmt = select(FlakyQuarantine)
    if repository_id is not None:
        stmt = stmt.where(FlakyQuarantine.repository_id == repository_id)
    rows = db.execute(stmt.order_by(FlakyQuarantine.id.desc())).scalars().all()
    return [
        FlakyQuarantineResponse(
            id=r.id,
            repository_id=r.repository_id,
            suite_name=r.suite_name,
            test_name=r.test_name,
            reason=r.reason,
            quarantined_by=r.quarantined_by,
            quarantined_at=r.quarantined_at,
        )
        for r in rows
    ]


@router.post("/quarantine", response_model=FlakyQuarantineResponse, status_code=201)
def add_flaky_quarantine(
    data: FlakyQuarantineCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Mark a flaky test as quarantined. Idempotent: re-marking the same
    (repository_id, suite_name, test_name) tuple returns the existing row."""
    from datetime import datetime
    from sqlalchemy import select

    from src.audit.service import log_event
    from src.audit.event_types import AuditEventType
    from src.repos.models import Repository
    from src.stats.models import FlakyQuarantine

    repo = db.get(Repository, data.repository_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    existing = db.execute(
        select(FlakyQuarantine).where(
            FlakyQuarantine.repository_id == data.repository_id,
            FlakyQuarantine.suite_name == data.suite_name,
            FlakyQuarantine.test_name == data.test_name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return FlakyQuarantineResponse(
            id=existing.id,
            repository_id=existing.repository_id,
            suite_name=existing.suite_name,
            test_name=existing.test_name,
            reason=existing.reason,
            quarantined_by=existing.quarantined_by,
            quarantined_at=existing.quarantined_at,
        )

    row = FlakyQuarantine(
        repository_id=data.repository_id,
        suite_name=data.suite_name,
        test_name=data.test_name,
        reason=data.reason,
        quarantined_by=current_user.id,
        quarantined_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    db.refresh(row)

    try:
        log_event(
            db,
            AuditEventType.FLAKY_TEST_QUARANTINED,
            user_id=current_user.id,
            resource_id=row.repository_id,
            detail={
                "quarantine_id": row.id,
                "suite_name": row.suite_name,
                "test_name": row.test_name,
            },
            ip_address=request.client.host if request.client else None,
        )
    except AttributeError:
        # Audit event type may not be present on older DBs — safe to skip.
        pass
    db.commit()

    return FlakyQuarantineResponse(
        id=row.id,
        repository_id=row.repository_id,
        suite_name=row.suite_name,
        test_name=row.test_name,
        reason=row.reason,
        quarantined_by=row.quarantined_by,
        quarantined_at=row.quarantined_at,
    )


@router.delete("/quarantine/{quarantine_id}", status_code=204)
def remove_flaky_quarantine(
    quarantine_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Unquarantine a flaky test."""
    from src.audit.service import log_event
    from src.audit.event_types import AuditEventType
    from src.stats.models import FlakyQuarantine

    row = db.get(FlakyQuarantine, quarantine_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Quarantine entry not found")
    details = {
        "quarantine_id": row.id,
        "suite_name": row.suite_name,
        "test_name": row.test_name,
    }
    repo_id = row.repository_id
    db.delete(row)

    try:
        log_event(
            db,
            AuditEventType.FLAKY_TEST_UNQUARANTINED,
            user_id=current_user.id,
            resource_id=repo_id,
            detail=details,
            ip_address=request.client.host if request.client else None,
        )
    except AttributeError:
        pass
    db.commit()


@router.get("/duration", response_model=list[DurationStat])
def duration_stats(
    days: int = Query(default=30, ge=1, le=365),
    repository_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get test duration statistics."""
    return get_duration_stats(db, days, repository_id, limit)


@router.get("/heatmap", response_model=list[HeatmapCell])
def heatmap(
    days: int = Query(default=14, ge=1, le=90),
    repository_id: int | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get failure heatmap data."""
    return get_heatmap_data(db, days, repository_id, limit)


@router.post("/aggregate")
def aggregate_kpis(
    days: int = Query(default=365, ge=1, le=3650),
    _current_user: User = Depends(get_current_user),
):
    """Trigger KPI aggregation from execution runs into KpiRecord table."""
    result = aggregate_daily_kpis(days)
    return result


@router.get("/data-status")
def data_status(
    _current_user: User = Depends(get_current_user),
):
    """Return staleness info: last aggregation date vs last finished run."""
    return get_data_status()


# --- Analysis endpoints ---


@router.get("/analysis/kpis")
def available_kpis(
    _current_user: User = Depends(get_current_user),
):
    """Return metadata for all available KPIs."""
    return AVAILABLE_KPIS


@router.post("/analysis", response_model=AnalysisResponse)
@limiter.limit("10/minute")
def create_analysis_endpoint(
    request: Request,
    data: AnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Create a new analysis and dispatch background computation."""
    invalid = set(data.selected_kpis) - set(AVAILABLE_KPIS.keys())
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown KPI IDs: {', '.join(sorted(invalid))}",
        )
    analysis = create_analysis(db, data, current_user.id)
    db.commit()
    dispatch_task(run_analysis, analysis.id)

    # Re-serialize for response
    return _analysis_to_response(analysis)


@router.get("/analysis", response_model=list[AnalysisListResponse])
def list_analyses_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all analyses (paginated, without results blob)."""
    analyses = list_analyses(db, page, page_size)
    return [_analysis_to_list_response(a) for a in analyses]


@router.get("/analysis/{analysis_id}", response_model=AnalysisResponse)
def get_analysis_endpoint(
    analysis_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get a single analysis with full results."""
    analysis = get_analysis(db, analysis_id)
    if not analysis:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Analysis not found")
    return _analysis_to_response(analysis)


def _analysis_to_response(analysis) -> dict:
    """Convert AnalysisReport ORM object to response dict with parsed JSON fields."""
    selected = analysis.selected_kpis
    if isinstance(selected, str):
        try:
            selected = json.loads(selected)
        except (json.JSONDecodeError, TypeError):
            selected = []

    results = analysis.results
    if isinstance(results, str):
        try:
            results = json.loads(results)
        except (json.JSONDecodeError, TypeError):
            results = None

    return {
        "id": analysis.id,
        "repository_id": analysis.repository_id,
        "status": analysis.status,
        "selected_kpis": selected,
        "date_from": analysis.date_from,
        "date_to": analysis.date_to,
        "results": results,
        "error_message": analysis.error_message,
        "progress": analysis.progress,
        "reports_analyzed": analysis.reports_analyzed,
        "triggered_by": analysis.triggered_by,
        "started_at": analysis.started_at,
        "completed_at": analysis.completed_at,
        "created_at": analysis.created_at,
    }


def _analysis_to_list_response(analysis) -> dict:
    """Convert for list view (no results blob)."""
    selected = analysis.selected_kpis
    if isinstance(selected, str):
        try:
            selected = json.loads(selected)
        except (json.JSONDecodeError, TypeError):
            selected = []

    return {
        "id": analysis.id,
        "repository_id": analysis.repository_id,
        "status": analysis.status,
        "selected_kpis": selected,
        "date_from": analysis.date_from,
        "date_to": analysis.date_to,
        "error_message": analysis.error_message,
        "progress": analysis.progress,
        "reports_analyzed": analysis.reports_analyzed,
        "triggered_by": analysis.triggered_by,
        "started_at": analysis.started_at,
        "completed_at": analysis.completed_at,
        "created_at": analysis.created_at,
    }
