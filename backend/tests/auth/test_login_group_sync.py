"""Story 3-5: dedicated tests for inline transactional login-time group sync.

These are separate from the Story 2-2 happy-path callback tests — they
lock in the 3-5 AC contract so regressions to the sync semantics fail
with a clear signal even if the callback-happy-path tests still pass.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import (
    IdentityProvider,
    IdPGroupMapping,
    OidcLoginAttempt,
    User,
)
from src.encryption import encrypt_value
from src.teams.models import Team, TeamMember
from tests.fixtures.mock_oidc import ISSUER, mock_oidc  # noqa: F401
from tests.auth.test_sso_callback import _CLIENT_ID, _make_idp, _make_attempt


BASE_URL = "/api/v1/auth/sso"


def _seed_team_and_mapping(
    db: Session, idp: IdentityProvider, group_name: str, role: str = "editor"
) -> tuple[Team, IdPGroupMapping]:
    team = Team(name=f"Team-{group_name}")
    db.add(team)
    db.commit()
    db.refresh(team)
    mapping = IdPGroupMapping(
        idp_id=idp.id,
        team_id=team.id,
        group_claim_value=group_name,
        role=role,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return team, mapping


def _do_login(
    client: TestClient,
    attempt: OidcLoginAttempt,
    mock_oidc,
    email: str = "alice@example.com",
    groups: list[str] | None = None,
) -> None:
    mock_oidc.with_claims(
        sub="u1",
        email=email,
        nonce=attempt.nonce,
        groups=groups if groups is not None else [],
    )
    resp = client.get(
        f"{BASE_URL}/callback",
        params={"code": "mock-code", "state": attempt.state},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302)


def _user_memberships(db: Session, user_email: str) -> list[TeamMember]:
    user = db.query(User).filter(User.email == user_email).one()
    return (
        db.query(TeamMember)
        .filter(TeamMember.user_id == user.id)
        .all()
    )


class TestLoginGroupSync:
    def test_idempotent_on_repeat_login(
        self, client: TestClient, db_session: Session, mock_oidc
    ) -> None:
        idp = _make_idp(db_session)
        team, _ = _seed_team_and_mapping(db_session, idp, "engineering")

        # First login — creates the membership.
        attempt1 = _make_attempt(db_session, idp, state="state-1", nonce="nonce-1")
        _do_login(client, attempt1, mock_oidc, groups=["engineering"])

        first = _user_memberships(db_session, "alice@example.com")
        assert len(first) == 1
        assert first[0].team_id == team.id
        assert first[0].source == "idp_group_sync"

        # Second login — same claims — must not duplicate.
        attempt2 = _make_attempt(db_session, idp, state="state-2", nonce="nonce-2")
        _do_login(client, attempt2, mock_oidc, groups=["engineering"])

        second = _user_memberships(db_session, "alice@example.com")
        assert len(second) == 1
        assert second[0].id == first[0].id

    def test_manual_grant_survives_sync(
        self, client: TestClient, db_session: Session, mock_oidc
    ) -> None:
        idp = _make_idp(db_session)
        manual_team, _ = _seed_team_and_mapping(
            db_session, idp, "security"  # unused mapping — just to create team
        )
        # Recreate a Team without a matching IdPGroupMapping so it's a pure
        # manual grant that the sync should NEVER see as "expected".
        standalone_team = Team(name="Standalone-Manual")
        db_session.add(standalone_team)
        db_session.commit()
        db_session.refresh(standalone_team)

        # Log in once to create the user.
        attempt1 = _make_attempt(db_session, idp, state="st-m1", nonce="n-m1")
        _do_login(client, attempt1, mock_oidc, groups=[])

        user = db_session.query(User).filter(User.email == "alice@example.com").one()
        manual = TeamMember(
            team_id=standalone_team.id,
            user_id=user.id,
            role="admin",
            source="manual",
        )
        db_session.add(manual)
        db_session.commit()

        # Second login with empty groups — sync must NOT touch the manual row.
        attempt2 = _make_attempt(db_session, idp, state="st-m2", nonce="n-m2")
        _do_login(client, attempt2, mock_oidc, groups=[])

        after = (
            db_session.query(TeamMember)
            .filter(TeamMember.user_id == user.id, TeamMember.source == "manual")
            .all()
        )
        assert len(after) == 1
        assert after[0].team_id == standalone_team.id

    def test_role_drift_updates_existing_row(
        self, client: TestClient, db_session: Session, mock_oidc
    ) -> None:
        idp = _make_idp(db_session)
        team, mapping = _seed_team_and_mapping(
            db_session, idp, "engineering", role="viewer"
        )

        attempt1 = _make_attempt(db_session, idp, state="drift-1", nonce="n-d1")
        _do_login(client, attempt1, mock_oidc, groups=["engineering"])

        first = _user_memberships(db_session, "alice@example.com")
        assert first[0].role == "viewer"
        member_id = first[0].id

        # Admin updates the mapping role.
        mapping.role = "admin"
        db_session.commit()

        attempt2 = _make_attempt(db_session, idp, state="drift-2", nonce="n-d2")
        _do_login(client, attempt2, mock_oidc, groups=["engineering"])

        after = _user_memberships(db_session, "alice@example.com")
        assert len(after) == 1
        assert after[0].id == member_id  # same row, not delete+insert
        assert after[0].role == "admin"

    def test_group_removed_drops_synced_membership(
        self, client: TestClient, db_session: Session, mock_oidc
    ) -> None:
        idp = _make_idp(db_session)
        _team, _ = _seed_team_and_mapping(db_session, idp, "engineering")

        attempt1 = _make_attempt(db_session, idp, state="drop-1", nonce="n-drop-1")
        _do_login(client, attempt1, mock_oidc, groups=["engineering"])
        assert len(_user_memberships(db_session, "alice@example.com")) == 1

        attempt2 = _make_attempt(db_session, idp, state="drop-2", nonce="n-drop-2")
        _do_login(client, attempt2, mock_oidc, groups=[])

        # No membership left — the sync dropped the stale row.
        remaining = _user_memberships(db_session, "alice@example.com")
        assert len(remaining) == 0

    def test_seen_groups_cache_populated_after_login(
        self, client: TestClient, db_session: Session, mock_oidc
    ) -> None:
        from src.auth.seen_groups import list_seen_groups

        idp = _make_idp(db_session)
        attempt = _make_attempt(db_session, idp, state="seen-1", nonce="n-seen-1")
        _do_login(
            client, attempt, mock_oidc, groups=["engineering", "security"]
        )

        cached = list_seen_groups(db_session, idp.id)
        assert sorted(cached) == ["engineering", "security"]
