"""Story 3-5: seen-groups cache (AppSetting-backed)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import IdentityProvider, User
from src.auth.seen_groups import list_seen_groups, record_seen_groups
from src.encryption import encrypt_value
from src.teams.service import list_available_groups_for_idp
from tests.conftest import auth_header


@pytest.fixture
def idp(db_session: Session) -> IdentityProvider:
    p = IdentityProvider(
        name="seen-groups-idp",
        provider_type="generic",
        issuer_url="https://idp.test/",
        client_id="sg-client",
        client_secret_encrypted=encrypt_value("secret").encode(),
        is_enabled=True,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


class TestSeenGroupsCache:
    def test_record_persists_distinct_values(
        self, db_session: Session, idp: IdentityProvider
    ) -> None:
        record_seen_groups(db_session, idp.id, ["alpha", "beta"])
        assert sorted(list_seen_groups(db_session, idp.id)) == ["alpha", "beta"]

    def test_record_merges_without_duplicates(
        self, db_session: Session, idp: IdentityProvider
    ) -> None:
        record_seen_groups(db_session, idp.id, ["alpha", "beta"])
        record_seen_groups(db_session, idp.id, ["beta", "gamma"])
        assert sorted(list_seen_groups(db_session, idp.id)) == [
            "alpha",
            "beta",
            "gamma",
        ]

    def test_empty_groups_is_noop(
        self, db_session: Session, idp: IdentityProvider
    ) -> None:
        record_seen_groups(db_session, idp.id, [])
        assert list_seen_groups(db_session, idp.id) == []

    def test_ignores_non_string_entries(
        self, db_session: Session, idp: IdentityProvider
    ) -> None:
        # The id_token claim is supposed to be a list of strings; defend
        # against the defensive-programming case of unexpected types.
        record_seen_groups(db_session, idp.id, ["alpha", 42, None, "beta"])  # type: ignore[list-item]
        assert sorted(list_seen_groups(db_session, idp.id)) == ["alpha", "beta"]

    def test_distinct_idps_have_separate_caches(
        self, db_session: Session, idp: IdentityProvider
    ) -> None:
        other = IdentityProvider(
            name="other-idp",
            provider_type="generic",
            issuer_url="https://other.test/",
            client_id="other-client",
            client_secret_encrypted=encrypt_value("x").encode(),
            is_enabled=True,
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        record_seen_groups(db_session, idp.id, ["alpha"])
        record_seen_groups(db_session, other.id, ["zulu"])
        assert list_seen_groups(db_session, idp.id) == ["alpha"]
        assert list_seen_groups(db_session, other.id) == ["zulu"]


class TestAvailableGroupsUnion:
    def test_endpoint_includes_seen_groups_even_without_mappings(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        idp: IdentityProvider,
    ) -> None:
        record_seen_groups(db_session, idp.id, ["engineering", "security"])
        db_session.commit()

        resp = client.get(
            f"/api/v1/auth/idp-providers/{idp.id}/available-groups",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json() == ["engineering", "security"]

    def test_mapped_and_seen_are_unioned_and_sorted(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        idp: IdentityProvider,
    ) -> None:
        # Map one group.
        team_resp = client.post(
            "/api/v1/teams",
            json={"name": "T"},
            headers=auth_header(admin_user),
        )
        tid = team_resp.json()["id"]
        client.post(
            f"/api/v1/teams/{tid}/group-mappings",
            json={"idp_id": idp.id, "group_name": "mapped-only", "role": "viewer"},
            headers=auth_header(admin_user),
        )
        # Record a separate seen group.
        record_seen_groups(db_session, idp.id, ["seen-only"])
        # And one that's both.
        record_seen_groups(db_session, idp.id, ["mapped-only"])
        db_session.commit()

        resp = client.get(
            f"/api/v1/auth/idp-providers/{idp.id}/available-groups",
            headers=auth_header(admin_user),
        )
        assert resp.json() == ["mapped-only", "seen-only"]

    def test_available_groups_deduplicates(
        self, db_session: Session, idp: IdentityProvider
    ) -> None:
        record_seen_groups(db_session, idp.id, ["dup", "dup", "other"])
        assert sorted(list_seen_groups(db_session, idp.id)) == ["dup", "other"]
