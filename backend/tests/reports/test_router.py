"""Tests for the reports API endpoints."""

import pytest

from src.execution.models import ExecutionRun
from src.repos.models import Repository
from src.reports.models import Report, TestResult
from tests.conftest import auth_header


def _make_repo(user_id: int, **overrides) -> Repository:
    """Helper to build a Repository instance with sensible defaults."""
    defaults = {
        "name": "test-repo",
        "git_url": "https://github.com/org/test-repo.git",
        "default_branch": "main",
        "local_path": "/tmp/workspace/test-repo",
        "auto_sync": True,
        "sync_interval_minutes": 15,
        "created_by": user_id,
    }
    defaults.update(overrides)
    return Repository(**defaults)


def _make_run(repo_id: int, user_id: int, **overrides) -> ExecutionRun:
    """Helper to build an ExecutionRun instance with sensible defaults."""
    defaults = {
        "repository_id": repo_id,
        "target_path": "tests/suite.robot",
        "branch": "main",
        "status": "passed",
        "triggered_by": user_id,
    }
    defaults.update(overrides)
    return ExecutionRun(**defaults)


def _make_report(run_id: int, **overrides) -> Report:
    """Helper to build a Report instance with sensible defaults."""
    defaults = {
        "execution_run_id": run_id,
        "output_xml_path": "/tmp/output.xml",
        "total_tests": 5,
        "passed_tests": 4,
        "failed_tests": 1,
        "skipped_tests": 0,
        "total_duration_seconds": 10.5,
    }
    defaults.update(overrides)
    return Report(**defaults)


def _make_test_result(report_id: int, **overrides) -> TestResult:
    """Helper to build a TestResult instance with sensible defaults."""
    defaults = {
        "report_id": report_id,
        "suite_name": "Test Suite",
        "test_name": "Test Case",
        "status": "PASS",
        "duration_seconds": 1.0,
    }
    defaults.update(overrides)
    return TestResult(**defaults)


def _setup_report(db_session, admin_user, **report_overrides):
    """Create a Repository, ExecutionRun, and Report. Return the report."""
    repo = _make_repo(admin_user.id)
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)

    run = _make_run(repo.id, admin_user.id)
    db_session.add(run)
    db_session.flush()
    db_session.refresh(run)

    report = _make_report(run.id, **report_overrides)
    db_session.add(report)
    db_session.flush()
    db_session.refresh(report)

    return report


