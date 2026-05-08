"""Story SECURITY-1 — force the seed admin to rotate the default password.

Covers:
- `ensure_admin_exists` marks the seed admin and pessimistically
  upgrades any pre-existing admin still using the well-known default.
- The new `POST /auth/change-password` endpoint clears the flag
  and rejects the standard error cases.
- `/auth/me` surfaces the flag in both states.
- Login emits a WARNING to `roboscope.auth` when the flag is set.
"""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.models import User
from src.auth.service import (
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_ADMIN_PASSWORD,
    authenticate_user,
    ensure_admin_exists,
    hash_password,
)
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# ensure_admin_exists — fresh DB + legacy upgrade
# ---------------------------------------------------------------------------


class TestEnsureAdminExists:
    def test_fresh_db_seeds_admin_with_flag(self, db_session: Session):
        # Wipe any conftest-created users so this is a real "first ever" call.
        db_session.execute(User.__table__.delete())
        db_session.flush()

        ensure_admin_exists(db_session)

        admin = db_session.execute(
            select(User).where(User.email == DEFAULT_ADMIN_EMAIL)
        ).scalar_one()
        assert admin.password_change_required is True
        assert admin.role == Role.ADMIN

    def test_legacy_admin_with_default_password_gets_upgraded(
        self, db_session: Session,
    ):
        """A pre-existing admin row still on the well-known default
        password gets the flag flipped on by `ensure_admin_exists`.
        """
        db_session.execute(User.__table__.delete())
        legacy = User(
            email="legacy-admin@example.com",
            username="legacy-admin",
            hashed_password=hash_password(DEFAULT_ADMIN_PASSWORD),
            role=Role.ADMIN,
            password_change_required=False,
        )
        db_session.add(legacy)
        db_session.flush()

        ensure_admin_exists(db_session)

        db_session.refresh(legacy)
        assert legacy.password_change_required is True

    def test_user_with_custom_password_is_not_flipped(
        self, db_session: Session,
    ):
        db_session.execute(User.__table__.delete())
        normal = User(
            email="normal@example.com",
            username="normal",
            hashed_password=hash_password("not-the-default-pw"),
            role=Role.EDITOR,
            password_change_required=False,
        )
        db_session.add(normal)
        db_session.flush()

        ensure_admin_exists(db_session)

        db_session.refresh(normal)
        assert normal.password_change_required is False


# ---------------------------------------------------------------------------
# authenticate_user — WARNING on flagged login
# ---------------------------------------------------------------------------


class TestAuthLogsWarning:
    def test_login_emits_warning_when_flag_set(
        self, db_session: Session, caplog,
    ):
        user = User(
            email="flagged@example.com",
            username="flagged",
            hashed_password=hash_password("correct-horse"),
            role=Role.EDITOR,
            is_active=True,
            password_change_required=True,
        )
        db_session.add(user)
        db_session.flush()

        with caplog.at_level(logging.WARNING, logger="roboscope.auth"):
            result = authenticate_user(db_session, user.email, "correct-horse")

        assert result is not None
        assert any(
            "password_change_required=True" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        )

    def test_login_no_warning_when_flag_clear(
        self, db_session: Session, caplog,
    ):
        user = User(
            email="clean@example.com",
            username="clean",
            hashed_password=hash_password("correct-horse"),
            role=Role.EDITOR,
            is_active=True,
            password_change_required=False,
        )
        db_session.add(user)
        db_session.flush()

        with caplog.at_level(logging.WARNING, logger="roboscope.auth"):
            authenticate_user(db_session, user.email, "correct-horse")

        assert not any(
            "password_change_required" in r.message for r in caplog.records
        )


# ---------------------------------------------------------------------------
# /auth/change-password endpoint
# ---------------------------------------------------------------------------


@pytest.fixture
def flagged_user(db_session: Session) -> User:
    user = User(
        email="rotate-me@example.com",
        username="rotate-me",
        hashed_password=hash_password("originalPW1"),
        role=Role.EDITOR,
        is_active=True,
        password_change_required=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


class TestChangePasswordEndpoint:
    def test_happy_path_clears_flag(self, client, db_session, flagged_user):
        resp = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "originalPW1",
                "new_password": "brandNewSecret9",
            },
            headers=auth_header(flagged_user),
        )
        assert resp.status_code == 204
        db_session.refresh(flagged_user)
        assert flagged_user.password_change_required is False
        # Password was actually rotated:
        from src.auth.service import verify_password
        assert verify_password("brandNewSecret9", flagged_user.hashed_password)
        assert not verify_password("originalPW1", flagged_user.hashed_password)

    def test_rejects_wrong_current(self, client, flagged_user):
        resp = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "WRONG",
                "new_password": "brandNewSecret9",
            },
            headers=auth_header(flagged_user),
        )
        assert resp.status_code == 401

    def test_rejects_short_new(self, client, flagged_user):
        # Pydantic 422 from min_length=8 in the schema.
        resp = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "originalPW1",
                "new_password": "short",
            },
            headers=auth_header(flagged_user),
        )
        assert resp.status_code == 422

    def test_rejects_same_as_current(self, client, flagged_user):
        resp = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "originalPW1",
                "new_password": "originalPW1",
            },
            headers=auth_header(flagged_user),
        )
        assert resp.status_code == 422

    def test_unauthenticated_rejected(self, client):
        resp = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "x",
                "new_password": "12345678",
            },
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /auth/me surfaces the flag
# ---------------------------------------------------------------------------


class TestMeIncludesFlag:
    def test_flag_true_for_flagged_user(self, client, flagged_user):
        resp = client.get(
            "/api/v1/auth/me",
            headers=auth_header(flagged_user),
        )
        assert resp.status_code == 200
        assert resp.json()["password_change_required"] is True

    def test_flag_false_for_normal_user(self, client, admin_user):
        resp = client.get(
            "/api/v1/auth/me",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["password_change_required"] is False
