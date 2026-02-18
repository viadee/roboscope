"""Statistics and KPI API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.stats.schemas import (
    DurationStat,
    FlakyTest,
    HeatmapCell,
    OverviewKpi,
    SuccessRatePoint,
    TrendPoint,
)
from src.stats.service import (
    get_duration_stats,
    get_flaky_tests,
    get_heatmap_data,
    get_overview,
    get_success_rate_trend,
    get_trends,
)

router = APIRouter()


@router.get("/overview", response_model=OverviewKpi)
async def overview(
    days: int = Query(default=30, ge=1, le=365),
    repository_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get dashboard overview KPIs."""
    return await get_overview(db, repository_id, days)


@router.get("/success-rate", response_model=list[SuccessRatePoint])
async def success_rate(
    days: int = Query(default=30, ge=1, le=365),
    repository_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get success rate trend over time."""
    return await get_success_rate_trend(db, days, repository_id)


@router.get("/trends", response_model=list[TrendPoint])
async def trends(
    days: int = Query(default=30, ge=1, le=365),
    repository_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get pass/fail/error trends over time."""
    return await get_trends(db, days, repository_id)


@router.get("/flaky", response_model=list[FlakyTest])
async def flaky_tests(
    days: int = Query(default=30, ge=1, le=365),
    min_runs: int = Query(default=3, ge=2),
    repository_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get flaky test analysis."""
    return await get_flaky_tests(db, days, min_runs, repository_id)


@router.get("/duration", response_model=list[DurationStat])
async def duration_stats(
    days: int = Query(default=30, ge=1, le=365),
    repository_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get test duration statistics."""
    return await get_duration_stats(db, days, repository_id, limit)


@router.get("/heatmap", response_model=list[HeatmapCell])
async def heatmap(
    days: int = Query(default=14, ge=1, le=90),
    repository_id: int | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get failure heatmap data."""
    return await get_heatmap_data(db, days, repository_id, limit)
