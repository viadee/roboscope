"""Tests for Identity Provider dry-run probe endpoint."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.models import IdentityProvider
from src.auth.service import hash_password
from tests.conftest import auth_header
from tests.fixtures.mock_oidc import ISSUER, mock_oidc  # noqa: F401

BASE_URL = "/api/v1/auth/idp-providers"

VALID_IDP_DATA = {
    "name": "dry-run-test",
    "provider_type": "oidc_azure_ad",
    "issuer_url": ISSUER,
    "client_id": "client-id-123",
    "client_secret": "super-secret-value",
    "scopes": "openid profile email",
    "group_claim_name": "groups",
}


def _create_user(db: Session, role: str, suffix: str = ""):
    from src.auth.models import User

    user = User(
        email=f"{role}{suffix}@test.com",
        username=f"{role}{suffix}",
        hashed_password=hash_password("password123"),
        role=role,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


def _create_idp(client: TestClient, headers: dict, **overrides):
    data = {**VALID_IDP_DATA, **overrides}
    resp = client.post(BASE_URL, json=data, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_dry_run_success(
    client: TestClient, db_session: Session, mock_oidc
):
    admin = _create_user(db_session, Role.ADMIN, "_dr1")
    headers = auth_header(admin)
    idp_id = _create_idp(client, headers)

    resp = client.post(
        f"{BASE_URL}/{idp_id}/dry-run", headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_status"] == "passed"
    assert len(body["checks"]) == 3
    assert body["elapsed_ms"] > 0
    for check in body["checks"]:
        assert check["status"] == "passed"


def test_dry_run_updates_db_fields(
    client: TestClient, db_session: Session, mock_oidc
):
    admin = _create_user(db_session, Role.ADMIN, "_dr2")
    headers = auth_header(admin)
    idp_id = _create_idp(client, headers)

    client.post(f"{BASE_URL}/{idp_id}/dry-run", headers=headers)

    idp = db_session.query(IdentityProvider).filter_by(id=idp_id).first()
    assert idp is not None
    assert idp.last_dry_run_at is not None
    assert idp.last_dry_run_status == "passed"
    assert idp.discovery_cache_json is not None
    assert idp.discovery_cached_at is not None


def test_dry_run_unreachable_issuer(
    client: TestClient, db_session: Session
):
    admin = _create_user(db_session, Role.ADMIN, "_dr3")
    headers = auth_header(admin)
    idp_id = _create_idp(
        client, headers,
        name="unreachable-idp",
        issuer_url="https://unreachable.invalid",
    )

    with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
        router.get(
            "https://unreachable.invalid"
            "/.well-known/openid-configuration"
        ).mock(side_effect=httpx.ConnectError("unreachable"))

        resp = client.post(
            f"{BASE_URL}/{idp_id}/dry-run", headers=headers
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_status"] == "failed"
    checks = {c["check_name"]: c for c in body["checks"]}
    assert checks["issuer_reachable"]["status"] == "failed"


def test_dry_run_discovery_missing_keys(
    client: TestClient, db_session: Session
):
    admin = _create_user(db_session, Role.ADMIN, "_dr4")
    headers = auth_header(admin)
    idp_id = _create_idp(
        client, headers,
        name="bad-discovery-idp",
        issuer_url="https://bad-discovery.local",
    )

    with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
        router.get(
            "https://bad-discovery.local"
            "/.well-known/openid-configuration"
        ).mock(return_value=httpx.Response(200, json={
            "issuer": "https://bad-discovery.local",
            "authorization_endpoint": "https://bad-discovery.local/auth",
        }))

        resp = client.post(
            f"{BASE_URL}/{idp_id}/dry-run", headers=headers
        )

    body = resp.json()
    assert body["overall_status"] == "failed"
    checks = {c["check_name"]: c for c in body["checks"]}
    assert checks["issuer_reachable"]["status"] == "passed"
    assert checks["discovery_valid"]["status"] == "failed"
    assert "jwks_uri" in checks["discovery_valid"]["detail"]


def test_dry_run_jwks_fetch_fails(
    client: TestClient, db_session: Session
):
    admin = _create_user(db_session, Role.ADMIN, "_dr5")
    headers = auth_header(admin)
    idp_id = _create_idp(
        client, headers,
        name="bad-jwks-idp",
        issuer_url="https://bad-jwks.local",
    )

    with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
        router.get(
            "https://bad-jwks.local"
            "/.well-known/openid-configuration"
        ).mock(return_value=httpx.Response(200, json={
            "issuer": "https://bad-jwks.local",
            "authorization_endpoint": "https://bad-jwks.local/auth",
            "token_endpoint": "https://bad-jwks.local/token",
            "jwks_uri": "https://bad-jwks.local/jwks",
        }))
        router.get("https://bad-jwks.local/jwks").mock(
            return_value=httpx.Response(500)
        )

        resp = client.post(
            f"{BASE_URL}/{idp_id}/dry-run", headers=headers
        )

    body = resp.json()
    assert body["overall_status"] == "failed"
    checks = {c["check_name"]: c for c in body["checks"]}
    assert checks["issuer_reachable"]["status"] == "passed"
    assert checks["discovery_valid"]["status"] == "passed"
    assert checks["jwks_fetched"]["status"] == "failed"


def test_dry_run_idp_not_found(
    client: TestClient, db_session: Session
):
    admin = _create_user(db_session, Role.ADMIN, "_dr6")
    headers = auth_header(admin)
    resp = client.post(
        f"{BASE_URL}/99999/dry-run", headers=headers
    )
    assert resp.status_code == 404


def test_dry_run_rbac_forbidden(
    client: TestClient, db_session: Session
):
    viewer = _create_user(db_session, Role.VIEWER, "_dr7")
    headers = auth_header(viewer)
    resp = client.post(
        f"{BASE_URL}/1/dry-run", headers=headers
    )
    assert resp.status_code == 403


def test_dry_run_failed_preserves_existing_cache(
    client: TestClient, db_session: Session
):
    """AC4: a failing probe must NOT overwrite a previously-cached discovery."""
    admin = _create_user(db_session, Role.ADMIN, "_dr8")
    headers = auth_header(admin)
    idp_id = _create_idp(
        client, headers,
        name="no-cache-idp",
        issuer_url="https://no-cache.invalid",
    )

    # Seed a prior successful cache
    prior_cache = (
        '{"issuer":"https://no-cache.invalid",'
        '"jwks_uri":"https://no-cache.invalid/jwks"}'
    )
    prior_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    seeded = db_session.query(IdentityProvider).filter_by(id=idp_id).first()
    assert seeded is not None
    seeded.discovery_cache_json = prior_cache
    seeded.discovery_cached_at = prior_at
    db_session.commit()

    with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
        router.get(
            "https://no-cache.invalid"
            "/.well-known/openid-configuration"
        ).mock(side_effect=httpx.ConnectError("unreachable"))

        client.post(
            f"{BASE_URL}/{idp_id}/dry-run", headers=headers
        )

    db_session.expire_all()
    idp = db_session.query(IdentityProvider).filter_by(id=idp_id).first()
    assert idp is not None
    assert idp.last_dry_run_at is not None
    assert idp.last_dry_run_status == "failed"
    # Prior cache preserved, not cleared
    assert idp.discovery_cache_json == prior_cache
    assert idp.discovery_cached_at is not None
