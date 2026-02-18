"""Statistics and KPI service."""

from datetime import date, timedelta

from sqlalchemy import and_, case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.execution.models import ExecutionRun, RunStatus
from src.reports.models import Report, TestResult
from src.repos.models import Repository
from src.stats.models import KpiRecord
from src.stats.schemas import (
    DurationStat,
    FlakyTest,
    HeatmapCell,
    OverviewKpi,
    SuccessRatePoint,
    TrendPoint,
)


async def get_overview(
    db: AsyncSession,
    repository_id: int | None = None,
    days: int = 30,
) -> OverviewKpi:
    """Get dashboard overview KPIs."""
    since = date.today() - timedelta(days=days)

    # Base query for runs
    run_query = select(ExecutionRun).where(
        ExecutionRun.created_at >= str(since)
    )
    if repository_id:
        run_query = run_query.where(ExecutionRun.repository_id == repository_id)

    # Total runs
    total_result = await db.execute(
        select(func.count()).select_from(run_query.subquery())
    )
    total_runs = total_result.scalar() or 0

    # Passed runs
    passed_query = run_query.where(ExecutionRun.status == RunStatus.PASSED)
    passed_result = await db.execute(
        select(func.count()).select_from(passed_query.subquery())
    )
    passed_runs = passed_result.scalar() or 0

    # Failed runs
    failed_query = run_query.where(ExecutionRun.status == RunStatus.FAILED)
    failed_result = await db.execute(
        select(func.count()).select_from(failed_query.subquery())
    )
    failed_runs = failed_result.scalar() or 0

    # Average duration
    avg_result = await db.execute(
        select(func.avg(ExecutionRun.duration_seconds)).where(
            ExecutionRun.created_at >= str(since),
            ExecutionRun.duration_seconds.is_not(None),
        )
    )
    avg_duration = avg_result.scalar() or 0.0

    # Total tests from reports
    test_count_result = await db.execute(
        select(func.sum(Report.total_tests)).where(
            Report.created_at >= str(since)
        )
    )
    total_tests = test_count_result.scalar() or 0

    # Active repos
    repo_result = await db.execute(
        select(func.count(distinct(ExecutionRun.repository_id))).where(
            ExecutionRun.created_at >= str(since)
        )
    )
    active_repos = repo_result.scalar() or 0

    # Success rate
    success_rate = (passed_runs / total_runs * 100) if total_runs > 0 else 0.0

    return OverviewKpi(
        total_runs=total_runs,
        passed_runs=passed_runs,
        failed_runs=failed_runs,
        success_rate=round(success_rate, 1),
        avg_duration_seconds=round(avg_duration, 1),
        total_tests=total_tests,
        flaky_tests=0,  # Calculated separately
        active_repos=active_repos,
    )


async def get_success_rate_trend(
    db: AsyncSession,
    days: int = 30,
    repository_id: int | None = None,
) -> list[SuccessRatePoint]:
    """Get success rate over time."""
    since = date.today() - timedelta(days=days)
    points: list[SuccessRatePoint] = []

    # Get KPI records
    query = select(KpiRecord).where(KpiRecord.date >= since).order_by(KpiRecord.date)
    if repository_id:
        query = query.where(KpiRecord.repository_id == repository_id)

    result = await db.execute(query)
    records = result.scalars().all()

    # Group by date
    date_map: dict[date, dict] = {}
    for record in records:
        if record.date not in date_map:
            date_map[record.date] = {"total": 0, "passed": 0}
        date_map[record.date]["total"] += record.total_runs
        date_map[record.date]["passed"] += record.passed_runs

    for d, data in sorted(date_map.items()):
        rate = (data["passed"] / data["total"] * 100) if data["total"] > 0 else 0.0
        points.append(SuccessRatePoint(
            date=d,
            success_rate=round(rate, 1),
            total_runs=data["total"],
        ))

    return points


async def get_trends(
    db: AsyncSession,
    days: int = 30,
    repository_id: int | None = None,
) -> list[TrendPoint]:
    """Get trend data for pass/fail/error over time."""
    since = date.today() - timedelta(days=days)

    query = select(KpiRecord).where(KpiRecord.date >= since).order_by(KpiRecord.date)
    if repository_id:
        query = query.where(KpiRecord.repository_id == repository_id)

    result = await db.execute(query)
    records = result.scalars().all()

    date_map: dict[date, TrendPoint] = {}
    for record in records:
        if record.date not in date_map:
            date_map[record.date] = TrendPoint(date=record.date)
        point = date_map[record.date]
        point.passed += record.passed_runs
        point.failed += record.failed_runs
        point.error += record.error_runs
        point.total += record.total_runs
        if record.avg_duration_seconds > 0:
            point.avg_duration = record.avg_duration_seconds

    return sorted(date_map.values(), key=lambda p: p.date)


