"""POST /repos/{id}/sync must not dispatch a second sync while one is
already in flight (audit finding 2.3) — mirrors the 120s in-flight guard
`GET /environments/{id}/keywords` already had.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.repos.models import Repository
from tests.conftest import auth_header


@pytest.fixture
def git_repo(db_session: Session, admin_user) -> Repository:
    repo = Repository(
        name="sync-guard-repo",
        repo_type="git",
        git_url="https://github.com/org/sync-guard-repo.git",
        default_branch="main",
        local_path="/tmp/sync-guard-repo",
        created_by=admin_user.id,
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


class TestSyncInFlightGuard:
    @patch("src.repos.router.dispatch_task")
    def test_dispatches_when_no_sync_in_flight(self, mock_dispatch, client, git_repo, admin_user):
        mock_dispatch.return_value = MagicMock(id="task-1")
        resp = client.post(
            f"/api/v1/repos/{git_repo.id}/sync", headers=auth_header(admin_user)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "syncing"
        assert mock_dispatch.call_count == 1

    @patch("src.repos.router.dispatch_task")
    def test_skips_second_dispatch_while_syncing(
        self, mock_dispatch, client, db_session, git_repo, admin_user
    ):
        git_repo.sync_status = "syncing"
        db_session.commit()
        db_session.refresh(git_repo)
        assert git_repo.updated_at is not None

        resp = client.post(
            f"/api/v1/repos/{git_repo.id}/sync", headers=auth_header(admin_user)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "syncing"
        assert resp.json()["message"] == "Sync already in progress"
        assert mock_dispatch.call_count == 0

    @patch("src.repos.router.dispatch_task")
    def test_dispatches_again_once_the_in_flight_window_expires(
        self, mock_dispatch, client, db_session, git_repo, admin_user
    ):
        mock_dispatch.return_value = MagicMock(id="task-2")
        git_repo.sync_status = "syncing"
        db_session.commit()
        db_session.query(Repository).filter(Repository.id == git_repo.id).update(
            {"updated_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=200)}
        )
        db_session.commit()

        resp = client.post(
            f"/api/v1/repos/{git_repo.id}/sync", headers=auth_header(admin_user)
        )
        assert resp.status_code == 200
        assert mock_dispatch.call_count == 1
