"""Story 3-4: bulk-create teams via import-from-IdP-groups."""

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


AVAILABLE = "/api/v1/auth/idp-providers"
IMPORT_URL = "/api/v1/teams/import-from-idp-groups"


@pytest.fixture
def idp(db_session: Session) -> IdentityProvider:
    p = IdentityProvider(
        name="bulk-idp",
        provider_type="generic",
        issuer_url="https://idp.test/",
        client_id="bulk-client",
        client_secret_encrypted=encrypt_value("secret").encode(),
        is_enabled=True,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def editor_user(db_session: Session) -> User:
    u = User(
        email="editor-bulk@test.com",
        username="editor-bulk",
        hashed_password=hash_password("pw"),
        role="editor",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


class TestAvailableGroups:
    def test_returns_empty_for_new_idp(
        self, client: TestClient, admin_user: User, idp: IdentityProvider
    ) -> None:
        resp = client.get(
            f"{AVAILABLE}/{idp.id}/available-groups",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_distinct_sorted_groups_after_mapping(
        self,
        client: TestClient,
        admin_user: User,
        idp: IdentityProvider,
        db_session: Session,
    ) -> None:
        # Seed mappings via the CRUD endpoint.
        team_resp = client.post(
            "/api/v1/teams",
            json={"name": "T"},
            headers=auth_header(admin_user),
        )
        tid = team_resp.json()["id"]
        for g in ["zebra", "alpha", "mango"]:
            client.post(
                f"/api/v1/teams/{tid}/group-mappings",
                json={"idp_id": idp.id, "group_name": g, "role": "viewer"},
                headers=auth_header(admin_user),
            )

        resp = client.get(
            f"{AVAILABLE}/{idp.id}/available-groups",
            headers=auth_header(admin_user),
        )
        assert resp.json() == ["alpha", "mango", "zebra"]

    def test_nonexistent_idp_returns_404(
        self, client: TestClient, admin_user: User
    ) -> None:
        resp = client.get(
            f"{AVAILABLE}/99999/available-groups",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    def test_editor_forbidden(
        self, client: TestClient, editor_user: User, idp: IdentityProvider
    ) -> None:
        resp = client.get(
            f"{AVAILABLE}/{idp.id}/available-groups",
            headers=auth_header(editor_user),
        )
        assert resp.status_code == 403


class TestBulkImport:
    def test_import_creates_teams_and_mappings(
        self,
        client: TestClient,
        admin_user: User,
        idp: IdentityProvider,
        db_session: Session,
    ) -> None:
        resp = client.post(
            IMPORT_URL,
            json={
                "idp_id": idp.id,
                "groups": [
                    {"group_name": "eng", "team_name": "Engineering", "role": "editor"},
                    {"group_name": "qa", "team_name": "Quality Assurance", "role": "viewer"},
                ],
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 2
        assert body["skipped"] == 0
        assert body["failed"] == 0
        assert len(body["team_ids"]) == 2

        teams = db_session.query(Team).filter(
            Team.name.in_(["Engineering", "Quality Assurance"])
        ).all()
        assert len(teams) == 2

    def test_import_skips_taken_team_names(
        self,
        client: TestClient,
        admin_user: User,
        idp: IdentityProvider,
        db_session: Session,
    ) -> None:
        # Pre-create a team with the target name.
        client.post(
            "/api/v1/teams",
            json={"name": "Engineering"},
            headers=auth_header(admin_user),
        )

        resp = client.post(
            IMPORT_URL,
            json={
                "idp_id": idp.id,
                "groups": [
                    {"group_name": "eng", "team_name": "Engineering", "role": "editor"},
                ],
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        # Team was reused (not duplicated), mapping was created.
        assert body["created"] == 1
        assert len(body["team_ids"]) == 1

    def test_import_skips_duplicate_mapping(
        self,
        client: TestClient,
        admin_user: User,
        idp: IdentityProvider,
    ) -> None:
        # First pass.
        first = client.post(
            IMPORT_URL,
            json={
                "idp_id": idp.id,
                "groups": [
                    {"group_name": "eng", "team_name": "Eng", "role": "editor"},
                ],
            },
            headers=auth_header(admin_user),
        )
        assert first.json()["created"] == 1

        # Second pass: same pair — should skip.
        second = client.post(
            IMPORT_URL,
            json={
                "idp_id": idp.id,
                "groups": [
                    {"group_name": "eng", "team_name": "Eng", "role": "viewer"},
                ],
            },
            headers=auth_header(admin_user),
        )
        body = second.json()
        assert body["created"] == 0
        assert body["skipped"] == 1

    def test_import_unknown_idp_returns_404(
        self, client: TestClient, admin_user: User
    ) -> None:
        resp = client.post(
            IMPORT_URL,
            json={
                "idp_id": 99999,
                "groups": [
                    {"group_name": "g", "team_name": "T", "role": "viewer"},
                ],
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    def test_import_emits_audit_per_new_row(
        self,
        client: TestClient,
        admin_user: User,
        idp: IdentityProvider,
        db_session: Session,
    ) -> None:
        client.post(
            IMPORT_URL,
            json={
                "idp_id": idp.id,
                "groups": [
                    {"group_name": "g1", "team_name": "T1", "role": "viewer"},
                    {"group_name": "g2", "team_name": "T2", "role": "viewer"},
                ],
            },
            headers=auth_header(admin_user),
        )
        created_events = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "team.created")
            .all()
        )
        mapping_events = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "group_mapping.created")
            .all()
        )
        # Two teams created, two mappings created.
        assert len(created_events) == 2
        assert len(mapping_events) == 2

    def test_editor_forbidden(
        self, client: TestClient, editor_user: User, idp: IdentityProvider
    ) -> None:
        resp = client.post(
            IMPORT_URL,
            json={
                "idp_id": idp.id,
                "groups": [
                    {"group_name": "g", "team_name": "T", "role": "viewer"},
                ],
            },
            headers=auth_header(editor_user),
        )
        assert resp.status_code == 403
