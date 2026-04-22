"""Story 3-3: IdP group-to-Team mapping endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.audit.models import AuditLog
from src.auth.models import IdentityProvider, User
from src.auth.service import hash_password
from src.encryption import encrypt_value
from src.teams.models import Team
from tests.conftest import auth_header


BASE = "/api/v1/teams"
DEL_BASE = "/api/v1/group-mappings"


@pytest.fixture
def idp(db_session: Session) -> IdentityProvider:
    p = IdentityProvider(
        name="test-idp",
        provider_type="generic",
        issuer_url="https://idp.test/",
        client_id="gm-client",
        client_secret_encrypted=encrypt_value("secret").encode(),
        is_enabled=True,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def team(db_session: Session) -> Team:
    t = Team(name="Mappers")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture
def editor_user(db_session: Session) -> User:
    u = User(
        email="editor-gm@test.com",
        username="editor-gm",
        hashed_password=hash_password("pw"),
        role="editor",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


class TestCreateMapping:
    def test_admin_creates_mapping_with_audit(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        idp: IdentityProvider,
        team: Team,
    ) -> None:
        resp = client.post(
            f"{BASE}/{team.id}/group-mappings",
            json={
                "idp_id": idp.id,
                "group_name": "engineering",
                "role": "editor",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["group_claim_value"] == "engineering"
        assert body["role"] == "editor"

        events = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "group_mapping.created")
            .all()
        )
        assert len(events) == 1

    def test_duplicate_returns_409(
        self,
        client: TestClient,
        admin_user: User,
        idp: IdentityProvider,
        team: Team,
    ) -> None:
        payload = {
            "idp_id": idp.id,
            "group_name": "eng",
            "role": "viewer",
        }
        first = client.post(
            f"{BASE}/{team.id}/group-mappings",
            json=payload,
            headers=auth_header(admin_user),
        )
        assert first.status_code == 201
        second = client.post(
            f"{BASE}/{team.id}/group-mappings",
            json=payload,
            headers=auth_header(admin_user),
        )
        assert second.status_code == 409
        assert second.json()["detail"] == "group_mapping.duplicate"

    def test_unknown_team_returns_404(
        self,
        client: TestClient,
        admin_user: User,
        idp: IdentityProvider,
    ) -> None:
        resp = client.post(
            f"{BASE}/99999/group-mappings",
            json={
                "idp_id": idp.id,
                "group_name": "eng",
                "role": "viewer",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    def test_unknown_idp_returns_404(
        self,
        client: TestClient,
        admin_user: User,
        team: Team,
    ) -> None:
        resp = client.post(
            f"{BASE}/{team.id}/group-mappings",
            json={
                "idp_id": 99999,
                "group_name": "eng",
                "role": "viewer",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "idp.not_found"

    def test_editor_cannot_create(
        self,
        client: TestClient,
        editor_user: User,
        idp: IdentityProvider,
        team: Team,
    ) -> None:
        resp = client.post(
            f"{BASE}/{team.id}/group-mappings",
            json={
                "idp_id": idp.id,
                "group_name": "eng",
                "role": "viewer",
            },
            headers=auth_header(editor_user),
        )
        assert resp.status_code == 403


class TestListMappings:
    def test_list_returns_mappings_sorted(
        self,
        client: TestClient,
        admin_user: User,
        idp: IdentityProvider,
        team: Team,
    ) -> None:
        for name in ["zebra", "alpha", "mango"]:
            client.post(
                f"{BASE}/{team.id}/group-mappings",
                json={"idp_id": idp.id, "group_name": name, "role": "viewer"},
                headers=auth_header(admin_user),
            )
        resp = client.get(
            f"{BASE}/{team.id}/group-mappings",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        names = [m["group_claim_value"] for m in resp.json()]
        assert names == ["alpha", "mango", "zebra"]

    def test_list_empty_for_nonexistent_team_returns_404(
        self, client: TestClient, admin_user: User
    ) -> None:
        resp = client.get(
            f"{BASE}/99999/group-mappings",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404


class TestDeleteMapping:
    def test_delete_emits_audit(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        idp: IdentityProvider,
        team: Team,
    ) -> None:
        create = client.post(
            f"{BASE}/{team.id}/group-mappings",
            json={"idp_id": idp.id, "group_name": "eng", "role": "viewer"},
            headers=auth_header(admin_user),
        )
        mid = create.json()["id"]

        resp = client.delete(
            f"{DEL_BASE}/{mid}", headers=auth_header(admin_user)
        )
        assert resp.status_code == 204

        events = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "group_mapping.deleted")
            .all()
        )
        assert len(events) == 1

    def test_delete_nonexistent_returns_404(
        self, client: TestClient, admin_user: User
    ) -> None:
        resp = client.delete(
            f"{DEL_BASE}/99999", headers=auth_header(admin_user)
        )
        assert resp.status_code == 404

    def test_editor_cannot_delete(
        self,
        client: TestClient,
        editor_user: User,
        admin_user: User,
        idp: IdentityProvider,
        team: Team,
    ) -> None:
        create = client.post(
            f"{BASE}/{team.id}/group-mappings",
            json={"idp_id": idp.id, "group_name": "eng", "role": "viewer"},
            headers=auth_header(admin_user),
        )
        mid = create.json()["id"]
        resp = client.delete(
            f"{DEL_BASE}/{mid}", headers=auth_header(editor_user)
        )
        assert resp.status_code == 403
