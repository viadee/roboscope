"""Story 3-14: PATCH /group-mappings/{id} endpoint."""

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
        name="update-idp",
        provider_type="generic",
        issuer_url="https://idp.test/",
        client_id="upd-client",
        client_secret_encrypted=encrypt_value("secret").encode(),
        is_enabled=True,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def team(db_session: Session) -> Team:
    t = Team(name="UpdateMappers")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture
def editor_user(db_session: Session) -> User:
    u = User(
        email="edit-gm-update@t.com",
        username="edit-gm-update",
        hashed_password=hash_password("pw"),
        role="editor",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _make_mapping(
    client: TestClient, admin: User, team: Team, idp: IdentityProvider
) -> int:
    resp = client.post(
        f"{BASE}/{team.id}/group-mappings",
        json={"idp_id": idp.id, "group_name": "eng", "role": "viewer"},
        headers=auth_header(admin),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


class TestUpdateGroupMapping:
    def test_admin_updates_role_with_audit(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        idp: IdentityProvider,
        team: Team,
    ) -> None:
        mid = _make_mapping(client, admin_user, team, idp)

        resp = client.patch(
            f"{DEL_BASE}/{mid}",
            json={"role": "editor"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "editor"

        events = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "group_mapping.updated")
            .all()
        )
        assert len(events) == 1

    def test_nonexistent_returns_404(
        self, client: TestClient, admin_user: User
    ) -> None:
        resp = client.patch(
            f"{DEL_BASE}/99999",
            json={"role": "editor"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    def test_editor_forbidden(
        self,
        client: TestClient,
        admin_user: User,
        editor_user: User,
        idp: IdentityProvider,
        team: Team,
    ) -> None:
        mid = _make_mapping(client, admin_user, team, idp)
        resp = client.patch(
            f"{DEL_BASE}/{mid}",
            json={"role": "editor"},
            headers=auth_header(editor_user),
        )
        assert resp.status_code == 403
