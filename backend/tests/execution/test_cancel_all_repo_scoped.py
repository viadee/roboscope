"""`POST /runs/cancel-all` must only cancel runs the caller has RUNNER+
effective role on (audit finding 2.2).

Before this fix, a global `require_role(RUNNER)` gated the whole
endpoint, but every PENDING/RUNNING run across ALL repos was cancelled
regardless of the caller's per-repo access — inconsistent with the
repo-scoped `POST /runs/{run_id}/cancel`.
"""

import pytest
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.service import hash_password
from src.execution.models import ExecutionRun, RunStatus
from src.repos.models import ProjectMember, Repository
from tests.conftest import auth_header


@pytest.fixture
def scoped_runner(db_session: Session) -> User:
    u = User(
        email="cancel-all-viewer@test.com",
        username="cancel-all-viewer",
        hashed_password=hash_password("pw123456"),
        role="viewer",
    )
    db_session.add(u)
    db_session.flush()
    db_session.refresh(u)
    return u


def _mk_repo(db_session: Session, admin_user, name: str) -> Repository:
    repo = Repository(
        name=name, repo_type="local", local_path=f"/tmp/{name}", created_by=admin_user.id
    )
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)
    return repo


def _mk_run(db_session: Session, admin_user, repo: Repository, status=RunStatus.PENDING) -> ExecutionRun:
    run = ExecutionRun(
        repository_id=repo.id,
        target_path="suite.robot",
        branch="main",
        status=status,
        triggered_by=admin_user.id,
    )
    db_session.add(run)
    db_session.flush()
    db_session.refresh(run)
    return run


def test_cancel_all_only_cancels_runs_on_repos_with_runner_grant(
    client, db_session, admin_user, scoped_runner
):
    repo_a = _mk_repo(db_session, admin_user, "cancel-all-repo-a")
    repo_b = _mk_repo(db_session, admin_user, "cancel-all-repo-b")
    db_session.add(
        ProjectMember(user_id=scoped_runner.id, repository_id=repo_a.id, role="runner")
    )
    db_session.commit()

    run_a = _mk_run(db_session, admin_user, repo_a)
    run_b = _mk_run(db_session, admin_user, repo_b)
    db_session.commit()

    resp = client.post("/api/v1/runs/cancel-all", headers=auth_header(scoped_runner))
    assert resp.status_code == 200
    assert resp.json()["cancelled"] == 1

    db_session.refresh(run_a)
    db_session.refresh(run_b)
    assert run_a.status == RunStatus.CANCELLED
    assert run_b.status == RunStatus.PENDING


def test_cancel_all_admin_cancels_everything(client, db_session, admin_user):
    repo_a = _mk_repo(db_session, admin_user, "cancel-all-repo-c")
    repo_b = _mk_repo(db_session, admin_user, "cancel-all-repo-d")
    run_a = _mk_run(db_session, admin_user, repo_a)
    run_b = _mk_run(db_session, admin_user, repo_b)
    db_session.commit()

    resp = client.post("/api/v1/runs/cancel-all", headers=auth_header(admin_user))
    assert resp.status_code == 200
    assert resp.json()["cancelled"] == 2

    db_session.refresh(run_a)
    db_session.refresh(run_b)
    assert run_a.status == RunStatus.CANCELLED
    assert run_b.status == RunStatus.CANCELLED


def test_cancel_all_no_access_cancels_nothing(client, db_session, admin_user, scoped_runner):
    repo = _mk_repo(db_session, admin_user, "cancel-all-repo-e")
    run = _mk_run(db_session, admin_user, repo)
    db_session.commit()

    resp = client.post("/api/v1/runs/cancel-all", headers=auth_header(scoped_runner))
    assert resp.status_code == 200
    assert resp.json()["cancelled"] == 0

    db_session.refresh(run)
    assert run.status == RunStatus.PENDING
