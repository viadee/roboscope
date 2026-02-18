"""Statistics and KPI API endpoints."""

import asyncio
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from src.celery_app import dispatch_task
from src.database import get_db
from src.stats.analysis import run_analysis
from src.stats.schemas import (
    AVAILABLE_KPIS,
    AnalysisCreate,
    AnalysisListResponse,
    AnalysisResponse,
    DurationStat,
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
    """Get flaky test analysis."""
    return get_flaky_tests(db, days, min_runs, repository_id)


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
def create_analysis_endpoint(
    data: AnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.RUNNER)),
):
    """Create a new analysis and dispatch background computation."""
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
