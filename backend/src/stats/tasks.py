"""Background tasks for KPI aggregation."""

import logging
from datetime import date

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.config import settings

import src.auth.models  # noqa: F401
import src.repos.models  # noqa: F401

from src.execution.models import ExecutionRun, RunStatus
from src.reports.models import Report
from src.stats.models import KpiRecord

logger = logging.getLogger("mateox.stats.tasks")

_sync_url = settings.sync_database_url
_sync_engine = create_engine(_sync_url)


def _get_sync_session() -> Session:
    return Session(_sync_engine)


def aggregate_daily_kpis() -> dict:
    """Aggregate daily KPIs from execution runs."""
    today = date.today()

    with _get_sync_session() as session:
        # Get all repos that had runs today
        repo_query = select(
            ExecutionRun.repository_id,
            ExecutionRun.branch,
        ).where(
            func.date(ExecutionRun.created_at) == today,
        ).distinct()

        repos = session.execute(repo_query).all()

        aggregated = 0
        for row in repos:
            repo_id = row.repository_id
            branch = row.branch

            # Check if record already exists for today
            existing = session.execute(
                select(KpiRecord).where(
                    KpiRecord.date == today,
                    KpiRecord.repository_id == repo_id,
                    KpiRecord.branch == branch,
                )
            ).scalar_one_or_none()

            # Count runs by status
            runs_query = select(ExecutionRun).where(
                func.date(ExecutionRun.created_at) == today,
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
                    func.date(ExecutionRun.created_at) == today,
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
                    date=today,
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
        logger.info("Aggregated KPIs for %d repo/branch combos on %s", aggregated, today)
        return {"status": "success", "aggregated": aggregated, "date": str(today)}
