"""Tests for Identity Provider CRUD API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.models import IdentityProvider
from src.auth.service import hash_password
from src.encryption import decrypt_value, is_encrypted
from tests.conftest import auth_header

BASE_URL = "/api/v1/auth/idp-providers"

VALID_IDP_DATA = {
    "name": "azure-prod",
    "provider_type": "oidc_azure_ad",
    "issuer_url": "https://login.microsoftonline.com/tenant-id/v2.0",
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


@pytest.fixture
def admin(db_session: Session):
    return _create_user(db_session, Role.ADMIN, "_idp")


@pytest.fixture
def admin_headers(admin):
    return auth_header(admin)


def test_create_idp_success(client: TestClient, admin_headers: dict):
    resp = client.post(BASE_URL, json=VALID_IDP_DATA, headers=admin_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] is not None
    assert body["name"] == "azure-prod"
    assert body["provider_type"] == "oidc_azure_ad"
    assert body["is_enabled"] is False
    assert "client_secret" not in body
    assert "client_secret_encrypted" not in body


def test_create_idp_secret_encrypted(
    client: TestClient, admin_headers: dict, db_session: Session
):
    client.post(BASE_URL, json=VALID_IDP_DATA, headers=admin_headers)
    idp = db_session.query(IdentityProvider).filter_by(name="azure-prod").first()
    assert idp is not None
    encrypted_str = idp.client_secret_encrypted.decode()
    assert encrypted_str != "super-secret-value"
    assert is_encrypted(encrypted_str)
    assert decrypt_value(encrypted_str) == "super-secret-value"


def test_create_idp_duplicate_name(client: TestClient, admin_headers: dict):
    client.post(BASE_URL, json=VALID_IDP_DATA, headers=admin_headers)
    resp = client.post(BASE_URL, json=VALID_IDP_DATA, headers=admin_headers)
    assert resp.status_code == 409


def test_create_idp_invalid_provider_type(client: TestClient, admin_headers: dict):
    data = {**VALID_IDP_DATA, "provider_type": "invalid"}
    resp = client.post(BASE_URL, json=data, headers=admin_headers)
    assert resp.status_code == 422


def test_create_idp_invalid_issuer_url(client: TestClient, admin_headers: dict):
    data = {**VALID_IDP_DATA, "name": "bad-url", "issuer_url": "file:///etc/passwd"}
    resp = client.post(BASE_URL, json=data, headers=admin_headers)
    assert resp.status_code == 422


def test_update_idp_null_secret_rejected(client: TestClient, admin_headers: dict):
    create_resp = client.post(BASE_URL, json=VALID_IDP_DATA, headers=admin_headers)
    idp_id = create_resp.json()["id"]
    resp = client.patch(
        f"{BASE_URL}/{idp_id}",
        json={"client_secret": None},
        headers=admin_headers,
    )
    assert resp.status_code == 422


def test_list_idps(client: TestClient, admin_headers: dict):
    data1 = {**VALID_IDP_DATA, "name": "idp-one"}
    data2 = {**VALID_IDP_DATA, "name": "idp-two"}
    client.post(BASE_URL, json=data1, headers=admin_headers)
    client.post(BASE_URL, json=data2, headers=admin_headers)
    resp = client.get(BASE_URL, headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    for item in body:
        assert "client_secret" not in item
        assert "client_secret_encrypted" not in item


def test_get_idp_by_id(client: TestClient, admin_headers: dict):
    create_resp = client.post(BASE_URL, json=VALID_IDP_DATA, headers=admin_headers)
    idp_id = create_resp.json()["id"]
    resp = client.get(f"{BASE_URL}/{idp_id}", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "azure-prod"
    assert "client_secret" not in body
    assert "client_secret_encrypted" not in body


def test_get_idp_not_found(client: TestClient, admin_headers: dict):
    resp = client.get(f"{BASE_URL}/99999", headers=admin_headers)
    assert resp.status_code == 404


def test_update_idp(client: TestClient, admin_headers: dict):
    create_resp = client.post(BASE_URL, json=VALID_IDP_DATA, headers=admin_headers)
    idp_id = create_resp.json()["id"]
    resp = client.patch(
        f"{BASE_URL}/{idp_id}",
        json={"scopes": "openid email"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["scopes"] == "openid email"


def test_update_idp_secret(
    client: TestClient, admin_headers: dict, db_session: Session
):
    create_resp = client.post(BASE_URL, json=VALID_IDP_DATA, headers=admin_headers)
    idp_id = create_resp.json()["id"]
    client.patch(
        f"{BASE_URL}/{idp_id}",
        json={"client_secret": "new-secret"},
        headers=admin_headers,
    )
    idp = db_session.query(IdentityProvider).filter_by(id=idp_id).first()
    assert idp is not None
    decrypted = decrypt_value(idp.client_secret_encrypted.decode())
    assert decrypted == "new-secret"


def test_delete_idp(client: TestClient, admin_headers: dict):
    create_resp = client.post(BASE_URL, json=VALID_IDP_DATA, headers=admin_headers)
    idp_id = create_resp.json()["id"]
    resp = client.delete(f"{BASE_URL}/{idp_id}", headers=admin_headers)
    assert resp.status_code == 204
    resp = client.get(f"{BASE_URL}/{idp_id}", headers=admin_headers)
    assert resp.status_code == 404


def test_rbac_viewer_forbidden(client: TestClient, db_session: Session):
    user = _create_user(db_session, Role.VIEWER, "_idp")
    headers = auth_header(user)
    assert client.get(BASE_URL, headers=headers).status_code == 403
    assert client.post(BASE_URL, json=VALID_IDP_DATA, headers=headers).status_code == 403
    assert client.get(f"{BASE_URL}/1", headers=headers).status_code == 403
    assert client.patch(f"{BASE_URL}/1", json={}, headers=headers).status_code == 403
    assert client.delete(f"{BASE_URL}/1", headers=headers).status_code == 403


def test_rbac_runner_forbidden(client: TestClient, db_session: Session):
    user = _create_user(db_session, Role.RUNNER, "_idp")
    headers = auth_header(user)
    assert client.get(BASE_URL, headers=headers).status_code == 403
    assert client.post(BASE_URL, json=VALID_IDP_DATA, headers=headers).status_code == 403


def test_rbac_editor_forbidden(client: TestClient, db_session: Session):
    user = _create_user(db_session, Role.EDITOR, "_idp")
    headers = auth_header(user)
    assert client.get(BASE_URL, headers=headers).status_code == 403
    assert client.post(BASE_URL, json=VALID_IDP_DATA, headers=headers).status_code == 403
