"""Pydantic schemas for KPI and statistics."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


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


# --- Analysis schemas ---


class AnalysisCreate(BaseModel):
    """Request to create a new analysis."""

    repository_id: int | None = None
    selected_kpis: list[str]
    date_from: date | None = None
    date_to: date | None = None


class AnalysisResponse(BaseModel):
    """Full analysis response with results."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int | None = None
    status: str
    selected_kpis: list[str] | str
    date_from: date | None = None
    date_to: date | None = None
    results: dict | str | None = None
    error_message: str | None = None
    progress: int = 0
    reports_analyzed: int = 0
    triggered_by: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class AnalysisListResponse(BaseModel):
    """Lightweight analysis list item (without results blob)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int | None = None
    status: str
    selected_kpis: list[str] | str
    date_from: date | None = None
    date_to: date | None = None
    error_message: str | None = None
    progress: int = 0
    reports_analyzed: int = 0
    triggered_by: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


AVAILABLE_KPIS: dict[str, dict] = {
    "keyword_frequency": {
        "id": "keyword_frequency",
        "name": "Keyword Frequency",
        "category": "keywords",
        "description": "Top used keywords ranked by call count, with library and percentage",
    },
    "keyword_duration_impact": {
        "id": "keyword_duration_impact",
        "name": "Keyword Duration Impact",
        "category": "keywords",
        "description": "Keywords ranked by cumulative time consumed",
    },
    "library_distribution": {
        "id": "library_distribution",
        "name": "Library Distribution",
        "category": "keywords",
        "description": "Keyword calls distributed across libraries",
    },
    "test_complexity": {
        "id": "test_complexity",
        "name": "Test Complexity",
        "category": "quality",
        "description": "Steps per test case: avg/min/max with histogram distribution",
    },
    "assertion_density": {
        "id": "assertion_density",
        "name": "Assertion Density",
        "category": "quality",
        "description": "Ratio of assertion keywords to total per test",
    },
    "tag_coverage": {
        "id": "tag_coverage",
        "name": "Tag Coverage",
        "category": "quality",
        "description": "Tag distribution, untagged test count, avg tags per test",
    },
    "error_patterns": {
        "id": "error_patterns",
        "name": "Error Patterns",
        "category": "maintenance",
        "description": "Cluster similar error messages by frequency",
    },
    "redundancy_detection": {
        "id": "redundancy_detection",
        "name": "Redundancy Detection",
        "category": "maintenance",
        "description": "Repeated keyword sequences appearing across multiple tests",
    },
    "source_test_stats": {
        "id": "source_test_stats",
        "name": "Source Test Analysis",
        "category": "source",
        "description": "Test case length, complexity, and keyword usage from .robot source files",
    },
    "source_library_distribution": {
        "id": "source_library_distribution",
        "name": "Source Library Imports",
        "category": "source",
        "description": "Library import distribution across .robot/.resource source files",
    },
    "test_pass_rate_trend": {
        "id": "test_pass_rate_trend",
        "name": "Test Pass Rate",
        "category": "execution",
        "description": "Pass/fail rate per test across runs",
    },
    "slowest_tests": {
        "id": "slowest_tests",
        "name": "Slowest Tests",
        "category": "execution",
        "description": "Top tests ranked by average execution duration",
    },
    "flakiness_score": {
        "id": "flakiness_score",
        "name": "Flakiness Score",
        "category": "execution",
        "description": "Tests ranked by status transition frequency",
    },
    "failure_heatmap": {
        "id": "failure_heatmap",
        "name": "Failure Heatmap",
        "category": "execution",
        "description": "Test x date matrix showing pass/fail status",
    },
    "suite_duration_treemap": {
        "id": "suite_duration_treemap",
        "name": "Suite Duration",
        "category": "execution",
        "description": "Execution time breakdown by test suite",
    },
}
