"""Story SH-2 — heal-audit parser + suspect-classification tests."""

from __future__ import annotations

import json
from pathlib import Path

from src.recording.heal.heal_report import (
    append_heal_audit,
    parse_heal_audit,
    ISO_TIMESTAMP_RE,
)


def _write_audit(tmp_path: Path, records: list[dict]) -> Path:
    p = tmp_path / "heal_audit.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return p


def _write_output_xml(tmp_path: Path, tests: dict[str, str]) -> Path:
    """Minimal RF output.xml with a single suite wrapping all tests."""
    parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    parts.append('<robot generator="test-fixture">')
    parts.append('<suite name="Demo">')
    for name, status in tests.items():
        parts.append(f'<test name="{name}"><status status="{status}"/></test>')
    parts.append("</suite></robot>")
    p = tmp_path / "output.xml"
    p.write_text("\n".join(parts), encoding="utf-8")
    return p


class TestParseHealAudit:
    def test_empty_file_returns_empty_report(self, tmp_path: Path) -> None:
        audit = _write_audit(tmp_path, [])
        report = parse_heal_audit(audit)
        assert report.total_heals == 0
        assert report.entries == []

    def test_missing_file_returns_empty_report(self, tmp_path: Path) -> None:
        report = parse_heal_audit(tmp_path / "does-not-exist.jsonl")
        assert report.total_heals == 0

    def test_confirms_heal_when_test_passed(self, tmp_path: Path) -> None:
        audit = _write_audit(tmp_path, [{
            "timestamp": "2026-04-24T09:00:00Z",
            "test_name": "Login Works",
            "keyword": "Click",
            "original_selector": "id=submit",
            "healed_selector": "[data-testid=submit]",
            "confidence": 0.95,
            "source": "sidecar",
        }])
        output_xml = _write_output_xml(tmp_path, {"Login Works": "PASS"})
        report = parse_heal_audit(audit, output_xml=output_xml)
        assert report.total_heals == 1
        assert report.confirmed == 1
        assert report.suspect == 0
        assert report.entries[0].outcome == "confirmed"

    def test_marks_suspect_when_test_failed(self, tmp_path: Path) -> None:
        audit = _write_audit(tmp_path, [{
            "timestamp": "2026-04-24T09:00:00Z",
            "test_name": "Broken Test",
            "keyword": "Click",
            "original_selector": "id=submit",
            "healed_selector": "text=Submit",
            "confidence": 0.7,
            "source": "transposition",
        }])
        output_xml = _write_output_xml(tmp_path, {"Broken Test": "FAIL"})
        report = parse_heal_audit(audit, output_xml=output_xml)
        assert report.suspect == 1
        assert report.entries[0].outcome == "suspect"

    def test_no_output_xml_leaves_outcome_unknown(self, tmp_path: Path) -> None:
        audit = _write_audit(tmp_path, [{
            "timestamp": "2026-04-24T09:00:00Z",
            "test_name": "X",
            "keyword": "Click",
            "original_selector": "id=a",
            "healed_selector": "id=b",
            "confidence": 0.8,
            "source": "transposition",
        }])
        report = parse_heal_audit(audit, output_xml=None)
        assert report.entries[0].outcome == "unknown"
        assert report.confirmed == 0
        assert report.suspect == 0

    def test_malformed_line_is_skipped(self, tmp_path: Path) -> None:
        p = tmp_path / "heal_audit.jsonl"
        p.write_text(
            '{"ok": true}\nnot-json\n{"another": "ok"}\n',
            encoding="utf-8",
        )
        report = parse_heal_audit(p)
        # Two valid records → two entries; malformed middle line skipped.
        assert report.total_heals == 2

    def test_skipped_test_outcome_not_counted_as_suspect(
        self, tmp_path: Path
    ) -> None:
        audit = _write_audit(tmp_path, [{
            "timestamp": "2026-04-24T09:00:00Z",
            "test_name": "Skipped Test",
            "keyword": "Click",
            "original_selector": "id=a",
            "healed_selector": "id=b",
            "confidence": 0.9,
            "source": "sidecar",
        }])
        output_xml = _write_output_xml(tmp_path, {"Skipped Test": "SKIP"})
        report = parse_heal_audit(audit, output_xml=output_xml)
        assert report.entries[0].outcome == "skipped"
        assert report.suspect == 0
        assert report.confirmed == 0


class TestAppendHealAudit:
    def test_writes_parseable_jsonl_with_iso_timestamp(
        self, tmp_path: Path
    ) -> None:
        audit = tmp_path / "nested" / "heal_audit.jsonl"
        append_heal_audit(
            audit,
            test_name="Demo",
            keyword="Click",
            original_selector="id=a",
            healed_selector="id=b",
            confidence=0.99,
            source="sidecar",
        )
        assert audit.is_file()
        record = json.loads(audit.read_text(encoding="utf-8").strip())
        assert record["keyword"] == "Click"
        assert ISO_TIMESTAMP_RE.match(record["timestamp"]) is not None

    def test_multiple_appends_accumulate(self, tmp_path: Path) -> None:
        audit = tmp_path / "heal_audit.jsonl"
        for i in range(3):
            append_heal_audit(
                audit,
                test_name="T",
                keyword="Click",
                original_selector=f"id=x{i}",
                healed_selector=f"id=y{i}",
                confidence=0.8,
                source="transposition",
            )
        lines = audit.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
