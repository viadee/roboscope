"""Tests for the Robot Framework output.xml parser."""

import pytest

from src.reports.parser import ParsedReport, ParsedTestResult, parse_output_xml


SAMPLE_OUTPUT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2024-01-01T12:00:00.000000">
  <suite id="s1" name="Test Suite">
    <test id="s1-t1" name="Test One" line="5">
      <kw name="Log" library="BuiltIn">
        <msg timestamp="2024-01-01T12:00:01.000000" level="INFO">Hello</msg>
        <status status="PASS" starttime="2024-01-01T12:00:00.500000" endtime="2024-01-01T12:00:01.000000"/>
      </kw>
      <tag>smoke</tag>
      <status status="PASS" starttime="2024-01-01T12:00:00.000000" endtime="2024-01-01T12:00:01.000000"/>
    </test>
    <test id="s1-t2" name="Test Two" line="10">
      <kw name="Fail" library="BuiltIn">
        <msg timestamp="2024-01-01T12:00:02.000000" level="FAIL">Assertion failed</msg>
        <status status="FAIL" starttime="2024-01-01T12:00:01.500000" endtime="2024-01-01T12:00:02.000000"/>
      </kw>
      <status status="FAIL" starttime="2024-01-01T12:00:01.000000" endtime="2024-01-01T12:00:02.000000">Assertion failed</status>
    </test>
    <status status="FAIL" starttime="2024-01-01T12:00:00.000000" endtime="2024-01-01T12:00:02.000000"/>
  </suite>
  <statistics>
    <total>
      <stat pass="1" fail="1" skip="0">All Tests</stat>
    </total>
  </statistics>
</robot>
"""

# Same XML but using start/end attributes (the format the parser actually reads).
SAMPLE_OUTPUT_XML_WITH_DURATIONS = """\
<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2024-01-01T12:00:00.000000">
  <suite id="s1" name="Test Suite">
    <test id="s1-t1" name="Test One" line="5">
      <kw name="Log" library="BuiltIn">
        <msg timestamp="2024-01-01T12:00:01.000000" level="INFO">Hello</msg>
        <status status="PASS" start="2024-01-01T12:00:00.500000" end="2024-01-01T12:00:01.000000"/>
      </kw>
      <tag>smoke</tag>
      <status status="PASS" start="2024-01-01T12:00:00.000000" end="2024-01-01T12:00:01.000000"/>
    </test>
    <test id="s1-t2" name="Test Two" line="10">
      <kw name="Fail" library="BuiltIn">
        <msg timestamp="2024-01-01T12:00:02.000000" level="FAIL">Assertion failed</msg>
        <status status="FAIL" start="2024-01-01T12:00:01.500000" end="2024-01-01T12:00:02.000000"/>
      </kw>
      <status status="FAIL" start="2024-01-01T12:00:01.000000" end="2024-01-01T12:00:02.000000">Assertion failed</status>
    </test>
    <status status="FAIL" start="2024-01-01T12:00:00.000000" end="2024-01-01T12:00:02.000000"/>
  </suite>
  <statistics>
    <total>
      <stat pass="1" fail="1" skip="0">All Tests</stat>
    </total>
  </statistics>
