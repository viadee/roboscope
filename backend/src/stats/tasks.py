"""Background tasks for KPI aggregation."""

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func, select

import src.auth.models  # noqa: F401
import src.repos.models  # noqa: F401

from src.database import get_sync_session
from src.execution.models import ExecutionRun, RunStatus
from src.reports.models import Report
from src.stats.models import KpiRecord
from src.stats.analysis import run_analysis  # noqa: F401 — re-export for task registration

logger = logging.getLogger("roboscope.stats.tasks")


def aggregate_daily_kpis(days: int = 365) -> dict:
    """Aggregate daily KPIs from execution runs.

    Covers all dates with runs in the last ``days`` days (default: all).
    Existing KpiRecords are updated (upsert).
    """
    since = date.today() - timedelta(days=days)

    with get_sync_session() as session:
        # Get all distinct (date, repo, branch) combos with runs in the range
        combo_query = select(
            func.date(ExecutionRun.created_at).label("run_date"),
            ExecutionRun.repository_id,
            ExecutionRun.branch,
        ).where(
            func.date(ExecutionRun.created_at) >= since,
        ).distinct()

        combos = session.execute(combo_query).all()

        aggregated = 0
        for row in combos:
            run_date = row.run_date
            repo_id = row.repository_id
            branch = row.branch

            # Normalize run_date (might be string from SQLite)
            if isinstance(run_date, str):
                run_date = date.fromisoformat(run_date)

            # Check if record already exists
            existing = session.execute(
                select(KpiRecord).where(
                    KpiRecord.date == run_date,
                    KpiRecord.repository_id == repo_id,
                    KpiRecord.branch == branch,
                )
            ).scalar_one_or_none()

            # Count runs by status
            runs_query = select(ExecutionRun).where(
                func.date(ExecutionRun.created_at) == run_date,
                ExecutionRun.repository_id == repo_id,
                ExecutionRun.branch == branch,
            )

            total = session.execute(
                select(func.count()).select_from(runs_query.subquery())
            ).scalar() or 0

            passed = session.execute(
                select(func.count()).select_from(
                    runs_query.where(ExecutionRun.status == RunStatus.PASSED).subquery()
                )
            ).scalar() or 0

            failed = session.execute(
                select(func.count()).select_from(
                    runs_query.where(ExecutionRun.status == RunStatus.FAILED).subquery()
                )
            ).scalar() or 0

            error = session.execute(
                select(func.count()).select_from(
                    runs_query.where(ExecutionRun.status == RunStatus.ERROR).subquery()
                )
            ).scalar() or 0

            avg_duration = session.execute(
                select(func.avg(ExecutionRun.duration_seconds)).where(
                    func.date(ExecutionRun.created_at) == run_date,
                    ExecutionRun.repository_id == repo_id,
                    ExecutionRun.branch == branch,
                    ExecutionRun.duration_seconds.is_not(None),
                )
            ).scalar() or 0.0

            success_rate = (passed / total * 100) if total > 0 else 0.0

            if existing:
                existing.total_runs = total
                existing.passed_runs = passed
                existing.failed_runs = failed
                existing.error_runs = error
                existing.avg_duration_seconds = round(avg_duration, 2)
                existing.success_rate = round(success_rate, 1)
            else:
                record = KpiRecord(
                    date=run_date,
                    repository_id=repo_id,
                    branch=branch,
                    total_runs=total,
                    passed_runs=passed,
                    failed_runs=failed,
                    error_runs=error,
                    avg_duration_seconds=round(avg_duration, 2),
                    success_rate=round(success_rate, 1),
                )
                session.add(record)

            aggregated += 1

        session.commit()
        logger.info("Aggregated KPIs for %d repo/branch/date combos", aggregated)
        return {"status": "success", "aggregated": aggregated}


def get_data_status() -> dict:
    """Return timestamps for staleness check.

    Returns the last KPI aggregation date and the last finished run timestamp,
    so the frontend can determine if data is stale.
    """
    with get_sync_session() as session:
        # Last KPI aggregation date
        last_kpi_result = session.execute(
            select(func.max(KpiRecord.date))
        )
        last_kpi_date = last_kpi_result.scalar()

        # Last finished run (terminal status)
        last_run_result = session.execute(
            select(func.max(ExecutionRun.updated_at)).where(
                ExecutionRun.status.in_([
                    RunStatus.PASSED, RunStatus.FAILED, RunStatus.ERROR,
                ])
            )
        )
        last_run_at = last_run_result.scalar()

        # Normalize
        last_aggregated = str(last_kpi_date) if last_kpi_date else None
        last_run_finished = None
        if last_run_at:
            if isinstance(last_run_at, str):
                last_run_finished = last_run_at
            elif isinstance(last_run_at, datetime):
                last_run_finished = last_run_at.isoformat()
            else:
                last_run_finished = str(last_run_at)

        return {
            "last_aggregated": last_aggregated,
            "last_run_finished": last_run_finished,
        }
