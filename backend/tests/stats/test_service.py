"""Tests for stats service."""

from datetime import date, timedelta

import pytest

from src.execution.models import ExecutionRun, RunStatus
from src.reports.models import Report, TestResult
from src.repos.models import Repository
from src.stats.models import KpiRecord
from src.stats.service import (
    get_duration_stats,
    get_flaky_tests,
    get_overview,
    get_success_rate_trend,
    get_trends,
)


def _make_repo(user_id: int, **overrides) -> Repository:
    """Helper to build a Repository with sensible defaults."""
    defaults = {
        "name": "stats-repo",
        "git_url": "https://github.com/org/stats-repo.git",
        "default_branch": "main",
        "local_path": "/tmp/workspace/stats-repo",
        "auto_sync": True,
        "sync_interval_minutes": 15,
        "created_by": user_id,
    }
    defaults.update(overrides)
    return Repository(**defaults)


def _make_run(repo_id: int, user_id: int, **overrides) -> ExecutionRun:
    """Helper to build an ExecutionRun with sensible defaults."""
    defaults = {
        "repository_id": repo_id,
        "target_path": "/tests",
        "branch": "main",
        "status": RunStatus.PASSED,
        "triggered_by": user_id,
        "duration_seconds": 10.0,
    }
    defaults.update(overrides)
    return ExecutionRun(**defaults)


def _make_report(run_id: int, **overrides) -> Report:
    """Helper to build a Report with sensible defaults."""
    defaults = {
        "execution_run_id": run_id,
        "output_xml_path": "/tmp/output.xml",
        "total_tests": 10,
        "passed_tests": 8,
        "failed_tests": 2,
        "skipped_tests": 0,
        "total_duration_seconds": 30.0,
    }
    defaults.update(overrides)
    return Report(**defaults)


def _make_test_result(report_id: int, **overrides) -> TestResult:
    """Helper to build a TestResult with sensible defaults."""
    defaults = {
        "report_id": report_id,
        "suite_name": "MySuite",
        "test_name": "test_example",
        "status": "PASS",
        "duration_seconds": 1.5,
    }
    defaults.update(overrides)
    return TestResult(**defaults)


class TestGetOverview:
    async def test_overview_no_data(self, db_session):
        """With an empty database, all KPIs should be zero."""
        result = await get_overview(db_session)

        assert result.total_runs == 0
        assert result.passed_runs == 0
        assert result.failed_runs == 0
        assert result.success_rate == 0.0
        assert result.avg_duration_seconds == 0.0
        assert result.total_tests == 0
        assert result.active_repos == 0

    async def test_overview_with_runs(self, db_session, admin_user):
        """Overview should reflect runs and reports in the database."""
        repo = _make_repo(admin_user.id)
        db_session.add(repo)
        await db_session.flush()
        await db_session.refresh(repo)

        # Create some runs: 2 passed, 1 failed
        run1 = _make_run(repo.id, admin_user.id, status=RunStatus.PASSED, duration_seconds=20.0)
        run2 = _make_run(repo.id, admin_user.id, status=RunStatus.PASSED, duration_seconds=30.0)
        run3 = _make_run(repo.id, admin_user.id, status=RunStatus.FAILED, duration_seconds=10.0)
        db_session.add_all([run1, run2, run3])
        await db_session.flush()
        await db_session.refresh(run1)
        await db_session.refresh(run2)

        # Create reports for the passed runs
        report1 = _make_report(run1.id, total_tests=5)
        report2 = _make_report(run2.id, total_tests=8)
        db_session.add_all([report1, report2])
        await db_session.flush()

        result = await get_overview(db_session)

        assert result.total_runs == 3
        assert result.passed_runs == 2
        assert result.failed_runs == 1
        assert result.success_rate == 66.7  # 2/3 * 100 rounded to 1 decimal
        assert result.avg_duration_seconds == 20.0  # (20+30+10)/3
        assert result.total_tests == 13  # 5 + 8
        assert result.active_repos == 1

    async def test_overview_with_repository_filter(self, db_session, admin_user):
        """Overview should filter by repository_id when provided."""
        repo1 = _make_repo(admin_user.id, name="repo-a")
        repo2 = _make_repo(admin_user.id, name="repo-b")
        db_session.add_all([repo1, repo2])
        await db_session.flush()
        await db_session.refresh(repo1)
        await db_session.refresh(repo2)

        run1 = _make_run(repo1.id, admin_user.id, status=RunStatus.PASSED)
        run2 = _make_run(repo2.id, admin_user.id, status=RunStatus.FAILED)
        db_session.add_all([run1, run2])
        await db_session.flush()

        result = await get_overview(db_session, repository_id=repo1.id)

        assert result.total_runs == 1
        assert result.passed_runs == 1
        assert result.failed_runs == 0


