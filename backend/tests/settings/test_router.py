"""Tests for settings API endpoints."""

import pytest

from src.settings.models import AppSetting
from src.settings.service import seed_default_settings
from tests.conftest import auth_header


def _make_setting(**overrides) -> AppSetting:
    """Helper to build an AppSetting with sensible defaults."""
    defaults = {
        "key": "test_key",
        "value": "test_value",
        "value_type": "string",
        "category": "general",
        "description": "A test setting",
    }
    defaults.update(overrides)
    return AppSetting(**defaults)


class TestGetSettings:
    def test_get_settings_as_admin(self, client, db_session, admin_user):
        """GET / as admin should return list of settings."""
        # Seed some settings
        s1 = _make_setting(key="setting_a", value="val_a", category="general")
        s2 = _make_setting(key="setting_b", value="val_b", category="execution")
        db_session.add_all([s1, s2])
        db_session.flush()

        response = client.get(
            "/api/v1/settings",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        # Each setting should have the expected fields
        keys = {s["key"] for s in data}
        assert "setting_a" in keys
        assert "setting_b" in keys

    def test_get_settings_as_non_admin_forbidden(self, client, runner_user):
        """GET / as non-admin should return 403."""
        response = client.get(
            "/api/v1/settings",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 403

    def test_get_settings_unauthenticated(self, client):
        """GET / without auth should return 401."""
        response = client.get("/api/v1/settings")
        assert response.status_code == 401

    def test_get_settings_empty(self, client, admin_user):
        """GET / should return empty list when no settings exist."""
        response = client.get(
            "/api/v1/settings",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_get_settings_with_category_filter(self, client, db_session, admin_user):
        """GET /?category=general should filter by category."""
        s1 = _make_setting(key="gen_key", value="gen_val", category="general")
        s2 = _make_setting(key="exec_key", value="exec_val", category="execution")
        s3 = _make_setting(key="gen_key2", value="gen_val2", category="general")
        db_session.add_all([s1, s2, s3])
        db_session.flush()

        response = client.get(
            "/api/v1/settings?category=general",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        categories = {s["category"] for s in data}
        assert categories == {"general"}

    def test_get_settings_response_schema(self, client, db_session, admin_user):
        """GET / response should match SettingResponse schema."""
        s = _make_setting(
            key="schema_check",
            value="42",
            value_type="int",
            category="execution",
            description="Schema validation test",
        )
        db_session.add(s)
        db_session.flush()

        response = client.get(
            "/api/v1/settings",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        setting = data[0]
        assert "id" in setting
        assert setting["key"] == "schema_check"
        assert setting["value"] == "42"
        assert setting["value_type"] == "int"
        assert setting["category"] == "execution"
        assert setting["description"] == "Schema validation test"


class TestPatchSettings:
    def test_patch_settings_as_admin(self, client, db_session, admin_user):
        """PATCH / as admin should update settings and return updated list."""
        s1 = _make_setting(key="patch_me", value="old_value")
        s2 = _make_setting(key="patch_also", value="old_also")
        db_session.add_all([s1, s2])
        db_session.flush()

        response = client.patch(
            "/api/v1/settings",
            json={
                "settings": [
                    {"key": "patch_me", "value": "new_value"},
                    {"key": "patch_also", "value": "new_also"},
                ]
            },
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        values = {s["key"]: s["value"] for s in data}
        assert values["patch_me"] == "new_value"
        assert values["patch_also"] == "new_also"

    def test_patch_settings_as_non_admin_forbidden(self, client, runner_user):
        """PATCH / as non-admin should return 403."""
        response = client.patch(
            "/api/v1/settings",
            json={"settings": [{"key": "some_key", "value": "some_value"}]},
            headers=auth_header(runner_user),
        )
        assert response.status_code == 403

    def test_patch_settings_unauthenticated(self, client):
        """PATCH / without auth should return 401."""
        response = client.patch(
            "/api/v1/settings",
            json={"settings": [{"key": "some_key", "value": "some_value"}]},
        )
        assert response.status_code == 401

    def test_patch_nonexistent_key_ignored(self, client, db_session, admin_user):
        """PATCH / with a key that does not exist should skip it silently."""
        s1 = _make_setting(key="exists_key", value="old")
        db_session.add(s1)
        db_session.flush()

        response = client.patch(
            "/api/v1/settings",
            json={
                "settings": [
                    {"key": "exists_key", "value": "updated"},
                    {"key": "ghost_key", "value": "ghost"},
                ]
            },
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["key"] == "exists_key"
        assert data[0]["value"] == "updated"

    def test_patch_empty_settings_list(self, client, admin_user):
        """PATCH / with empty settings list should return empty list."""
        response = client.patch(
            "/api/v1/settings",
            json={"settings": []},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_patch_then_get_reflects_changes(self, client, db_session, admin_user):
        """After PATCH, a subsequent GET should reflect the updated values."""
        s = _make_setting(key="verify_key", value="before")
        db_session.add(s)
        db_session.flush()

        # Update
        client.patch(
            "/api/v1/settings",
            json={"settings": [{"key": "verify_key", "value": "after"}]},
            headers=auth_header(admin_user),
        )

        # Verify via GET
        response = client.get(
            "/api/v1/settings",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["key"] == "verify_key"
        assert data[0]["value"] == "after"
