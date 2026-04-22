"""Story 5-4: ApiToken reassign endpoint."""

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


ENDPOINT = "/api/v1/webhooks/tokens/{tid}/reassign"


def _mk_user(db: Session, *, role: str, email: str, active: bool = True) -> User:
    u = User(
        email=email,
        username=email.split("@")[0],
        hashed_password=hash_password("pw"),
        role=role,
        is_active=active,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


class TestReassign:
    def test_reassigns_owner_and_audits(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        alice = _mk_user(db_session, role="editor", email="alice-tok@test.com", active=False)
        bob = _mk_user(db_session, role="editor", email="bob-tok@test.com")
        token_row, _ = create_api_token(
            db_session, name="shared-ci", role="editor", user_id=alice.id
        )
        db_session.commit()

        resp = client.post(
            ENDPOINT.format(tid=token_row.id),
            json={"user_id": bob.id},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["user_id"] == bob.id

        db_session.expire_all()
        refreshed = db_session.get(ApiToken, token_row.id)
        assert refreshed is not None
        assert refreshed.user_id == bob.id

        audits = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action == "api_token.reassigned",
                AuditLog.resource_id == token_row.id,
            )
            .all()
        )
        assert len(audits) == 1
        detail = json.loads(audits[0].detail)
        assert detail["old_user_id"] == alice.id
        assert detail["new_user_id"] == bob.id

    def test_role_recap_never_elevates(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        """Token role=editor, new owner is VIEWER → token role drops to VIEWER."""
        alice = _mk_user(db_session, role="editor", email="alice-recap@test.com")
        charlie = _mk_user(db_session, role="viewer", email="charlie@test.com")
        token_row, _ = create_api_token(
            db_session, name="recap-test", role="editor", user_id=alice.id
        )
        db_session.commit()

        resp = client.post(
            ENDPOINT.format(tid=token_row.id),
            json={"user_id": charlie.id},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    def test_role_recap_does_not_elevate_upward(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        """Token role=viewer, new owner is ADMIN → token role stays viewer
        (the cap is tightening-only; the token's own scoped role is the floor)."""
        alice = _mk_user(db_session, role="viewer", email="alice-noelevate@test.com")
        delta = _mk_user(db_session, role="admin", email="delta@test.com")
        token_row, _ = create_api_token(
            db_session, name="low-token", role="viewer", user_id=alice.id
        )
        db_session.commit()

        resp = client.post(
            ENDPOINT.format(tid=token_row.id),
            json={"user_id": delta.id},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    def test_rejects_inactive_new_owner(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        alice = _mk_user(db_session, role="editor", email="alice-inactdest@test.com")
        echo = _mk_user(db_session, role="editor", email="echo@test.com", active=False)
        token_row, _ = create_api_token(
            db_session, name="reassign-fail", role="editor", user_id=alice.id
        )
        db_session.commit()

        resp = client.post(
            ENDPOINT.format(tid=token_row.id),
            json={"user_id": echo.id},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    def test_404_on_unknown_token(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        bob = _mk_user(db_session, role="editor", email="bob-404@test.com")
        resp = client.post(
            ENDPOINT.format(tid=99999),
            json={"user_id": bob.id},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    def test_404_on_unknown_new_owner(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        alice = _mk_user(db_session, role="editor", email="alice-owner404@test.com")
        token_row, _ = create_api_token(
            db_session, name="owner-404", role="editor", user_id=alice.id
        )
        db_session.commit()

        resp = client.post(
            ENDPOINT.format(tid=token_row.id),
            json={"user_id": 99999},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404
