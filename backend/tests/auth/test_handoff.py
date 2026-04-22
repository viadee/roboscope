"""Tests for the IdP handoff artifact endpoint and generator."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.service import hash_password
from tests.conftest import auth_header

BASE_URL = "/api/v1/auth/idp-providers"

_IDP_DATA = {
    "name": "handoff-test-idp",
    "provider_type": "oidc_azure_ad",
    "issuer_url": "https://login.microsoftonline.com/tenant/v2.0",
    "client_id": "client-xyz",
    "client_secret": "secret-xyz",
    "scopes": "openid profile email groups",
    "group_claim_name": "groups",
}


def _make_admin(db: Session, suffix: str = ""):
    from src.auth.models import User

    user = User(
        email=f"admin-handoff{suffix}@test.com",
        username=f"admin-handoff{suffix}",
        hashed_password=hash_password("password"),
        role="admin",
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


def _seed_idp(client: TestClient, headers: dict) -> int:
    res = client.post(BASE_URL, json=_IDP_DATA, headers=headers)
    assert res.status_code == 201
    return res.json()["id"]


# ---------------------------------------------------------------------------
# PDF endpoint tests
# ---------------------------------------------------------------------------


def test_handoff_pdf_returns_bytes(client: TestClient, db_session: Session):
    admin = _make_admin(db_session, "-pdf")
    headers = auth_header(admin)
    idp_id = _seed_idp(client, headers)

    res = client.get(f"{BASE_URL}/{idp_id}/handoff?format=pdf&lang=en", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment" in res.headers["content-disposition"]
    assert ".pdf" in res.headers["content-disposition"]
    assert len(res.content) > 1000
    assert res.content[:4] == b"%PDF"


def test_handoff_markdown_contains_mermaid(client: TestClient, db_session: Session):
    admin = _make_admin(db_session, "-md")
    headers = auth_header(admin)
    idp_id = _seed_idp(client, headers)

    res = client.get(f"{BASE_URL}/{idp_id}/handoff?format=md&lang=en", headers=headers)
    assert res.status_code == 200
    assert "markdown" in res.headers["content-type"]
    text = res.content.decode("utf-8")
    assert "```mermaid" in text
    assert "sequenceDiagram" in text
    assert "auth/sso/callback" in text


def test_handoff_404_on_missing_idp(client: TestClient, db_session: Session):
    admin = _make_admin(db_session, "-404")
    headers = auth_header(admin)

    res = client.get(f"{BASE_URL}/99999/handoff?format=pdf&lang=en", headers=headers)
    assert res.status_code == 404


def test_handoff_locale_changes_heading(client: TestClient, db_session: Session):
    admin = _make_admin(db_session, "-locale")
    headers = auth_header(admin)
    idp_id = _seed_idp(client, headers)

    res_en = client.get(f"{BASE_URL}/{idp_id}/handoff?format=md&lang=en", headers=headers)
    res_de = client.get(f"{BASE_URL}/{idp_id}/handoff?format=md&lang=de", headers=headers)

    text_en = res_en.content.decode("utf-8")
    text_de = res_de.content.decode("utf-8")

    assert "Callback URL" in text_en
    assert "Callback-URL" in text_de
    assert "Test-Login" in text_de


def test_handoff_filename_uses_idp_name(client: TestClient, db_session: Session):
    admin = _make_admin(db_session, "-fn")
    headers = auth_header(admin)
    idp_id = _seed_idp(client, headers)

    res = client.get(f"{BASE_URL}/{idp_id}/handoff?format=pdf&lang=fr", headers=headers)
    assert res.status_code == 200
    assert "handoff-test-idp" in res.headers["content-disposition"]
    assert "fr" in res.headers["content-disposition"]


# ---------------------------------------------------------------------------
# Unit tests for generator module
# ---------------------------------------------------------------------------


def test_generate_markdown_all_locales():
    from src.auth.handoff_generator import generate_markdown

    class MockIdp:
        provider_type = "oidc_generic"
        scopes = "openid profile email"
        group_claim_name = "groups"
        name = "Test"

    idp = MockIdp()
    for lang in ("en", "de", "fr", "es"):
        md = generate_markdown(idp, "http://localhost:8000/", lang)
        assert "auth/sso/callback" in md
        assert "openid profile email" in md
        assert "groups" in md


def test_generate_pdf_valid_bytes_all_locales():
    from src.auth.handoff_generator import generate_pdf

    class MockIdp:
        provider_type = "oidc_google"
        scopes = "openid profile email"
        group_claim_name = "groups"
        name = "Test"

    idp = MockIdp()
    for lang in ("en", "de", "fr", "es"):
        pdf_bytes = generate_pdf(idp, "https://roboscope.example.com/", lang)
        assert pdf_bytes[:4] == b"%PDF"
        assert len(pdf_bytes) > 500
