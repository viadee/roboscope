"""Story 5-3: user deactivation cascade-revokes ApiTokens + audits.

Locks in:
  - PATCH /users/{id} with is_active=false revokes every active ApiToken
    owned by that user (sets is_active=False on each row).
  - Exactly one `user.deactivated` audit row per deactivation, with
    revoked_api_tokens count and revoked_token_ids list in detail.
  - Re-PATCH with is_active=false (idempotent, already-inactive user) does
    NOT double-emit the audit row and does NOT re-flip already-revoked
    tokens.
  - DELETE /users/{id} (soft-delete) performs the same cascade.
  - A deactivated user's existing JWT returns 401 (session invariance
    Story 2-6, kept as regression guard).
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.audit.models import AuditLog
from src.auth.models import User
from src.auth.service import hash_password
from src.webhooks.models import ApiToken
from src.webhooks.service import create_api_token
from tests.conftest import auth_header


def _mk_user(db: Session, email: str) -> User:
    u = User(
        email=email,
        username=email.split("@")[0],
        hashed_password=hash_password("pw"),
        role="runner",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _active_tokens(db: Session, user_id: int) -> list[ApiToken]:
    return (
        db.query(ApiToken)
        .filter(ApiToken.user_id == user_id, ApiToken.is_active.is_(True))
        .all()
    )


class TestDeactivationCascade:
    def test_patch_is_active_false_revokes_tokens(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        target = _mk_user(db_session, "deact-1@test.com")
        create_api_token(db_session, name="t1", role="runner", user_id=target.id)
        create_api_token(db_session, name="t2", role="runner", user_id=target.id)
        db_session.commit()

        assert len(_active_tokens(db_session, target.id)) == 2

        resp = client.patch(
            f"/api/v1/auth/users/{target.id}",
            json={"is_active": False},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        db_session.expire_all()
        assert len(_active_tokens(db_session, target.id)) == 0

    def test_deactivation_emits_audit_with_cascade_count(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        target = _mk_user(db_session, "deact-2@test.com")
        _t1, _ = create_api_token(db_session, name="t1", role="runner", user_id=target.id)
        _t2, _ = create_api_token(db_session, name="t2", role="runner", user_id=target.id)
        _t3, _ = create_api_token(db_session, name="t3", role="runner", user_id=target.id)
        db_session.commit()

        client.patch(
            f"/api/v1/auth/users/{target.id}",
            json={"is_active": False},
            headers=auth_header(admin_user),
        )

        audits = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action == "user.deactivated",
                AuditLog.resource_id == target.id,
            )
            .all()
        )
        assert len(audits) == 1
        detail = json.loads(audits[0].detail)
        assert detail["revoked_api_tokens"] == 3
        assert len(detail["revoked_token_ids"]) == 3
        from src.auth.pii_hash import hash_email, is_email_hash
        assert "email" not in detail, "plaintext email must not leak into audit detail"
        assert is_email_hash(detail["email_hash"])
        assert detail["email_hash"] == hash_email(target.email)

    def test_patch_already_inactive_user_does_not_reemit_audit(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        target = _mk_user(db_session, "deact-3@test.com")
        create_api_token(db_session, name="t1", role="runner", user_id=target.id)
        db_session.commit()

        client.patch(
            f"/api/v1/auth/users/{target.id}",
            json={"is_active": False},
            headers=auth_header(admin_user),
        )
        # Second deactivation: already inactive — must be a no-op audit-wise.
        client.patch(
            f"/api/v1/auth/users/{target.id}",
            json={"is_active": False},
            headers=auth_header(admin_user),
        )

        audits = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action == "user.deactivated",
                AuditLog.resource_id == target.id,
            )
            .all()
        )
        assert len(audits) == 1

    def test_delete_user_also_cascades(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        target = _mk_user(db_session, "deact-4@test.com")
        create_api_token(db_session, name="t1", role="runner", user_id=target.id)
        db_session.commit()

        resp = client.delete(
            f"/api/v1/auth/users/{target.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 204
        db_session.expire_all()
        assert len(_active_tokens(db_session, target.id)) == 0

        audits = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action == "user.deactivated",
                AuditLog.resource_id == target.id,
            )
            .all()
        )
        assert len(audits) == 1

    def test_deactivated_user_jwt_returns_401_regression(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        target = _mk_user(db_session, "deact-5@test.com")
        db_session.commit()

        headers = auth_header(target)
        pre = client.get("/api/v1/auth/me", headers=headers)
        assert pre.status_code == 200

        client.patch(
            f"/api/v1/auth/users/{target.id}",
            json={"is_active": False},
            headers=auth_header(admin_user),
        )

        post = client.get("/api/v1/auth/me", headers=headers)
        assert post.status_code == 401
