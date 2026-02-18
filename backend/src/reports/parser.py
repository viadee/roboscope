"""Robot Framework output.xml parser."""

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET


@dataclass
class ParsedTestResult:
    """A single parsed test result."""

    suite_name: str = ""
    test_name: str = ""
    status: str = ""  # PASS, FAIL, SKIP
    duration_seconds: float = 0.0
    error_message: str = ""
    tags: list[str] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""


@dataclass
class ParsedReport:
    """Complete parsed report."""

    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    total_duration_seconds: float = 0.0
    test_results: list[ParsedTestResult] = field(default_factory=list)
    generated: str = ""
    suite_name: str = ""


def parse_output_xml(xml_path: str) -> ParsedReport:
    """Parse a Robot Framework output.xml file into a structured report.

    Args:
        xml_path: Path to the output.xml file.

    Returns:
        ParsedReport with all test results and statistics.

    Raises:
        FileNotFoundError: If the xml file doesn't exist.
        ET.ParseError: If the xml is malformed.
    """
    path = Path(xml_path)
    if not path.exists():
        raise FileNotFoundError(f"output.xml not found: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    report = ParsedReport()

    # Get generation timestamp
    report.generated = root.get("generated", "")

    # Parse all test results recursively from suites
    _parse_suite(root, report, "")

    # Calculate totals
    report.total_tests = len(report.test_results)
    report.passed_tests = sum(1 for t in report.test_results if t.status == "PASS")
    report.failed_tests = sum(1 for t in report.test_results if t.status == "FAIL")
    report.skipped_tests = sum(1 for t in report.test_results if t.status == "SKIP")
    report.total_duration_seconds = sum(t.duration_seconds for t in report.test_results)

    return report


def _parse_suite(element: ET.Element, report: ParsedReport, parent_suite: str) -> None:
    """Recursively parse suites and their test cases."""
    for suite_elem in element.iter("suite"):
        suite_name = suite_elem.get("name", "")
        full_suite_name = f"{parent_suite}.{suite_name}" if parent_suite else suite_name

        if not report.suite_name:
            report.suite_name = suite_name

        for test_elem in suite_elem.findall("test"):
            result = _parse_test(test_elem, full_suite_name)
            report.test_results.append(result)


def _parse_test(test_elem: ET.Element, suite_name: str) -> ParsedTestResult:
    """Parse a single test element."""
    result = ParsedTestResult()
    result.test_name = test_elem.get("name", "")
    result.suite_name = suite_name

    # Status
    status_elem = test_elem.find("status")
    if status_elem is not None:
        result.status = status_elem.get("status", "FAIL")
        result.start_time = status_elem.get("start", "")
        result.end_time = status_elem.get("end", "")

        # Calculate duration from start/end times
        result.duration_seconds = _calc_duration(result.start_time, result.end_time)

        # Error message (text content of status element for failures)
        if result.status == "FAIL" and status_elem.text:
            result.error_message = status_elem.text.strip()

    # Tags
    tags_elem = test_elem.find("tag")
    if tags_elem is not None and tags_elem.text:
        result.tags.append(tags_elem.text)

    # Also check for multiple tags
    for tag_elem in test_elem.findall(".//tag"):
        if tag_elem.text and tag_elem.text not in result.tags:
            result.tags.append(tag_elem.text)

    return result


def parse_output_xml_deep(xml_path: str) -> dict:
    """Parse a Robot Framework output.xml into a deep hierarchical structure.

    Returns nested dict with suites -> tests -> keywords -> messages.
    """
    path = Path(xml_path)
    if not path.exists():
        raise FileNotFoundError(f"output.xml not found: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    generated = root.get("generated", "")

    # Parse the root suite
    root_suite_elem = root.find("suite")
    suites = []
    if root_suite_elem is not None:
        suites = [_parse_suite_deep(root_suite_elem)]

    # Parse statistics
    statistics = _parse_statistics(root)

    return {
        "suites": suites,
        "statistics": statistics,
        "generated": generated,
    }


def _parse_suite_deep(suite_elem: ET.Element) -> dict:
    """Recursively parse a suite element into a nested dict."""
    name = suite_elem.get("name", "")
    source = suite_elem.get("source", "")

    # Suite status
    status_elem = suite_elem.find("status")
    suite_status = "UNKNOWN"
    start_time = ""
    end_time = ""
    if status_elem is not None:
        suite_status = status_elem.get("status", "UNKNOWN")
        start_time = status_elem.get("start", "")
        end_time = status_elem.get("end", "")

    duration = _calc_duration(start_time, end_time)

    # Documentation
    doc_elem = suite_elem.find("doc")
    doc = doc_elem.text.strip() if doc_elem is not None and doc_elem.text else ""

    # Parse direct child suites
    child_suites = []
    for child in suite_elem.findall("suite"):
        child_suites.append(_parse_suite_deep(child))

    # Parse direct child tests
    tests = []
    for test_elem in suite_elem.findall("test"):
        tests.append(_parse_test_deep(test_elem))

    return {
        "name": name,
        "source": source,
        "status": suite_status,
        "start_time": start_time,
        "end_time": end_time,
        "duration": duration,
        "doc": doc,
        "suites": child_suites,
        "tests": tests,
    }


def _parse_test_deep(test_elem: ET.Element) -> dict:
    """Parse a test element including its keywords."""
    name = test_elem.get("name", "")

    # Status
    status_elem = test_elem.find("status")
    test_status = "FAIL"
    start_time = ""
    end_time = ""
    error_message = ""
    if status_elem is not None:
        test_status = status_elem.get("status", "FAIL")
        start_time = status_elem.get("start", "")
        end_time = status_elem.get("end", "")
        if test_status == "FAIL" and status_elem.text:
            error_message = status_elem.text.strip()

    duration = _calc_duration(start_time, end_time)

    # Documentation
    doc_elem = test_elem.find("doc")
    doc = doc_elem.text.strip() if doc_elem is not None and doc_elem.text else ""

    # Tags
    tags = []
    for tag_elem in test_elem.findall(".//tag"):
        if tag_elem.text:
            tags.append(tag_elem.text)

    # Keywords
    keywords = []
    for kw_elem in test_elem.findall("kw"):
        keywords.append(_parse_keyword_deep(kw_elem))

    return {
        "name": name,
        "status": test_status,
        "start_time": start_time,
        "end_time": end_time,
        "duration": duration,
        "doc": doc,
        "tags": tags,
        "error_message": error_message,
        "keywords": keywords,
    }


def _parse_keyword_deep(kw_elem: ET.Element) -> dict:
    """Recursively parse a keyword element."""
    name = kw_elem.get("name", "")
    kw_type = kw_elem.get("type", "kw")
    library = kw_elem.get("library", "")

    # Status
    status_elem = kw_elem.find("status")
    kw_status = "UNKNOWN"
    start_time = ""
    end_time = ""
    if status_elem is not None:
        kw_status = status_elem.get("status", "UNKNOWN")
        start_time = status_elem.get("start", "")
        end_time = status_elem.get("end", "")

    duration = _calc_duration(start_time, end_time)

    # Documentation
    doc_elem = kw_elem.find("doc")
    doc = doc_elem.text.strip() if doc_elem is not None and doc_elem.text else ""

    # Arguments
    arguments = []
    for arg_elem in kw_elem.findall("arg"):
        if arg_elem.text:
            arguments.append(arg_elem.text)

    # Messages
    messages = []
    for msg_elem in kw_elem.findall("msg"):
        messages.append({
            "timestamp": msg_elem.get("timestamp", ""),
            "level": msg_elem.get("level", "INFO"),
            "text": msg_elem.text.strip() if msg_elem.text else "",
        })

    # Nested keywords
    child_keywords = []
    for child_kw in kw_elem.findall("kw"):
        child_keywords.append(_parse_keyword_deep(child_kw))

    return {
        "name": name,
        "type": kw_type,
        "library": library,
        "status": kw_status,
        "start_time": start_time,
        "end_time": end_time,
        "duration": duration,
        "doc": doc,
        "arguments": arguments,
        "messages": messages,
        "keywords": child_keywords,
    }


def _parse_statistics(root: ET.Element) -> dict:
    """Parse the statistics section of output.xml."""
    stats = {"total": {}, "tag": [], "suite": []}
    stat_elem = root.find("statistics")
    if stat_elem is None:
        return stats

    # Total stats
    total_elem = stat_elem.find("total")
    if total_elem is not None:
        for stat in total_elem.findall("stat"):
            name = stat.text.strip() if stat.text else ""
            stats["total"][name] = {
                "pass": int(stat.get("pass", "0")),
                "fail": int(stat.get("fail", "0")),
                "skip": int(stat.get("skip", "0")),
            }

    return stats


def _calc_duration(start: str, end: str) -> float:
    """Calculate duration in seconds from Robot Framework timestamp strings.

    Robot Framework timestamps are like: 20240101 12:00:00.000
    """
    if not start or not end:
        return 0.0

    try:
        from datetime import datetime

        # RF 7+ format: 20240101 12:00:00.000
        fmt = "%Y%m%d %H:%M:%S.%f"
        start_dt = datetime.strptime(start, fmt)
        end_dt = datetime.strptime(end, fmt)
        delta = end_dt - start_dt
        return max(0.0, delta.total_seconds())
    except (ValueError, TypeError):
        try:
            # RF older format or ISO format
            from datetime import datetime

            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            delta = end_dt - start_dt
            return max(0.0, delta.total_seconds())
        except (ValueError, TypeError):
            return 0.0
