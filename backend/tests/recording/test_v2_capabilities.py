"""Story DEPLOY-1 — recorder capability probe.

Covers the heuristic in `_web_playwright_viable`: headless Linux → no,
Linux with DISPLAY → yes, explicit override beats heuristic either way.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from tests.conftest import auth_header


ENDPOINT = "/api/v1/recordings/sessions/capabilities"


class TestPlatformHeuristic:
    def test_linux_without_display_returns_false(
        self, client: TestClient, admin_user: User, monkeypatch
    ) -> None:
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.delenv("ROBOSCOPE_HEADED_BROWSER", raising=False)
        resp = client.get(ENDPOINT, headers=auth_header(admin_user))
        assert resp.status_code == 200
        assert resp.json()["web_playwright_viable"] is False

    def test_linux_with_display_returns_true(
        self, client: TestClient, admin_user: User, monkeypatch
    ) -> None:
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.delenv("ROBOSCOPE_HEADED_BROWSER", raising=False)
        resp = client.get(ENDPOINT, headers=auth_header(admin_user))
        assert resp.status_code == 200
        assert resp.json()["web_playwright_viable"] is True

    def test_linux_with_wayland_display_returns_true(
        self, client: TestClient, admin_user: User, monkeypatch
    ) -> None:
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        monkeypatch.delenv("ROBOSCOPE_HEADED_BROWSER", raising=False)
        resp = client.get(ENDPOINT, headers=auth_header(admin_user))
        assert resp.json()["web_playwright_viable"] is True

    def test_darwin_defaults_to_true(
        self, client: TestClient, admin_user: User, monkeypatch
    ) -> None:
        monkeypatch.setattr("sys.platform", "darwin")
        monkeypatch.delenv("ROBOSCOPE_HEADED_BROWSER", raising=False)
        resp = client.get(ENDPOINT, headers=auth_header(admin_user))
        assert resp.json()["web_playwright_viable"] is True


class TestExplicitOverride:
    def test_override_false_beats_local_display(
        self, client: TestClient, admin_user: User, monkeypatch
    ) -> None:
        monkeypatch.setattr("sys.platform", "darwin")
        monkeypatch.setenv("ROBOSCOPE_HEADED_BROWSER", "false")
        resp = client.get(ENDPOINT, headers=auth_header(admin_user))
        assert resp.json()["web_playwright_viable"] is False

    def test_override_true_beats_headless_linux(
        self, client: TestClient, admin_user: User, monkeypatch
    ) -> None:
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("ROBOSCOPE_HEADED_BROWSER", "true")
        resp = client.get(ENDPOINT, headers=auth_header(admin_user))
        assert resp.json()["web_playwright_viable"] is True


class TestDesktopTransports:
    def test_desktop_windows_only_on_windows(
        self, client: TestClient, admin_user: User, monkeypatch
    ) -> None:
        # The pywinauto dependency is also required (see the gating tests
        # below); pin it present here so this test isolates the OS check.
        monkeypatch.setattr(
            "src.recording.win32_input.pywinauto_available", lambda: True
        )
        monkeypatch.setattr("sys.platform", "darwin")
        resp = client.get(ENDPOINT, headers=auth_header(admin_user))
        body = resp.json()
        assert body["desktop_windows_viable"] is False
        assert body["desktop_macos_viable"] is False

        monkeypatch.setattr("sys.platform", "win32")
        resp = client.get(ENDPOINT, headers=auth_header(admin_user))
        body = resp.json()
        assert body["desktop_windows_viable"] is True
        # DM.1 NO-GO lock — macOS stays false regardless of host platform.
        assert body["desktop_macos_viable"] is False

    def test_desktop_windows_false_when_pywinauto_missing(
        self, client: TestClient, admin_user: User, monkeypatch
    ) -> None:
        """Regression: a Windows host WITHOUT the `windows` extra installed
        used to report viable=True, so the launcher offered desktop
        recording and the background task crashed straight to "beendet"
        with the ModuleNotFoundError buried in the backend log. The
        capability probe must reflect the missing dependency."""
        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.setattr(
            "src.recording.win32_input.pywinauto_available", lambda: False
        )
        resp = client.get(ENDPOINT, headers=auth_header(admin_user))
        assert resp.status_code == 200
        assert resp.json()["desktop_windows_viable"] is False

    def test_desktop_windows_true_when_pywinauto_present(
        self, client: TestClient, admin_user: User, monkeypatch
    ) -> None:
        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.setattr(
            "src.recording.win32_input.pywinauto_available", lambda: True
        )
        resp = client.get(ENDPOINT, headers=auth_header(admin_user))
        assert resp.json()["desktop_windows_viable"] is True


class TestAuth:
    def test_requires_authentication(self, client: TestClient) -> None:
        resp = client.get(ENDPOINT)
        assert resp.status_code == 401