class TestGetSuccessRateTrend:
    async def test_success_rate_trend_empty(self, db_session):
        """With no KPI records, should return an empty list."""
        result = await get_success_rate_trend(db_session)
        assert result == []

    async def test_success_rate_trend_with_records(self, db_session, admin_user):
        """Should return aggregated success rate points sorted by date."""
        repo = _make_repo(admin_user.id)
        db_session.add(repo)
        await db_session.flush()
        await db_session.refresh(repo)

        today = date.today()
        yesterday = today - timedelta(days=1)

        kpi1 = KpiRecord(
            date=yesterday,
            repository_id=repo.id,
            total_runs=10,
            passed_runs=8,
            failed_runs=2,
            error_runs=0,
            avg_duration_seconds=15.0,
            success_rate=80.0,
        )
        kpi2 = KpiRecord(
            date=today,
            repository_id=repo.id,
            total_runs=5,
            passed_runs=5,
            failed_runs=0,
            error_runs=0,
            avg_duration_seconds=12.0,
            success_rate=100.0,
        )
        db_session.add_all([kpi1, kpi2])
        await db_session.flush()

        result = await get_success_rate_trend(db_session)

        assert len(result) == 2
        assert result[0].date == yesterday
        assert result[0].success_rate == 80.0
        assert result[0].total_runs == 10
        assert result[1].date == today
        assert result[1].success_rate == 100.0
        assert result[1].total_runs == 5


class TestGetTrends:
    async def test_trends_empty(self, db_session):
        """With no KPI records, should return an empty list."""
        result = await get_trends(db_session)
        assert result == []

    async def test_trends_with_records(self, db_session, admin_user):
        """Should return trend points with pass/fail/error breakdowns."""
        repo = _make_repo(admin_user.id)
        db_session.add(repo)
        await db_session.flush()
        await db_session.refresh(repo)

        today = date.today()

        kpi = KpiRecord(
            date=today,
            repository_id=repo.id,
            total_runs=10,
            passed_runs=7,
            failed_runs=2,
            error_runs=1,
            avg_duration_seconds=20.0,
            success_rate=70.0,
        )
        db_session.add(kpi)
        await db_session.flush()

        result = await get_trends(db_session)

        assert len(result) == 1
        point = result[0]
        assert point.date == today
        assert point.passed == 7
        assert point.failed == 2
        assert point.error == 1
        assert point.total == 10
        assert point.avg_duration == 20.0


class TestGetFlakyTests:
    async def test_flaky_tests_empty(self, db_session):
        """With no test results, should return an empty list."""
        result = await get_flaky_tests(db_session)
        assert result == []

    async def test_flaky_tests_detected(self, db_session, admin_user):
        """A test with both PASS and FAIL results should be detected as flaky."""
        repo = _make_repo(admin_user.id)
        db_session.add(repo)
        await db_session.flush()
        await db_session.refresh(repo)

        # Create multiple runs with reports and test results
        runs = []
        for i in range(4):
            run = _make_run(repo.id, admin_user.id, status=RunStatus.PASSED)
            db_session.add(run)
            await db_session.flush()
            await db_session.refresh(run)
            runs.append(run)

        reports = []
        for run in runs:
            report = _make_report(run.id, total_tests=1)
            db_session.add(report)
            await db_session.flush()
            await db_session.refresh(report)
            reports.append(report)

        # Flaky test: alternates between PASS and FAIL
        statuses = ["PASS", "FAIL", "PASS", "FAIL"]
        for report, status in zip(reports, statuses):
            tr = _make_test_result(
                report.id,
                test_name="test_flaky_one",
                suite_name="FlakyTests",
                status=status,
            )
            db_session.add(tr)
        await db_session.flush()

        result = await get_flaky_tests(db_session, min_runs=3)

        assert len(result) == 1
        flaky = result[0]
        assert flaky.test_name == "test_flaky_one"
        assert flaky.suite_name == "FlakyTests"
        assert flaky.total_runs == 4
        assert flaky.pass_count == 2
        assert flaky.fail_count == 2
        assert flaky.flaky_rate == 50.0  # min(2,2)/4 * 100

    async def test_stable_tests_not_flaky(self, db_session, admin_user):
        """A test that only passes should NOT be detected as flaky."""
        repo = _make_repo(admin_user.id, name="stable-repo")
        db_session.add(repo)
        await db_session.flush()
        await db_session.refresh(repo)

        runs = []
        for i in range(4):
            run = _make_run(repo.id, admin_user.id, status=RunStatus.PASSED)
            db_session.add(run)
            await db_session.flush()
            await db_session.refresh(run)
            runs.append(run)

        reports = []
        for run in runs:
            report = _make_report(run.id, total_tests=1)
            db_session.add(report)
            await db_session.flush()
            await db_session.refresh(report)
            reports.append(report)

        # Stable test: always passes
        for report in reports:
            tr = _make_test_result(
                report.id,
                test_name="test_always_pass",
                suite_name="StableTests",
                status="PASS",
            )
            db_session.add(tr)
        await db_session.flush()

        result = await get_flaky_tests(db_session, min_runs=3)
        assert len(result) == 0

    async def test_flaky_tests_min_runs_filter(self, db_session, admin_user):
        """Tests with fewer runs than min_runs should not be included."""
        repo = _make_repo(admin_user.id, name="few-runs-repo")
        db_session.add(repo)
        await db_session.flush()
        await db_session.refresh(repo)

        # Only 2 runs, but with alternating status
        runs = []
        for i in range(2):
            run = _make_run(repo.id, admin_user.id, status=RunStatus.PASSED)
            db_session.add(run)
            await db_session.flush()
            await db_session.refresh(run)
            runs.append(run)

        reports = []
        for run in runs:
            report = _make_report(run.id, total_tests=1)
            db_session.add(report)
            await db_session.flush()
            await db_session.refresh(report)
            reports.append(report)

        statuses = ["PASS", "FAIL"]
        for report, status in zip(reports, statuses):
            tr = _make_test_result(
                report.id,
                test_name="test_short_lived",
                suite_name="ShortSuite",
                status=status,
            )
            db_session.add(tr)
        await db_session.flush()

        # min_runs=3 so the 2-run test should be excluded
        result = await get_flaky_tests(db_session, min_runs=3)
        assert len(result) == 0


