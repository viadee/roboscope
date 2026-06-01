"""Tests for `src.main` boot-time wiring — formatter selection,
banner suppression under pytest, browser auto-open guard.

Story LAUNCH-1: standalone-start UX. The text-log toggle and the
ready-banner are *opt-in* via env vars (`LOG_FORMAT=text`,
`OPEN_BROWSER=1`). Without those, we must keep emitting JSON the
way Docker / CI / log shippers expect.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from pythonjsonlogger.json import JsonFormatter

from src.main import (
    _build_formatter,
    _print_ready_banner,
    _supports_unicode_box,
)


class TestFormatterDefault:
    def test_unset_log_format_yields_json(self, monkeypatch):
        """AC4 regression: leaving LOG_FORMAT unset MUST keep emitting
        JSON. Docker, `make dev`, the test suite, and any
        log-shipper integration all rely on this default."""
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        formatter = _build_formatter()
        assert isinstance(formatter, JsonFormatter), (
            f"expected JsonFormatter when LOG_FORMAT is unset, got {type(formatter).__name__}"
        )

    def test_log_format_json_yields_json(self, monkeypatch):
        monkeypatch.setenv("LOG_FORMAT", "json")
        assert isinstance(_build_formatter(), JsonFormatter)

    def test_log_format_text_yields_text(self, monkeypatch):
        """AC1: `LOG_FORMAT=text` flips to a plain `logging.Formatter`."""
        monkeypatch.setenv("LOG_FORMAT", "text")
        formatter = _build_formatter()
        assert not isinstance(formatter, JsonFormatter)
        assert isinstance(formatter, logging.Formatter)
        # Render a sample record through it — the output should be
        # human-readable, not JSON.
        record = logging.LogRecord(
            name="roboscope.test", level=logging.INFO, pathname=__file__,
            lineno=1, msg="hello", args=(), exc_info=None,
        )
        rendered = formatter.format(record)
        assert "INFO" in rendered
        assert "roboscope.test" in rendered
        assert "hello" in rendered
        assert not rendered.startswith("{")  # not JSON

    def test_log_format_text_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("LOG_FORMAT", "TEXT")
        assert not isinstance(_build_formatter(), JsonFormatter)


class TestBannerSuppressionUnderPytest:
    def test_banner_does_not_print_when_pytest_running(self, capsys):
        """Pytest sets `PYTEST_CURRENT_TEST`; the banner must
        no-op so test output stays clean. Real boot ALSO doesn't
        have this env var, so the suppression is precise."""
        # We're running under pytest right now — PYTEST_CURRENT_TEST is set.
        _print_ready_banner()
        captured = capsys.readouterr()
        assert captured.out == "", (
            f"banner leaked under pytest: {captured.out!r}"
        )

    def test_banner_prints_when_not_under_pytest(self, monkeypatch, capsys):
        """Drop the pytest sentinel and the banner should fire."""
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("OPEN_BROWSER", raising=False)
        _print_ready_banner()
        captured = capsys.readouterr()
        assert "RoboScope is running" in captured.out
        assert "http://localhost:" in captured.out


class TestUnicodeBoxDetection:
    def test_windows_uses_ascii(self, monkeypatch):
        """AC5: Windows cmd in legacy code-pages mojibakes
        `═` — we fall back to `=`."""
        monkeypatch.setattr("sys.platform", "win32")
        assert _supports_unicode_box() is False

    def test_non_utf8_pythonioencoding_falls_back(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("PYTHONIOENCODING", "latin-1")
        assert _supports_unicode_box() is False

    def test_utf8_pythonioencoding_keeps_unicode(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
        assert _supports_unicode_box() is True

    def test_unset_pythonioencoding_on_linux_keeps_unicode(self, monkeypatch):
        """Modern Linux/macOS terminals are UTF-8 by default; absence
        of PYTHONIOENCODING shouldn't force ASCII."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.delenv("PYTHONIOENCODING", raising=False)
        assert _supports_unicode_box() is True


class TestOpenBrowserGuard:
    def test_open_browser_unset_does_not_call_webbrowser(self, monkeypatch):
        """AC3: `OPEN_BROWSER` defaults OFF. webbrowser.open must NOT
        fire on an unconfigured boot."""
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("OPEN_BROWSER", raising=False)
        with patch("src.main.webbrowser.open") as mock_open:
            _print_ready_banner()
            mock_open.assert_not_called()

    def test_open_browser_truthy_fires(self, monkeypatch, capsys):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.setenv("OPEN_BROWSER", "1")
        with patch("src.main.webbrowser.open") as mock_open:
            _print_ready_banner()
            mock_open.assert_called_once()
            assert mock_open.call_args[0][0].startswith("http://localhost:")

    @pytest.mark.parametrize("value", ["true", "yes", "1"])
    def test_open_browser_truthy_aliases(self, monkeypatch, value):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.setenv("OPEN_BROWSER", value)
        with patch("src.main.webbrowser.open") as mock_open:
            _print_ready_banner()
            mock_open.assert_called_once()

    @pytest.mark.parametrize("value", ["", "0", "false", "no", "off"])
    def test_open_browser_falsy_skips(self, monkeypatch, value):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.setenv("OPEN_BROWSER", value)
        with patch("src.main.webbrowser.open") as mock_open:
            _print_ready_banner()
            mock_open.assert_not_called()

    def test_open_browser_failure_does_not_raise(self, monkeypatch):
        """A headless install with `OPEN_BROWSER=1` must NOT crash
        startup — webbrowser.open can raise on missing $BROWSER."""
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.setenv("OPEN_BROWSER", "1")
        with patch("src.main.webbrowser.open", side_effect=RuntimeError("no browser")):
            # Must not raise.
            _print_ready_banner()
