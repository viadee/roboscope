"""Story SH-2 — RoboScopeHeal library safety-envelope unit tests.

Mocks out `BuiltIn.run_keyword` so these run without a real Robot
Framework + Browser stack.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.recording.heal.library import RoboScopeHeal


def _make_lib(**overrides):
    """Construct a RoboScopeHeal with a mocked BuiltIn."""
    lib = RoboScopeHeal(**overrides)
    lib._builtin = MagicMock()
    lib._builtin.get_variable_value.return_value = []
    lib._builtin.get_library_instance.side_effect = Exception("no Browser")
    return lib


class TestHappyPath:
    def test_no_failure_calls_underlying_keyword_once(self) -> None:
        lib = _make_lib()
        lib._builtin.run_keyword.return_value = "OK"
        result = lib.heal_click("id=submit")
        assert result == "OK"
        lib._builtin.run_keyword.assert_called_once_with("Click", "id=submit")
        assert lib._heals_in_current_test == 0


class TestRetryOnSelectorTimeout:
    def test_first_failure_triggers_heal_and_second_call_succeeds(self) -> None:
        lib = _make_lib(confidence_threshold_mutating=0.5)
        # First invocation fails with a known selector-timeout signature,
        # second succeeds with any argument.
        lib._builtin.run_keyword.side_effect = [
            Exception("locator('id=submit').click: Timeout 5000ms"),
            "OK",
        ]
        result = lib.heal_click("id=submit")
        assert result == "OK"
        assert lib._builtin.run_keyword.call_count == 2
        assert lib._heals_in_current_test == 1

    def test_non_selector_error_not_retried(self) -> None:
        lib = _make_lib()
        lib._builtin.run_keyword.side_effect = ValueError("incorrect args")
        with pytest.raises(ValueError):
            lib.heal_click("id=submit")
        # Only the original call — no retry on unrelated errors.
        assert lib._builtin.run_keyword.call_count == 1
        assert lib._heals_in_current_test == 0

    def test_retry_candidate_also_fails_reraises_original(self) -> None:
        lib = _make_lib(confidence_threshold_mutating=0.5)
        lib._builtin.run_keyword.side_effect = [
            Exception("Element 'id=submit' not found"),
            Exception("Element not found either"),
        ]
        with pytest.raises(Exception, match="Element 'id=submit' not found"):
            lib.heal_click("id=submit")
        # At most 1 retry per call → 2 underlying invocations.
        assert lib._builtin.run_keyword.call_count == 2
        assert lib._heals_in_current_test == 0  # swap didn't succeed


class TestBudget:
    def test_exhausted_budget_skips_retry(self) -> None:
        lib = _make_lib(max_heals_per_test=0)  # no budget at all
        lib._builtin.run_keyword.side_effect = Exception(
            "Element 'id=submit' not found"
        )
        with pytest.raises(Exception, match="not found"):
            lib.heal_click("id=submit")
        # Only the original attempt — no retry because budget was 0.
        assert lib._builtin.run_keyword.call_count == 1


class TestThresholds:
    def test_below_threshold_does_not_retry(self) -> None:
        # XPath transpositions score ~0.35. With a 0.7 threshold no
        # candidate qualifies, so the failure propagates.
        lib = _make_lib(confidence_threshold_mutating=0.99)
        lib._builtin.run_keyword.side_effect = Exception(
            "Element 'xpath=//button[1]' not found"
        )
        with pytest.raises(Exception, match="not found"):
            lib.heal_click("xpath=//button[1]")
        # Above-threshold check happens before the retry call.
        assert lib._builtin.run_keyword.call_count == 1


class TestOptOut:
    def test_no_heal_tag_bypasses_the_retry(self) -> None:
        lib = _make_lib()
        lib._builtin.get_variable_value.return_value = ["no-heal"]
        lib._builtin.run_keyword.side_effect = Exception(
            "Element not found"
        )
        with pytest.raises(Exception, match="not found"):
            lib.heal_click("id=submit")
        # No retry, even though the error message matches.
        assert lib._builtin.run_keyword.call_count == 1


class TestAuditLog:
    def test_successful_heal_appends_audit_line(self, tmp_path: Path) -> None:
        lib = _make_lib(
            output_dir=str(tmp_path),
            confidence_threshold_mutating=0.5,
        )
        lib._builtin.get_variable_value.side_effect = lambda name, *a, **kw: {
            "${TEST TAGS}": [],
            "${TEST NAME}": "My Flaky Test",
        }.get(name, None)
        lib._builtin.run_keyword.side_effect = [
            Exception("Element 'id=submit' not found"),
            "OK",
        ]
        lib.heal_click("id=submit")

        audit = tmp_path / "heal_audit.jsonl"
        assert audit.is_file()
        lines = audit.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["test_name"] == "My Flaky Test"
        assert record["keyword"] == "Click"
        assert record["original_selector"] == "id=submit"
        assert record["source"] == "transposition"
        assert 0.0 <= record["confidence"] <= 1.0

    def test_failed_retry_does_not_write_audit(self, tmp_path: Path) -> None:
        lib = _make_lib(
            output_dir=str(tmp_path),
            confidence_threshold_mutating=0.5,
        )
        lib._builtin.run_keyword.side_effect = [
            Exception("Element not found"),
            Exception("still not found"),
        ]
        with pytest.raises(Exception):
            lib.heal_click("id=submit")
        audit = tmp_path / "heal_audit.jsonl"
        assert not audit.exists(), "audit must only reflect successful heals"


class TestCommandIdLookup:
    """RECORDER-IDMAP — `_lookup_command_id` correlates the failed
    selector to the recorded command via the sidecar.

    Two real-world variants of the failed-selector string need to
    resolve to the same recorded command:
      1. plain inner selector (`#accept-all`) — top-frame click.
      2. composite cross-frame selector (`iframe[src*="..."] >>>
         #accept-all`) — Sourcepoint / OneTrust consent banner case.
    The sidecar always stores only the inner selector on the
    candidate; the iframe wrap lives separately on `cmd.frame_url`.
    """

    @staticmethod
    def _write_sidecar(tmp_path: Path, sidecar_name: str = "flow.rbs.json") -> Path:
        sidecar = tmp_path / sidecar_name
        sidecar.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "transport": "web_playwright",
                    "session_id": "s1",
                    "commands": [
                        {
                            "id": "abc123def456",
                            "index": 0,
                            "keyword": "Click",
                            "args": {},
                            "selector_candidates": [
                                {
                                    "strategy": "css",
                                    "value": "#accept-all",
                                    "quality_score": 90,
                                    "verified_unique": True,
                                }
                            ],
                            "active_candidate_index": 0,
                            "frame_url": "https://message-eu.sp-prod.net/?id=42",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return sidecar

    def test_top_frame_inner_selector_resolves_to_command_id(self, tmp_path: Path) -> None:
        sidecar = self._write_sidecar(tmp_path)
        lib = _make_lib(sidecar_path=str(sidecar))
        assert lib._lookup_command_id("#accept-all") == "abc123def456"

    def test_iframe_wrapped_selector_resolves_to_command_id(self, tmp_path: Path) -> None:
        sidecar = self._write_sidecar(tmp_path)
        lib = _make_lib(sidecar_path=str(sidecar))
        composite = 'iframe[src*="message-eu.sp-prod.net"] >>> #accept-all'
        assert lib._lookup_command_id(composite) == "abc123def456"

    def test_chained_iframe_selector_resolves_to_command_id(self, tmp_path: Path) -> None:
        sidecar = self._write_sidecar(tmp_path)
        lib = _make_lib(sidecar_path=str(sidecar))
        composite = (
            'iframe[src*="outer.example"] >>> iframe[src*="inner.example"] >>> #accept-all'
        )
        assert lib._lookup_command_id(composite) == "abc123def456"

    def test_unrelated_selector_returns_none(self, tmp_path: Path) -> None:
        sidecar = self._write_sidecar(tmp_path)
        lib = _make_lib(sidecar_path=str(sidecar))
        assert lib._lookup_command_id("#something-else") is None

    def test_unwrap_iframe_prefix_passthrough_for_plain_selectors(self) -> None:
        # `text="Login"` is not an iframe wrap — must not be touched.
        assert RoboScopeHeal._unwrap_iframe_prefix("text=\"Login\"") == "text=\"Login\""
        # `iframe` keyword without the `[...]` attribute selector is also
        # not the cross-frame dialect; leave it alone.
        assert RoboScopeHeal._unwrap_iframe_prefix("iframe") == "iframe"


class TestFingerprintHealIframeBlindspot:
    """Story SH-3 fingerprint walker, RECORDER-FRAMES guard.

    The fingerprint walker JS uses ``document.querySelectorAll`` on
    the TOP frame. Cross-origin iframes (Sourcepoint / OneTrust /
    TCF cookie banners — the dominant iframe case in real
    recordings) can't be traversed via ``contentDocument``, so a
    walker run for an iframe-wrapped failed selector would emit
    candidate selectors that target the wrong DOM. The runtime
    guard refuses to walk in that case so a heal can never silently
    click the wrong element.

    Sidecar fingerprint LOOKUP, however, must still resolve the
    stored fingerprint via the inner selector so a future cross-
    frame walker (Browser library frame-scoped Evaluate JS) can
    reuse the stored signature without another schema migration.
    """

    @staticmethod
    def _write_sidecar_with_fingerprint(tmp_path: Path) -> Path:
        sc = tmp_path / "flow.rbs.json"
        sc.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "commands": [
                        {
                            "id": "fpcmd0000001",
                            "index": 0,
                            "keyword": "Click",
                            "args": {},
                            "selector_candidates": [
                                {
                                    "strategy": "css",
                                    "value": "#accept-all",
                                    "quality_score": 90,
                                    "verified_unique": True,
                                }
                            ],
                            "active_candidate_index": 0,
                            "frame_url": "https://message-eu.sp-prod.net/?id=42",
                            "element_fingerprint": {
                                "tag": "button",
                                "id": "accept-all",
                                "testid": None,
                                "classes": ["sp-accept"],
                                "name": None,
                                "role": "button",
                                "text": "Accept all",
                                "ancestors": [],
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return sc

    def test_lookup_stored_fingerprint_strips_iframe_wrap(
        self, tmp_path: Path
    ) -> None:
        sc = self._write_sidecar_with_fingerprint(tmp_path)
        lib = _make_lib(sidecar_path=str(sc))
        # Top-frame lookup still works.
        fp_top = lib._lookup_stored_fingerprint("#accept-all")
        assert fp_top is not None
        assert fp_top["text"] == "Accept all"
        # Iframe-wrapped lookup resolves to the SAME stored
        # fingerprint via the inner selector.
        composite = 'iframe[src*="message-eu.sp-prod.net"] >>> #accept-all'
        fp_frame = lib._lookup_stored_fingerprint(composite)
        assert fp_frame == fp_top

    def test_try_fingerprint_heal_skips_walker_for_iframe_selector(
        self, tmp_path: Path
    ) -> None:
        sc = self._write_sidecar_with_fingerprint(tmp_path)
        lib = _make_lib(sidecar_path=str(sc))
        # Pretend Browser library is reachable so we get past that
        # early-return — the iframe guard must trip BEFORE the walker
        # JS runs. If the guard didn't fire, run_keyword would be
        # invoked at least once for "Evaluate JavaScript".
        lib._builtin.get_library_instance.side_effect = None
        lib._builtin.get_library_instance.return_value = object()

        composite = 'iframe[src*="message-eu.sp-prod.net"] >>> #accept-all'
        result = lib._try_fingerprint_heal(composite, threshold=0.5)
        assert result is None
        # The walker JS must NEVER run for an iframe-wrapped selector;
        # otherwise it would emit top-frame candidate selectors that
        # silently click the wrong element on retry.
        eval_calls = [
            c for c in lib._builtin.run_keyword.call_args_list
            if c.args and c.args[0] == "Evaluate JavaScript"
        ]
        assert eval_calls == [], (
            "fingerprint walker must NOT run for iframe-wrapped failed "
            f"selectors, but it was invoked: {eval_calls}"
        )

    def test_try_fingerprint_heal_still_runs_for_top_frame_selector(
        self, tmp_path: Path
    ) -> None:
        # Backward compatibility — when the failed selector has no
        # iframe wrap, the walker must still attempt to fire (its own
        # internal failures still degrade gracefully to None).
        sc = self._write_sidecar_with_fingerprint(tmp_path)
        lib = _make_lib(sidecar_path=str(sc))
        lib._builtin.get_library_instance.side_effect = None
        lib._builtin.get_library_instance.return_value = object()
        # Walker JS returns no live candidates — match=None is fine,
        # we're only asserting the JS DID run.
        lib._builtin.run_keyword.return_value = []

        result = lib._try_fingerprint_heal("#accept-all", threshold=0.5)
        assert result is None
        # The walker JS DID run for the top-frame case.
        eval_calls = [
            c for c in lib._builtin.run_keyword.call_args_list
            if c.args and c.args[0] == "Evaluate JavaScript"
        ]
        assert len(eval_calls) == 1, (
            "top-frame fingerprint heal should still run the walker JS"
        )
