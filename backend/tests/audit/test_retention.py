"""Tests for retention enforcement."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from tests.conftest import auth_header


class TestRetentionService:
    """Unit tests for enforce_retention()."""

    def _make_old_report(self, db_session, days_old=100):
        """Create a report with an old created_at timestamp."""
        from src.reports.models import Report
        import src.auth.models  # noqa: F401
        import src.repos.models  # noqa: F401

        old_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        report = Report(
            total_tests=5,
            passed_tests=3,
            failed_tests=2,
            skipped_tests=0,
            total_duration_seconds=10.0,
            output_xml_path="/tmp/fake-output.xml",
        )
        db_session.add(report)
        db_session.flush()
        # Manually set created_at to old date
        report.created_at = old_date.replace(tzinfo=None)
        db_session.flush()
        db_session.refresh(report)
        return report

    def _make_recent_report(self, db_session):
        """Create a report with a recent timestamp."""
        from src.reports.models import Report
        report = Report(
            total_tests=1,
            passed_tests=1,
            failed_tests=0,
            skipped_tests=0,
            total_duration_seconds=1.0,
            output_xml_path="/tmp/recent-output.xml",
        )
        db_session.add(report)
        db_session.flush()
        return report

    def test_dry_run_does_not_delete(self, db_session: Session, admin_user):
        """Dry run counts but doesn't delete."""
        self._make_old_report(db_session, days_old=100)

        # Mock get_sync_session to return our test session
        with patch("src.audit.retention.get_sync_session") as mock_session:
            mock_session.return_value.__enter__ = lambda s: db_session
            mock_session.return_value.__exit__ = lambda s, *a: None

            from src.audit.retention import enforce_retention
            result = enforce_retention(dry_run=True)

        assert result["status"] == "dry_run"
        assert result["deleted_reports"] == 1

        # Report should still exist
        from src.reports.models import Report
        from sqlalchemy import select
        reports = db_session.execute(select(Report)).scalars().all()
        assert len(reports) == 1

    def test_actual_run_deletes_old_reports(self, db_session: Session, admin_user):
        """Actual run deletes old reports."""
        self._make_old_report(db_session, days_old=100)
        self._make_recent_report(db_session)

        with patch("src.audit.retention.get_sync_session") as mock_session:
            mock_session.return_value.__enter__ = lambda s: db_session
            mock_session.return_value.__exit__ = lambda s, *a: None

            from src.audit.retention import enforce_retention
            result = enforce_retention(dry_run=False)

        assert result["status"] == "completed"
        assert result["deleted_reports"] == 1

        # Recent report should still exist
        from src.reports.models import Report
        from sqlalchemy import select
        reports = db_session.execute(select(Report)).scalars().all()
        assert len(reports) == 1

    def test_disabled_when_retention_zero(self, db_session: Session):
        """Retention disabled when days=0."""
        with patch("src.audit.retention.get_sync_session") as mock_session:
            mock_session.return_value.__enter__ = lambda s: db_session
            mock_session.return_value.__exit__ = lambda s, *a: None

            # Seed setting with 0
            from src.settings.models import AppSetting
            setting = AppSetting(key="report_retention_days", value="0", value_type="int", category="retention")
            db_session.add(setting)
            db_session.flush()

            from src.audit.retention import enforce_retention
            result = enforce_retention()

        assert result["status"] == "disabled"


class TestRetentionRouter:
    """API endpoint tests for retention trigger."""

    def test_trigger_dry_run(self, client, admin_user):
        resp = client.post(
            "/api/v1/audit/retention/run?dry_run=true",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("dry_run", "disabled", "completed")

    def test_trigger_non_admin_forbidden(self, client, runner_user):
        resp = client.post(
            "/api/v1/audit/retention/run",
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 403
