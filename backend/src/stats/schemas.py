"""Pydantic schemas for KPI and statistics."""

from datetime import date

from pydantic import BaseModel


class OverviewKpi(BaseModel):
    """Dashboard overview KPIs."""

    total_runs: int = 0
    passed_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    avg_duration_seconds: float = 0.0
    total_tests: int = 0
    flaky_tests: int = 0
    active_repos: int = 0


class SuccessRatePoint(BaseModel):
    """Single data point for success rate over time."""

    date: date
    success_rate: float
    total_runs: int


class TrendPoint(BaseModel):
    """Single data point for trend charts."""

    date: date
    passed: int = 0
    failed: int = 0
    error: int = 0
    total: int = 0
    avg_duration: float = 0.0


class FlakyTest(BaseModel):
    """Flaky test information."""

    test_name: str
    suite_name: str
    total_runs: int = 0
    pass_count: int = 0
    fail_count: int = 0
    flaky_rate: float = 0.0
    last_status: str = ""


class DurationStat(BaseModel):
    """Duration statistics."""

    test_name: str
    avg_duration: float
    min_duration: float
    max_duration: float
    run_count: int


class HeatmapCell(BaseModel):
    """Single cell in a failure heatmap."""

    test_name: str
    date: date
    status: str  # PASS, FAIL, SKIP, NONE
    duration: float = 0.0


class StatsFilter(BaseModel):
    """Filter parameters for stats queries."""

    start_date: date | None = None
    end_date: date | None = None
    repository_id: int | None = None
    branch: str | None = None
    environment_id: int | None = None
    tag: str | None = None