class TestGetDurationStats:
    async def test_duration_stats_empty(self, db_session):
        """With no test results, should return an empty list."""
        result = await get_duration_stats(db_session)
        assert result == []

    async def test_duration_stats_with_data(self, db_session, admin_user):
        """Should return aggregated duration statistics per test."""
        repo = _make_repo(admin_user.id)
        db_session.add(repo)
        await db_session.flush()
        await db_session.refresh(repo)

        # Create two runs with reports and test results
        run1 = _make_run(repo.id, admin_user.id)
        run2 = _make_run(repo.id, admin_user.id)
        db_session.add_all([run1, run2])
        await db_session.flush()
        await db_session.refresh(run1)
        await db_session.refresh(run2)

        report1 = _make_report(run1.id)
        report2 = _make_report(run2.id)
        db_session.add_all([report1, report2])
        await db_session.flush()
        await db_session.refresh(report1)
        await db_session.refresh(report2)

        # Same test with different durations across reports
        tr1 = _make_test_result(report1.id, test_name="test_slow", duration_seconds=5.0)
        tr2 = _make_test_result(report2.id, test_name="test_slow", duration_seconds=15.0)
        # Another test
        tr3 = _make_test_result(report1.id, test_name="test_fast", duration_seconds=1.0)
        tr4 = _make_test_result(report2.id, test_name="test_fast", duration_seconds=2.0)
        db_session.add_all([tr1, tr2, tr3, tr4])
        await db_session.flush()

        result = await get_duration_stats(db_session)

        assert len(result) == 2
        # Results ordered by avg_duration descending, so test_slow first
        slow = result[0]
        assert slow.test_name == "test_slow"
        assert slow.avg_duration == 10.0  # (5+15)/2
        assert slow.min_duration == 5.0
        assert slow.max_duration == 15.0
        assert slow.run_count == 2

        fast = result[1]
        assert fast.test_name == "test_fast"
        assert fast.avg_duration == 1.5  # (1+2)/2
        assert fast.min_duration == 1.0
        assert fast.max_duration == 2.0
        assert fast.run_count == 2

    async def test_duration_stats_respects_limit(self, db_session, admin_user):
        """The limit parameter should cap the number of results."""
        repo = _make_repo(admin_user.id, name="limit-repo")
        db_session.add(repo)
        await db_session.flush()
        await db_session.refresh(repo)

        run = _make_run(repo.id, admin_user.id)
        db_session.add(run)
        await db_session.flush()
        await db_session.refresh(run)

        report = _make_report(run.id)
        db_session.add(report)
        await db_session.flush()
        await db_session.refresh(report)

        # Create 5 different tests
        for i in range(5):
            tr = _make_test_result(
                report.id,
                test_name=f"test_number_{i}",
                duration_seconds=float(i + 1),
            )
            db_session.add(tr)
        await db_session.flush()

        result = await get_duration_stats(db_session, limit=3)
        assert len(result) == 3
