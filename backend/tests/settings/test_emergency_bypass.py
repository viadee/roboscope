"""Story 5-1: Emergency-bypass toggle API + auto-expire."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.audit.models import AuditLog
from src.auth.models import User
from src.auth.retention_cleanup import expire_sso_emergency_bypass
from src.auth.service import hash_password
from src.settings.service import get_setting_value, seed_default_settings
from tests.conftest import auth_header


ENDPOINT = "/api/v1/settings/sso-emergency-bypass"


def _mk_editor(db: Session) -> User:
    u = User(
        email="edit-bypass@test.com",
        username="edit-bypass",
        hashed_password=hash_password("pw"),
        role="editor",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


class TestActivate:
    def test_admin_activates_writes_flag_expires_and_audit(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        seed_default_settings(db_session)
        db_session.commit()

        resp = client.post(
            ENDPOINT, json={"hours": 4}, headers=auth_header(admin_user)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["active"] is True
        assert body["expires_at"] is not None
        assert body["max_hours"] == 24

        assert get_setting_value(db_session, "sso_emergency_bypass") == "true"
        expires = get_setting_value(db_session, "sso_emergency_bypass_expires_at")
        assert expires  # non-empty ISO string

        audits = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "sso.emergency_bypass.activated")
            .all()
        )
        assert len(audits) == 1
        detail = json.loads(audits[0].detail)
        assert detail["duration_hours"] == 4
        assert detail["actor_id"] == admin_user.id

    def test_rejects_above_max_hours(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        seed_default_settings(db_session)
        db_session.commit()

        resp = client.post(
            ENDPOINT, json={"hours": 48}, headers=auth_header(admin_user)
        )
        assert resp.status_code == 400
        assert "24" in resp.json()["detail"]

    def test_editor_forbidden(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        editor = _mk_editor(db_session)
        resp = client.post(
            ENDPOINT, json={"hours": 2}, headers=auth_header(editor)
        )
        assert resp.status_code == 403


class TestDeactivate:
    def test_manual_deactivate_emits_audit(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        seed_default_settings(db_session)
        db_session.commit()

        client.post(
            ENDPOINT, json={"hours": 4}, headers=auth_header(admin_user)
        )
        resp = client.delete(ENDPOINT, headers=auth_header(admin_user))
        assert resp.status_code == 200
        assert resp.json()["active"] is False

        assert get_setting_value(db_session, "sso_emergency_bypass") == "false"

        audits = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "sso.emergency_bypass.deactivated")
            .all()
        )
        assert len(audits) == 1
        assert json.loads(audits[0].detail)["reason"] == "manual"

    def test_deactivate_when_already_inactive_is_idempotent(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        seed_default_settings(db_session)
        db_session.commit()
        # Never activated.

        resp = client.delete(ENDPOINT, headers=auth_header(admin_user))
        assert resp.status_code == 200

        audits = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "sso.emergency_bypass.deactivated")
            .all()
        )
        # No audit row: nothing was active to deactivate.
        assert len(audits) == 0


class TestAutoExpire:
    def test_expire_flips_flag_and_audits(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        """Manually set an already-past expiry and verify the cleanup job
        flips the flag off and emits the deactivated audit with reason=expired."""
        seed_default_settings(db_session)
        db_session.commit()

        client.post(
            ENDPOINT, json={"hours": 1}, headers=auth_header(admin_user)
        )
        # Force an already-past expiry.
        from src.settings.service import get_setting
        exp = get_setting(db_session, "sso_emergency_bypass_expires_at")
        assert exp is not None
        exp.value = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        db_session.commit()

        expired = expire_sso_emergency_bypass(db_session)
        assert expired is True

        assert get_setting_value(db_session, "sso_emergency_bypass") == "false"
        audits = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "sso.emergency_bypass.deactivated")
            .all()
        )
        # Two: the manual activation path + our expire.
        reasons = {json.loads(a.detail)["reason"] for a in audits}
        assert "expired" in reasons

    def test_not_expired_yet_is_noop(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        seed_default_settings(db_session)
        db_session.commit()
        client.post(
            ENDPOINT, json={"hours": 4}, headers=auth_header(admin_user)
        )
        expired = expire_sso_emergency_bypass(db_session)
        assert expired is False
        assert get_setting_value(db_session, "sso_emergency_bypass") == "true"


class TestStatus:
    def test_status_reflects_activation(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        seed_default_settings(db_session)
        db_session.commit()

        pre = client.get(ENDPOINT, headers=auth_header(admin_user))
        assert pre.status_code == 200
        assert pre.json()["active"] is False

        client.post(
            ENDPOINT, json={"hours": 2}, headers=auth_header(admin_user)
        )
        post = client.get(ENDPOINT, headers=auth_header(admin_user))
        assert post.json()["active"] is True
