"""Tests for webhook CRUD, dispatch, and git inbound."""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.webhooks.service import (
    _sign_payload,
    create_webhook,
    delete_webhook,
    get_webhook,
    list_webhooks,
    update_webhook,
)
from tests.conftest import auth_header


class TestWebhookService:
    """Unit tests for webhook service functions."""

    def test_create_webhook(self, db_session: Session, admin_user):
        wh = create_webhook(db_session, {
            "name": "Slack",
            "url": "https://hooks.slack.com/test",
            "events": ["run.passed", "run.failed"],
        }, admin_user.id)
        assert wh.name == "Slack"
        assert wh.url == "https://hooks.slack.com/test"
        assert json.loads(wh.events) == ["run.passed", "run.failed"]

    def test_create_webhook_invalid_event(self, db_session: Session, admin_user):
        with pytest.raises(ValueError, match="Invalid events"):
            create_webhook(db_session, {
                "name": "Bad",
                "url": "https://example.com",
                "events": ["run.passed", "invalid.event"],
            }, admin_user.id)

    def test_update_webhook(self, db_session: Session, admin_user):
        wh = create_webhook(db_session, {
            "name": "Original",
            "url": "https://example.com",
        }, admin_user.id)
        updated = update_webhook(db_session, wh, {"name": "Updated", "is_active": False})
        assert updated.name == "Updated"
        assert updated.is_active is False

    def test_delete_webhook(self, db_session: Session, admin_user):
        wh = create_webhook(db_session, {
            "name": "Delete Me",
            "url": "https://example.com",
        }, admin_user.id)
        wh_id = wh.id
        delete_webhook(db_session, wh)
        assert get_webhook(db_session, wh_id) is None

    def test_list_webhooks(self, db_session: Session, admin_user):
        create_webhook(db_session, {"name": "W1", "url": "https://a.com"}, admin_user.id)
        create_webhook(db_session, {"name": "W2", "url": "https://b.com"}, admin_user.id)
        webhooks = list_webhooks(db_session)
        assert len(webhooks) == 2

    def test_hmac_signature(self):
        payload = '{"event":"run.passed","run_id":1}'
        secret = "test-secret"
        sig = _sign_payload(payload, secret)
        expected = hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256,
        ).hexdigest()
        assert sig == expected


