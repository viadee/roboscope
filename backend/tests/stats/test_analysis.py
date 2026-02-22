"""Tests for stats analysis compute functions and bug fixes."""

from datetime import date, datetime, time, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.execution.models import ExecutionRun, RunStatus
from src.reports.models import Report, TestResult
from src.repos.models import Repository
from src.stats.analysis import (
    _broadcast_analysis_status,
    compute_assertion_density,
    compute_error_patterns,
    compute_failure_heatmap,
    compute_flakiness_score,
    compute_keyword_frequency,
    compute_library_distribution,
    compute_redundancy_detection,
    compute_slowest_tests,
    compute_suite_duration_treemap,
    compute_test_complexity,
    compute_test_pass_rate_trend,
)
from src.stats.schemas import AVAILABLE_KPIS
from tests.conftest import auth_header


def _make_repo(user_id: int, **overrides) -> Repository:
    defaults = {
        "name": "analysis-repo",
        "git_url": "https://github.com/org/analysis-repo.git",
        "default_branch": "main",
        "local_path": "/tmp/workspace/analysis-repo",
        "auto_sync": True,
        "sync_interval_minutes": 15,
        "created_by": user_id,
    }
    defaults.update(overrides)
    return Repository(**defaults)


def _make_run(repo_id: int, user_id: int, **overrides) -> ExecutionRun:
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
    defaults = {
        "report_id": report_id,
        "suite_name": "MySuite",
        "test_name": "test_example",
        "status": "PASS",
        "duration_seconds": 1.5,
    }
    defaults.update(overrides)
    return TestResult(**defaults)


def _seed_test_results(db_session, admin_user):
    """Create repo, runs, reports, and test results for testing compute functions."""
    repo = _make_repo(admin_user.id)
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)

    results = []
    for i in range(4):
        run = _make_run(repo.id, admin_user.id, status=RunStatus.PASSED)
        db_session.add(run)
        db_session.flush()
        db_session.refresh(run)

        report = _make_report(run.id, total_tests=2)
        db_session.add(report)
        db_session.flush()
        db_session.refresh(report)

        # Test A: alternates PASS/FAIL (flaky)
        tr_a = _make_test_result(
            report.id,
            test_name="test_login",
            suite_name="AuthSuite",
            status="PASS" if i % 2 == 0 else "FAIL",
            duration_seconds=2.0 + i,
            start_time=f"2026-02-{10+i:02d}T10:00:00",
        )
        db_session.add(tr_a)

        # Test B: always passes
        tr_b = _make_test_result(
            report.id,
            test_name="test_homepage",
            suite_name="UISuite",
            status="PASS",
            duration_seconds=0.5 + i * 0.1,
            start_time=f"2026-02-{10+i:02d}T10:01:00",
        )
        db_session.add(tr_b)

        # Test C: always fails
        tr_c = _make_test_result(
            report.id,
            test_name="test_broken",
            suite_name="AuthSuite",
            status="FAIL",
            duration_seconds=1.0,
            start_time=f"2026-02-{10+i:02d}T10:02:00",
        )
        db_session.add(tr_c)

    db_session.flush()
    return repo


# --- Test: _broadcast_analysis_status helper ---


class TestBroadcastAnalysisStatus:
    def test_broadcast_does_not_crash_without_event_loop(self):
        """_broadcast_analysis_status should not raise when no event loop exists."""
        mock_ws = MagicMock()
        mock_ws.broadcast.return_value = MagicMock()
        with patch("src.websocket.manager.ws_manager", mock_ws):
            with patch("src.main._event_loop", None, create=True):
                # Should not raise
                _broadcast_analysis_status(1, "completed", 100)

    def test_broadcast_schedules_coroutine(self):
        """When event loop is running, should schedule coroutine via run_coroutine_threadsafe."""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        mock_ws = MagicMock()

        # Create a real coroutine for asyncio.run_coroutine_threadsafe
        import asyncio

        async def fake_broadcast(*args, **kwargs):
            pass

        mock_ws.broadcast.return_value = fake_broadcast()

        with patch("src.websocket.manager.ws_manager", mock_ws):
            with patch("src.main._event_loop", mock_loop, create=True):
                with patch("asyncio.run_coroutine_threadsafe") as mock_rct:
                    _broadcast_analysis_status(42, "running", 50)

        mock_ws.broadcast.assert_called_once_with({
            "type": "analysis_status_changed",
            "analysis_id": 42,
            "status": "running",
            "progress": 50,
        })
        mock_rct.assert_called_once()


