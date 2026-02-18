"""Tests for stats API endpoints."""

from datetime import date, timedelta

import pytest

from src.execution.models import ExecutionRun, RunStatus
from src.reports.models import Report, TestResult
from src.repos.models import Repository
from src.stats.models import KpiRecord
from tests.conftest import auth_header


def _make_repo(user_id: int, **overrides) -> Repository:
    """Helper to build a Repository with sensible defaults."""
    defaults = {
        "name": "stats-api-repo",
        "git_url": "https://github.com/org/stats-api-repo.git",
        "default_branch": "main",
        "local_path": "/tmp/workspace/stats-api-repo",
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


class TestOverviewEndpoint:
    async def test_overview_authenticated(self, client, admin_user):
        """GET /overview should return KPI data for an authenticated user."""
        response = await client.get(
            "/api/v1/stats/overview",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_runs" in data
        assert "passed_runs" in data
        assert "failed_runs" in data
        assert "success_rate" in data
        assert "avg_duration_seconds" in data
        assert "total_tests" in data
        assert "active_repos" in data

    async def test_overview_unauthenticated(self, client):
        """GET /overview should return 403 without authentication."""
        response = await client.get("/api/v1/stats/overview")
        assert response.status_code == 403

    async def test_overview_with_days_param(self, client, admin_user):
        """GET /overview should accept days query parameter."""
        response = await client.get(
            "/api/v1/stats/overview?days=7",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200

    async def test_overview_with_data(self, client, db_session, admin_user):
        """GET /overview should reflect actual database data."""
        repo = _make_repo(admin_user.id)
        db_session.add(repo)
        await db_session.flush()
        await db_session.refresh(repo)

        run = _make_run(repo.id, admin_user.id, status=RunStatus.PASSED, duration_seconds=25.0)
        db_session.add(run)
        await db_session.flush()
        await db_session.refresh(run)

        report = _make_report(run.id, total_tests=12)
        db_session.add(report)
        await db_session.flush()

        response = await client.get(
            "/api/v1/stats/overview",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_runs"] == 1
        assert data["passed_runs"] == 1
        assert data["total_tests"] == 12


class TestSuccessRateEndpoint:
    async def test_success_rate_authenticated(self, client, admin_user):
        """GET /success-rate should return a list for an authenticated user."""
        response = await client.get(
            "/api/v1/stats/success-rate",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_success_rate_unauthenticated(self, client):
        """GET /success-rate should return 403 without authentication."""
        response = await client.get("/api/v1/stats/success-rate")
        assert response.status_code == 403

    async def test_success_rate_with_data(self, client, db_session, admin_user):
        """GET /success-rate should return trend data when KPI records exist."""
        repo = _make_repo(admin_user.id)
        db_session.add(repo)
        await db_session.flush()
        await db_session.refresh(repo)

        kpi = KpiRecord(
            date=date.today(),
            repository_id=repo.id,
            total_runs=10,
            passed_runs=9,
            failed_runs=1,
            error_runs=0,
            avg_duration_seconds=10.0,
            success_rate=90.0,
        )
        db_session.add(kpi)
        await db_session.flush()

        response = await client.get(
            "/api/v1/stats/success-rate",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["success_rate"] == 90.0
        assert data[0]["total_runs"] == 10


class TestTrendsEndpoint:
    async def test_trends_authenticated(self, client, admin_user):
        """GET /trends should return a list for an authenticated user."""
        response = await client.get(
            "/api/v1/stats/trends",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_trends_unauthenticated(self, client):
        """GET /trends should return 403 without authentication."""
        response = await client.get("/api/v1/stats/trends")
        assert response.status_code == 403

    async def test_trends_with_data(self, client, db_session, admin_user):
        """GET /trends should return pass/fail/error breakdown when data exists."""
        repo = _make_repo(admin_user.id)
        db_session.add(repo)
        await db_session.flush()
        await db_session.refresh(repo)

        kpi = KpiRecord(
            date=date.today(),
            repository_id=repo.id,
            total_runs=10,
            passed_runs=7,
            failed_runs=2,
            error_runs=1,
            avg_duration_seconds=15.0,
            success_rate=70.0,
        )
        db_session.add(kpi)
        await db_session.flush()

        response = await client.get(
            "/api/v1/stats/trends",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["passed"] == 7
        assert data[0]["failed"] == 2
        assert data[0]["error"] == 1


class TestFlakyEndpoint:
    async def test_flaky_authenticated(self, client, admin_user):
        """GET /flaky should return a list for an authenticated user."""
        response = await client.get(
            "/api/v1/stats/flaky",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_flaky_unauthenticated(self, client):
        """GET /flaky should return 403 without authentication."""
        response = await client.get("/api/v1/stats/flaky")
        assert response.status_code == 403

    async def test_flaky_with_data(self, client, db_session, admin_user):
        """GET /flaky should detect flaky tests from test results."""
        repo = _make_repo(admin_user.id)
        db_session.add(repo)
        await db_session.flush()
        await db_session.refresh(repo)

        # Create runs, reports, and alternating test results
        for i in range(4):
            run = _make_run(repo.id, admin_user.id, status=RunStatus.PASSED)
            db_session.add(run)
            await db_session.flush()
            await db_session.refresh(run)

            report = _make_report(run.id, total_tests=1)
            db_session.add(report)
            await db_session.flush()
            await db_session.refresh(report)

            tr = _make_test_result(
                report.id,
                test_name="test_flaky_api",
                suite_name="ApiSuite",
                status="PASS" if i % 2 == 0 else "FAIL",
            )
            db_session.add(tr)
        await db_session.flush()

        response = await client.get(
            "/api/v1/stats/flaky?min_runs=3",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["test_name"] == "test_flaky_api"
        assert data[0]["pass_count"] == 2
        assert data[0]["fail_count"] == 2


class TestDurationEndpoint:
    async def test_duration_authenticated(self, client, admin_user):
        """GET /duration should return a list for an authenticated user."""
        response = await client.get(
            "/api/v1/stats/duration",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_duration_unauthenticated(self, client):
        """GET /duration should return 403 without authentication."""
        response = await client.get("/api/v1/stats/duration")
        assert response.status_code == 403

    async def test_duration_with_data(self, client, db_session, admin_user):
        """GET /duration should return aggregated duration stats."""
        repo = _make_repo(admin_user.id)
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

        tr = _make_test_result(report.id, test_name="test_timed", duration_seconds=3.5)
        db_session.add(tr)
        await db_session.flush()

        response = await client.get(
            "/api/v1/stats/duration",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["test_name"] == "test_timed"
        assert data[0]["avg_duration"] == 3.5


class TestHeatmapEndpoint:
    async def test_heatmap_authenticated(self, client, admin_user):
        """GET /heatmap should return a list for an authenticated user."""
        response = await client.get(
            "/api/v1/stats/heatmap",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_heatmap_unauthenticated(self, client):
        """GET /heatmap should return 403 without authentication."""
        response = await client.get("/api/v1/stats/heatmap")
        assert response.status_code == 403

    async def test_heatmap_empty_when_no_failures(self, client, db_session, admin_user):
        """GET /heatmap should return empty list when no tests have failed."""
        repo = _make_repo(admin_user.id)
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

        # Only passing test results
        tr = _make_test_result(report.id, test_name="test_ok", status="PASS")
        db_session.add(tr)
        await db_session.flush()

        response = await client.get(
            "/api/v1/stats/heatmap",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_heatmap_with_failures(self, client, db_session, admin_user):
        """GET /heatmap should return cells for failing tests."""
        repo = _make_repo(admin_user.id)
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

        tr = _make_test_result(report.id, test_name="test_broken", status="FAIL", duration_seconds=2.0)
        db_session.add(tr)
        await db_session.flush()

        response = await client.get(
            "/api/v1/stats/heatmap",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["test_name"] == "test_broken"