class TestWebhookRouter:
    """API endpoint tests for webhooks."""

    def test_create_webhook_editor(self, client, admin_user):
        """Editor+ can create webhooks."""
        resp = client.post(
            "/api/v1/webhooks/hooks",
            json={
                "name": "Test Hook",
                "url": "https://example.com/webhook",
                "events": ["run.passed", "run.failed"],
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Hook"
        assert data["events"] == ["run.passed", "run.failed"]
        assert data["has_secret"] is False

    def test_create_webhook_with_secret(self, client, admin_user):
        resp = client.post(
            "/api/v1/webhooks/hooks",
            json={
                "name": "Secure Hook",
                "url": "https://example.com/webhook",
                "secret": "my-secret",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201
        assert resp.json()["has_secret"] is True

    def test_create_webhook_viewer_forbidden(self, client, viewer_user):
        resp = client.post(
            "/api/v1/webhooks/hooks",
            json={"name": "Fail", "url": "https://example.com"},
            headers=auth_header(viewer_user),
        )
        assert resp.status_code == 403

    def test_list_webhooks(self, client, admin_user):
        client.post(
            "/api/v1/webhooks/hooks",
            json={"name": "W1", "url": "https://a.com"},
            headers=auth_header(admin_user),
        )
        resp = client.get(
            "/api/v1/webhooks/hooks",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_delete_webhook(self, client, admin_user):
        create_resp = client.post(
            "/api/v1/webhooks/hooks",
            json={"name": "Delete Me", "url": "https://a.com"},
            headers=auth_header(admin_user),
        )
        wh_id = create_resp.json()["id"]
        resp = client.delete(
            f"/api/v1/webhooks/hooks/{wh_id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 204

    def test_get_available_events(self, client, admin_user):
        resp = client.get(
            "/api/v1/webhooks/events",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert "run.passed" in events
        assert "run.failed" in events

    def test_update_webhook(self, client, admin_user):
        create_resp = client.post(
            "/api/v1/webhooks/hooks",
            json={"name": "Original", "url": "https://a.com"},
            headers=auth_header(admin_user),
        )
        wh_id = create_resp.json()["id"]
        resp = client.patch(
            f"/api/v1/webhooks/hooks/{wh_id}",
            json={"name": "Updated", "is_active": False},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
        assert resp.json()["is_active"] is False


class TestGitWebhookInbound:
    """Tests for the inbound git webhook endpoint."""

    def test_github_push_no_matching_repo(self, client):
        """Push for unknown repo returns 'ignored'."""
        resp = client.post(
            "/api/v1/webhooks/git",
            json={
                "ref": "refs/heads/main",
                "repository": {
                    "clone_url": "https://github.com/unknown/repo.git",
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_invalid_payload(self, client):
        """Payload without repository URL returns 422."""
        resp = client.post(
            "/api/v1/webhooks/git",
            json={"some": "data"},
        )
        assert resp.status_code == 422

    def test_github_push_triggers_run(self, client, db_session, admin_user):
        """Push for matching repo triggers a test run."""
        from src.repos.models import Repository

        repo = Repository(
            name="Test Repo",
            repo_type="git",
            git_url="https://github.com/test/repo.git",
            local_path="/tmp/test-repo",
            default_branch="main",
            created_by=admin_user.id,
        )
        db_session.add(repo)
        db_session.flush()

        # Mock dispatch_task to avoid actually running
        with patch("src.task_executor.dispatch_task") as mock_dispatch:
            mock_dispatch.return_value = MagicMock(id="test-task-id")
            resp = client.post(
                "/api/v1/webhooks/git",
                json={
                    "ref": "refs/heads/develop",
                    "repository": {
                        "clone_url": "https://github.com/test/repo.git",
                    },
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "triggered"
        assert data["repository"] == "Test Repo"
        assert data["branch"] == "develop"

    def test_gitlab_push_format(self, client, db_session, admin_user):
        """GitLab push payload format also works."""
        from src.repos.models import Repository

        repo = Repository(
            name="GL Repo",
            repo_type="git",
            git_url="https://gitlab.com/test/repo.git",
            local_path="/tmp/gl-repo",
            default_branch="main",
            created_by=admin_user.id,
        )
        db_session.add(repo)
        db_session.flush()

        with patch("src.task_executor.dispatch_task") as mock_dispatch:
            mock_dispatch.return_value = MagicMock(id="test-task-id")
            resp = client.post(
                "/api/v1/webhooks/git",
                json={
                    "ref": "refs/heads/main",
                    "repository": {
                        "git_http_url": "https://gitlab.com/test/repo.git",
                    },
                },
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "triggered"

    # -----------------------------------------------------------------
    # Story REPO-4 — webhook pre-syncs the repo before triggering the run
    # -----------------------------------------------------------------

    def test_webhook_dispatches_sync_before_run(
        self, client, db_session, admin_user,
    ):
        """The webhook must dispatch sync_repo BEFORE execute_test_run.
        The task executor uses max_workers=1 so dispatch order = run order.
        """
        from src.repos.models import Repository
        from src.repos.tasks import sync_repo
        from src.execution.tasks import execute_test_run

        repo = Repository(
            name="Sync First",
            repo_type="git",
            git_url="https://github.com/test/sync-first.git",
            local_path="/tmp/sync-first",
            default_branch="main",
            created_by=admin_user.id,
        )
        db_session.add(repo)
        db_session.flush()

        called: list = []

        def record(fn, *args, **kwargs):
            called.append(fn)
            return MagicMock(id=f"task-{len(called)}")

        with patch("src.task_executor.dispatch_task", side_effect=record):
            resp = client.post(
                "/api/v1/webhooks/git",
                json={
                    "ref": "refs/heads/main",
                    "repository": {
                        "clone_url": "https://github.com/test/sync-first.git",
                    },
                },
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "triggered"
        # Order matters: sync_repo first, execute_test_run second.
        assert called == [sync_repo, execute_test_run]

    def test_webhook_skips_sync_for_local_repo(
        self, client, db_session, admin_user,
    ):
        """Local repos have no upstream — no pre-sync, just dispatch the run."""
        from src.repos.models import Repository
        from src.execution.tasks import execute_test_run

        # `repo_type='local'` shouldn't normally match a webhook payload
        # (no git_url to compare against), but if a user mis-configured
        # one with a URL we should still skip the sync.
        repo = Repository(
            name="Local Lookalike",
            repo_type="local",
            git_url="https://github.com/test/local.git",  # mis-configured
            local_path="/tmp/local-lookalike",
            default_branch="main",
            created_by=admin_user.id,
        )
        db_session.add(repo)
        db_session.flush()

        called: list = []

        def record(fn, *args, **kwargs):
            called.append(fn)
            return MagicMock(id=f"task-{len(called)}")

        with patch("src.task_executor.dispatch_task", side_effect=record):
            resp = client.post(
                "/api/v1/webhooks/git",
                json={
                    "ref": "refs/heads/main",
                    "repository": {
                        "clone_url": "https://github.com/test/local.git",
                    },
                },
            )

        assert resp.status_code == 200
        assert called == [execute_test_run]

    def test_webhook_run_proceeds_when_sync_dispatch_fails(
        self, client, db_session, admin_user,
    ):
        """A TaskDispatchError on the sync must NOT abort the run."""
        from src.repos.models import Repository
        from src.repos.tasks import sync_repo
        from src.execution.tasks import execute_test_run
        from src.task_executor import TaskDispatchError

        repo = Repository(
            name="Sync Fails",
            repo_type="git",
            git_url="https://github.com/test/sync-fails.git",
            local_path="/tmp/sync-fails",
            default_branch="main",
            created_by=admin_user.id,
        )
        db_session.add(repo)
        db_session.flush()

        attempts: list = []

        def record(fn, *args, **kwargs):
            attempts.append(fn)
            if fn is sync_repo:
                raise TaskDispatchError("queue saturated")
            return MagicMock(id=f"task-{len(attempts)}")

        with patch("src.task_executor.dispatch_task", side_effect=record):
            resp = client.post(
                "/api/v1/webhooks/git",
                json={
                    "ref": "refs/heads/main",
                    "repository": {
                        "clone_url": "https://github.com/test/sync-fails.git",
                    },
                },
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "triggered"
        # Both were attempted; the run dispatch succeeded after the sync
        # dispatch raised.
        assert attempts == [sync_repo, execute_test_run]