class TestListReportsEndpoint:
    def test_list_reports_authenticated(self, client, db_session, admin_user):
        """GET /api/v1/reports returns a list of reports for authenticated users."""
        report = _setup_report(db_session, admin_user)

        response = client.get(
            "/api/v1/reports",
            headers=auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == report.id
        assert data[0]["total_tests"] == 5
        assert data[0]["passed_tests"] == 4
        assert data[0]["failed_tests"] == 1

    def test_list_reports_empty(self, client, admin_user):
        """GET /api/v1/reports returns an empty list when no reports exist."""
        response = client.get(
            "/api/v1/reports",
            headers=auth_header(admin_user),
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_list_reports_unauthenticated(self, client):
        """GET /api/v1/reports without a token returns 401."""
        response = client.get("/api/v1/reports")

        assert response.status_code == 401


class TestGetReportDetailEndpoint:
    def test_get_report_with_test_results(self, client, db_session, admin_user):
        """GET /api/v1/reports/{id} returns a report with its test results."""
        report = _setup_report(db_session, admin_user)

        tr_a = _make_test_result(
            report.id,
            test_name="Login Test",
            suite_name="Auth Suite",
            status="PASS",
            duration_seconds=1.5,
        )
        tr_b = _make_test_result(
            report.id,
            test_name="Logout Test",
            suite_name="Auth Suite",
            status="FAIL",
            duration_seconds=0.8,
            error_message="Element not found",
        )
        db_session.add_all([tr_a, tr_b])
        db_session.flush()

        response = client.get(
            f"/api/v1/reports/{report.id}",
            headers=auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["report"]["id"] == report.id
        assert data["report"]["total_tests"] == 5
        assert len(data["test_results"]) == 2

        test_names = [tr["test_name"] for tr in data["test_results"]]
        assert "Login Test" in test_names
        assert "Logout Test" in test_names

    def test_get_report_not_found(self, client, admin_user):
        """GET /api/v1/reports/{id} for a nonexistent report returns 404."""
        response = client.get(
            "/api/v1/reports/99999",
            headers=auth_header(admin_user),
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_report_unauthenticated(self, client):
        """GET /api/v1/reports/{id} without a token returns 401."""
        response = client.get("/api/v1/reports/1")

        assert response.status_code == 401


class TestGetReportTestsEndpoint:
    def test_get_tests(self, client, db_session, admin_user):
        """GET /api/v1/reports/{id}/tests returns all test results."""
        report = _setup_report(db_session, admin_user)

        tr_pass = _make_test_result(
            report.id, test_name="Pass Test", status="PASS"
        )
        tr_fail = _make_test_result(
            report.id, test_name="Fail Test", status="FAIL", error_message="Broken"
        )
        db_session.add_all([tr_pass, tr_fail])
        db_session.flush()

        response = client.get(
            f"/api/v1/reports/{report.id}/tests",
            headers=auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_get_tests_with_status_filter(self, client, db_session, admin_user):
        """GET /api/v1/reports/{id}/tests?status=FAIL returns only failing tests."""
        report = _setup_report(db_session, admin_user)

        tr_pass = _make_test_result(
            report.id, test_name="Pass Test", status="PASS"
        )
        tr_fail = _make_test_result(
            report.id, test_name="Fail Test", status="FAIL"
        )
        db_session.add_all([tr_pass, tr_fail])
        db_session.flush()

        response = client.get(
            f"/api/v1/reports/{report.id}/tests",
            params={"status": "FAIL"},
            headers=auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["test_name"] == "Fail Test"
        assert data[0]["status"] == "FAIL"

    def test_get_tests_report_not_found(self, client, admin_user):
        """GET /api/v1/reports/{id}/tests for a nonexistent report returns 404."""
        response = client.get(
            "/api/v1/reports/99999/tests",
            headers=auth_header(admin_user),
        )

        assert response.status_code == 404

    def test_get_tests_unauthenticated(self, client):
        """GET /api/v1/reports/{id}/tests without a token returns 401."""
        response = client.get("/api/v1/reports/1/tests")

        assert response.status_code == 401


class TestCompareReportsEndpoint:
    def test_compare(self, client, db_session, admin_user):
        """GET /api/v1/reports/compare?report_a=X&report_b=Y returns comparison."""
        repo = _make_repo(admin_user.id)
        db_session.add(repo)
        db_session.flush()
        db_session.refresh(repo)

        run_a = _make_run(repo.id, admin_user.id)
        db_session.add(run_a)
        db_session.flush()
        db_session.refresh(run_a)

        run_b = _make_run(repo.id, admin_user.id)
        db_session.add(run_b)
        db_session.flush()
        db_session.refresh(run_b)

        report_a = _make_report(
            run_a.id, total_tests=3, passed_tests=2, failed_tests=1,
            total_duration_seconds=10.0,
        )
        report_b = _make_report(
            run_b.id, total_tests=3, passed_tests=2, failed_tests=1,
            total_duration_seconds=15.0,
        )
        db_session.add_all([report_a, report_b])
        db_session.flush()
        db_session.refresh(report_a)
        db_session.refresh(report_b)

        # New failure: PASS -> FAIL
        db_session.add(_make_test_result(report_a.id, test_name="Test X", status="PASS"))
        db_session.add(_make_test_result(report_b.id, test_name="Test X", status="FAIL"))
        # Fixed: FAIL -> PASS
        db_session.add(_make_test_result(report_a.id, test_name="Test Y", status="FAIL"))
        db_session.add(_make_test_result(report_b.id, test_name="Test Y", status="PASS"))
        # Consistent failure
        db_session.add(_make_test_result(report_a.id, test_name="Test Z", status="FAIL"))
        db_session.add(_make_test_result(report_b.id, test_name="Test Z", status="FAIL"))
        db_session.flush()

        response = client.get(
            "/api/v1/reports/compare",
            params={"report_a": report_a.id, "report_b": report_b.id},
            headers=auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["report_a"]["id"] == report_a.id
        assert data["report_b"]["id"] == report_b.id
        assert data["new_failures"] == ["Test X"]
        assert data["fixed_tests"] == ["Test Y"]
        assert data["consistent_failures"] == ["Test Z"]
        assert data["duration_diff_seconds"] == pytest.approx(5.0)

    def test_compare_report_not_found(self, client, db_session, admin_user):
        """GET /api/v1/reports/compare with a nonexistent report returns 404."""
        report = _setup_report(db_session, admin_user)

        response = client.get(
            "/api/v1/reports/compare",
            params={"report_a": report.id, "report_b": 99999},
            headers=auth_header(admin_user),
        )

        assert response.status_code == 404

    def test_compare_unauthenticated(self, client):
        """GET /api/v1/reports/compare without a token returns 401."""
        response = client.get(
            "/api/v1/reports/compare",
            params={"report_a": 1, "report_b": 2},
        )

        assert response.status_code == 401