# --- Test: Date filtering fix ---


class TestDateFilteringFix:
    def test_datetime_combine_produces_correct_types(self):
        """Verify datetime.combine produces proper datetime objects, not strings."""
        d = date(2026, 1, 15)
        dt_min = datetime.combine(d, time.min)
        dt_max = datetime.combine(d, time.max)

        assert isinstance(dt_min, datetime)
        assert isinstance(dt_max, datetime)
        assert dt_min == datetime(2026, 1, 15, 0, 0, 0)
        assert dt_max.hour == 23
        assert dt_max.minute == 59


# --- Test: KPI validation ---


class TestKpiValidation:
    def test_unknown_kpi_rejected(self, client, admin_user):
        """POST /analysis with unknown KPI IDs should return 422."""
        response = client.post(
            "/api/v1/stats/analysis",
            json={
                "selected_kpis": ["nonexistent_kpi", "keyword_frequency"],
            },
            headers=auth_header(admin_user),
        )
        assert response.status_code == 422
        assert "nonexistent_kpi" in response.json()["detail"]

    def test_valid_kpis_accepted(self, client, admin_user):
        """POST /analysis with valid KPI IDs should succeed."""
        response = client.post(
            "/api/v1/stats/analysis",
            json={
                "selected_kpis": ["keyword_frequency"],
            },
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200

    def test_all_new_kpis_in_available(self):
        """All 5 new execution KPIs should be in AVAILABLE_KPIS."""
        new_kpis = [
            "test_pass_rate_trend",
            "slowest_tests",
            "flakiness_score",
            "failure_heatmap",
            "suite_duration_treemap",
        ]
        for kpi_id in new_kpis:
            assert kpi_id in AVAILABLE_KPIS
            assert AVAILABLE_KPIS[kpi_id]["category"] == "execution"

    def test_available_kpis_count(self):
        """AVAILABLE_KPIS should contain 15 entries (10 original + 5 new)."""
        assert len(AVAILABLE_KPIS) == 15

    def test_kpis_endpoint_returns_all(self, client, admin_user):
        """GET /analysis/kpis should return all 15 KPIs."""
        response = client.get(
            "/api/v1/stats/analysis/kpis",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 15
        assert "test_pass_rate_trend" in data
        assert data["test_pass_rate_trend"]["category"] == "execution"


# --- Test: compute_test_pass_rate_trend ---


class TestComputeTestPassRateTrend:
    def test_empty_db(self, db_session):
        """Should return empty results for empty DB."""
        result = compute_test_pass_rate_trend(db_session, None, None, None)
        assert result["total_tests"] == 0
        assert result["tests"] == []

    def test_with_data(self, db_session, admin_user):
        """Should compute pass rates correctly."""
        _seed_test_results(db_session, admin_user)
        result = compute_test_pass_rate_trend(db_session, None, None, None)

        assert result["total_tests"] == 3
        tests_by_name = {t["test_name"]: t for t in result["tests"]}

        # test_homepage always passes → 100%
        assert tests_by_name["test_homepage"]["pass_rate"] == 100.0
        assert tests_by_name["test_homepage"]["pass_count"] == 4

        # test_broken always fails → 0%
        assert tests_by_name["test_broken"]["pass_rate"] == 0.0
        assert tests_by_name["test_broken"]["fail_count"] == 4

        # test_login alternates → 50%
        assert tests_by_name["test_login"]["pass_rate"] == 50.0

    def test_sorted_by_worst_pass_rate(self, db_session, admin_user):
        """Results should be sorted by worst pass rate first."""
        _seed_test_results(db_session, admin_user)
        result = compute_test_pass_rate_trend(db_session, None, None, None)

        rates = [t["pass_rate"] for t in result["tests"]]
        assert rates == sorted(rates)  # ascending = worst first


# --- Test: compute_slowest_tests ---


class TestComputeSlowestTests:
    def test_empty_db(self, db_session):
        result = compute_slowest_tests(db_session, None, None, None)
        assert result["total_tests"] == 0

    def test_with_data(self, db_session, admin_user):
        _seed_test_results(db_session, admin_user)
        result = compute_slowest_tests(db_session, None, None, None)

        assert result["total_tests"] == 3
        # First should be slowest (test_login has 2.0, 3.0, 4.0, 5.0 → avg 3.5)
        assert result["tests"][0]["test_name"] == "test_login"
        assert result["tests"][0]["avg_duration"] > 0
        assert result["tests"][0]["min_duration"] <= result["tests"][0]["max_duration"]

    def test_sorted_by_duration_descending(self, db_session, admin_user):
        _seed_test_results(db_session, admin_user)
        result = compute_slowest_tests(db_session, None, None, None)

        durations = [t["avg_duration"] for t in result["tests"]]
        assert durations == sorted(durations, reverse=True)


# --- Test: compute_flakiness_score ---


class TestComputeFlakinessScore:
    def test_empty_db(self, db_session):
        result = compute_flakiness_score(db_session, None, None, None)
        assert result["total_tests"] == 0

    def test_detects_flaky_test(self, db_session, admin_user):
        _seed_test_results(db_session, admin_user)
        result = compute_flakiness_score(db_session, None, None, None)

        # test_login alternates PASS/FAIL → should have high flakiness
        flaky_names = [t["test_name"] for t in result["tests"]]
        assert "test_login" in flaky_names

        login = next(t for t in result["tests"] if t["test_name"] == "test_login")
        assert login["flakiness_score"] > 0
        assert login["transitions"] > 0
        assert len(login["timeline"]) > 0

    def test_stable_tests_excluded(self, db_session, admin_user):
        _seed_test_results(db_session, admin_user)
        result = compute_flakiness_score(db_session, None, None, None)

        # test_homepage always passes → score 0 → excluded from results
        flaky_names = [t["test_name"] for t in result["tests"]]
        assert "test_homepage" not in flaky_names


# --- Test: compute_failure_heatmap ---


class TestComputeFailureHeatmap:
    def test_empty_db(self, db_session):
        result = compute_failure_heatmap(db_session, None, None, None)
        assert result["dates"] == []
        assert result["tests"] == []

    def test_with_failures(self, db_session, admin_user):
        _seed_test_results(db_session, admin_user)
        result = compute_failure_heatmap(db_session, None, None, None)

        # test_broken and test_login both have failures
        test_names = [t["test_name"] for t in result["tests"]]
        assert "test_broken" in test_names

        # Each test row should have cells for each date
        assert len(result["dates"]) > 0
        for test_row in result["tests"]:
            assert len(test_row["cells"]) == len(result["dates"])
            for cell in test_row["cells"]:
                assert cell["status"] in ("PASS", "FAIL", "NONE")


# --- Test: compute_suite_duration_treemap ---


class TestComputeSuiteDurationTreemap:
    def test_empty_db(self, db_session):
        result = compute_suite_duration_treemap(db_session, None, None, None)
        assert result["suites"] == []

    def test_with_data(self, db_session, admin_user):
        _seed_test_results(db_session, admin_user)
        result = compute_suite_duration_treemap(db_session, None, None, None)

        assert result["total_duration"] > 0
        suite_names = [s["suite_name"] for s in result["suites"]]
        assert "AuthSuite" in suite_names
        assert "UISuite" in suite_names

        # Percentages should sum to ~100%
        total_pct = sum(s["percentage"] for s in result["suites"])
        assert 99.0 <= total_pct <= 101.0

    def test_sorted_by_duration_descending(self, db_session, admin_user):
        _seed_test_results(db_session, admin_user)
        result = compute_suite_duration_treemap(db_session, None, None, None)

        durations = [s["total_duration"] for s in result["suites"]]
        assert durations == sorted(durations, reverse=True)


# --- Test: existing compute functions still work ---


class TestExistingComputeFunctions:
    def test_keyword_frequency_empty(self):
        result = compute_keyword_frequency([])
        assert result["total_calls"] == 0
        assert result["unique_keywords"] == 0

    def test_keyword_frequency_with_data(self):
        keywords = [
            {"name": "Log", "library": "BuiltIn", "type": "kw", "duration": 0.1, "status": "PASS"},
            {"name": "Log", "library": "BuiltIn", "type": "kw", "duration": 0.1, "status": "PASS"},
            {"name": "Sleep", "library": "BuiltIn", "type": "kw", "duration": 1.0, "status": "PASS"},
        ]
        result = compute_keyword_frequency(keywords)
        assert result["total_calls"] == 3
        assert result["unique_keywords"] == 2
        assert result["top_keywords"][0]["name"] == "Log"
        assert result["top_keywords"][0]["count"] == 2

    def test_test_complexity_empty(self):
        result = compute_test_complexity([])
        assert result["avg"] == 0

    def test_library_distribution_empty(self):
        result = compute_library_distribution([])
        assert result["libraries"] == []
