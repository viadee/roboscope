"""Story 2-5: public SSO settings endpoint (no auth required).

Exposes the subset of admin settings that the unauthenticated login page
needs to render correctly. No secrets, no internal endpoints.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.settings.models import AppSetting

ENDPOINT = "/api/v1/auth/sso/public-settings"


@pytest.fixture
def seed_settings(db_session: Session) -> None:
    """Seed the two settings the endpoint surfaces."""
    db_session.add(
        AppSetting(
            key="hide_local_login_form",
            value="false",
            value_type="bool",
            category="auth",
        )
    )
    db_session.add(
        AppSetting(
            key="admin_contact_email",
            value="security@example.com",
            value_type="string",
            category="auth",
        )
    )
    db_session.commit()


class TestPublicSsoSettings:
    def test_endpoint_is_unauthenticated(
        self, client: TestClient, seed_settings
    ) -> None:
        """No Authorization header → 200 with the expected shape."""
        resp = client.get(ENDPOINT)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"hide_local_login_form", "admin_contact_email"}
        assert body["hide_local_login_form"] is False
        assert body["admin_contact_email"] == "security@example.com"

    def test_reflects_hide_local_login_form_true(
        self, client: TestClient, db_session: Session, seed_settings
    ) -> None:
        """Flipping the setting to 'true' is reflected in the response."""
        row = (
            db_session.query(AppSetting)
            .filter(AppSetting.key == "hide_local_login_form")
            .one()
        )
        row.value = "true"
        db_session.commit()

        resp = client.get(ENDPOINT)
        assert resp.status_code == 200
        assert resp.json()["hide_local_login_form"] is True

    def test_case_insensitive_true_parsing(
        self, client: TestClient, db_session: Session, seed_settings
    ) -> None:
        """The service stores the string value verbatim; parsing is lower()."""
        row = (
            db_session.query(AppSetting)
            .filter(AppSetting.key == "hide_local_login_form")
            .one()
        )
        row.value = "True"
        db_session.commit()

        resp = client.get(ENDPOINT)
        assert resp.status_code == 200
        assert resp.json()["hide_local_login_form"] is True

    def test_defaults_when_settings_missing(self, client: TestClient) -> None:
        """When no seed rows exist (fresh DB), the endpoint still returns 200."""
        resp = client.get(ENDPOINT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["hide_local_login_form"] is False
        assert body["admin_contact_email"] == ""
