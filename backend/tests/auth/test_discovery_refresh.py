"""Tests for OIDC discovery cache refresh job and manual trigger endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.service import hash_password
from tests.conftest import auth_header

BASE_URL = "/api/v1/auth/idp-providers"


def _make_admin(db: Session, suffix: str = ""):
    from src.auth.models import User

    user = User(
        email=f"admin-dr{suffix}@test.com",
        username=f"admin-dr{suffix}",
        hashed_password=hash_password("password"),
        role="admin",
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


def _make_mock_idp(
    idp_id: int = 1,
    name: str = "test-idp",
    is_enabled: bool = True,
    discovery_cached_at: datetime | None = None,
):
    idp = MagicMock()
    idp.id = idp_id
    idp.name = name
    idp.is_enabled = is_enabled
    idp.discovery_cached_at = discovery_cached_at
    return idp


def _stale_time() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=25)


def _fresh_time() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=1)


# ---------------------------------------------------------------------------
# Unit tests for refresh_discovery_cache()
# ---------------------------------------------------------------------------


def test_stale_idp_is_refreshed():
    """Enabled IdP with stale cache should have probe_idp_discovery called."""
    stale_idp = _make_mock_idp(discovery_cached_at=_stale_time())
    mock_session = MagicMock()
    mock_session.__enter__ = lambda s: s
    mock_session.__exit__ = MagicMock(return_value=False)

    with (
        patch("src.auth.discovery_refresh.get_sync_session", return_value=mock_session),
        patch("src.auth.discovery_refresh.list_identity_providers", return_value=[stale_idp]),
        patch("src.auth.discovery_refresh.probe_idp_discovery") as mock_probe,
    ):
        from src.auth.discovery_refresh import refresh_discovery_cache

        result = refresh_discovery_cache()

    mock_probe.assert_called_once()
    assert result["refreshed"] == 1
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["status"] == "completed"


def test_fresh_idp_is_skipped():
    """Enabled IdP with a fresh cache should be skipped (no probe call)."""
    fresh_idp = _make_mock_idp(discovery_cached_at=_fresh_time())
    mock_session = MagicMock()
    mock_session.__enter__ = lambda s: s
    mock_session.__exit__ = MagicMock(return_value=False)

    with (
        patch("src.auth.discovery_refresh.get_sync_session", return_value=mock_session),
        patch("src.auth.discovery_refresh.list_identity_providers", return_value=[fresh_idp]),
        patch("src.auth.discovery_refresh.probe_idp_discovery") as mock_probe,
    ):
        from src.auth.discovery_refresh import refresh_discovery_cache

        result = refresh_discovery_cache()

    mock_probe.assert_not_called()
    assert result["skipped"] == 1
    assert result["refreshed"] == 0


def test_disabled_idp_is_skipped():
    """Disabled IdP should be skipped regardless of cache age."""
    disabled_idp = _make_mock_idp(is_enabled=False, discovery_cached_at=None)
    mock_session = MagicMock()
    mock_session.__enter__ = lambda s: s
    mock_session.__exit__ = MagicMock(return_value=False)

    with (
        patch("src.auth.discovery_refresh.get_sync_session", return_value=mock_session),
        patch("src.auth.discovery_refresh.list_identity_providers", return_value=[disabled_idp]),
        patch("src.auth.discovery_refresh.probe_idp_discovery") as mock_probe,
    ):
        from src.auth.discovery_refresh import refresh_discovery_cache

        result = refresh_discovery_cache()

    mock_probe.assert_not_called()
    assert result["skipped"] == 1
    assert result["refreshed"] == 0


def test_probe_failure_tallied_without_aborting():
    """A probe exception for one IdP increments failed count but continues."""
    idp1 = _make_mock_idp(idp_id=1, discovery_cached_at=_stale_time())
    idp2 = _make_mock_idp(idp_id=2, name="idp2", discovery_cached_at=_stale_time())
    mock_session = MagicMock()
    mock_session.__enter__ = lambda s: s
    mock_session.__exit__ = MagicMock(return_value=False)

    def probe_side_effect(session, idp):
        if idp.id == 1:
            raise ConnectionError("IdP unreachable")

    with (
        patch("src.auth.discovery_refresh.get_sync_session", return_value=mock_session),
        patch("src.auth.discovery_refresh.list_identity_providers", return_value=[idp1, idp2]),
        patch("src.auth.discovery_refresh.probe_idp_discovery", side_effect=probe_side_effect),
    ):
        from src.auth.discovery_refresh import refresh_discovery_cache

        result = refresh_discovery_cache()

    assert result["failed"] == 1
    assert result["refreshed"] == 1


# ---------------------------------------------------------------------------
# Manual trigger endpoint
# ---------------------------------------------------------------------------


def test_manual_trigger_endpoint(client: TestClient, db_session: Session):
    admin = _make_admin(db_session)
    headers = auth_header(admin)

    with (
        patch("src.auth.discovery_refresh.get_sync_session") as mock_sess,
        patch("src.auth.discovery_refresh.list_identity_providers", return_value=[]),
    ):
        mock_sess.return_value.__enter__ = lambda s: MagicMock()
        mock_sess.return_value.__exit__ = MagicMock(return_value=False)

        res = client.post(f"{BASE_URL}/discovery-cache/refresh", headers=headers)

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed"
    assert "refreshed" in body
    assert "failed" in body
    assert "skipped" in body
