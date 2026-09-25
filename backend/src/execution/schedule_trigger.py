"""Schedule heartbeat: fire due schedules (registered per-minute in main.py)."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

# FK model imports so the bg-thread session can resolve every FK.
import src.auth.models  # noqa: F401
import src.environments.models  # noqa: F401
import src.repos.models  # noqa: F401
from src.auth.models import User
from src.database import get_sync_session
from src.execution.models import ExecutionRun, RunStatus, Schedule
from src.execution.service import compute_next_run, create_run_from_schedule
from src.repos.models import Repository

logger = logging.getLogger("roboscope.execution.schedules")


def _skip_reason(session, schedule: Schedule) -> str | None:
    creator = session.get(User, schedule.created_by)
    if creator is None or not creator.is_active:
        return "creator is inactive or deleted"
    if session.get(Repository, schedule.repository_id) is None:
        return "repository no longer exists"
    busy = session.execute(
        select(ExecutionRun.id).where(
            ExecutionRun.schedule_id == schedule.id,
            ExecutionRun.status.in_([RunStatus.PENDING, RunStatus.RUNNING]),
        ).limit(1)
    ).first()
    if busy:
        return f"previous run {busy[0]} is still pending/running"
    return None


def run_due_schedules(now: datetime | None = None) -> dict:
    """Fire every active schedule whose `next_run_at <= now`.

    Each due schedule fires at most once per tick and its `next_run_at`
    is recomputed from `now`, so a backend that was down for hours
    coalesces all missed slots into a single run. Runs in the APScheduler
    thread, so it never raises.
    """
    now = now or datetime.now(timezone.utc)
    now_naive = now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo else now
    fired: list[int] = []
    skipped: list[int] = []
    try:
        with get_sync_session() as session:
            # Active schedules created before next_run_at was maintained.
            for s in session.scalars(
                select(Schedule).where(Schedule.is_active.is_(True), Schedule.next_run_at.is_(None))
            ).all():
                try:
                    s.next_run_at = compute_next_run(s.cron_expression, now)
                except ValueError:
                    logger.warning(
                        "Schedule %d has an invalid cron %r; pausing it", s.id, s.cron_expression
                    )
                    s.is_active = False
            session.commit()

            due = session.scalars(
                select(Schedule).where(
                    Schedule.is_active.is_(True), Schedule.next_run_at <= now_naive
                )
            ).all()
            for s in due:
                s.next_run_at = compute_next_run(s.cron_expression, now)
                reason = _skip_reason(session, s)
                if reason:
                    logger.warning("Schedule %d (%s) skipped: %s", s.id, s.name, reason)
                    skipped.append(s.id)
                    session.commit()
                    continue
                run = create_run_from_schedule(session, s, s.created_by, now)
                logger.info("Schedule %d (%s) fired run %d", s.id, s.name, run.id)
                fired.append(run.id)
    except Exception:
        logger.exception("Schedule heartbeat failed")
        return {"fired": fired, "skipped": skipped, "error": True}
    return {"fired": fired, "skipped": skipped, "error": False}
