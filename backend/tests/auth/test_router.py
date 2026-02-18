"""Tests for auth API endpoints."""

import pytest
from tests.conftest import auth_header


class TestLogin:
    async def test_login_success(self, client, admin_user):
        response = await client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client, admin_user):
        response = await client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "wrongpass",
        })
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client):
        response = await client.post("/api/v1/auth/login", json={
            "email": "ghost@test.com",
            "password": "pass123",
        })
        assert response.status_code == 401


class TestMe:
    async def test_get_me_authenticated(self, client, admin_user):
        response = await client.get("/api/v1/auth/me", headers=auth_header(admin_user))
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@test.com"
        assert data["role"] == "admin"

    async def test_get_me_no_token(self, client):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 403

    async def test_get_me_invalid_token(self, client):
        response = await client.get("/api/v1/auth/me", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert response.status_code == 401


class TestRefresh:
    async def test_refresh_token(self, client, admin_user):
        # First login
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123",
        })
        refresh_token = login_resp.json()["refresh_token"]

        # Refresh
        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_refresh_invalid_token(self, client):
        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid",
        })
        assert response.status_code == 401


class TestUserManagement:
    async def test_list_users_admin(self, client, admin_user):
        response = await client.get("/api/v1/auth/users", headers=auth_header(admin_user))
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_list_users_non_admin_forbidden(self, client, runner_user):
        response = await client.get("/api/v1/auth/users", headers=auth_header(runner_user))
        assert response.status_code == 403

    async def test_create_user_admin(self, client, admin_user):
        response = await client.post("/api/v1/auth/users", json={
            "email": "new@test.com",
            "username": "newuser",
            "password": "pass123",
            "role": "runner",
        }, headers=auth_header(admin_user))
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@test.com"
        assert data["role"] == "runner"

    async def test_create_user_duplicate_email(self, client, admin_user):
        response = await client.post("/api/v1/auth/users", json={
            "email": "admin@test.com",
            "username": "dup",
            "password": "pass123",
        }, headers=auth_header(admin_user))
        assert response.status_code == 409

    async def test_patch_user(self, client, admin_user, runner_user):
        response = await client.patch(
            f"/api/v1/auth/users/{runner_user.id}",
            json={"role": "editor"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        assert response.json()["role"] == "editor"

    async def test_delete_user(self, client, admin_user, viewer_user):
        response = await client.delete(
            f"/api/v1/auth/users/{viewer_user.id}",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 204

    async def test_delete_self_forbidden(self, client, admin_user):
        response = await client.delete(
            f"/api/v1/auth/users/{admin_user.id}",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 400


class TestPasswordReset:
    async def test_admin_can_reset_user_password(self, client, admin_user, runner_user):
        """Admin should be able to reset another user's password via PATCH."""
        response = await client.patch(
            f"/api/v1/auth/users/{runner_user.id}",
            json={"password": "newpass123"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200

        # Verify the new password works by logging in
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "runner@test.com",
            "password": "newpass123",
        })
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.json()

    async def test_old_password_no_longer_works(self, client, admin_user, runner_user):
        """After password reset, old password should fail."""
        # Reset password
        await client.patch(
            f"/api/v1/auth/users/{runner_user.id}",
            json={"password": "brandnew456"},
            headers=auth_header(admin_user),
        )

        # Old password should fail
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "runner@test.com",
            "password": "runner123",
        })
        assert login_resp.status_code == 401

    async def test_password_too_short_rejected(self, client, admin_user, runner_user):
        """Password shorter than 6 characters should be rejected."""
        response = await client.patch(
            f"/api/v1/auth/users/{runner_user.id}",
            json={"password": "abc"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 422

    async def test_non_admin_cannot_reset_password(self, client, runner_user, viewer_user):
        """Non-admin user should not be able to reset passwords."""
        response = await client.patch(
            f"/api/v1/auth/users/{viewer_user.id}",
            json={"password": "newpass123"},
            headers=auth_header(runner_user),
        )
        assert response.status_code == 403

    async def test_reset_password_with_other_fields(self, client, admin_user, runner_user):
        """Password reset can be combined with other field updates."""
        response = await client.patch(
            f"/api/v1/auth/users/{runner_user.id}",
            json={"password": "combo123", "username": "runner_updated"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "runner_updated"

        # Verify new password works
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "runner@test.com",
            "password": "combo123",
        })
        assert login_resp.status_code == 200
