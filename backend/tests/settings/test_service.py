"""Tests for settings service."""

import pytest

from src.settings.models import AppSetting
from src.settings.schemas import SettingUpdate
from src.settings.service import (
    DEFAULT_SETTINGS,
    get_setting,
    get_setting_value,
    list_settings,
    seed_default_settings,
    update_settings,
)


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


class TestListSettings:
    def test_list_empty(self, db_session):
        """With no settings, should return an empty list."""
        result = list_settings(db_session)
        assert result == []

    def test_list_with_settings(self, db_session):
        """Should return all settings ordered by category and key."""
        s1 = _make_setting(key="beta_key", category="general")
        s2 = _make_setting(key="alpha_key", category="execution")
        s3 = _make_setting(key="gamma_key", category="general")
        db_session.add_all([s1, s2, s3])
        db_session.flush()

        result = list_settings(db_session)
        assert len(result) == 3
        # Ordered by category, then key
        assert result[0].key == "alpha_key"  # execution
        assert result[1].key == "beta_key"  # general
        assert result[2].key == "gamma_key"  # general

    def test_list_with_category_filter(self, db_session):
        """Should filter settings by category when specified."""
        s1 = _make_setting(key="exec_setting", category="execution", value="val1")
        s2 = _make_setting(key="gen_setting", category="general", value="val2")
        s3 = _make_setting(key="ret_setting", category="retention", value="val3")
        db_session.add_all([s1, s2, s3])
        db_session.flush()

        result = list_settings(db_session, category="execution")
        assert len(result) == 1
        assert result[0].key == "exec_setting"

    def test_list_with_nonexistent_category(self, db_session):
        """Filtering by a category that has no settings should return empty list."""
        s1 = _make_setting(key="some_key", category="general")
        db_session.add(s1)
        db_session.flush()

        result = list_settings(db_session, category="nonexistent")
        assert result == []


class TestGetSetting:
    def test_get_setting_found(self, db_session):
        """Should return the setting when it exists."""
        setting = _make_setting(key="find_me", value="found_value")
        db_session.add(setting)
        db_session.flush()

        result = get_setting(db_session, "find_me")
        assert result is not None
        assert result.key == "find_me"
        assert result.value == "found_value"

    def test_get_setting_not_found(self, db_session):
        """Should return None when the setting does not exist."""
        result = get_setting(db_session, "nonexistent_key")
        assert result is None


class TestGetSettingValue:
    def test_get_setting_value_exists(self, db_session):
        """Should return the value when the setting exists."""
        setting = _make_setting(key="my_key", value="my_value")
        db_session.add(setting)
        db_session.flush()

        result = get_setting_value(db_session, "my_key")
        assert result == "my_value"

    def test_get_setting_value_default(self, db_session):
        """Should return the default when the setting does not exist."""
        result = get_setting_value(db_session, "missing_key", default="fallback")
        assert result == "fallback"

    def test_get_setting_value_empty_default(self, db_session):
        """Should return empty string when setting is missing and no default given."""
        result = get_setting_value(db_session, "missing_key")
        assert result == ""


class TestUpdateSettings:
    def test_update_existing_settings(self, db_session):
        """Should update values for existing settings."""
        s1 = _make_setting(key="update_me", value="old_value")
        s2 = _make_setting(key="also_update", value="old_also")
        db_session.add_all([s1, s2])
        db_session.flush()

        updates = [
            SettingUpdate(key="update_me", value="new_value"),
            SettingUpdate(key="also_update", value="new_also"),
        ]
        result = update_settings(db_session, updates)

        assert len(result) == 2
        values = {s.key: s.value for s in result}
        assert values["update_me"] == "new_value"
        assert values["also_update"] == "new_also"

    def test_update_nonexistent_setting_ignored(self, db_session):
        """Updating a key that does not exist should be silently skipped."""
        s1 = _make_setting(key="real_key", value="real_value")
        db_session.add(s1)
        db_session.flush()

        updates = [
            SettingUpdate(key="real_key", value="updated"),
            SettingUpdate(key="ghost_key", value="ghost_value"),
        ]
        result = update_settings(db_session, updates)

        # Only the existing setting should be returned
        assert len(result) == 1
        assert result[0].key == "real_key"
        assert result[0].value == "updated"

    def test_update_empty_list(self, db_session):
        """Updating with an empty list should return an empty list."""
        result = update_settings(db_session, [])
        assert result == []


class TestSeedDefaultSettings:
    def test_seed_creates_defaults(self, db_session):
        """Seeding should create all default settings."""
        seed_default_settings(db_session)

        result = list_settings(db_session)
        assert len(result) == len(DEFAULT_SETTINGS)

        keys = {s.key for s in result}
        expected_keys = {d["key"] for d in DEFAULT_SETTINGS}
        assert keys == expected_keys

    def test_seed_is_idempotent(self, db_session):
        """Seeding twice should not create duplicate settings."""
        seed_default_settings(db_session)
        seed_default_settings(db_session)

        result = list_settings(db_session)
        assert len(result) == len(DEFAULT_SETTINGS)

    def test_seed_does_not_overwrite_existing(self, db_session):
        """Seeding should not overwrite a setting that already exists."""
        # Pre-create a setting with a custom value
        custom = _make_setting(
            key="default_runner",
            value="docker",
            value_type="string",
            category="execution",
            description="Custom description",
        )
        db_session.add(custom)
        db_session.flush()

        seed_default_settings(db_session)

        setting = get_setting(db_session, "default_runner")
        assert setting is not None
        # Value should remain the custom one, not the seed default
        assert setting.value == "docker"

    def test_seed_creates_correct_categories(self, db_session):
        """Seeded settings should have correct categories."""
        seed_default_settings(db_session)

        result = list_settings(db_session)
        category_map = {s.key: s.category for s in result}

        assert category_map["default_runner"] == "execution"
        assert category_map["max_parallel_runs"] == "execution"
        assert category_map["log_level"] == "general"
        assert category_map["report_retention_days"] == "retention"
        assert category_map["docker_default_image"] == "docker"