async def get_flaky_tests(
    db: AsyncSession,
    days: int = 30,
    min_runs: int = 3,
    repository_id: int | None = None,
) -> list[FlakyTest]:
    """Detect flaky tests (tests that alternate between pass and fail)."""
    since = date.today() - timedelta(days=days)

    # Get all test results within the period
    query = (
        select(
            TestResult.test_name,
            TestResult.suite_name,
            TestResult.status,
        )
        .join(Report, TestResult.report_id == Report.id)
        .join(ExecutionRun, Report.execution_run_id == ExecutionRun.id)
        .where(ExecutionRun.created_at >= str(since))
    )
    if repository_id:
        query = query.where(ExecutionRun.repository_id == repository_id)

    result = await db.execute(query)
    rows = result.all()

    # Group by test name
    test_map: dict[str, dict] = {}
    for row in rows:
        key = f"{row.suite_name}::{row.test_name}"
        if key not in test_map:
            test_map[key] = {
                "test_name": row.test_name,
                "suite_name": row.suite_name,
                "statuses": [],
            }
        test_map[key]["statuses"].append(row.status)

    # Find flaky tests
    flaky_tests: list[FlakyTest] = []
    for key, data in test_map.items():
        statuses = data["statuses"]
        if len(statuses) < min_runs:
            continue

        pass_count = sum(1 for s in statuses if s == "PASS")
        fail_count = sum(1 for s in statuses if s == "FAIL")

        # A test is flaky if it has both passes and failures
        if pass_count > 0 and fail_count > 0:
            flaky_rate = min(pass_count, fail_count) / len(statuses)
            flaky_tests.append(FlakyTest(
                test_name=data["test_name"],
                suite_name=data["suite_name"],
                total_runs=len(statuses),
                pass_count=pass_count,
                fail_count=fail_count,
                flaky_rate=round(flaky_rate * 100, 1),
                last_status=statuses[-1],
            ))

    # Sort by flaky rate descending
    flaky_tests.sort(key=lambda t: t.flaky_rate, reverse=True)
    return flaky_tests


async def get_duration_stats(
    db: AsyncSession,
    days: int = 30,
    repository_id: int | None = None,
    limit: int = 20,
) -> list[DurationStat]:
    """Get duration statistics per test."""
    since = date.today() - timedelta(days=days)

    query = (
        select(
            TestResult.test_name,
            func.avg(TestResult.duration_seconds).label("avg_duration"),
            func.min(TestResult.duration_seconds).label("min_duration"),
            func.max(TestResult.duration_seconds).label("max_duration"),
            func.count(TestResult.id).label("run_count"),
        )
        .join(Report, TestResult.report_id == Report.id)
        .join(ExecutionRun, Report.execution_run_id == ExecutionRun.id)
        .where(ExecutionRun.created_at >= str(since))
        .group_by(TestResult.test_name)
        .order_by(func.avg(TestResult.duration_seconds).desc())
        .limit(limit)
    )
    if repository_id:
        query = query.where(ExecutionRun.repository_id == repository_id)

    result = await db.execute(query)
    rows = result.all()

    return [
        DurationStat(
            test_name=row.test_name,
            avg_duration=round(row.avg_duration, 2),
            min_duration=round(row.min_duration, 2),
            max_duration=round(row.max_duration, 2),
            run_count=row.run_count,
        )
        for row in rows
    ]


async def get_heatmap_data(
    db: AsyncSession,
    days: int = 14,
    repository_id: int | None = None,
    limit: int = 30,
) -> list[HeatmapCell]:
    """Get failure heatmap data (test x date matrix)."""
    since = date.today() - timedelta(days=days)

    # Get most-failing tests first
    failing_query = (
        select(
            TestResult.test_name,
            func.count(TestResult.id).label("fail_count"),
        )
        .join(Report, TestResult.report_id == Report.id)
        .join(ExecutionRun, Report.execution_run_id == ExecutionRun.id)
        .where(
            ExecutionRun.created_at >= str(since),
            TestResult.status == "FAIL",
        )
        .group_by(TestResult.test_name)
        .order_by(func.count(TestResult.id).desc())
        .limit(limit)
    )
    if repository_id:
        failing_query = failing_query.where(ExecutionRun.repository_id == repository_id)

    failing_result = await db.execute(failing_query)
    top_failing = [row.test_name for row in failing_result.all()]

    if not top_failing:
        return []

    # Get results for those tests over the period
    query = (
        select(
            TestResult.test_name,
            TestResult.status,
            TestResult.duration_seconds,
            ExecutionRun.created_at,
        )
        .join(Report, TestResult.report_id == Report.id)
        .join(ExecutionRun, Report.execution_run_id == ExecutionRun.id)
        .where(
            ExecutionRun.created_at >= str(since),
            TestResult.test_name.in_(top_failing),
        )
    )

    result = await db.execute(query)
    cells: list[HeatmapCell] = []

    for row in result.all():
        run_date = row.created_at.date() if hasattr(row.created_at, "date") else row.created_at
        cells.append(HeatmapCell(
            test_name=row.test_name,
            date=run_date,
            status=row.status,
            duration=row.duration_seconds,
        ))

    return cells
