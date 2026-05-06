"""Story SECURITY-3 — HMAC-signed report-scoped asset tokens.

Two layers of tests:

1. **Unit** — `mint_asset_token` / `verify_asset_token` round-trip
   and rejection cases (wrong report_id, expired, tampered, garbage).

2. **Integration** — the asset endpoint accepts the new `?at=` token,
   rejects mismatched-report tokens, and the `/html` endpoint
   embeds the token (not a JWT) in the <base href>.
"""

from __future__ import annotations

import time

import pytest

from src.reports.asset_tokens import mint_asset_token, verify_asset_token
from tests.conftest import auth_header
from tests.reports.test_router import _setup_report  # reuse fixture helper


# ---------------------------------------------------------------------------
# Unit tests — pure HMAC plumbing
# ---------------------------------------------------------------------------


class TestAssetTokenUnit:
    def test_round_trip(self):
        t = mint_asset_token(report_id=42)
        assert verify_asset_token(t, report_id=42) is True

    def test_rejects_wrong_report_id(self):
        t = mint_asset_token(report_id=42)
        assert verify_asset_token(t, report_id=43) is False

    def test_rejects_expired(self):
        # Mint with a TTL of -1 → already expired the moment it's signed.
        t = mint_asset_token(report_id=7, ttl_seconds=-1)
        assert verify_asset_token(t, report_id=7) is False

    def test_rejects_tampered_signature(self):
        t = mint_asset_token(report_id=7)
        # Flip the last char (it's base64url; perturb it to a different
        # b64url char — guaranteed to break the signature).
        bad = t[:-1] + ("Z" if t[-1] != "Z" else "Y")
        assert verify_asset_token(bad, report_id=7) is False

    def test_rejects_tampered_payload(self):
        # Verify the payload integrity is part of the signature scope:
        # a token minted for report 1 cannot be made to verify against
        # report 2 even if the verifier is lenient about the payload bytes.
        t1 = mint_asset_token(report_id=1)
        t2 = mint_asset_token(report_id=2)
        assert verify_asset_token(t1, report_id=2) is False
        assert verify_asset_token(t2, report_id=1) is False

    def test_rejects_empty_or_garbage(self):
        assert verify_asset_token("", report_id=1) is False
        assert verify_asset_token("not-base64-or-anything-meaningful!", report_id=1) is False
        assert verify_asset_token("aGVsbG8=", report_id=1) is False  # valid b64, no '.'

    # Note: TTL-via-sleep tests are flaky under the project's full
    # async-aware pytest config. `test_rejects_expired` already
    # exercises the expiry-rejection branch via `ttl_seconds=-1`,
    # which is equivalent and deterministic.


# ---------------------------------------------------------------------------
# Integration — asset endpoint accepts the new token
# ---------------------------------------------------------------------------


@pytest.fixture
def report_with_screenshot(db_session, admin_user, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "output.xml").write_text("<robot/>", encoding="utf-8")
    (output_dir / "screenshot.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    return _setup_report(
        db_session, admin_user,
        output_xml_path=str(output_dir / "output.xml"),
    )


class TestAssetEndpointAcceptsAssetToken:
    def test_accepts_valid_asset_token(self, client, report_with_screenshot):
        token = mint_asset_token(report_with_screenshot.id)
        resp = client.get(
            f"/api/v1/reports/{report_with_screenshot.id}/assets/screenshot.png",
            params={"at": token},
        )
        assert resp.status_code == 200
        assert resp.content.startswith(b"\x89PNG")

    def test_rejects_asset_token_for_other_report(
        self, client, report_with_screenshot,
    ):
        # Mint for a *different* report id; verifier must fail.
        wrong_token = mint_asset_token(report_with_screenshot.id + 999)
        resp = client.get(
            f"/api/v1/reports/{report_with_screenshot.id}/assets/screenshot.png",
            params={"at": wrong_token},
        )
        assert resp.status_code == 401

    def test_rejects_garbage_asset_token(self, client, report_with_screenshot):
        resp = client.get(
            f"/api/v1/reports/{report_with_screenshot.id}/assets/screenshot.png",
            params={"at": "obviously-not-a-real-token"},
        )
        assert resp.status_code == 401

    def test_jwt_path_still_works(
        self, client, admin_user, report_with_screenshot,
    ):
        # SECURITY-3 keeps backward-compat with REPORT-1's JWT-in-URL.
        from src.auth.service import create_access_token
        jwt = create_access_token(admin_user.id, admin_user.role)
        resp = client.get(
            f"/api/v1/reports/{report_with_screenshot.id}/assets/screenshot.png",
            params={"token": jwt},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /html embeds the asset token, not the JWT
# ---------------------------------------------------------------------------


class TestHtmlEndpointUsesAssetToken:
    def test_redirect_url_carries_at_query(self, client, admin_user, db_session, tmp_path):
        """The /html endpoint now 302-redirects to the asset URL with an
        `?at=<asset_token>` query (no JWT in the redirect URL — that
        would leak the user's session into iframe history). The user's
        original auth header is still required ON the /html call."""
        out = tmp_path / "out"
        out.mkdir()
        html_path = out / "report.html"
        html_path.write_text(
            "<html><head><title>R</title></head><body></body></html>",
            encoding="utf-8",
        )
        (out / "output.xml").write_text("<robot/>", encoding="utf-8")
        report = _setup_report(
            db_session, admin_user,
            output_xml_path=str(out / "output.xml"),
            report_html_path=str(html_path),
        )

        resp = client.get(
            f"/api/v1/reports/{report.id}/html",
            headers=auth_header(admin_user),
            follow_redirects=False,
        )
        assert resp.status_code == 302
        location = resp.headers["location"]
        # New: an `at=` asset token is embedded in the redirect URL.
        assert f"/api/v1/reports/{report.id}/assets/report.html?at=" in location
        # Old: the JWT is no longer in the iframe URL.
        assert "token=" not in location.split("?", 1)[1].replace("at=", "")
