"""Story SH-2 — parse the run-time heal audit log into a structured
report the frontend can render.

Every `Heal *` keyword that swapped a selector appends a JSONL line to
`<run_output_dir>/heal_audit.jsonl`. After the run finishes, this
module reads the file, cross-references the test outcomes with the
Robot Framework `output.xml` (best-effort), and classifies each heal
as `confirmed` (the test passed) or `suspect` (the test ultimately
failed — the heal may have clicked the wrong element).
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HealAuditEntry:
    timestamp: str
    test_name: str
    keyword: str
    original_selector: str
    healed_selector: str
    confidence: float
    source: str  # "sidecar" | "transposition"
    outcome: str = "unknown"  # filled in by parse_heal_audit

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "test_name": self.test_name,
            "keyword": self.keyword,
            "original_selector": self.original_selector,
            "healed_selector": self.healed_selector,
            "confidence": self.confidence,
            "source": self.source,
            "outcome": self.outcome,
        }


@dataclass
class HealReport:
    total_heals: int = 0
    confirmed: int = 0
    suspect: int = 0
    entries: list[HealAuditEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_heals": self.total_heals,
            "confirmed": self.confirmed,
            "suspect": self.suspect,
            "entries": [e.to_dict() for e in self.entries],
        }


def _parse_output_xml_for_test_outcomes(output_xml: Path) -> dict[str, str]:
    """Return `{test_name: "PASS" | "FAIL" | "SKIP"}` from output.xml.

    Robot Framework's XML shape:
      <robot>
        <suite>
          <test name="...">
            <status status="PASS|FAIL|SKIP" />
          </test>
        </suite>
      </robot>
    """
    outcomes: dict[str, str] = {}
    try:
        root = ET.parse(output_xml).getroot()
    except (OSError, ET.ParseError):
        return outcomes
    for test in root.iter("test"):
        name = test.attrib.get("name", "")
        status_el = test.find("status")
        status = status_el.attrib.get("status", "") if status_el is not None else ""
        if name and status:
            outcomes[name] = status
    return outcomes


def parse_heal_audit(
    audit_path: Path,
    *,
    output_xml: Path | None = None,
) -> HealReport:
    """Read the JSONL audit log and classify each entry against test outcomes.

    Missing or empty audit file → an empty report (all zeros). A
    malformed JSONL line is silently skipped rather than aborting the
    whole parse.
    """
    if not audit_path.is_file():
        return HealReport()

    # Load test outcomes best-effort — a heal on a run that didn't
    # produce an output.xml at all stays `unknown`.
    outcomes: dict[str, str] = {}
    if output_xml is not None:
        outcomes = _parse_output_xml_for_test_outcomes(output_xml)

    entries: list[HealAuditEntry] = []
    for line in audit_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        entry = HealAuditEntry(
            timestamp=str(record.get("timestamp", "")),
            test_name=str(record.get("test_name", "")),
            keyword=str(record.get("keyword", "")),
            original_selector=str(record.get("original_selector", "")),
            healed_selector=str(record.get("healed_selector", "")),
            confidence=_coerce_float(record.get("confidence"), 0.0),
            source=str(record.get("source", "transposition")),
        )
        status = outcomes.get(entry.test_name)
        if status == "PASS":
            entry.outcome = "confirmed"
        elif status == "FAIL":
            entry.outcome = "suspect"
        elif status == "SKIP":
            entry.outcome = "skipped"
        else:
            entry.outcome = "unknown"
        entries.append(entry)

    confirmed = sum(1 for e in entries if e.outcome == "confirmed")
    suspect = sum(1 for e in entries if e.outcome == "suspect")
    return HealReport(
        total_heals=len(entries),
        confirmed=confirmed,
        suspect=suspect,
        entries=entries,
    )


def _coerce_float(v: object, default: float) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Heal-audit writer — used by the RF library at runtime.
# ---------------------------------------------------------------------------


def append_heal_audit(
    audit_path: Path,
    *,
    test_name: str,
    keyword: str,
    original_selector: str,
    healed_selector: str,
    confidence: float,
    source: str,
) -> None:
    """Append a single JSONL record to the audit file. Best-effort — a
    filesystem error does NOT take the test down; we log to stderr and
    keep going. A failed audit write means the heal still helped the
    test pass; losing the audit is far less bad than killing the run.
    """
    from datetime import datetime, timezone

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_name": test_name,
        "keyword": keyword,
        "original_selector": original_selector,
        "healed_selector": healed_selector,
        "confidence": round(float(confidence), 4),
        "source": source,
    }
    try:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        import sys as _sys

        print(
            f"[roboscope-heal] failed to write heal audit {audit_path}: {exc}",
            file=_sys.stderr,
        )


# Regex the parser uses to recognise a valid ISO-8601-ish timestamp.
# Exposed so tests can assert we write something parseable.
ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
)
