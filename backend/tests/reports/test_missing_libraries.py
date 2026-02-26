"""Tests for the missing library detection feature."""

import pytest

from src.environments.models import Environment
from src.execution.models import ExecutionRun
from src.explorer.library_mapping import BUILTIN_LIBRARIES
from src.repos.models import Repository
from src.reports.models import Report, TestResult
from src.reports.service import MISSING_LIB_PATTERNS, detect_missing_libraries
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Unit tests: regex patterns
# ---------------------------------------------------------------------------


class TestMissingLibPatterns:
    def test_importing_library_failed(self):
        text = "Importing test library 'Browser' failed: ModuleNotFoundError"
        matches = MISSING_LIB_PATTERNS[0].findall(text)
        assert matches == ["Browser"]

    def test_importing_library_without_test(self):
        text = "Importing library 'SeleniumLibrary' failed: No module"
        matches = MISSING_LIB_PATTERNS[0].findall(text)
        assert matches == ["SeleniumLibrary"]

    def test_no_module_named(self):
        text = "No module named 'robotframework_browser.utils'"
        matches = MISSING_LIB_PATTERNS[1].findall(text)
        assert matches == ["robotframework_browser.utils"]

    def test_no_module_simple(self):
        text = "No module named 'requests'"
        matches = MISSING_LIB_PATTERNS[1].findall(text)
        assert matches == ["requests"]

    def test_no_match_on_unrelated_error(self):
        text = "Element 'id=login-btn' not found on page"
        for pattern in MISSING_LIB_PATTERNS:
            assert pattern.findall(text) == []


# ---------------------------------------------------------------------------
# Service: detect_missing_libraries
# ---------------------------------------------------------------------------


def _setup_full(db_session, admin_user, error_messages, env_id=None):
    """Create repo, env, run, report, and failed test results."""
    repo = Repository(
        name="test-repo",
        git_url="https://github.com/org/test-repo.git",
        default_branch="main",
        local_path="/tmp/workspace/test-repo",
        auto_sync=True,
        sync_interval_minutes=15,
        created_by=admin_user.id,
    )
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)

    run = ExecutionRun(
        repository_id=repo.id,
        target_path="tests/suite.robot",
        branch="main",
        status="failed",
        triggered_by=admin_user.id,
        environment_id=env_id,
    )
    db_session.add(run)
    db_session.flush()
    db_session.refresh(run)

    report = Report(
        execution_run_id=run.id,
        output_xml_path="/tmp/output.xml",
        total_tests=len(error_messages),
        passed_tests=0,
        failed_tests=len(error_messages),
        skipped_tests=0,
        total_duration_seconds=5.0,
    )
    db_session.add(report)
    db_session.flush()
    db_session.refresh(report)

    for i, msg in enumerate(error_messages):
        tr = TestResult(
            report_id=report.id,
            suite_name="Suite",
            test_name=f"Test {i}",
            status="FAIL",
            duration_seconds=1.0,
            error_message=msg,
        )
        db_session.add(tr)
    db_session.flush()

    return report


class TestDetectMissingLibraries:
    def test_detects_missing_library(self, db_session, admin_user):
        report = _setup_full(db_session, admin_user, [
            "Importing test library 'Browser' failed: ModuleNotFoundError",
        ])
        result = detect_missing_libraries(db_session, report.id)
        assert len(result.libraries) == 1
        assert result.libraries[0].library_name == "Browser"
        assert result.libraries[0].pypi_package == "robotframework-browser"

    def test_detects_no_module_named(self, db_session, admin_user):
        report = _setup_full(db_session, admin_user, [
            "No module named 'selenium'",
        ])
        result = detect_missing_libraries(db_session, report.id)
        assert len(result.libraries) == 1
        assert result.libraries[0].library_name == "selenium"

    def test_deduplicates_libraries(self, db_session, admin_user):
        report = _setup_full(db_session, admin_user, [
            "Importing library 'Browser' failed: ModuleNotFoundError",
            "Importing library 'Browser' failed: ModuleNotFoundError",
        ])
        result = detect_missing_libraries(db_session, report.id)
        assert len(result.libraries) == 1

    def test_skips_builtin_libraries(self, db_session, admin_user):
        report = _setup_full(db_session, admin_user, [
            "Importing library 'Collections' failed: unexpected error",
        ])
        result = detect_missing_libraries(db_session, report.id)
        assert len(result.libraries) == 0

    def test_handles_dotted_module(self, db_session, admin_user):
        report = _setup_full(db_session, admin_user, [
            "No module named 'robotframework_browser.utils'",
        ])
        result = detect_missing_libraries(db_session, report.id)
        assert len(result.libraries) == 1
        assert result.libraries[0].library_name == "robotframework_browser"

    def test_resolves_environment(self, db_session, admin_user):
        env = Environment(
            name="test-env",
            python_version="3.12",
            venv_path="/tmp/venv",
            created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        report = _setup_full(db_session, admin_user, [
            "Importing library 'Browser' failed: ModuleNotFoundError",
        ], env_id=env.id)

        result = detect_missing_libraries(db_session, report.id)
        assert result.environment_id == env.id
        assert result.environment_name == "test-env"

    def test_no_environment(self, db_session, admin_user):
        report = _setup_full(db_session, admin_user, [
            "Importing library 'Browser' failed: ModuleNotFoundError",
        ], env_id=None)
        result = detect_missing_libraries(db_session, report.id)
        assert result.environment_id is None
        assert result.environment_name is None

    def test_nonexistent_report(self, db_session, admin_user):
        result = detect_missing_libraries(db_session, 99999)
        assert result.libraries == []

    def test_no_failed_tests(self, db_session, admin_user):
        report = _setup_full(db_session, admin_user, [])
        result = detect_missing_libraries(db_session, report.id)
        assert result.libraries == []


# ---------------------------------------------------------------------------
# Router: GET /reports/{id}/missing-libraries
# ---------------------------------------------------------------------------


class TestMissingLibrariesEndpoint:
    def test_returns_missing_libraries(self, client, db_session, admin_user):
        report = _setup_full(db_session, admin_user, [
            "Importing library 'Browser' failed: ModuleNotFoundError",
        ])

        response = client.get(
            f"/api/v1/reports/{report.id}/missing-libraries",
            headers=auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["libraries"]) == 1
        assert data["libraries"][0]["library_name"] == "Browser"
        assert data["libraries"][0]["pypi_package"] == "robotframework-browser"

    def test_report_not_found(self, client, admin_user):
        response = client.get(
            "/api/v1/reports/99999/missing-libraries",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_unauthenticated(self, client):
        response = client.get("/api/v1/reports/1/missing-libraries")
        assert response.status_code == 401
