"""Tests for the reports service (CRUD, comparison)."""

import pytest

from src.execution.models import ExecutionRun
from src.repos.models import Repository
from src.reports.models import Report, TestResult
from src.reports.service import (
    compare_reports,
    get_report,
    get_report_by_run,
    get_test_results,
    list_reports,
)


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


def _setup_repo_and_run(db_session, admin_user, **run_overrides):
    """Create a Repository and ExecutionRun, return (repo, run)."""
    repo = _make_repo(admin_user.id)
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)

    run = _make_run(repo.id, admin_user.id, **run_overrides)
    db_session.add(run)
    db_session.flush()
    db_session.refresh(run)

    return repo, run


class TestListReports:
    def test_list_empty(self, db_session):
        """Listing reports on an empty database returns an empty list."""
        reports, total = list_reports(db_session)

        assert reports == []
        assert total == 0

    def test_list_with_reports(self, db_session, admin_user):
        """Listing reports returns all existing reports and correct total."""
        repo, run_a = _setup_repo_and_run(db_session, admin_user)

        run_b = _make_run(repo.id, admin_user.id)
        db_session.add(run_b)
        db_session.flush()
        db_session.refresh(run_b)

        report_a = _make_report(run_a.id, total_tests=3, passed_tests=3, failed_tests=0)
        report_b = _make_report(run_b.id, total_tests=5, passed_tests=4, failed_tests=1)
        db_session.add_all([report_a, report_b])
        db_session.flush()

        reports, total = list_reports(db_session)

        assert total == 2
        assert len(reports) == 2

    def test_list_with_pagination(self, db_session, admin_user):
        """Pagination returns the correct page slice."""
        repo = _make_repo(admin_user.id)
        db_session.add(repo)
        db_session.flush()
        db_session.refresh(repo)

        # Create 3 runs + reports
        for i in range(3):
            run = _make_run(repo.id, admin_user.id)
            db_session.add(run)
            db_session.flush()
            db_session.refresh(run)

            report = _make_report(run.id, total_tests=i + 1)
            db_session.add(report)

        db_session.flush()

        reports, total = list_reports(db_session, page=1, page_size=2)

        assert total == 3
        assert len(reports) == 2

    def test_list_filter_by_repository(self, db_session, admin_user):
        """Filtering by repository_id returns only reports for that repo."""
        repo_a = _make_repo(admin_user.id, name="repo-a")
        repo_b = _make_repo(admin_user.id, name="repo-b")
        db_session.add_all([repo_a, repo_b])
        db_session.flush()
        db_session.refresh(repo_a)
        db_session.refresh(repo_b)

        run_a = _make_run(repo_a.id, admin_user.id)
        run_b = _make_run(repo_b.id, admin_user.id)
        db_session.add_all([run_a, run_b])
        db_session.flush()
        db_session.refresh(run_a)
        db_session.refresh(run_b)

        report_a = _make_report(run_a.id)
        report_b = _make_report(run_b.id)
        db_session.add_all([report_a, report_b])
        db_session.flush()

        reports, total = list_reports(db_session, repository_id=repo_a.id)

        assert total == 1
        assert len(reports) == 1


class TestGetReport:
    def test_get_found(self, db_session, admin_user):
        """Getting a report by ID returns the report when it exists."""
        _, run = _setup_repo_and_run(db_session, admin_user)

        report = _make_report(run.id)
        db_session.add(report)
        db_session.flush()
        db_session.refresh(report)

        result = get_report(db_session, report.id)

        assert result is not None
        assert result.id == report.id
        assert result.total_tests == 5

    def test_get_not_found(self, db_session):
        """Getting a nonexistent report returns None."""
        result = get_report(db_session, 99999)

        assert result is None


class TestGetReportByRun:
    def test_get_by_run_found(self, db_session, admin_user):
        """Getting a report by execution run ID returns the report."""
        _, run = _setup_repo_and_run(db_session, admin_user)

        report = _make_report(run.id, total_tests=7)
        db_session.add(report)
        db_session.flush()
        db_session.refresh(report)

        result = get_report_by_run(db_session, run.id)

        assert result is not None
        assert result.execution_run_id == run.id
        assert result.total_tests == 7

    def test_get_by_run_not_found(self, db_session):
        """Getting a report for a nonexistent run returns None."""
        result = get_report_by_run(db_session, 99999)

        assert result is None


class TestGetTestResults:
    def test_get_results(self, db_session, admin_user):
        """Fetching test results for a report returns all results."""
        _, run = _setup_repo_and_run(db_session, admin_user)

        report = _make_report(run.id)
        db_session.add(report)
        db_session.flush()
        db_session.refresh(report)

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

        results = get_test_results(db_session, report.id)

        assert len(results) == 2
        names = [r.test_name for r in results]
        assert "Login Test" in names
        assert "Logout Test" in names

    def test_get_results_ordered(self, db_session, admin_user):
        """Test results are ordered by suite_name, then test_name."""
        _, run = _setup_repo_and_run(db_session, admin_user)

        report = _make_report(run.id)
        db_session.add(report)
        db_session.flush()
        db_session.refresh(report)

        tr_z = _make_test_result(report.id, test_name="Z Test", suite_name="B Suite")
        tr_a = _make_test_result(report.id, test_name="A Test", suite_name="A Suite")
        tr_m = _make_test_result(report.id, test_name="M Test", suite_name="A Suite")
        db_session.add_all([tr_z, tr_a, tr_m])
        db_session.flush()

        results = get_test_results(db_session, report.id)

        assert results[0].suite_name == "A Suite"
        assert results[0].test_name == "A Test"
        assert results[1].suite_name == "A Suite"
        assert results[1].test_name == "M Test"
        assert results[2].suite_name == "B Suite"
        assert results[2].test_name == "Z Test"

    def test_get_results_empty(self, db_session, admin_user):
        """Fetching results for a report with no test results returns empty list."""
        _, run = _setup_repo_and_run(db_session, admin_user)

        report = _make_report(run.id)
        db_session.add(report)
        db_session.flush()
        db_session.refresh(report)

        results = get_test_results(db_session, report.id)

        assert results == []