</robot>
"""


class TestParseOutputXml:
    """Tests for parse_output_xml with a sample Robot Framework output.xml."""

    def test_parse_returns_parsed_report(self, tmp_path):
        """parse_output_xml returns a ParsedReport instance."""
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        assert isinstance(result, ParsedReport)

    def test_parse_generated_timestamp(self, tmp_path):
        """Parser extracts the generated timestamp from the root element."""
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        assert result.generated == "2024-01-01T12:00:00.000000"

    def test_parse_suite_name(self, tmp_path):
        """Parser extracts the top-level suite name."""
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        assert result.suite_name == "Test Suite"

    def test_parse_test_count(self, tmp_path):
        """Parser counts the total number of tests."""
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        assert result.total_tests == 2

    def test_parse_passed_count(self, tmp_path):
        """Parser counts passing tests."""
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        assert result.passed_tests == 1

    def test_parse_failed_count(self, tmp_path):
        """Parser counts failing tests."""
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        assert result.failed_tests == 1

    def test_parse_skipped_count(self, tmp_path):
        """Parser counts skipped tests (none in sample)."""
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        assert result.skipped_tests == 0

    def test_parse_test_results_list(self, tmp_path):
        """Parser populates the test_results list with ParsedTestResult objects."""
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        assert len(result.test_results) == 2
        assert all(isinstance(tr, ParsedTestResult) for tr in result.test_results)


class TestParseStatuses:
    """Tests that parse correctly returns test statuses."""

    def test_passing_test_status(self, tmp_path):
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        passing = [tr for tr in result.test_results if tr.test_name == "Test One"]
        assert len(passing) == 1
        assert passing[0].status == "PASS"

    def test_failing_test_status(self, tmp_path):
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        failing = [tr for tr in result.test_results if tr.test_name == "Test Two"]
        assert len(failing) == 1
        assert failing[0].status == "FAIL"

    def test_failing_test_error_message(self, tmp_path):
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        failing = [tr for tr in result.test_results if tr.test_name == "Test Two"]
        assert failing[0].error_message == "Assertion failed"

    def test_passing_test_no_error_message(self, tmp_path):
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        passing = [tr for tr in result.test_results if tr.test_name == "Test One"]
        assert passing[0].error_message == ""


class TestParseDurations:
    """Tests for duration calculation using start/end attributes."""

    def test_duration_with_start_end_attributes(self, tmp_path):
        """When start/end attributes are present, durations are computed."""
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML_WITH_DURATIONS)

        result = parse_output_xml(str(xml_file))

        test_one = [tr for tr in result.test_results if tr.test_name == "Test One"][0]
        assert test_one.duration_seconds == pytest.approx(1.0, abs=0.01)

        test_two = [tr for tr in result.test_results if tr.test_name == "Test Two"][0]
        assert test_two.duration_seconds == pytest.approx(1.0, abs=0.01)

    def test_total_duration_with_start_end(self, tmp_path):
        """Total duration is the sum of individual test durations."""
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML_WITH_DURATIONS)

        result = parse_output_xml(str(xml_file))

        assert result.total_duration_seconds == pytest.approx(2.0, abs=0.01)

    def test_duration_zero_when_no_start_end(self, tmp_path):
        """When using starttime/endtime (not start/end), durations default to 0."""
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        # The parser reads 'start'/'end' attributes; the sample uses
        # 'starttime'/'endtime', so durations are 0.
        assert result.total_duration_seconds == 0.0


class TestParseTags:
    """Tests for tag extraction."""

    def test_test_with_tag(self, tmp_path):
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        test_one = [tr for tr in result.test_results if tr.test_name == "Test One"][0]
        assert "smoke" in test_one.tags

    def test_test_without_tags(self, tmp_path):
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        test_two = [tr for tr in result.test_results if tr.test_name == "Test Two"][0]
        assert test_two.tags == []


class TestParseSuiteName:
    """Tests for suite name assignment on test results."""

    def test_test_results_have_suite_name(self, tmp_path):
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(SAMPLE_OUTPUT_XML)

        result = parse_output_xml(str(xml_file))

        for tr in result.test_results:
            assert "Test Suite" in tr.suite_name


class TestParseFileNotFound:
    """Tests for error handling when the XML file does not exist."""

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError, match="output.xml not found"):
            parse_output_xml("/nonexistent/path/output.xml")

    def test_file_not_found_includes_path(self):
        bad_path = "/tmp/does_not_exist/output.xml"
        with pytest.raises(FileNotFoundError, match=bad_path):
            parse_output_xml(bad_path)


class TestParseMalformedXml:
    """Tests for malformed XML handling."""

    def test_malformed_xml_raises_parse_error(self, tmp_path):
        from xml.etree.ElementTree import ParseError

        xml_file = tmp_path / "output.xml"
        xml_file.write_text("<robot><not-closed>")

        with pytest.raises(ParseError):
            parse_output_xml(str(xml_file))


class TestParseEmptyRobot:
    """Tests for a valid but empty robot XML (no tests)."""

    def test_empty_suite(self, tmp_path):
        xml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2024-01-01T12:00:00.000000">
  <suite id="s1" name="Empty Suite">
    <status status="PASS" start="2024-01-01T12:00:00.000000" end="2024-01-01T12:00:00.000000"/>
  </suite>
  <statistics>
    <total>
      <stat pass="0" fail="0" skip="0">All Tests</stat>
    </total>
  </statistics>
</robot>
"""
        xml_file = tmp_path / "output.xml"
        xml_file.write_text(xml_content)

        result = parse_output_xml(str(xml_file))

        assert result.total_tests == 0
        assert result.passed_tests == 0
        assert result.failed_tests == 0
        assert result.skipped_tests == 0
        assert result.total_duration_seconds == 0.0
        assert result.test_results == []
