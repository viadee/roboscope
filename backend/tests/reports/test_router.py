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


class TestUniqueTestsEndpoint:
    def test_list_unique_tests(self, client, db_session, admin_user):
        """GET /api/v1/reports/tests/unique returns unique test names."""
        report = _setup_report(db_session, admin_user)
        db_session.add(
            _make_test_result(report.id, test_name="Login Test", suite_name="Auth")
        )
        db_session.add(
            _make_test_result(report.id, test_name="Search Test", suite_name="UI")
        )
        db_session.flush()

        response = client.get(
            "/api/v1/reports/tests/unique",
            headers=auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        names = [t["test_name"] for t in data]
        assert "Login Test" in names

    def test_list_unique_tests_with_search(self, client, db_session, admin_user):
        """GET /api/v1/reports/tests/unique?search=Login filters by name."""
        report = _setup_report(db_session, admin_user)
        db_session.add(
            _make_test_result(report.id, test_name="Login Test", suite_name="Auth")
        )
        db_session.add(
            _make_test_result(report.id, test_name="Search Test", suite_name="UI")
        )
        db_session.flush()

        response = client.get(
            "/api/v1/reports/tests/unique",
            params={"search": "Login"},
            headers=auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["test_name"] == "Login Test"

    def test_list_unique_tests_unauthenticated(self, client):
        """GET /api/v1/reports/tests/unique without token returns 401."""
        response = client.get("/api/v1/reports/tests/unique")
        assert response.status_code == 401


class TestTestHistoryEndpoint:
    def test_get_test_history(self, client, db_session, admin_user):
        """GET /api/v1/reports/tests/history returns history for a test."""
        report = _setup_report(db_session, admin_user)
        db_session.add(
            _make_test_result(
                report.id, test_name="Login Test", suite_name="Auth", status="PASS",
                duration_seconds=2.5,
            )
        )
        db_session.flush()

        response = client.get(
            "/api/v1/reports/tests/history",
            params={"test_name": "Login Test"},
            headers=auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["test_name"] == "Login Test"
        assert data["total_runs"] == 1
        assert data["pass_count"] == 1
        assert data["fail_count"] == 0
        assert data["pass_rate"] == 100.0
        assert len(data["history"]) == 1
        assert data["history"][0]["status"] == "PASS"

    def test_get_test_history_empty(self, client, admin_user):
        """GET /api/v1/reports/tests/history for unknown test returns empty history."""
        response = client.get(
            "/api/v1/reports/tests/history",
            params={"test_name": "Nonexistent Test"},
            headers=auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_runs"] == 0
        assert data["history"] == []

    def test_get_test_history_requires_test_name(self, client, admin_user):
        """GET /api/v1/reports/tests/history without test_name returns 422."""
        response = client.get(
            "/api/v1/reports/tests/history",
            headers=auth_header(admin_user),
        )

        assert response.status_code == 422

    def test_get_test_history_unauthenticated(self, client):
        """GET /api/v1/reports/tests/history without token returns 401."""
        response = client.get(
            "/api/v1/reports/tests/history",
            params={"test_name": "Test"},
        )
        assert response.status_code == 401


class TestReportAssetEndpoint:
    """Story REPORT-1 — `/reports/{id}/assets/{path}` is no longer
    anonymous; auth is required via Bearer header or `?token=<jwt>`.
    Path-traversal protection is layered on top of auth.
    """

    @pytest.fixture
    def report_with_asset(self, db_session, admin_user, tmp_path):
        """Set up a Report row whose `output_xml_path` lives in tmp_path
        and seed a real asset file beside it."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (output_dir / "output.xml").write_text("<robot/>", encoding="utf-8")
        (output_dir / "screenshot.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-image")
        report = _setup_report(
            db_session, admin_user,
            output_xml_path=str(output_dir / "output.xml"),
        )
        return report

    def test_rejects_anonymous(self, client, report_with_asset):
        """No Bearer, no ?token → 401."""
        resp = client.get(
            f"/api/v1/reports/{report_with_asset.id}/assets/screenshot.png",
        )
        assert resp.status_code == 401

    def test_accepts_bearer(self, client, admin_user, report_with_asset):
        """Authorization: Bearer <jwt> → 200."""
        resp = client.get(
            f"/api/v1/reports/{report_with_asset.id}/assets/screenshot.png",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.content.startswith(b"\x89PNG")

    def test_accepts_query_token(self, client, admin_user, report_with_asset):
        """`?token=<jwt>` → 200 — the iframe path."""
        from src.auth.service import create_access_token

        token = create_access_token(admin_user.id, admin_user.role)
        resp = client.get(
            f"/api/v1/reports/{report_with_asset.id}/assets/screenshot.png",
            params={"token": token},
        )
        assert resp.status_code == 200
        assert resp.content.startswith(b"\x89PNG")

    def test_rejects_garbage_token(self, client, report_with_asset):
        """Random `?token=` value → 401."""
        resp = client.get(
            f"/api/v1/reports/{report_with_asset.id}/assets/screenshot.png",
            params={"token": "not-a-real-jwt"},
        )
        assert resp.status_code == 401

    def test_rejects_refresh_token(self, client, admin_user, report_with_asset):
        """Refresh tokens (type='refresh') must NOT unlock asset access."""
        from src.auth.service import create_refresh_token

        rtok = create_refresh_token(admin_user.id)
        resp = client.get(
            f"/api/v1/reports/{report_with_asset.id}/assets/screenshot.png",
            params={"token": rtok},
        )
        assert resp.status_code == 401

    def test_path_traversal_still_blocked(
        self, client, admin_user, report_with_asset,
    ):
        """Even authenticated, `../` paths are rejected (regression guard)."""
        resp = client.get(
            f"/api/v1/reports/{report_with_asset.id}/assets/..%2F..%2Fetc%2Fpasswd",
            headers=auth_header(admin_user),
        )
        # FastAPI's URL decoding may yield 403 (our explicit check) or 404
        # (if the resolved path is missing) — both are acceptable, what
        # matters is that we don't return /etc/passwd contents.
        assert resp.status_code in (403, 404)

    def test_html_report_base_href_contains_token(
        self, client, admin_user, db_session, tmp_path,
    ):
        """The injected `<base>` tag must include the access token so
        iframe-loaded asset requests inherit auth via query param.
        """
        # Set up a minimal HTML report on disk and point the Report row
        # at it.
        out = tmp_path / "out"
        out.mkdir()
        html_path = out / "report.html"
        html_path.write_text(
            "<html><head><title>R</title></head><body><img src='shot.png'></body></html>",
            encoding="utf-8",
        )
        (out / "output.xml").write_text("<robot/>", encoding="utf-8")
        report = _setup_report(
            db_session, admin_user,
            output_xml_path=str(out / "output.xml"),
            report_html_path=str(html_path),
        )

        resp = client.get(
            f"/api/v1/reports/{report.id}/html",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.text
        assert f'<base href="/api/v1/reports/{report.id}/assets/?token=' in body
