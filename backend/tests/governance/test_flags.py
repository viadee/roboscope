"""Unit tests for the GOV feature-flag resolver — precedence ENV > DB > default."""

import pytest

from src.auth.constants import Role
from src.governance.flags import (
    env_key,
    resolve_flag,
    resolve_package_op_role,
    settings_key,
)
from src.settings.models import AppSetting


def _set_db_flag(db, flag, value: str):
    db.add(
        AppSetting(
            key=settings_key(flag),
            value=value,
            value_type="bool",
            category="features",
        )
    )
    db.flush()


class TestEnvKey:
    def test_camel_to_upper_snake(self):
        assert env_key("packageManagement") == "ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT"


class TestPrecedence:
    def test_default_is_on_when_unset(self, db_session, monkeypatch):
        monkeypatch.delenv("ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT", raising=False)
        r = resolve_flag(db_session, "packageManagement")
        assert r.value is True
        assert r.locked is False

    def test_db_false_turns_off(self, db_session, monkeypatch):
        monkeypatch.delenv("ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT", raising=False)
        _set_db_flag(db_session, "packageManagement", "false")
        r = resolve_flag(db_session, "packageManagement")
        assert r.value is False
        assert r.locked is False

    def test_env_true_beats_db_false_and_locks(self, db_session, monkeypatch):
        _set_db_flag(db_session, "packageManagement", "false")
        monkeypatch.setenv("ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT", "true")
        r = resolve_flag(db_session, "packageManagement")
        assert r.value is True
        assert r.locked is True

    def test_env_false_beats_db_true_and_locks(self, db_session, monkeypatch):
        _set_db_flag(db_session, "packageManagement", "true")
        monkeypatch.setenv("ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT", "0")
        r = resolve_flag(db_session, "packageManagement")
        assert r.value is False
        assert r.locked is True

    @pytest.mark.parametrize("raw,expected", [("yes", True), ("on", True), ("no", False), ("off", False)])
    def test_bool_parsing_variants(self, db_session, monkeypatch, raw, expected):
        monkeypatch.setenv("ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT", raw)
        assert resolve_flag(db_session, "packageManagement").value is expected

    def test_garbage_env_falls_through_to_default(self, db_session, monkeypatch):
        monkeypatch.setenv("ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT", "maybe")
        # unparseable env is ignored → default ON, not locked
        r = resolve_flag(db_session, "packageManagement")
        assert r.value is True
        assert r.locked is False

    @pytest.mark.parametrize("raw,expected", [(" TRUE ", True), ("\toff\n", False), ("On", True)])
    def test_whitespace_and_case_insensitive(self, db_session, monkeypatch, raw, expected):
        monkeypatch.setenv("ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT", raw)
        assert resolve_flag(db_session, "packageManagement").value is expected

    def test_empty_db_value_falls_through_to_default(self, db_session, monkeypatch):
        monkeypatch.delenv("ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT", raising=False)
        _set_db_flag(db_session, "packageManagement", "")  # empty string == "unset"
        r = resolve_flag(db_session, "packageManagement")
        assert r.value is True
        assert r.locked is False


class TestRoleFloor:
    def test_default_is_editor(self, db_session):
        assert resolve_package_op_role(db_session, "install") == Role.EDITOR

    def test_db_override(self, db_session):
        db_session.add(
            AppSetting(
                key="features.packageManagement.role.install",
                value="admin",
                value_type="string",
                category="features",
            )
        )
        db_session.flush()
        assert resolve_package_op_role(db_session, "install") == Role.ADMIN

    def test_unknown_op_falls_back_to_default(self, db_session):
        assert resolve_package_op_role(db_session, "nonsense_op") == Role.EDITOR

    def test_invalid_role_falls_back_to_default(self, db_session):
        db_session.add(
            AppSetting(
                key="features.packageManagement.role.install",
                value="superuser",
                value_type="string",
                category="features",
            )
        )
        db_session.flush()
        assert resolve_package_op_role(db_session, "install") == Role.EDITOR
