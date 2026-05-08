"""Tests for IdP client_secret encryption at rest, response hygiene, and
graceful decrypt (Story 1.5 ACs)."""

from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.idp_service import get_decrypted_client_secret
from src.auth.models import IdentityProvider
from src.auth.service import hash_password
from src.encryption import is_encrypted
from tests.conftest import auth_header

BASE_URL = "/api/v1/auth/idp-providers"

SECRET = "s3cret-v4lu3-plaintext-only-for-tests"

VALID_IDP_DATA = {
    "name": "secret-test-idp",
    "provider_type": "oidc_azure_ad",
    "issuer_url": "https://login.microsoftonline.com/tenant-id/v2.0",
    "client_id": "client-id-123",
    "client_secret": SECRET,
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


def _create_idp(
    client: TestClient, headers: dict, name_suffix: str = ""
) -> int:
    data = {**VALID_IDP_DATA, "name": f"{VALID_IDP_DATA['name']}{name_suffix}"}
    resp = client.post(BASE_URL, json=data, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_client_secret_encrypted_at_rest(
    client: TestClient, db_session: Session
):
    """AC1: ciphertext in DB != plaintext; Fernet-encrypted."""
    admin = _create_user(db_session, Role.ADMIN, "_cs1")
    headers = auth_header(admin)
    idp_id = _create_idp(client, headers, "-1")

    db_session.expire_all()
    idp = db_session.query(IdentityProvider).filter_by(id=idp_id).first()
    assert idp is not None
    assert idp.client_secret_encrypted is not None
    assert SECRET.encode("utf-8") not in idp.client_secret_encrypted
    assert is_encrypted(idp.client_secret_encrypted.decode("utf-8")) is True


def test_client_secret_not_in_response_body(
    client: TestClient, db_session: Session
):
    """AC1 + AC4: plaintext secret never appears in API response bodies."""
    admin = _create_user(db_session, Role.ADMIN, "_cs2")
    headers = auth_header(admin)

    create_resp = client.post(BASE_URL, json=VALID_IDP_DATA, headers=headers)
    assert create_resp.status_code == 201
    assert SECRET not in create_resp.text
    assert "client_secret" not in create_resp.json()
    assert "client_secret_encrypted" not in create_resp.json()

    idp_id = create_resp.json()["id"]
    get_resp = client.get(f"{BASE_URL}/{idp_id}", headers=headers)
    assert get_resp.status_code == 200
    assert SECRET not in get_resp.text
    assert "client_secret" not in get_resp.json()
    assert "client_secret_encrypted" not in get_resp.json()

    list_resp = client.get(BASE_URL, headers=headers)
    assert list_resp.status_code == 200
    assert SECRET not in list_resp.text

    new_secret = "r0tated-secret-value"
    patch_resp = client.patch(
        f"{BASE_URL}/{idp_id}",
        json={"client_secret": new_secret},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert new_secret not in patch_resp.text
    assert SECRET not in patch_resp.text


def test_get_decrypted_client_secret_roundtrip(
    client: TestClient, db_session: Session
):
    """AC2: decrypt helper returns the original plaintext."""
    admin = _create_user(db_session, Role.ADMIN, "_cs3")
    headers = auth_header(admin)
    idp_id = _create_idp(client, headers, "-3")

    db_session.expire_all()
    idp = db_session.query(IdentityProvider).filter_by(id=idp_id).first()
    assert idp is not None
    assert get_decrypted_client_secret(idp) == SECRET


def test_get_decrypted_client_secret_legacy_plaintext_fallback(
    client: TestClient, db_session: Session
):
    """AC3: if stored bytes are not a valid Fernet token, return as plaintext."""
    admin = _create_user(db_session, Role.ADMIN, "_cs4")
    headers = auth_header(admin)
    idp_id = _create_idp(client, headers, "-4")

    legacy = "plain-legacy-secret"
    idp = db_session.query(IdentityProvider).filter_by(id=idp_id).first()
    assert idp is not None
    idp.client_secret_encrypted = legacy.encode("utf-8")
    db_session.commit()

    db_session.expire_all()
    idp = db_session.query(IdentityProvider).filter_by(id=idp_id).first()
    assert idp is not None
    assert get_decrypted_client_secret(idp) == legacy


def test_audit_middleware_does_not_capture_request_body():
    """AC5 regression guard: the audit middleware must not read request body.

    The middleware's background daemon thread uses its own SessionLocal,
    isolated from the test session, so DB-level verification is unreliable.
    Instead, enforce the architectural invariant structurally: the middleware
    source must never invoke any request-body extraction API.
    """
    import inspect

    from src.audit import middleware as audit_mw

    src = inspect.getsource(audit_mw)
    forbidden = [
        "request.body",
        "await request.body",
        "request.json",
        ".body()",
        "request.stream",
        "request.form",
        "request.receive",
        "request._body",
        "request.scope",
    ]
    for pat in forbidden:
        assert pat not in src, (
            f"Audit middleware must stay body-blind; found '{pat}'"
        )
    # Positive assertion: detail payload is limited to method/path/status
    assert '"method": method' in src
    assert '"path": path' in src
    assert '"status": status_code' in src


def test_client_secret_not_in_logs(
    client: TestClient, db_session: Session, caplog
):
    """AC1: plaintext secret must not appear in any captured log record."""
    caplog.set_level(logging.DEBUG)
    admin = _create_user(db_session, Role.ADMIN, "_cs6")
    headers = auth_header(admin)
    idp_id = _create_idp(client, headers, "-6")
    client.get(f"{BASE_URL}/{idp_id}", headers=headers)
    client.patch(
        f"{BASE_URL}/{idp_id}",
        json={"client_secret": "second-rotated-secret"},
        headers=headers,
    )

    serialized = json.dumps([
        {"msg": r.getMessage(), "name": r.name, "level": r.levelname}
        for r in caplog.records
    ])
    assert SECRET not in serialized
    assert "second-rotated-secret" not in serialized


def test_rotated_secret_key_falls_back_with_warning(
    client: TestClient, db_session: Session, caplog
):
    """AC3: a Fernet token encrypted under an OLD SECRET_KEY fails decrypt
    under the current key and is returned as-is with a warning log."""
    from unittest.mock import patch

    from src.config import settings
    from src.encryption import encrypt_value

    admin = _create_user(db_session, Role.ADMIN, "_cs7")
    headers = auth_header(admin)
    idp_id = _create_idp(client, headers, "-7")

    # Produce a Fernet ciphertext under a different SECRET_KEY
    old_key = "rotated-away-key-" + "x" * 32
    with patch.object(settings, "SECRET_KEY", old_key):
        stale_ciphertext = encrypt_value("original-plaintext-secret")

    # Store it on the IdP under the CURRENT SECRET_KEY
    idp = db_session.query(IdentityProvider).filter_by(id=idp_id).first()
    assert idp is not None
    idp.client_secret_encrypted = stale_ciphertext.encode("utf-8")
    db_session.commit()

    caplog.clear()
    caplog.set_level(logging.WARNING)
    db_session.expire_all()
    idp = db_session.query(IdentityProvider).filter_by(id=idp_id).first()
    assert idp is not None
    result = get_decrypted_client_secret(idp)

    # Fallback returns the ciphertext string as-is; a warning is emitted
    assert result == stale_ciphertext
    assert any(
        "legacy-plaintext fallback" in r.getMessage()
        for r in caplog.records
    ), "expected a warning log on fallback"


def test_422_validation_error_does_not_echo_client_secret(
    client: TestClient, db_session: Session
):
    """AC1/AC4: 422 responses from Pydantic validation must not echo
    the submitted `client_secret` value into the error envelope."""
    admin = _create_user(db_session, Role.ADMIN, "_cs8")
    headers = auth_header(admin)

    invalid_payload = {
        **VALID_IDP_DATA,
        "issuer_url": "ftp://not-a-valid-http-url",
        "client_secret": SECRET,
    }
    resp = client.post(BASE_URL, json=invalid_payload, headers=headers)
    assert resp.status_code == 422
    assert SECRET not in resp.text


def test_null_or_empty_client_secret_raises(db_session: Session):
    """Guard against DB drift: None or empty bytes must raise ValueError,
    not silently return an empty string."""
    import pytest

    idp = IdentityProvider(
        name="drift-test-idp",
        provider_type="oidc_azure_ad",
        issuer_url="https://idp.example",
        client_id="c",
        client_secret_encrypted=b"",
        scopes="openid",
        group_claim_name="groups",
    )
    with pytest.raises(ValueError):
        get_decrypted_client_secret(idp)
