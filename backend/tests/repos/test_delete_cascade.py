"""Deleting a repository removes everything that references it.

Regression (0.12.1 review): SQLite does not enforce foreign keys, so a bare
``db.delete(repo)`` left runs, reports, schedules and recordings pointing at a
missing repo; PostgreSQL rejected the delete with a 500.
"""

from pathlib import Path

import pytest
from sqlalchemy import func, select

from src.config import settings
from src.execution.models import ExecutionRun, RunStatus, Schedule
from src.recording.models import RecordingSession
from src.reports.models import Report
from src.repos.models import Repository
from src.repos.service import RepositoryBusyError, delete_repository
from src.stats.models import KpiRecord
from tests.conftest import auth_header


def _seed(db, user_id, run_status=RunStatus.PASSED, report_dir: Path | None = None):
    repo = Repository(name="doomed", repo_type="local", local_path="/tmp/doomed-repo", created_by=user_id)
    db.add(repo)
    db.flush()
    sched = Schedule(name="nightly", cron_expression="0 2 * * *", repository_id=repo.id,
                     target_path=".", created_by=user_id)
    db.add(sched)
    db.flush()
    run = ExecutionRun(repository_id=repo.id, target_path=".", triggered_by=user_id,
                       status=run_status, schedule_id=sched.id)
    db.add(run)
    db.flush()
    xml = str((report_dir / "output.xml") if report_dir else "/nonexistent/output.xml")
    db.add(Report(execution_run_id=run.id, output_xml_path=xml))
    db.add(RecordingSession(repository_id=repo.id, triggered_by=user_id))
    db.add(KpiRecord(date=__import__("datetime").date.today(), repository_id=repo.id))
    db.flush()
    return repo


def _count(db, model):
    return db.execute(select(func.count()).select_from(model)).scalar()


def test_delete_removes_dependents_and_report_files(db_session, admin_user, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path))
    run_dir = tmp_path / "run_1_abc"
    run_dir.mkdir()
    (run_dir / "output.xml").write_text("<robot/>")
    repo = _seed(db_session, admin_user.id, report_dir=run_dir)

    delete_repository(db_session, repo)

    for model in (Repository, ExecutionRun, Report, Schedule, RecordingSession, KpiRecord):
        assert _count(db_session, model) == 0, model.__name__
    assert not run_dir.exists()


@pytest.mark.parametrize("status", [RunStatus.PENDING, RunStatus.RUNNING])
def test_delete_refused_while_runs_active(db_session, admin_user, status):
    repo = _seed(db_session, admin_user.id, run_status=status)
    with pytest.raises(RepositoryBusyError):
        delete_repository(db_session, repo)
    assert _count(db_session, Repository) == 1


def test_delete_endpoint_returns_409_while_busy(client, db_session, admin_user):
    repo = _seed(db_session, admin_user.id, run_status=RunStatus.RUNNING)
    r = client.delete(f"/api/v1/repos/{repo.id}", headers=auth_header(admin_user))
    assert r.status_code == 409
