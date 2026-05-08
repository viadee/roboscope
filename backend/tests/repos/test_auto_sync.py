"""Story REPO-2 — auto-sync scheduler unit tests.

Pure DB-level checks of `due_repos(db, now)` selection logic. The
scheduler job's actual firing is implicitly tested via the existing
manual-sync flow (`POST /repos/{id}/sync` in test_router.py); the
scheduler is just APScheduler triggering the same `sync_repo` task.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy.orm import Session

from src.repos.models import Repository
from src.repos.service import due_repos
from src.repos.tasks import auto_sync_due_repos


# ---------------------------------------------------------------------------
# helper to create a repo in the DB session that the test fixture provides
# ---------------------------------------------------------------------------


def _mk_repo(db: Session, admin_user, **overrides) -> Repository:
    defaults = {
        "name": f"auto-sync-{overrides.get('name', 'r')}",
        "repo_type": "git",
        "git_url": "https://example.com/x.git",
        "default_branch": "main",
        "local_path": "/tmp/x",
        "auto_sync": True,
        "sync_interval_minutes": 15,
        "sync_status": "idle",
        "created_by": admin_user.id,
    }
    defaults.update(overrides)
    repo = Repository(**defaults)
    db.add(repo)
    db.flush()
    db.refresh(repo)
    return repo


# ---------------------------------------------------------------------------
# due_repos selection logic
# ---------------------------------------------------------------------------


class TestDueRepos:
    def test_picks_never_synced(self, db_session: Session, admin_user):
        repo = _mk_repo(db_session, admin_user, name="never", last_synced_at=None)
        out = due_repos(db_session)
        assert repo in out

    def test_picks_overdue(self, db_session: Session, admin_user):
        # Last sync 30 min ago, interval 15 → due.
        repo = _mk_repo(
            db_session, admin_user, name="overdue",
            last_synced_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            sync_interval_minutes=15,
        )
        out = due_repos(db_session)
        assert repo in out

    def test_skips_recent(self, db_session: Session, admin_user):
        # Last sync 2 min ago, interval 15 → not yet due.
        repo = _mk_repo(
            db_session, admin_user, name="recent",
            last_synced_at=datetime.now(timezone.utc) - timedelta(minutes=2),
            sync_interval_minutes=15,
        )
        out = due_repos(db_session)
        assert repo not in out

    def test_skips_local_repo(self, db_session: Session, admin_user):
        repo = _mk_repo(
            db_session, admin_user, name="local",
            repo_type="local", git_url=None, last_synced_at=None,
        )
        out = due_repos(db_session)
        assert repo not in out

    def test_skips_auto_sync_off(self, db_session: Session, admin_user):
        repo = _mk_repo(
            db_session, admin_user, name="off",
            auto_sync=False, last_synced_at=None,
        )
        out = due_repos(db_session)
        assert repo not in out

    def test_skips_in_flight(self, db_session: Session, admin_user):
        # `syncing` status → previous sync still running → skip this tick.
        repo = _mk_repo(
            db_session, admin_user, name="inflight",
            sync_status="syncing", last_synced_at=None,
        )
        out = due_repos(db_session)
        assert repo not in out

    def test_skips_no_git_url(self, db_session: Session, admin_user):
        # Defensive: a "git" repo type with no URL would crash dispatch.
        repo = _mk_repo(
            db_session, admin_user, name="nourl",
            git_url=None, last_synced_at=None,
        )
        out = due_repos(db_session)
        assert repo not in out

    def test_now_parameter_overrides_clock(self, db_session: Session, admin_user):
        # Passing `now` is what the tests rely on for time-travel.
        # Last sync at T0; interval 5; querying at T0+10 → due.
        t0 = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        repo = _mk_repo(
            db_session, admin_user, name="travel",
            last_synced_at=t0, sync_interval_minutes=5,
        )
        out_then = due_repos(db_session, now=t0 + timedelta(minutes=2))
        out_after = due_repos(db_session, now=t0 + timedelta(minutes=10))
        assert repo not in out_then
        assert repo in out_after

    def test_naive_last_synced_at_treated_as_utc(
        self, db_session: Session, admin_user,
    ):
        # Production path on SQLite stores `last_synced_at` naive.
        # Review fix M2 — both sides are normalised to aware UTC so
        # the comparison stays correct regardless of which side has tz.
        naive_30min_ago = (
            datetime.now(timezone.utc) - timedelta(minutes=30)
        ).replace(tzinfo=None)
        repo = _mk_repo(
            db_session, admin_user, name="naive",
            last_synced_at=naive_30min_ago, sync_interval_minutes=15,
        )
        out = due_repos(db_session)
        assert repo in out


# ---------------------------------------------------------------------------
# auto_sync_due_repos task entry point — error handling
# ---------------------------------------------------------------------------


class TestAutoSyncTask:
    def test_dispatches_for_due_repos(
        self, db_session: Session, admin_user,
    ):
        repo_a = _mk_repo(db_session, admin_user, name="a", last_synced_at=None)
        repo_b = _mk_repo(db_session, admin_user, name="b", last_synced_at=None)

        # The task opens its own `get_sync_session()` — re-route that
        # to the test's transactional session so the rows we just
        # inserted (and which will be rolled back at test teardown)
        # are visible.
        @contextmanager
        def reuse_test_session():
            yield db_session

        dispatched_ids: list[int] = []

        def fake_dispatch_task(_fn, repo_id, *_a, **_kw):
            dispatched_ids.append(repo_id)
            class Result:
                id = "fake-task-id"
            return Result()

        with patch("src.repos.tasks.get_sync_session", reuse_test_session), \
             patch("src.repos.tasks.dispatch_task", fake_dispatch_task):
            result = auto_sync_due_repos()

        assert sorted(dispatched_ids) == sorted([repo_a.id, repo_b.id])
        assert sorted(result["dispatched"]) == sorted([repo_a.id, repo_b.id])

    def test_swallows_dispatch_errors(self, db_session: Session, admin_user):
        from src.task_executor import TaskDispatchError

        _mk_repo(db_session, admin_user, name="err", last_synced_at=None)

        @contextmanager
        def reuse_test_session():
            yield db_session

        def boom(_fn, *_a, **_kw):
            raise TaskDispatchError("queue saturated")

        # Must NOT raise — APScheduler would otherwise log ERROR and
        # potentially suspend the job. Story AC requires graceful skip.
        with patch("src.repos.tasks.get_sync_session", reuse_test_session), \
             patch("src.repos.tasks.dispatch_task", boom):
            result = auto_sync_due_repos()

        assert result["dispatched"] == []
        assert result["skipped"] == 1

    def test_swallows_unexpected_exceptions(self, monkeypatch):
        # If the very query crashes, the task must still return a dict
        # rather than propagating into APScheduler.
        from src.repos import tasks as tasks_module

        def crash(*_a, **_kw):
            raise RuntimeError("DB unreachable")

        monkeypatch.setattr(tasks_module, "due_repos", crash)
        result = auto_sync_due_repos()
        assert result["error"] is True
        assert result["dispatched"] == []

    def test_recovers_stale_syncing_row(self, db_session: Session, admin_user):
        """A row stuck on `sync_status='syncing'` whose updated_at is older
        than the stale threshold is reset to 'error' on the next tick so
        the user isn't blocked waiting for a backend restart. Auto-sync
        OFF so the post-recovery `due_repos` pass doesn't re-flip the
        row to 'syncing' and obscure what we're checking."""
        from src.repos import tasks as tasks_module

        # Force updated_at to clearly stale by setting it via UPDATE
        # after creation (`onupdate` would otherwise overwrite to "now").
        repo = _mk_repo(
            db_session, admin_user, name="stuck",
            sync_status="syncing", last_synced_at=None,
            auto_sync=False,
        )
        old = datetime.now(timezone.utc) - timedelta(
            minutes=tasks_module._STALE_SYNCING_AFTER_MINUTES + 5
        )
        from sqlalchemy import update
        db_session.execute(
            update(Repository).where(Repository.id == repo.id).values(updated_at=old)
        )
        db_session.commit()

        @contextmanager
        def reuse_test_session():
            yield db_session

        with patch("src.repos.tasks.get_sync_session", reuse_test_session):
            result = auto_sync_due_repos()

        assert result["recovered"] == 1
        db_session.refresh(repo)
        assert repo.sync_status == "error"
        assert "stuck" in (repo.sync_error or "").lower()

    def test_leaves_fresh_syncing_row_alone(self, db_session: Session, admin_user):
        """A row that's only been 'syncing' for a few seconds is a real
        in-flight sync — must NOT be reset, otherwise we'd race the
        running sync_repo task. Auto-sync OFF so `due_repos` skips it
        and we test the recovery path in isolation."""
        repo = _mk_repo(
            db_session, admin_user, name="inflight",
            sync_status="syncing", last_synced_at=None,
            auto_sync=False,
        )

        @contextmanager
        def reuse_test_session():
            yield db_session

        with patch("src.repos.tasks.get_sync_session", reuse_test_session):
            result = auto_sync_due_repos()

        assert result["recovered"] == 0
        db_session.refresh(repo)
        assert repo.sync_status == "syncing"
