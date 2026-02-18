"""Tests for auth service."""

import pytest
from src.auth.service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_id,
)
from src.auth.schemas import RegisterRequest


class TestPasswordHashing:
    def test_hash_password_returns_different_hash(self):
        hashed = hash_password("secret123")
        assert hashed != "secret123"
        assert len(hashed) > 20

    def test_verify_password_correct(self):
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("secret123")
        assert verify_password("wrong", hashed) is False


class TestJwt:
    def test_create_access_token_contains_user_id(self):
        token = create_access_token(42, "admin")
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_create_refresh_token_type(self):
        token = create_refresh_token(42)
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["type"] == "refresh"

    def test_decode_invalid_token_raises(self):
        with pytest.raises(ValueError):
            decode_token("invalid.token.here")


class TestUserService:
    def test_create_user(self, db_session):
        data = RegisterRequest(
            email="new@test.com",
            username="newuser",
            password="pass123",
        )
        user = create_user(db_session, data)
        assert user.id is not None
        assert user.email == "new@test.com"
        assert user.username == "newuser"
        assert user.hashed_password != "pass123"

    def test_get_user_by_email(self, db_session, admin_user):
        user = get_user_by_email(db_session, "admin@test.com")
        assert user is not None
        assert user.id == admin_user.id

    def test_get_user_by_email_not_found(self, db_session):
        user = get_user_by_email(db_session, "nonexistent@test.com")
        assert user is None

    def test_get_user_by_id(self, db_session, admin_user):
        user = get_user_by_id(db_session, admin_user.id)
        assert user is not None
        assert user.email == "admin@test.com"

    def test_authenticate_user_correct(self, db_session, admin_user):
        user = authenticate_user(db_session, "admin@test.com", "admin123")
        assert user is not None
        assert user.id == admin_user.id

    def test_authenticate_user_wrong_password(self, db_session, admin_user):
        user = authenticate_user(db_session, "admin@test.com", "wrong")
        assert user is None

    def test_authenticate_user_nonexistent(self, db_session):
        user = authenticate_user(db_session, "ghost@test.com", "pass")
        assert user is None
