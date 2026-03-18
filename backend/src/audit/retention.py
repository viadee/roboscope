"""Retention enforcement — scheduled cleanup of old reports and runs."""

import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select

from src.database import get_sync_session
from src.reports.models import Report, TestResult
from src.execution.models import ExecutionRun

logger = logging.getLogger("roboscope.retention")


def enforce_retention(dry_run: bool = False) -> dict:
    """Delete reports and runs older than the configured retention period.

    Reads report_retention_days from app settings.
    Returns a summary dict with counts of deleted items.
    """
    with get_sync_session() as session:
        # Import models for FK resolution
        import src.auth.models  # noqa: F401
        import src.repos.models  # noqa: F401

        from src.settings.service import get_setting_value

        retention_days_str = get_setting_value(session, "report_retention_days", "90")
        retention_days = int(retention_days_str)

        if retention_days <= 0:
            logger.info("Retention enforcement disabled (retention_days=%d)", retention_days)
            return {"status": "disabled", "deleted_reports": 0, "deleted_runs": 0}

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        # SQLite stores naive datetimes, so strip tz for comparison
        cutoff_naive = cutoff.replace(tzinfo=None)

        logger.info(
            "Retention enforcement: deleting items older than %d days (cutoff: %s, dry_run=%s)",
            retention_days, cutoff.isoformat(), dry_run,
        )

        # Find old reports
        old_reports = session.execute(
            select(Report).where(Report.created_at < cutoff_naive)
        ).scalars().all()

        # Find old runs (without linked reports — those cascade from report delete)
        old_runs = session.execute(
            select(ExecutionRun).where(
                ExecutionRun.created_at < cutoff_naive,
                ExecutionRun.id.notin_(
                    select(Report.execution_run_id).where(Report.execution_run_id.isnot(None))
                ),
            )
        ).scalars().all()

        deleted_reports = len(old_reports)
        deleted_runs = len(old_runs)
        cleaned_dirs = 0

        if dry_run:
            logger.info(
                "DRY RUN — would delete %d reports, %d orphan runs",
                deleted_reports, deleted_runs,
            )
        else:
            # Delete report output directories
            for report in old_reports:
                # Clean up output directory if it exists
                if report.execution_run_id:
                    run = session.execute(
                        select(ExecutionRun).where(ExecutionRun.id == report.execution_run_id)
                    ).scalar_one_or_none()
                    if run and run.output_dir:
                        output_path = Path(run.output_dir)
                        if output_path.exists():
                            shutil.rmtree(output_path, ignore_errors=True)
                            cleaned_dirs += 1

                # Delete test results (cascade should handle this, but be explicit)
                session.execute(
                    delete(TestResult).where(TestResult.report_id == report.id)
                )
                session.delete(report)

            # Delete orphan runs
            for run in old_runs:
                if run.output_dir:
                    output_path = Path(run.output_dir)
                    if output_path.exists():
                        shutil.rmtree(output_path, ignore_errors=True)
                        cleaned_dirs += 1
                session.delete(run)

            session.commit()
            logger.info(
                "Retention enforcement complete: deleted %d reports, %d orphan runs, cleaned %d directories",
                deleted_reports, deleted_runs, cleaned_dirs,
            )

        # Log to audit
        try:
            from src.audit.service import log_audit
            log_audit(
                session,
                action="retention_cleanup",
                resource_type="system",
                detail={
                    "retention_days": retention_days,
                    "deleted_reports": deleted_reports,
                    "deleted_runs": deleted_runs,
                    "cleaned_dirs": cleaned_dirs,
                    "dry_run": dry_run,
                },
            )
            session.commit()
        except Exception:
            logger.debug("Could not log retention audit entry", exc_info=True)

        return {
            "status": "dry_run" if dry_run else "completed",
            "retention_days": retention_days,
            "deleted_reports": deleted_reports,
            "deleted_runs": deleted_runs,
            "cleaned_dirs": cleaned_dirs,
        }
