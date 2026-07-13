"""EXEC.4: read-only long-name + structural-id surfacing.

`TestResultResponse.long_name` is derived from the stored suite + test names
(no migration); the structural `id` (e.g. s1-t1) is surfaced via the on-demand
deep parser. Both degrade gracefully when absent.
"""

from src.reports.parser import parse_output_xml_deep
from src.reports.schemas import TestResultResponse

NESTED_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2024-01-01T12:00:00.000000">
  <suite id="s1" name="Root">
    <suite id="s1-s1" name="Child">
      <test id="s1-s1-t1" name="Login Works">
        <status status="PASS" start="2024-01-01T12:00:00.000000" end="2024-01-01T12:00:01.000000"/>
      </test>
      <status status="PASS" start="2024-01-01T12:00:00.000000" end="2024-01-01T12:00:01.000000"/>
    </suite>
    <status status="PASS" start="2024-01-01T12:00:00.000000" end="2024-01-01T12:00:01.000000"/>
  </suite>
</robot>
"""


def test_long_name_combines_suite_and_test():
    r = TestResultResponse(
        id=1, report_id=1, suite_name="Root.Child", test_name="Login Works",
        status="PASS", duration_seconds=1.0,
    )
    assert r.long_name == "Root.Child.Login Works"


def test_long_name_degrades_without_suite():
    r = TestResultResponse(
        id=1, report_id=1, suite_name="", test_name="Solo",
        status="PASS", duration_seconds=0.0,
    )
    assert r.long_name == "Solo"


def test_deep_parser_surfaces_structural_id(tmp_path):
    xml_file = tmp_path / "output.xml"
    xml_file.write_text(NESTED_XML)
    data = parse_output_xml_deep(str(xml_file))
    # Drill to the nested test and assert its structural id is exposed.
    child = data["suites"][0]["suites"][0]
    test = child["tests"][0]
    assert test["id"] == "s1-s1-t1"
    assert test["name"] == "Login Works"


def test_deep_parser_id_degrades_when_absent(tmp_path):
    xml_file = tmp_path / "output.xml"
    xml_file.write_text(
        '<robot generated="x"><suite id="s1" name="S">'
        '<test name="NoId"><status status="PASS" start="" end=""/></test>'
        '<status status="PASS" start="" end=""/></suite></robot>'
    )
    data = parse_output_xml_deep(str(xml_file))
    assert data["suites"][0]["tests"][0]["id"] == ""
