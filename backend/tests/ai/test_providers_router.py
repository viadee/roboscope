"""Story TEST-3 — `/api/v1/ai/providers` CRUD endpoint coverage.

Until this story the four provider-management endpoints (list,
create, update, delete) had no router-level tests; only `service.py`
helpers were exercised. The endpoints are admin-gated and never
expose API keys (a leak here would cost real money), so they're
exactly the kind of surface where a regression bites quietly.

These tests pin down:
  - 200 / 201 / 204 happy paths
  - admin-only enforcement (runner / unauthenticated → 401/403)
  - 404 on unknown provider id (update + delete)
  - the response shape *never* includes `api_key` or
    `api_key_encrypted`, only the boolean `has_api_key`
  - is_default mutual-exclusion: setting True flips others
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.ai.models import AiProvider
from src.ai.service import create_provider
from src.ai.schemas import AiProviderCreate
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# helpers — seed providers via the service layer
# ---------------------------------------------------------------------------


def _seed(db: Session, admin_user, **overrides) -> AiProvider:
    defaults = dict(
        name="a-provider",
        provider_type="openai",
        api_base_url=None,
        api_key="sk-test-secret",
        model_name="gpt-4o-mini",
        temperature=0.3,
        max_tokens=4096,
        is_default=False,
    )
    defaults.update(overrides)
    data = AiProviderCreate(**defaults)
    return create_provider(db, data, admin_user.id)


# ---------------------------------------------------------------------------
# GET /providers — list
# ---------------------------------------------------------------------------


class TestListProviders:
    def test_empty(self, client, admin_user):
        resp = client.get(
            "/api/v1/ai/providers",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_seeded(self, client, db_session, admin_user):
        _seed(db_session, admin_user, name="alpha")
        _seed(db_session, admin_user, name="beta")
        resp = client.get(
            "/api/v1/ai/providers",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        names = sorted(p["name"] for p in resp.json())
        assert names == ["alpha", "beta"]

    def test_response_omits_api_key(self, client, db_session, admin_user):
        _seed(db_session, admin_user, name="secret")
        resp = client.get(
            "/api/v1/ai/providers",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()[0]
        # Must not leak the encrypted blob, and the plaintext must
        # have been encrypted at rest before the response was built.
        assert "api_key" not in body
        assert "api_key_encrypted" not in body
        # Presence is signalled via a boolean flag.
        assert body["has_api_key"] is True

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/api/v1/ai/providers")
        assert resp.status_code == 401

    def test_runner_can_list(self, client, runner_user):
        # Listing is gated only by `get_current_user` (any authed role
        # can read). Document & lock that in.
        resp = client.get(
            "/api/v1/ai/providers",
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /providers — create
# ---------------------------------------------------------------------------


class TestCreateProvider:
    def test_happy_path(self, client, admin_user, db_session):
        resp = client.post(
            "/api/v1/ai/providers",
            headers=auth_header(admin_user),
            json={
                "name": "new-provider",
                "provider_type": "anthropic",
                "model_name": "claude-3-5-sonnet",
                "api_key": "sk-anthropic-secret",
                "temperature": 0.5,
                "max_tokens": 8192,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "new-provider"
        assert body["provider_type"] == "anthropic"
        assert body["has_api_key"] is True
        # The plaintext api_key never round-trips back.
        assert "api_key" not in body
        # Stored encrypted, not plaintext.
        from src.ai.models import AiProvider
        from sqlalchemy import select
        row = db_session.execute(
            select(AiProvider).where(AiProvider.id == body["id"])
        ).scalar_one()
        assert row.api_key_encrypted is not None
        assert row.api_key_encrypted != "sk-anthropic-secret"

    def test_no_api_key_marks_has_api_key_false(self, client, admin_user):
        resp = client.post(
            "/api/v1/ai/providers",
            headers=auth_header(admin_user),
            json={
                "name": "no-key-provider",
                "provider_type": "ollama",
                "model_name": "llama3",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["has_api_key"] is False

    def test_invalid_provider_type_422(self, client, admin_user):
        resp = client.post(
            "/api/v1/ai/providers",
            headers=auth_header(admin_user),
            json={
                "name": "x",
                "provider_type": "totally-fake-vendor",
                "model_name": "x",
            },
        )
        assert resp.status_code == 422

    def test_runner_user_forbidden(self, client, runner_user):
        resp = client.post(
            "/api/v1/ai/providers",
            headers=auth_header(runner_user),
            json={
                "name": "x", "provider_type": "openai", "model_name": "x",
            },
        )
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client):
        resp = client.post("/api/v1/ai/providers", json={
            "name": "x", "provider_type": "openai", "model_name": "x",
        })
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /providers/{id} — update
# ---------------------------------------------------------------------------


class TestUpdateProvider:
    def test_partial_update(self, client, admin_user, db_session):
        prov = _seed(db_session, admin_user, name="orig", temperature=0.3)
        resp = client.patch(
            f"/api/v1/ai/providers/{prov.id}",
            headers=auth_header(admin_user),
            json={"temperature": 0.9},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["temperature"] == 0.9
        # Untouched fields remain.
        assert body["name"] == "orig"

    def test_unset_api_key_via_empty_string(self, client, admin_user, db_session):
        prov = _seed(db_session, admin_user, name="had-key")
        resp = client.patch(
            f"/api/v1/ai/providers/{prov.id}",
            headers=auth_header(admin_user),
            json={"api_key": ""},
        )
        assert resp.status_code == 200
        # An empty string clears the encrypted blob (service treats
        # falsy as "remove the key").
        assert resp.json()["has_api_key"] is False

    def test_404_on_unknown_id(self, client, admin_user):
        resp = client.patch(
            "/api/v1/ai/providers/99999",
            headers=auth_header(admin_user),
            json={"temperature": 0.5},
        )
        assert resp.status_code == 404

    def test_runner_user_forbidden(self, client, runner_user, admin_user, db_session):
        prov = _seed(db_session, admin_user, name="locked")
        resp = client.patch(
            f"/api/v1/ai/providers/{prov.id}",
            headers=auth_header(runner_user),
            json={"temperature": 0.5},
        )
        assert resp.status_code == 403


class TestUpdateIsDefaultMutex:
    def test_setting_default_true_clears_other_defaults(
        self, client, admin_user, db_session,
    ):
        a = _seed(db_session, admin_user, name="A", is_default=True)
        b = _seed(db_session, admin_user, name="B", is_default=False)
        # Promote B → A must lose default.
        resp = client.patch(
            f"/api/v1/ai/providers/{b.id}",
            headers=auth_header(admin_user),
            json={"is_default": True},
        )
        assert resp.status_code == 200
        # Re-fetch both via list.
        listing = client.get(
            "/api/v1/ai/providers", headers=auth_header(admin_user),
        ).json()
        by_id = {p["id"]: p for p in listing}
        assert by_id[a.id]["is_default"] is False
        assert by_id[b.id]["is_default"] is True


# ---------------------------------------------------------------------------
# DELETE /providers/{id}
# ---------------------------------------------------------------------------


class TestDeleteProvider:
    def test_204_on_success(self, client, admin_user, db_session):
        prov = _seed(db_session, admin_user, name="del-me")
        resp = client.delete(
            f"/api/v1/ai/providers/{prov.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 204
        # Subsequent GET returns 404 via list-empty.
        listing = client.get(
            "/api/v1/ai/providers", headers=auth_header(admin_user),
        ).json()
        assert all(p["id"] != prov.id for p in listing)

    def test_404_on_unknown_id(self, client, admin_user):
        resp = client.delete(
            "/api/v1/ai/providers/99999",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    def test_runner_user_forbidden(self, client, runner_user, admin_user, db_session):
        prov = _seed(db_session, admin_user, name="cant-delete")
        resp = client.delete(
            f"/api/v1/ai/providers/{prov.id}",
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client, admin_user, db_session):
        prov = _seed(db_session, admin_user, name="needs-auth")
        resp = client.delete(f"/api/v1/ai/providers/{prov.id}")
        assert resp.status_code == 401
