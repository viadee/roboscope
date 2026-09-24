"""Story V14.1 — scheduled runs fire (heartbeat + "Run now")."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.execution.models import ExecutionRun, RunStatus, RunType, Schedule
from src.execution.schedule_trigger import run_due_schedules
from src.execution.service import compute_next_run
from src.repos.models import Repository
from tests.conftest import auth_header

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
NOW_NAIVE = NOW.replace(tzinfo=None)


@pytest.fixture
def repo(db_session: Session, admin_user):
    r = Repository(
        name="sched-repo",
        git_url="https://example.com/x.git",
        default_branch="main",
        local_path="/tmp/sched-repo",
        created_by=admin_user.id,
    )
    db_session.add(r)
    db_session.flush()
    return r


def _schedule(db: Session, repo, user, **kw) -> Schedule:
    defaults = dict(
        name="Nightly",
        cron_expression="0 2 * * *",
        repository_id=repo.id,
        target_path="tests/smoke",
        branch="dev",
        runner_type="subprocess",
        tags_include="smoke",
        tags_exclude="slow",
        created_by=user.id,
        is_active=True,
        next_run_at=NOW_NAIVE - timedelta(minutes=1),
    )
    defaults.update(kw)
    s = Schedule(**defaults)
    db.add(s)
    db.flush()
    return s


@pytest.fixture
def tick(db_session: Session):
    """Run the heartbeat against the test session with dispatch patched."""
    dispatch = MagicMock(return_value=MagicMock(id="task-1"))

    @contextmanager
    def reuse():
        yield db_session

    def _tick(now=NOW):
        with (
            patch("src.execution.schedule_trigger.get_sync_session", reuse),
            patch("src.execution.service.dispatch_task", dispatch),
        ):
            return run_due_schedules(now=now)

    _tick.dispatch = dispatch
    return _tick


def _runs(db: Session, schedule: Schedule) -> list[ExecutionRun]:
    return list(db.scalars(select(ExecutionRun).where(ExecutionRun.schedule_id == schedule.id)))


class TestCronValidation:
    def test_invalid_cron_is_422(self, client, admin_user, repo):
        resp = client.post(
            "/api/v1/schedules",
            headers=auth_header(admin_user),
            json={
                "name": "x",
                "cron_expression": "every day",
                "repository_id": repo.id,
                "target_path": ".",
            },
        )
        assert resp.status_code == 422

    def test_invalid_cron_on_update_is_422(self, client, admin_user, repo, db_session):
        s = _schedule(db_session, repo, admin_user)
        resp = client.patch(
            f"/api/v1/schedules/{s.id}",
            headers=auth_header(admin_user),
            json={"cron_expression": "61 * * * *"},
        )
        assert resp.status_code == 422

    def test_valid_cron_sets_next_run_at(self, client, admin_user, repo):
        resp = client.post(
            "/api/v1/schedules",
            headers=auth_header(admin_user),
            json={
                "name": "x",
                "cron_expression": "0 2 * * 1-5",
                "repository_id": repo.id,
                "target_path": ".",
            },
        )
        assert resp.status_code == 201
        nxt = datetime.fromisoformat(resp.json()["next_run_at"].rstrip("Z"))
        assert nxt > datetime.now(timezone.utc).replace(tzinfo=None)

    def test_compute_next_run_is_strictly_after_now(self):
        at_slot = compute_next_run("* * * * *", NOW)
        assert at_slot > NOW_NAIVE and at_slot.tzinfo is None


class TestHeartbeat:
    def test_due_schedule_fires_one_run_with_copied_fields(
        self, db_session, admin_user, repo, tick
    ):
        s = _schedule(db_session, repo, admin_user)
        result = tick()
        runs = _runs(db_session, s)
        assert len(runs) == 1 and result["fired"] == [runs[0].id]
        r = runs[0]
        assert (r.repository_id, r.target_path, r.branch, r.tags_include, r.tags_exclude) == (
            repo.id,
            "tests/smoke",
            "dev",
            "smoke",
            "slow",
        )
        assert r.triggered_by == admin_user.id and r.run_type == RunType.SCHEDULED
        assert r.variables is None and r.advanced_config is None
        assert r.task_id == "task-1"
        assert s.last_run_at == NOW_NAIVE
        assert s.next_run_at == compute_next_run(s.cron_expression, NOW)
        tick.dispatch.assert_called_once()

    def test_not_due_does_nothing(self, db_session, admin_user, repo, tick):
        s = _schedule(db_session, repo, admin_user, next_run_at=NOW_NAIVE + timedelta(minutes=5))
        tick()
        assert _runs(db_session, s) == []

    def test_skips_when_previous_run_pending(self, db_session, admin_user, repo, tick):
        s = _schedule(db_session, repo, admin_user)
        db_session.add(
            ExecutionRun(
                repository_id=repo.id,
                target_path=".",
                status=RunStatus.PENDING,
                triggered_by=admin_user.id,
                schedule_id=s.id,
            )
        )
        db_session.flush()
        result = tick()
        assert len(_runs(db_session, s)) == 1
        assert result["skipped"] == [s.id]
        assert s.next_run_at > NOW_NAIVE

    def test_skips_inactive(self, db_session, admin_user, repo, tick):
        s = _schedule(db_session, repo, admin_user, is_active=False)
        tick()
        assert _runs(db_session, s) == []

    def test_deactivated_creator_produces_no_run(
        self, db_session, admin_user, runner_user, repo, tick
    ):
        s = _schedule(db_session, repo, runner_user)
        runner_user.is_active = False
        db_session.flush()
        tick()
        assert _runs(db_session, s) == []
        assert s.next_run_at > NOW_NAIVE

    def test_missed_slots_coalesce_into_one_run(self, db_session, admin_user, repo, tick):
        s = _schedule(
            db_session,
            repo,
            admin_user,
            cron_expression="* * * * *",
            next_run_at=NOW_NAIVE - timedelta(hours=6),
        )
        tick()
        tick(NOW + timedelta(seconds=10))  # still before the recomputed slot
        assert len(_runs(db_session, s)) == 1

    def test_backfills_missing_next_run_at_without_firing(self, db_session, admin_user, repo, tick):
        s = _schedule(db_session, repo, admin_user, next_run_at=None)
        tick()
        assert _runs(db_session, s) == []
        assert s.next_run_at is not None


class TestRunNow:
    def test_run_now_creates_run_and_keeps_next_run_at(self, client, db_session, admin_user, repo):
        nxt = NOW_NAIVE + timedelta(days=1)
        s = _schedule(db_session, repo, admin_user, is_active=False, next_run_at=nxt)
        with patch(
            "src.execution.service.dispatch_task", MagicMock(return_value=MagicMock(id="t"))
        ):
            resp = client.post(f"/api/v1/schedules/{s.id}/run", headers=auth_header(admin_user))
        assert resp.status_code == 201
        runs = _runs(db_session, s)
        assert len(runs) == 1 and runs[0].id == resp.json()["id"]
        assert s.next_run_at == nxt and s.last_run_at is not None

    def test_run_now_requires_runner(self, client, db_session, admin_user, viewer_user, repo):
        s = _schedule(db_session, repo, admin_user)
        resp = client.post(f"/api/v1/schedules/{s.id}/run", headers=auth_header(viewer_user))
        assert resp.status_code == 403
        assert _runs(db_session, s) == []

    def test_run_now_404(self, client, admin_user):
        assert (
            client.post("/api/v1/schedules/99999/run", headers=auth_header(admin_user)).status_code
            == 404
        )

    def test_delete_schedule_with_runs(self, client, db_session, admin_user, repo, tick):
        s = _schedule(db_session, repo, admin_user)
        tick()
        (run,) = _runs(db_session, s)
        assert (
            client.delete(f"/api/v1/schedules/{s.id}", headers=auth_header(admin_user)).status_code
            == 204
        )
        db_session.refresh(run)
        assert run.schedule_id is None
