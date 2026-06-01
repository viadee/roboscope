"""Walk a Robot Framework `output.xml` to locate the first failing keyword.

Story DEBUG-2 needs `(file_path, line_number, test_name, keyword_name)` for
the test that originally failed so we can:

1. Re-launch ONLY that test (via `--test "<name>"`).
2. Set a breakpoint on the line that actually failed (so the user lands
   in the right scope, not at the test header).

`reports.parser.parse_output_xml*` exists already but doesn't surface
keyword-level `source`/`line` attributes — the test-summary parser only
reads test status. Rather than bloat that public surface we keep a
focused walker here.

XML schema (RF 7.x):

    <robot>
      <suite source="...">
        <test name="...">
          <kw name="..." source="/abs/path/file.robot" line="42">
            <status status="FAIL">
            ...
          </kw>
          <status status="FAIL">message</status>
        </test>
      </suite>
    </robot>

Keywords nest; we want the deepest FAILing keyword in the first FAILing
test. Suite-level setups/teardowns can also fail — handled separately
since the breakpoint then points at the suite file rather than a test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree.ElementTree import Element as _Element

from defusedxml import ElementTree as ET  # noqa: N817 — match reports/parser.py


@dataclass
class FailingKeywordLocation:
    """Where the first failing keyword lives.

    `source` is the absolute path RF wrote into `output.xml`. The
    router translates that to a repo-relative path before handing it
    to RobotDebugSession (RF wants absolute paths for setBreakpoints
    anyway, but the audit-log + frontend display want repo-relative).
    """

    test_name: str
    keyword_name: str
    source: str
    line: int
    suite_source: str


def find_first_failing_keyword(xml_path: str | Path) -> FailingKeywordLocation | None:
    """Return the deepest FAILing keyword in the first FAILing test.

    Returns ``None`` when:

    * the file doesn't exist or is malformed,
    * no test failed,
    * the failing keyword has no ``source`` / ``line`` attributes
      (e.g. failing setup with no concrete keyword line — caller
      falls back to the test-header line).
    """
    path = Path(xml_path)
    if not path.exists():
        return None
    try:
        tree = ET.parse(str(path))
    except (ValueError, ET.ParseError):
        return None
    root = tree.getroot()

    suite = root.find("suite")
    if suite is None:
        return None

    return _scan_suite(suite, suite.get("source", ""))


def _scan_suite(suite: _Element, suite_source: str) -> FailingKeywordLocation | None:
    # First, scan tests directly in this suite.
    for test in suite.findall("test"):
        status = test.find("status")
        if status is None or status.get("status") != "FAIL":
            continue
        loc = _scan_test_for_failing_keyword(test, suite_source)
        if loc is not None:
            return loc
    # Then recurse into child suites.
    for child in suite.findall("suite"):
        loc = _scan_suite(child, child.get("source", "") or suite_source)
        if loc is not None:
            return loc
    return None


def _scan_test_for_failing_keyword(
    test: _Element, suite_source: str
) -> FailingKeywordLocation | None:
    test_name = test.get("name", "")
    found = _walk_keyword_tree_for_failure(test, default_source=suite_source)
    if found is None:
        return None
    kw_name, source, line = found
    return FailingKeywordLocation(
        test_name=test_name,
        keyword_name=kw_name,
        source=source,
        line=line,
        suite_source=suite_source,
    )


def _walk_keyword_tree_for_failure(
    parent: _Element, default_source: str
) -> tuple[str, str, int] | None:
    """Depth-first walk: deepest FAILing keyword wins.

    Returns ``(keyword_name, source, line)`` or ``None``.
    """
    deepest: tuple[str, str, int] | None = None
    for kw in parent.findall("kw"):
        status = kw.find("status")
        if status is None or status.get("status") != "FAIL":
            continue
        # Recurse first; deeper failures shadow the outer kw.
        nested = _walk_keyword_tree_for_failure(kw, default_source)
        if nested is not None:
            deepest = nested
            continue
        # Leaf: this is a failing keyword with no failing children —
        # emit it if it carries source/line metadata.
        source = kw.get("source") or default_source
        line_str = kw.get("line")
        if not source or not line_str:
            continue
        try:
            line = int(line_str)
        except ValueError:
            continue
        deepest = (kw.get("name", ""), source, line)
    return deepest
