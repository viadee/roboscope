"""Integration tests for /api/v1/teams endpoints (Story 3-1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.audit.models import AuditLog
from src.auth.models import User
from src.auth.service import hash_password
from tests.conftest import auth_header


BASE = "/api/v1/teams"


@pytest.fixture
def editor_user(db_session: Session) -> User:
    user = User(
        email="editor@test.com",
        username="editor",
        hashed_password=hash_password("ed1t0r!"),
        role="editor",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def member_user(db_session: Session) -> User:
    user = User(
        email="member@test.com",
        username="member",
        hashed_password=hash_password("memberpw"),
        role="viewer",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestTeamCrudEndpoints:
    def test_create_team_as_admin(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        resp = client.post(
            BASE,
            json={"name": "Alpha", "description": "Team A"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Alpha"
        assert body["external_id"] is None

        audits = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "team.created")
            .all()
        )
        assert len(audits) == 1

    def test_create_team_as_editor_forbidden(
        self, client: TestClient, editor_user: User
    ) -> None:
        resp = client.post(
            BASE,
            json={"name": "Alpha"},
            headers=auth_header(editor_user),
        )
        assert resp.status_code == 403

    def test_list_teams(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        client.post(
            BASE, json={"name": "Alpha"}, headers=auth_header(admin_user)
        )
        client.post(
            BASE, json={"name": "Bravo"}, headers=auth_header(admin_user)
        )
        resp = client.get(BASE, headers=auth_header(admin_user))
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()]
        assert names == ["Alpha", "Bravo"]

    def test_duplicate_name_returns_400(
        self, client: TestClient, admin_user: User
    ) -> None:
        client.post(
            BASE, json={"name": "Dup"}, headers=auth_header(admin_user)
        )
        resp = client.post(
            BASE, json={"name": "Dup"}, headers=auth_header(admin_user)
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "team.name_taken"

    def test_update_team(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        team_resp = client.post(
            BASE, json={"name": "Alpha"}, headers=auth_header(admin_user)
        )
        tid = team_resp.json()["id"]
        resp = client.put(
            f"{BASE}/{tid}",
            json={"description": "new description"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "new description"

    def test_delete_team(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        team_resp = client.post(
            BASE, json={"name": "Alpha"}, headers=auth_header(admin_user)
        )
        tid = team_resp.json()["id"]
        resp = client.delete(
            f"{BASE}/{tid}", headers=auth_header(admin_user)
        )
        assert resp.status_code == 204

        follow = client.get(f"{BASE}/{tid}", headers=auth_header(admin_user))
        assert follow.status_code == 404

    def test_delete_nonexistent_returns_404(
        self, client: TestClient, admin_user: User
    ) -> None:
        resp = client.delete(
            f"{BASE}/99999", headers=auth_header(admin_user)
        )
        assert resp.status_code == 404


class TestMemberCrudEndpoints:
    def test_add_member_and_detail_contains_email(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        member_user: User,
    ) -> None:
        team_resp = client.post(
            BASE, json={"name": "Alpha"}, headers=auth_header(admin_user)
        )
        tid = team_resp.json()["id"]

        add_resp = client.post(
            f"{BASE}/{tid}/members",
            json={"user_id": member_user.id, "role": "editor"},
            headers=auth_header(admin_user),
        )
        assert add_resp.status_code == 201
        assert add_resp.json()["source"] == "manual"

        detail = client.get(
            f"{BASE}/{tid}", headers=auth_header(admin_user)
        )
        assert detail.status_code == 200
        body = detail.json()
        assert len(body["members"]) == 1
        assert body["members"][0]["email"] == member_user.email

    def test_update_member_role(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        member_user: User,
    ) -> None:
        team_resp = client.post(
            BASE, json={"name": "Alpha"}, headers=auth_header(admin_user)
        )
        tid = team_resp.json()["id"]
        add_resp = client.post(
            f"{BASE}/{tid}/members",
            json={"user_id": member_user.id, "role": "viewer"},
            headers=auth_header(admin_user),
        )
        mid = add_resp.json()["id"]

        patch_resp = client.patch(
            f"{BASE}/{tid}/members/{mid}",
            json={"role": "admin"},
            headers=auth_header(admin_user),
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["role"] == "admin"

    def test_remove_member(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        member_user: User,
    ) -> None:
        team_resp = client.post(
            BASE, json={"name": "Alpha"}, headers=auth_header(admin_user)
        )
        tid = team_resp.json()["id"]
        add_resp = client.post(
            f"{BASE}/{tid}/members",
            json={"user_id": member_user.id, "role": "viewer"},
            headers=auth_header(admin_user),
        )
        mid = add_resp.json()["id"]

        resp = client.delete(
            f"{BASE}/{tid}/members/{mid}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 204

    def test_duplicate_member_returns_400(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        member_user: User,
    ) -> None:
        team_resp = client.post(
            BASE, json={"name": "Alpha"}, headers=auth_header(admin_user)
        )
        tid = team_resp.json()["id"]
        client.post(
            f"{BASE}/{tid}/members",
            json={"user_id": member_user.id, "role": "viewer"},
            headers=auth_header(admin_user),
        )
        resp = client.post(
            f"{BASE}/{tid}/members",
            json={"user_id": member_user.id, "role": "editor"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "team.member.already_exists"

    def test_member_audit_events(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        member_user: User,
    ) -> None:
        team_resp = client.post(
            BASE, json={"name": "Alpha"}, headers=auth_header(admin_user)
        )
        tid = team_resp.json()["id"]
        add_resp = client.post(
            f"{BASE}/{tid}/members",
            json={"user_id": member_user.id, "role": "viewer"},
            headers=auth_header(admin_user),
        )
        mid = add_resp.json()["id"]
        client.patch(
            f"{BASE}/{tid}/members/{mid}",
            json={"role": "editor"},
            headers=auth_header(admin_user),
        )
        client.delete(
            f"{BASE}/{tid}/members/{mid}",
            headers=auth_header(admin_user),
        )

        actions = {
            a.action
            for a in db_session.query(AuditLog)
            .filter(AuditLog.action.like("team_member.%"))
            .all()
        }
        assert {
            "team_member.added",
            "team_member.updated",
            "team_member.removed",
        } <= actions

    def test_editor_cannot_add_member(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        editor_user: User,
        member_user: User,
    ) -> None:
        team_resp = client.post(
            BASE, json={"name": "Alpha"}, headers=auth_header(admin_user)
        )
        tid = team_resp.json()["id"]
        resp = client.post(
            f"{BASE}/{tid}/members",
            json={"user_id": member_user.id, "role": "viewer"},
            headers=auth_header(editor_user),
        )
        assert resp.status_code == 403