class TestCompareReports:
    def _setup_two_reports(self, db_session, admin_user):
        """Create two reports with their supporting objects and return them."""
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
            run_a.id,
            total_tests=3,
            passed_tests=2,
            failed_tests=1,
            total_duration_seconds=10.0,
        )
        report_b = _make_report(
            run_b.id,
            total_tests=3,
            passed_tests=2,
            failed_tests=1,
            total_duration_seconds=12.0,
        )
        db_session.add_all([report_a, report_b])
        db_session.flush()
        db_session.refresh(report_a)
        db_session.refresh(report_b)

        return report_a, report_b

    def test_compare_new_failures(self, db_session, admin_user):
        """A test that was PASS in A and FAIL in B is a new failure."""
        report_a, report_b = self._setup_two_reports(db_session, admin_user)

        # Report A: test passes
        db_session.add(
            _make_test_result(report_a.id, test_name="Fragile Test", status="PASS")
        )
        # Report B: same test fails
        db_session.add(
            _make_test_result(report_b.id, test_name="Fragile Test", status="FAIL")
        )
        db_session.flush()

        comparison = compare_reports(db_session, report_a.id, report_b.id)

        assert "Fragile Test" in comparison.new_failures
        assert "Fragile Test" not in comparison.fixed_tests
        assert "Fragile Test" not in comparison.consistent_failures

    def test_compare_fixed_tests(self, db_session, admin_user):
        """A test that was FAIL in A and PASS in B is fixed."""
        report_a, report_b = self._setup_two_reports(db_session, admin_user)

        db_session.add(
            _make_test_result(report_a.id, test_name="Fixed Test", status="FAIL")
        )
        db_session.add(
            _make_test_result(report_b.id, test_name="Fixed Test", status="PASS")
        )
        db_session.flush()

        comparison = compare_reports(db_session, report_a.id, report_b.id)

        assert "Fixed Test" in comparison.fixed_tests
        assert "Fixed Test" not in comparison.new_failures
        assert "Fixed Test" not in comparison.consistent_failures

    def test_compare_consistent_failures(self, db_session, admin_user):
        """A test that was FAIL in both A and B is a consistent failure."""
        report_a, report_b = self._setup_two_reports(db_session, admin_user)

        db_session.add(
            _make_test_result(report_a.id, test_name="Always Broken", status="FAIL")
        )
        db_session.add(
            _make_test_result(report_b.id, test_name="Always Broken", status="FAIL")
        )
        db_session.flush()

        comparison = compare_reports(db_session, report_a.id, report_b.id)

        assert "Always Broken" in comparison.consistent_failures
        assert "Always Broken" not in comparison.new_failures
        assert "Always Broken" not in comparison.fixed_tests

    def test_compare_duration_diff(self, db_session, admin_user):
        """Duration diff is report_b duration minus report_a duration."""
        report_a, report_b = self._setup_two_reports(db_session, admin_user)

        comparison = compare_reports(db_session, report_a.id, report_b.id)

        # report_a duration=10.0, report_b duration=12.0
        assert comparison.duration_diff_seconds == pytest.approx(2.0)

    def test_compare_mixed_results(self, db_session, admin_user):
        """Comparison correctly categorises multiple tests across all buckets."""
        report_a, report_b = self._setup_two_reports(db_session, admin_user)

        # New failure
        db_session.add(_make_test_result(report_a.id, test_name="Test A", status="PASS"))
        db_session.add(_make_test_result(report_b.id, test_name="Test A", status="FAIL"))
        # Fixed
        db_session.add(_make_test_result(report_a.id, test_name="Test B", status="FAIL"))
        db_session.add(_make_test_result(report_b.id, test_name="Test B", status="PASS"))
        # Consistent failure
        db_session.add(_make_test_result(report_a.id, test_name="Test C", status="FAIL"))
        db_session.add(_make_test_result(report_b.id, test_name="Test C", status="FAIL"))
        # Both pass (not in any diff bucket)
        db_session.add(_make_test_result(report_a.id, test_name="Test D", status="PASS"))
        db_session.add(_make_test_result(report_b.id, test_name="Test D", status="PASS"))
        db_session.flush()

        comparison = compare_reports(db_session, report_a.id, report_b.id)

        assert comparison.new_failures == ["Test A"]
        assert comparison.fixed_tests == ["Test B"]
        assert comparison.consistent_failures == ["Test C"]

    def test_compare_report_not_found_raises(self, db_session, admin_user):
        """Comparing with a nonexistent report raises ValueError."""
        _, run = _setup_repo_and_run(db_session, admin_user)

        report = _make_report(run.id)
        db_session.add(report)
        db_session.flush()
        db_session.refresh(report)

        with pytest.raises(ValueError, match="One or both reports not found"):
            compare_reports(db_session, report.id, 99999)

    def test_compare_both_not_found_raises(self, db_session):
        """Comparing two nonexistent reports raises ValueError."""
        with pytest.raises(ValueError, match="One or both reports not found"):
            compare_reports(db_session, 99999, 88888)
