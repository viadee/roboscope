"""Background tasks for repository operations."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

import src.auth.models  # noqa: F401 — defines 'users' table

from src.database import get_sync_session
from src.repos.models import Repository
from src.repos.service import clone_repository, due_repos, sync_repository
from src.task_executor import TaskDispatchError, dispatch_task

logger = logging.getLogger("roboscope.repos.tasks")


def clone_repo(repo_id: int, max_retries: int = 3) -> dict:
    """Clone a git repository (runs in background thread)."""
    with get_sync_session() as session:
        repo = session.execute(
            select(Repository).where(Repository.id == repo_id)
        ).scalar_one_or_none()

        if repo is None:
            logger.error("Repository %d not found", repo_id)
            return {"status": "error", "message": "Repository not found"}

        repo.sync_status = "syncing"
        repo.sync_error = None
        session.commit()

        # Defensive: a git-typed repo without a git_url shouldn't reach
        # here (Pydantic + the router both enforce it), but if a stray
        # row slipped through migrations or a manual DB edit, surface
        # a clean error instead of crashing in GitPython.
        if not repo.git_url:
            repo.sync_status = "error"
            repo.sync_error = "No git URL configured"
            session.commit()
            return {"status": "error", "message": "No git URL configured"}

        last_exc = None
        for attempt in range(max_retries):
            try:
                logger.info(
                    "Cloning %s from %s (attempt %d/%d)",
                    repo.name, repo.git_url, attempt + 1, max_retries,
                )
                clone_repository(repo.git_url, repo.local_path, repo.default_branch)
                repo.last_synced_at = datetime.now(timezone.utc)
                repo.sync_status = "success"
                repo.sync_error = None
                session.commit()
                logger.info("Successfully cloned %s", repo.name)
                return {"status": "success", "message": f"Cloned {repo.name}"}
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Clone attempt %d/%d failed for %s: %s",
                    attempt + 1, max_retries, repo.name, exc,
                )

        # All retries exhausted
        logger.error("Clone failed for %s after %d attempts: %s", repo.name, max_retries, last_exc)
        repo.sync_status = "error"
        repo.sync_error = str(last_exc)[:500]
        session.commit()
        return {"status": "error", "message": str(last_exc)}


def sync_repo(repo_id: int, max_retries: int = 3) -> dict:
    """Sync (pull) a git repository (runs in background thread).

    If the local directory doesn't exist, clones it first.
    """
    with get_sync_session() as session:
        repo = session.execute(
            select(Repository).where(Repository.id == repo_id)
        ).scalar_one_or_none()

        if repo is None:
            logger.error("Repository %d not found", repo_id)
            return {"status": "error", "message": "Repository not found"}

        repo.sync_status = "syncing"
        repo.sync_error = None
        session.commit()

        last_exc = None
        for attempt in range(max_retries):
            try:
                local_path = Path(repo.local_path)

                # If the repo hasn't been cloned yet, clone it first
                if not local_path.exists() or not (local_path / ".git").exists():
                    if not repo.git_url:
                        repo.sync_status = "error"
                        repo.sync_error = "No git URL configured"
                        session.commit()
                        return {"status": "error", "message": "No git URL configured"}
                    logger.info("Local path missing — cloning %s from %s", repo.name, repo.git_url)
                    clone_repository(repo.git_url, repo.local_path, repo.default_branch)
                    repo.last_synced_at = datetime.now(timezone.utc)
                    repo.sync_status = "success"
                    repo.sync_error = None
                    session.commit()
                    return {"status": "success", "message": f"Cloned {repo.name}"}

                # Pull latest changes
                result = sync_repository(repo.local_path, repo.default_branch)
                repo.last_synced_at = datetime.now(timezone.utc)
                repo.sync_status = "success"
                repo.sync_error = None
                session.commit()
                logger.info("Synced %s: %s", repo.name, result)
                return {"status": "success", "message": result}
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Sync attempt %d/%d failed for %s: %s",
                    attempt + 1, max_retries, repo.name, exc,
                )

        # All retries exhausted
        logger.error("Sync failed for %s after %d attempts: %s", repo.name, max_retries, last_exc)
        repo.sync_status = "error"
        repo.sync_error = str(last_exc)[:500]
        session.commit()
        return {"status": "error", "message": str(last_exc)}


def auto_sync_due_repos() -> dict:
    """Story REPO-2 — APScheduler entry point.

    Polls every 5 min (registered in `main.py` lifespan), finds every
    repo whose `auto_sync` checkbox is on and `last_synced_at` is older
    than its configured `sync_interval_minutes`, and dispatches one
    `sync_repo` task per due repo. Returns a summary dict (handy for
    logs / future status surface).

    Important: this function runs *inside* the APScheduler thread, so
    it MUST NOT raise — uncaught exceptions would propagate and the
    scheduler logs them as ERROR + may suspend the job. We catch and
    log instead.
    """
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc)

    dispatched: list[int] = []
    skipped: int = 0
    try:
        with get_sync_session() as session:
            due = due_repos(session, now=now_utc)
            for repo in due:
                # Review fix M1 — flip status to `syncing` synchronously
                # at dispatch time so the next tick (and any concurrent
                # manual-sync click) sees the in-flight state and skips
                # this repo. The actual `sync_repo` task overwrites the
                # field on completion / failure, so we never strand a
                # repo as `syncing` even if dispatch raises.
                repo.sync_status = "syncing"
                session.commit()
                try:
                    dispatch_task(sync_repo, repo.id)
                    dispatched.append(repo.id)
                except TaskDispatchError as e:
                    logger.warning(
                        "auto-sync: dispatch failed for repo %d (%s): %s",
                        repo.id, repo.name, e,
                    )
                    # Roll the optimistic flag back so the next tick can
                    # try again instead of silently skipping forever.
                    repo.sync_status = "idle"
                    session.commit()
                    skipped += 1
        if dispatched or skipped:
            logger.info(
                "auto-sync: dispatched %d, skipped %d (queue busy)",
                len(dispatched), skipped,
            )
    except Exception:
        logger.exception("auto-sync tick crashed; will retry next 5min interval")
        return {"dispatched": dispatched, "skipped": skipped, "error": True}
    return {"dispatched": dispatched, "skipped": skipped}
