"""Tests for API token CRUD and authentication."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.webhooks.service import (
    TOKEN_PREFIX,
    create_api_token,
    get_token_by_hash,
    list_tokens,
    revoke_token,
    verify_token,
)
from tests.conftest import auth_header


class TestTokenService:
    """Unit tests for token service functions."""

    def test_generate_token_format(self, db_session: Session, admin_user):
        """Token starts with rbs_ prefix and is 68+ chars."""
        token_model, plaintext = create_api_token(
            db_session, name="test", role="runner", user_id=admin_user.id,
        )
        assert plaintext.startswith(TOKEN_PREFIX)
        assert len(plaintext) >= 68  # rbs_ + 64 hex chars

    def test_token_hash_matches(self, db_session: Session, admin_user):
        """Token can be found by hashing the plaintext."""
        token_model, plaintext = create_api_token(
            db_session, name="test", role="runner", user_id=admin_user.id,
        )
        token_hash = verify_token(plaintext)
        found = get_token_by_hash(db_session, token_hash)
        assert found is not None
        assert found.id == token_model.id

    def test_wrong_token_not_found(self, db_session: Session, admin_user):
        """Random token hash returns None."""
        create_api_token(db_session, name="test", role="runner", user_id=admin_user.id)
        found = get_token_by_hash(db_session, verify_token("rbs_wrong"))
        assert found is None

    def test_token_with_expiry(self, db_session: Session, admin_user):
        """Token with expiry has expires_at set."""
        token_model, _ = create_api_token(
            db_session, name="test", role="runner", user_id=admin_user.id,
            expires_in_days=30,
        )
        assert token_model.expires_at is not None
        # Compare as naive (SQLite stores without tz)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires = token_model.expires_at.replace(tzinfo=None) if token_model.expires_at.tzinfo else token_model.expires_at
        assert expires > now

    def test_token_without_expiry(self, db_session: Session, admin_user):
        """Token without expiry has expires_at=None."""
        token_model, _ = create_api_token(
            db_session, name="test", role="runner", user_id=admin_user.id,
        )
        assert token_model.expires_at is None

    def test_list_tokens(self, db_session: Session, admin_user):
        """List returns all active tokens."""
        create_api_token(db_session, name="t1", role="runner", user_id=admin_user.id)
        create_api_token(db_session, name="t2", role="editor", user_id=admin_user.id)
        tokens = list_tokens(db_session)
        assert len(tokens) == 2

    def test_revoke_token(self, db_session: Session, admin_user):
        """Revoking a token sets is_active=False."""
        token_model, _ = create_api_token(
            db_session, name="test", role="runner", user_id=admin_user.id,
        )
        revoked = revoke_token(db_session, token_model.id)
        assert revoked is not None
        assert revoked.is_active is False

    def test_revoked_token_not_in_list(self, db_session: Session, admin_user):
        """Revoked tokens don't appear in list."""
        token_model, _ = create_api_token(
            db_session, name="test", role="runner", user_id=admin_user.id,
        )
        revoke_token(db_session, token_model.id)
        tokens = list_tokens(db_session)
        assert len(tokens) == 0

    def test_prefix_display(self, db_session: Session, admin_user):
        """Prefix shows first 8 chars of random part."""
        token_model, plaintext = create_api_token(
            db_session, name="test", role="runner", user_id=admin_user.id,
        )
        expected_prefix = plaintext[:12]  # rbs_ + 8 hex chars
        assert token_model.prefix == expected_prefix


class TestTokenRouter:
    """API endpoint tests for tokens."""

    def test_create_token_admin(self, client, admin_user):
        """Admin can create a token."""
        resp = client.post(
            "/api/v1/webhooks/tokens",
            json={"name": "CI Token", "role": "runner"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "CI Token"
        assert data["role"] == "runner"
        assert "token" in data
        assert data["token"].startswith("rbs_")

    def test_create_token_non_admin_forbidden(self, client, runner_user):
        """Non-admin cannot create tokens."""
        resp = client.post(
            "/api/v1/webhooks/tokens",
            json={"name": "CI Token", "role": "runner"},
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 403

    def test_list_tokens(self, client, admin_user):
        """Admin can list tokens."""
        client.post(
            "/api/v1/webhooks/tokens",
            json={"name": "T1", "role": "runner"},
            headers=auth_header(admin_user),
        )
        resp = client.get(
            "/api/v1/webhooks/tokens",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_revoke_token(self, client, admin_user):
        """Admin can revoke a token."""
        create_resp = client.post(
            "/api/v1/webhooks/tokens",
            json={"name": "T1", "role": "runner"},
            headers=auth_header(admin_user),
        )
        token_id = create_resp.json()["id"]
        resp = client.delete(
            f"/api/v1/webhooks/tokens/{token_id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 204


class TestTokenAuth:
    """Tests for authenticating via API token instead of JWT."""

    def test_api_token_auth(self, client, admin_user):
        """API token can be used in Authorization header."""
        # Create token
        create_resp = client.post(
            "/api/v1/webhooks/tokens",
            json={"name": "Auth Test", "role": "runner"},
            headers=auth_header(admin_user),
        )
        token = create_resp.json()["token"]

        # Use API token to access /auth/me
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == admin_user.email

    def test_api_token_role_scoping(self, client, admin_user):
        """API token scopes role down — admin user with runner token can't admin."""
        create_resp = client.post(
            "/api/v1/webhooks/tokens",
            json={"name": "Runner Token", "role": "runner"},
            headers=auth_header(admin_user),
        )
        token = create_resp.json()["token"]

        # Runner token can't list users (admin-only)
        resp = client.get(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_revoked_token_rejected(self, client, admin_user):
        """Revoked token returns 401."""
        create_resp = client.post(
            "/api/v1/webhooks/tokens",
            json={"name": "Revoke Test", "role": "runner"},
            headers=auth_header(admin_user),
        )
        data = create_resp.json()
        token = data["token"]

        # Revoke
        client.delete(
            f"/api/v1/webhooks/tokens/{data['id']}",
            headers=auth_header(admin_user),
        )

        # Should fail
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    def test_invalid_token_rejected(self, client):
        """Random rbs_ token returns 401."""
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer rbs_invalid_token_value"},
        )
        assert resp.status_code == 401
