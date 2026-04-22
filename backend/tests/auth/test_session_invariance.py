"""Story 2-6: session invariance during IdP outage.

Locks in three invariants of the JWT-based auth flow:
  1. Valid JWT requests succeed even when the IdP is unreachable
     (stateless validation — no IdP roundtrip per request).
  2. `User.is_active` is re-checked on every request (no cache).
  3. Deactivated users receive HTTP 401 so clients prompt re-auth.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.constants import ERR_INACTIVE_USER
from src.auth.models import User
from tests.conftest import auth_header


ME_ENDPOINT = "/api/v1/auth/me"


class TestSessionInvariance:
    def test_valid_jwt_succeeds_during_idp_outage(
        self, client: TestClient, admin_user: User
    ) -> None:
        """AC1: JWT auth is stateless — no IdP call happens per request.

        We patch the OIDC discovery module (the only place the backend
        talks to the IdP) to raise on any call. The TestClient's own
        httpx transport is unaffected because it's the in-process ASGI
        transport, not an outbound HTTP call.
        """
        def _fail(*_args, **_kwargs):
            raise httpx.ConnectError("simulated IdP outage")

        # Patch every module-level discovery helper that would touch the IdP.
        # If the auth path tries to reach the IdP, these raise loudly.
        with (
            patch(
                "src.auth.oidc_discovery.probe_idp_discovery",
                side_effect=_fail,
            ),
            patch(
                "src.auth.oidc_discovery.get_or_fetch_discovery",
                side_effect=_fail,
            ),
            patch(
                "src.auth.oidc_discovery._fetch_json_object",
                side_effect=_fail,
            ),
        ):
            resp = client.get(ME_ENDPOINT, headers=auth_header(admin_user))
            assert resp.status_code == 200
            assert resp.json()["email"] == "admin@test.com"

    def test_deactivated_user_returns_401(
        self,
        client: TestClient,
        admin_user: User,
        db_session: Session,
    ) -> None:
        """AC3: deactivated users get 401 (not 403)."""
        headers = auth_header(admin_user)

        admin_user.is_active = False
        db_session.commit()

        resp = client.get(ME_ENDPOINT, headers=headers)
        assert resp.status_code == 401
        assert resp.json()["detail"] == ERR_INACTIVE_USER

    def test_is_active_is_rechecked_on_every_request(
        self,
        client: TestClient,
        admin_user: User,
        db_session: Session,
    ) -> None:
        """AC2: no cache — deactivation takes effect on the next request."""
        headers = auth_header(admin_user)

        first = client.get(ME_ENDPOINT, headers=headers)
        assert first.status_code == 200

        admin_user.is_active = False
        db_session.commit()

        second = client.get(ME_ENDPOINT, headers=headers)
        assert second.status_code == 401


class TestApiTokenSessionInvariance:
    def test_api_token_with_deactivated_user_is_rejected(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        """AC4: the API-token path also respects is_active."""
        from src.webhooks.service import create_api_token

        _api_token, raw_token = create_api_token(
            db_session,
            name="test-api-token",
            role="admin",
            user_id=admin_user.id,
        )
        db_session.commit()

        headers = {"Authorization": f"Bearer {raw_token}"}

        active = client.get(ME_ENDPOINT, headers=headers)
        assert active.status_code == 200

        admin_user.is_active = False
        db_session.commit()

        deactivated = client.get(ME_ENDPOINT, headers=headers)
        assert deactivated.status_code == 401
