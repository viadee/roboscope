"""Endpoint tests for GOV-2/GOV-4 — package-management lockdown + role floor."""

import pytest
from sqlalchemy import select

from src.audit.models import AuditLog
from src.environments.models import Environment
from src.settings.models import AppSetting
from tests.conftest import auth_header

ENV_FLAG = "ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT"


@pytest.fixture
def env(db_session, admin_user):
    e = Environment(name="gov-env", python_version="3.12", created_by=admin_user.id)
    db_session.add(e)
    db_session.flush()
    db_session.refresh(e)
    return e


def _mutating_calls(client, env_id, headers):
    """(label, response) for every package-mutating endpoint."""
    return [
        ("install", client.post(f"/api/v1/environments/{env_id}/packages", json={"name": "robotframework"}, headers=headers)),
        ("upgrade", client.post(f"/api/v1/environments/{env_id}/packages/robotframework/upgrade", headers=headers)),
        ("retry", client.post(f"/api/v1/environments/{env_id}/packages/robotframework/retry", headers=headers)),
        ("uninstall", client.delete(f"/api/v1/environments/{env_id}/packages/robotframework", headers=headers)),
        ("docker_build", client.post(f"/api/v1/environments/{env_id}/docker-build", headers=headers)),
        ("rfbrowser_init", client.post(f"/api/v1/environments/{env_id}/rfbrowser-init", headers=headers)),
    ]


class TestLockdownOff:
    def test_all_mutating_endpoints_403_when_flag_off_even_for_admin(
        self, client, env, admin_user, monkeypatch
    ):
        monkeypatch.setenv(ENV_FLAG, "false")
        for label, resp in _mutating_calls(client, env.id, auth_header(admin_user)):
            assert resp.status_code == 403, f"{label} should be 403 when locked, got {resp.status_code}"
            assert "feature_disabled:packageManagement" in resp.json()["detail"], label

    def test_read_endpoint_still_works_when_locked(self, client, env, admin_user, monkeypatch):
        monkeypatch.setenv(ENV_FLAG, "false")
        resp = client.get(f"/api/v1/environments/{env.id}/packages", headers=auth_header(admin_user))
        assert resp.status_code == 200

    def test_setup_default_is_locked(self, client, admin_user, monkeypatch):
        # Regression: setup-default provisions a venv + installs packages, so it
        # MUST be gated too (was bypassing the lockdown).
        monkeypatch.setenv(ENV_FLAG, "false")
        resp = client.post("/api/v1/environments/setup-default", headers=auth_header(admin_user))
        assert resp.status_code == 403
        assert "feature_disabled:packageManagement" in resp.json()["detail"]

    def test_lockdown_via_db_setting_no_env(self, client, env, admin_user, db_session, monkeypatch):
        # The path the admin UI actually uses: a DB row (locked=false), no ENV var.
        monkeypatch.delenv(ENV_FLAG, raising=False)
        db_session.add(
            AppSetting(
                key="features.packageManagement",
                value="false",
                value_type="bool",
                category="features",
            )
        )
        db_session.flush()
        resp = client.post(
            f"/api/v1/environments/{env.id}/packages",
            json={"name": "robotframework"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 403

    def test_blocked_attempt_is_audited(self, client, env, admin_user, db_session, monkeypatch):
        monkeypatch.setenv(ENV_FLAG, "false")
        client.post(
            f"/api/v1/environments/{env.id}/packages",
            json={"name": "robotframework"},
            headers=auth_header(admin_user),
        )
        rows = list(
            db_session.execute(
                select(AuditLog).where(AuditLog.action == "blocked")
            ).scalars().all()
        )
        assert any("feature_disabled:packageManagement" in (r.detail or "") for r in rows)


class TestRoleFloor:
    def test_viewer_blocked_by_role_floor_when_enabled(self, client, env, viewer_user, monkeypatch):
        monkeypatch.delenv(ENV_FLAG, raising=False)  # flag ON (default)
        resp = client.post(
            f"/api/v1/environments/{env.id}/packages",
            json={"name": "robotframework"},
            headers=auth_header(viewer_user),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "insufficient_role"

    def test_runner_blocked_at_default_editor_floor(self, client, env, runner_user, monkeypatch):
        # Adjacent boundary: RUNNER (1) < EDITOR (2) default floor → blocked.
        monkeypatch.delenv(ENV_FLAG, raising=False)
        resp = client.post(
            f"/api/v1/environments/{env.id}/packages",
            json={"name": "robotframework"},
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "insufficient_role"


class TestFeaturesEndpoint:
    def test_features_reflects_default_on(self, client, admin_user, monkeypatch):
        monkeypatch.delenv(ENV_FLAG, raising=False)
        resp = client.get("/api/v1/config/features", headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["flags"]["packageManagement"] is True
        assert body["locked"]["packageManagement"] is False

    def test_features_reflects_env_lock(self, client, admin_user, monkeypatch):
        monkeypatch.setenv(ENV_FLAG, "false")
        resp = client.get("/api/v1/config/features", headers=auth_header(admin_user))
        body = resp.json()
        assert body["flags"]["packageManagement"] is False
        assert body["locked"]["packageManagement"] is True

    def test_features_requires_auth(self, client):
        assert client.get("/api/v1/config/features").status_code == 401
