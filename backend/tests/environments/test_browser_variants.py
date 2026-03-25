"""Tests for Browser vs Browser-Batteries variant detection and mutual exclusion."""

import pytest
from unittest.mock import MagicMock

from src.environments.models import Environment, EnvironmentPackage
from src.environments.tasks import (
    _is_browser_package,
    _is_batteries_package,
    _is_any_browser_variant,
    _get_conflicting_browser_package,
)
from src.environments.service import (
    _has_browser_package,
    _has_batteries_package,
    generate_dockerfile,
)


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

class TestDetectionHelpers:
    """Test the _is_*_package helper functions."""

    def test_is_browser_package(self):
        assert _is_browser_package("robotframework-browser") is True
        assert _is_browser_package("robotframework_browser") is True
        assert _is_browser_package("ROBOTFRAMEWORK-BROWSER") is True

    def test_is_browser_package_rejects_batteries(self):
        assert _is_browser_package("robotframework-browser-batteries") is False

    def test_is_batteries_package(self):
        assert _is_batteries_package("robotframework-browser-batteries") is True
        assert _is_batteries_package("robotframework_browser_batteries") is True
        assert _is_batteries_package("ROBOTFRAMEWORK-BROWSER-BATTERIES") is True

    def test_is_batteries_package_rejects_standard(self):
        assert _is_batteries_package("robotframework-browser") is False

    def test_is_any_browser_variant(self):
        assert _is_any_browser_variant("robotframework-browser") is True
        assert _is_any_browser_variant("robotframework-browser-batteries") is True
        assert _is_any_browser_variant("robotframework-requests") is False

    def test_has_browser_package_with_version(self):
        assert _has_browser_package(["robotframework-browser==18.0.0"]) is True
        assert _has_browser_package(["robotframework-browser>=17.0"]) is True

    def test_has_batteries_package_with_version(self):
        assert _has_batteries_package(["robotframework-browser-batteries==1.0.0"]) is True
        assert _has_batteries_package(["robotframework-browser-batteries"]) is True

    def test_has_browser_does_not_match_batteries(self):
        assert _has_browser_package(["robotframework-browser-batteries"]) is False

    def test_has_batteries_does_not_match_standard(self):
        assert _has_batteries_package(["robotframework-browser"]) is False


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

class TestConflictDetection:
    """Test _get_conflicting_browser_package."""

    def _make_env_with_pkg(self, session, pkg_name, pkg_status="installed"):
        env = Environment(name="test", venv_path="/tmp/v", python_version="3.12", created_by=1)
        session.add(env)
        session.flush()
        pkg = EnvironmentPackage(
            environment_id=env.id,
            package_name=pkg_name,
            install_status=pkg_status,
        )
        session.add(pkg)
        session.flush()
        return env

    def test_no_conflict_for_non_browser(self, db_session):
        env = self._make_env_with_pkg(db_session, "robotframework-browser")
        result = _get_conflicting_browser_package(env.id, "robotframework-requests", db_session)
        assert result is None

    def test_conflict_when_browser_installed_and_batteries_requested(self, db_session):
        env = self._make_env_with_pkg(db_session, "robotframework-browser")
        result = _get_conflicting_browser_package(env.id, "robotframework-browser-batteries", db_session)
        assert result == "robotframework-browser"

    def test_conflict_when_batteries_installed_and_browser_requested(self, db_session):
        env = self._make_env_with_pkg(db_session, "robotframework-browser-batteries")
        result = _get_conflicting_browser_package(env.id, "robotframework-browser", db_session)
        assert result == "robotframework-browser-batteries"

    def test_no_conflict_when_same_variant(self, db_session):
        env = self._make_env_with_pkg(db_session, "robotframework-browser")
        result = _get_conflicting_browser_package(env.id, "robotframework-browser", db_session)
        assert result is None

    def test_no_conflict_when_other_is_failed(self, db_session):
        env = self._make_env_with_pkg(db_session, "robotframework-browser", pkg_status="failed")
        result = _get_conflicting_browser_package(env.id, "robotframework-browser-batteries", db_session)
        assert result is None  # Failed packages don't count as conflicting


# ---------------------------------------------------------------------------
# Dockerfile generation
# ---------------------------------------------------------------------------

class TestDockerfileGeneration:
    """Test generate_dockerfile for both Browser variants."""

    def test_standard_browser_includes_nodejs_and_rfbrowser_init(self):
        df = generate_dockerfile("3.12", ["robotframework", "robotframework-browser"])
        assert "nodejs" in df
        assert "rfbrowser init" in df
        assert "playwright" in df.lower()

    def test_batteries_skips_nodejs_and_rfbrowser_init(self):
        df = generate_dockerfile("3.12", ["robotframework", "robotframework-browser-batteries"])
        assert "nodejs" not in df
        assert "rfbrowser init" not in df
        # Still uses Playwright base image for system deps
        assert "playwright" in df.lower()

    def test_no_browser_uses_slim_image(self):
        df = generate_dockerfile("3.12", ["robotframework", "robotframework-requests"])
        assert "python:3.12-slim" in df
        assert "playwright" not in df.lower()
        assert "rfbrowser" not in df

    def test_custom_base_image_overrides(self):
        df = generate_dockerfile("3.12", ["robotframework-browser"], base_image="my-custom:latest")
        assert "FROM my-custom:latest" in df


# ---------------------------------------------------------------------------
# Router conflict check (HTTP 409)
# ---------------------------------------------------------------------------

class TestRouterConflictCheck:
    """Test that the install endpoint returns 409 on browser variant conflict."""

    def test_install_browser_when_batteries_exists(self, client, admin_user, db_session):
        from tests.conftest import auth_header

        env = Environment(name="test", venv_path="/tmp/v", python_version="3.12", created_by=admin_user.id)
        db_session.add(env)
        db_session.flush()
        pkg = EnvironmentPackage(
            environment_id=env.id,
            package_name="robotframework-browser-batteries",
            install_status="installed",
        )
        db_session.add(pkg)
        db_session.commit()

        resp = client.post(
            f"/api/v1/environments/{env.id}/packages",
            json={"package_name": "robotframework-browser"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 409
        assert "conflicting" in resp.json()["detail"].lower()

    def test_install_non_browser_succeeds(self, client, admin_user, db_session):
        from tests.conftest import auth_header

        env = Environment(name="test2", venv_path="/tmp/v2", python_version="3.12", created_by=admin_user.id)
        db_session.add(env)
        db_session.flush()
        pkg = EnvironmentPackage(
            environment_id=env.id,
            package_name="robotframework-browser",
            install_status="installed",
        )
        db_session.add(pkg)
        db_session.commit()

        resp = client.post(
            f"/api/v1/environments/{env.id}/packages",
            json={"package_name": "robotframework-requests"},
            headers=auth_header(admin_user),
        )
        # 201 or 503 (task dispatch may fail in test env, but not 409)
        assert resp.status_code != 409
