"""Core KPI computation engine for on-demand analysis."""

import asyncio
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import date, datetime, time
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.config import settings

import src.auth.models  # noqa: F401
import src.repos.models  # noqa: F401
import src.execution.models  # noqa: F401

from src.execution.models import ExecutionRun
from src.reports.models import Report, TestResult
from src.reports.parser import parse_output_xml_deep
from src.stats.keyword_library_map import resolve_keyword_library
from src.stats.models import AnalysisReport

logger = logging.getLogger("roboscope.stats.analysis")

_sync_url = settings.sync_database_url
_sync_engine = create_engine(_sync_url)


def _get_sync_session() -> Session:
    return Session(_sync_engine)


def _broadcast_analysis_status(analysis_id: int, status: str, progress: int = 0) -> None:
    """Broadcast analysis status change from a sync background thread."""
    from src.websocket.manager import ws_manager
    from src.main import _event_loop

    coro = ws_manager.broadcast({
        "type": "analysis_status_changed",
        "analysis_id": analysis_id,
        "status": status,
        "progress": progress,
    })

    if _event_loop and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, _event_loop)
    else:
        logger.warning("No event loop available to broadcast analysis %d status", analysis_id)


# --- Helpers ---


def _flatten_keywords(suites: list[dict]) -> list[dict]:
    """Recursively extract all keyword calls from parsed suites."""
    keywords: list[dict] = []

    def _walk_keywords(kw_list: list[dict]) -> None:
        for kw in kw_list:
            keywords.append({
                "name": kw.get("name", ""),
                "library": kw.get("library", ""),
                "type": kw.get("type", "kw"),
                "duration": kw.get("duration", 0.0),
                "status": kw.get("status", ""),
            })
            _walk_keywords(kw.get("keywords", []))

    def _walk_suites(suite_list: list[dict]) -> None:
        for suite in suite_list:
            for test in suite.get("tests", []):
                _walk_keywords(test.get("keywords", []))
            _walk_suites(suite.get("suites", []))

    _walk_suites(suites)
    return keywords


def _flatten_tests(suites: list[dict]) -> list[dict]:
    """Extract all tests with their keyword lists from parsed suites."""
    tests: list[dict] = []

    def _walk_suites(suite_list: list[dict], parent_suite: str = "") -> None:
        for suite in suite_list:
            suite_name = suite.get("name", "")
            full_name = f"{parent_suite}.{suite_name}" if parent_suite else suite_name
            for test in suite.get("tests", []):
                tests.append({
                    "name": test.get("name", ""),
                    "suite": full_name,
                    "status": test.get("status", ""),
                    "duration": test.get("duration", 0.0),
                    "tags": test.get("tags", []),
                    "error_message": test.get("error_message", ""),
                    "keywords": test.get("keywords", []),
                })
            _walk_suites(suite.get("suites", []), full_name)

    _walk_suites(suites)
    return tests


def _get_kw_names(kw_list: list[dict]) -> list[str]:
    """Get flat list of keyword names (top-level only) from a test's keywords."""
    return [kw.get("name", "") for kw in kw_list if kw.get("type", "kw") == "kw"]


# --- Keyword Library Enrichment ---


def _enrich_keyword_libraries(keywords: list[dict]) -> None:
    """Fill empty library fields using the keyword-to-library mapping.

    Modifies keywords in-place.  Keywords whose library remains unresolved
    after the mapping lookup are labelled "User Keywords".
    """
    for kw in keywords:
        if kw.get("library"):
            continue
        resolved = resolve_keyword_library(kw.get("name", ""))
        if resolved:
            kw["library"] = resolved
        else:
            # setup/teardown are BuiltIn constructs
            kw_type = kw.get("type", "kw")
            if kw_type in ("setup", "teardown"):
                kw["library"] = "BuiltIn"


# --- KPI Compute Functions ---


def compute_keyword_frequency(keywords: list[dict]) -> dict:
    """Top used keywords ranked by call count."""
    counter: Counter = Counter()
    lib_map: dict[str, str] = {}
    for kw in keywords:
        name = kw["name"]
        counter[name] += 1
        if name not in lib_map and kw["library"]:
            lib_map[name] = kw["library"]

    total = sum(counter.values()) or 1
    top = counter.most_common(50)
    return {
        "total_calls": sum(counter.values()),
        "unique_keywords": len(counter),
        "top_keywords": [
            {
                "name": name,
                "library": lib_map.get(name, ""),
                "count": count,
                "percentage": round(count / total * 100, 1),
            }
            for name, count in top
        ],
    }


def compute_keyword_duration_impact(keywords: list[dict]) -> dict:
    """Keywords ranked by cumulative time consumed."""
    duration_map: dict[str, float] = {}
    count_map: Counter = Counter()
    lib_map: dict[str, str] = {}

    for kw in keywords:
        name = kw["name"]
        duration_map[name] = duration_map.get(name, 0.0) + kw["duration"]
        count_map[name] += 1
        if name not in lib_map and kw["library"]:
            lib_map[name] = kw["library"]

    sorted_kws = sorted(duration_map.items(), key=lambda x: x[1], reverse=True)[:30]
    return {
        "top_by_duration": [
            {
                "name": name,
                "library": lib_map.get(name, ""),
                "total_duration": round(dur, 2),
                "avg_duration": round(dur / count_map[name], 2) if count_map[name] else 0,
                "calls": count_map[name],
            }
            for name, dur in sorted_kws
        ],
    }


def compute_library_distribution(keywords: list[dict]) -> dict:
    """Keyword calls distributed across libraries."""
    lib_count: Counter = Counter()
    lib_duration: dict[str, float] = {}

    for kw in keywords:
        lib = kw["library"] or "Unknown"
        lib_count[lib] += 1
        lib_duration[lib] = lib_duration.get(lib, 0.0) + kw["duration"]

    total = sum(lib_count.values()) or 1
    return {
        "libraries": [
            {
                "library": lib,
                "count": count,
                "percentage": round(count / total * 100, 1),
                "total_duration": round(lib_duration.get(lib, 0.0), 2),
            }
            for lib, count in lib_count.most_common()
        ],
    }


def compute_test_complexity(tests: list[dict]) -> dict:
    """Steps per test case: avg/min/max + histogram distribution."""
    if not tests:
        return {"avg": 0, "min": 0, "max": 0, "histogram": [], "tests": []}

    complexities = []
    for test in tests:
        kw_count = len(_get_kw_names(test["keywords"]))
        complexities.append({"name": test["name"], "suite": test["suite"], "steps": kw_count})

    steps = [c["steps"] for c in complexities]
    avg_steps = sum(steps) / len(steps) if steps else 0

    # Histogram buckets: 0-5, 6-10, 11-20, 21-50, 50+
    buckets = {"0-5": 0, "6-10": 0, "11-20": 0, "21-50": 0, "50+": 0}
    for s in steps:
        if s <= 5:
            buckets["0-5"] += 1
        elif s <= 10:
            buckets["6-10"] += 1
        elif s <= 20:
            buckets["11-20"] += 1
        elif s <= 50:
            buckets["21-50"] += 1
        else:
            buckets["50+"] += 1

    complexities.sort(key=lambda c: c["steps"], reverse=True)
    return {
        "avg": round(avg_steps, 1),
        "min": min(steps),
        "max": max(steps),
        "histogram": [{"bucket": k, "count": v} for k, v in buckets.items()],
        "tests": complexities[:30],
    }


def compute_assertion_density(tests: list[dict]) -> dict:
    """Ratio of assertion keywords to total per test."""
    assertion_pattern = re.compile(r"^(should|verify|must)\b", re.IGNORECASE)
    results = []

    for test in tests:
        kw_names = _get_kw_names(test["keywords"])
        total = len(kw_names) or 1
        assertions = sum(1 for name in kw_names if assertion_pattern.search(name))
        results.append({
            "name": test["name"],
            "suite": test["suite"],
            "total_keywords": len(kw_names),
            "assertion_count": assertions,
            "density": round(assertions / total * 100, 1),
        })

    avg_density = (
        sum(r["density"] for r in results) / len(results) if results else 0
    )
    no_assertions = [r for r in results if r["assertion_count"] == 0]
    results.sort(key=lambda r: r["density"])

    return {
        "avg_density": round(avg_density, 1),
        "tests_without_assertions": len(no_assertions),
        "total_tests": len(results),
        "tests": results[:30],
        "no_assertion_tests": no_assertions[:20],
    }


def compute_tag_coverage(tests: list[dict]) -> dict:
    """Tag distribution, untagged test count, avg tags per test."""
    tag_counter: Counter = Counter()
    untagged = 0
    total_tags = 0

    for test in tests:
        tags = test.get("tags", [])
        if not tags:
            untagged += 1
        total_tags += len(tags)
        for tag in tags:
            tag_counter[tag] += 1

    avg_tags = total_tags / len(tests) if tests else 0
    return {
        "total_tests": len(tests),
        "untagged_count": untagged,
        "avg_tags_per_test": round(avg_tags, 1),
        "tags": [
            {"tag": tag, "count": count}
            for tag, count in tag_counter.most_common(50)
        ],
    }


def compute_error_patterns(tests: list[dict]) -> dict:
    """Cluster similar error messages by frequency."""
    error_map: dict[str, list[str]] = {}

    for test in tests:
        msg = test.get("error_message", "")
        if not msg:
            continue
        # Simplify error message: strip file paths, line numbers, timestamps
        simplified = re.sub(r"[A-Za-z]:\\[^\s]+|/[^\s]+", "<path>", msg)
        simplified = re.sub(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\S*", "<ts>", simplified)
        simplified = re.sub(r"\b\d+\b", "<N>", simplified)
        simplified = simplified.strip()[:200]

        if simplified not in error_map:
            error_map[simplified] = []
        error_map[simplified].append(test["name"])

    patterns = sorted(error_map.items(), key=lambda x: len(x[1]), reverse=True)
    return {
        "total_errors": sum(len(v) for v in error_map.values()),
        "unique_patterns": len(error_map),
        "patterns": [
            {
                "pattern": pattern,
                "count": len(test_names),
                "example_tests": test_names[:5],
            }
            for pattern, test_names in patterns[:20]
        ],
    }


def compute_redundancy_detection(tests: list[dict]) -> dict:
    """Detect repeated keyword sequences (3-grams) across multiple tests."""
    ngram_tests: dict[tuple, list[str]] = {}
    n = 3

    for test in tests:
        kw_names = _get_kw_names(test["keywords"])
        if len(kw_names) < n:
            continue
        seen_in_test: set[tuple] = set()
        for i in range(len(kw_names) - n + 1):
            gram = tuple(kw_names[i:i + n])
            if gram not in seen_in_test:
                seen_in_test.add(gram)
                if gram not in ngram_tests:
                    ngram_tests[gram] = []
                ngram_tests[gram].append(test["name"])

    # Only keep sequences appearing in 2+ different tests
    shared = {
        gram: test_names
        for gram, test_names in ngram_tests.items()
        if len(set(test_names)) >= 2
    }

    sorted_shared = sorted(shared.items(), key=lambda x: len(x[1]), reverse=True)
    return {
        "total_shared_sequences": len(shared),
        "sequences": [
            {
                "keywords": list(gram),
                "occurrence_count": len(test_names),
                "unique_tests": len(set(test_names)),
                "tests": list(set(test_names))[:10],
            }
            for gram, test_names in sorted_shared[:20]
        ],
    }


# --- Source Analysis (parse .robot files directly) ---

# Directories to skip when scanning source files
_IGNORE_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".tox", ".pytest_cache", ".mypy_cache"}


def _parse_source_tests(base_path: str) -> list[dict]:
    """Parse .robot source files and extract test cases with their keyword steps.

    Returns list of dicts:
      { name, file, suite, lines, steps: [str], tags: [str], doc: str }
    """
    base = Path(base_path)
    if not base.exists() or not base.is_dir():
        return []

    tests: list[dict] = []

    for robot_file in base.rglob("*.robot"):
        if any(part in _IGNORE_DIRS for part in robot_file.parts):
            continue

        rel_path = str(robot_file.relative_to(base))
        suite_name = robot_file.stem

        try:
            content = robot_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        lines = content.splitlines()
        in_test_section = False
        current_test: dict | None = None

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            if stripped.lower().startswith("*** test case"):
                in_test_section = True
                if current_test:
                    current_test["line_end"] = i - 1
                    current_test["lines"] = current_test["line_end"] - current_test["line_start"] + 1
                    tests.append(current_test)
                    current_test = None
                continue

            if stripped.startswith("***"):
                if current_test:
                    current_test["line_end"] = i - 1
                    current_test["lines"] = current_test["line_end"] - current_test["line_start"] + 1
                    tests.append(current_test)
                    current_test = None
                in_test_section = False
                continue

            if not in_test_section:
                continue

            # New test case (non-indented, non-empty, non-comment)
            if stripped and not line.startswith((" ", "\t")) and not stripped.startswith("#"):
                if current_test:
                    current_test["line_end"] = i - 1
                    current_test["lines"] = current_test["line_end"] - current_test["line_start"] + 1
                    tests.append(current_test)
                current_test = {
                    "name": stripped,
                    "file": rel_path,
                    "suite": suite_name,
                    "line_start": i,
                    "line_end": i,
                    "lines": 0,
                    "steps": [],
                    "tags": [],
                    "doc": "",
                }
            elif current_test and stripped:
                # Indented line inside test case
                if stripped.startswith("#"):
                    continue
                if stripped.lower().startswith("[tags]"):
                    tags_str = stripped[6:].strip()
                    current_test["tags"] = [t.strip() for t in re.split(r"  +|\t+", tags_str) if t.strip()]
                elif stripped.lower().startswith("[documentation]"):
                    current_test["doc"] = stripped[15:].strip()
                elif stripped.lower().startswith("["):
                    # Other settings like [Setup], [Teardown], [Template], [Timeout]
                    pass
                else:
                    # Keyword step — extract the keyword name (first cell)
                    parts = re.split(r"  +|\t+", stripped)
                    if parts:
                        current_test["steps"].append(parts[0])

        # End of file
        if current_test:
            current_test["line_end"] = len(lines)
            current_test["lines"] = current_test["line_end"] - current_test["line_start"] + 1
            tests.append(current_test)

    return tests


def _parse_source_libraries(base_path: str) -> list[dict]:
    """Extract Library imports from .robot/.resource files.

    Returns list of dicts: { library_name, files: [str] }
    """
    base = Path(base_path)
    if not base.exists() or not base.is_dir():
        return []

    lib_map: dict[str, set[str]] = {}

    for file_path in base.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in {".robot", ".resource"}:
            continue
        if any(part in _IGNORE_DIRS for part in file_path.parts):
            continue

        rel_path = str(file_path.relative_to(base))

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            in_settings = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.lower().startswith("*** setting"):
                    in_settings = True
                    continue
                if stripped.startswith("***"):
                    in_settings = False
                    continue
                if not in_settings or not stripped or stripped.startswith("#"):
                    continue
                parts = re.split(r"  +|\t+", stripped)
                if parts and parts[0].lower() == "library" and len(parts) > 1:
                    lib_name = parts[1].strip()
                    if lib_name:
                        if lib_name not in lib_map:
                            lib_map[lib_name] = set()
                        lib_map[lib_name].add(rel_path)
        except Exception:
            continue

    return [
        {"library_name": name, "files": sorted(files)}
        for name, files in sorted(lib_map.items())
    ]


def compute_source_test_stats(base_path: str) -> dict:
    """Analyse .robot source files for test case metrics.

    Returns: total_files, total_tests, avg/min/max lines and steps,
    step_histogram, top_keywords, per-file summary.
    """
    tests = _parse_source_tests(base_path)

    if not tests:
        return {
            "total_files": 0, "total_tests": 0,
            "avg_lines": 0, "min_lines": 0, "max_lines": 0,
            "avg_steps": 0, "min_steps": 0, "max_steps": 0,
            "step_histogram": [], "top_keywords": [], "files": [],
        }

    files_set = {t["file"] for t in tests}
    all_lines = [t["lines"] for t in tests]
    all_steps = [len(t["steps"]) for t in tests]

    # Step histogram: same buckets as test_complexity
    buckets = {"0-5": 0, "6-10": 0, "11-20": 0, "21-50": 0, "50+": 0}
    for s in all_steps:
        if s <= 5:
            buckets["0-5"] += 1
        elif s <= 10:
            buckets["6-10"] += 1
        elif s <= 20:
            buckets["11-20"] += 1
        elif s <= 50:
            buckets["21-50"] += 1
        else:
            buckets["50+"] += 1

    # Top keywords across all tests
    kw_counter: Counter = Counter()
    for t in tests:
        for step in t["steps"]:
            kw_counter[step] += 1

    top_kws = kw_counter.most_common(30)
    total_kw_calls = sum(kw_counter.values())

    # Per-file summary
    file_summary: dict[str, dict] = {}
    for t in tests:
        f = t["file"]
        if f not in file_summary:
            file_summary[f] = {"path": f, "test_count": 0, "total_steps": 0}
        file_summary[f]["test_count"] += 1
        file_summary[f]["total_steps"] += len(t["steps"])

    file_list = sorted(file_summary.values(), key=lambda x: x["test_count"], reverse=True)
    for f in file_list:
        f["avg_steps"] = round(f["total_steps"] / f["test_count"], 1) if f["test_count"] else 0

    return {
        "total_files": len(files_set),
        "total_tests": len(tests),
        "avg_lines": round(sum(all_lines) / len(all_lines), 1) if all_lines else 0,
        "min_lines": min(all_lines) if all_lines else 0,
        "max_lines": max(all_lines) if all_lines else 0,
        "avg_steps": round(sum(all_steps) / len(all_steps), 1) if all_steps else 0,
        "min_steps": min(all_steps) if all_steps else 0,
        "max_steps": max(all_steps) if all_steps else 0,
        "step_histogram": [{"bucket": k, "count": v} for k, v in buckets.items()],
        "top_keywords": [
            {
                "name": name,
                "count": count,
                "percentage": round(count / total_kw_calls * 100, 1) if total_kw_calls else 0,
                "library": resolve_keyword_library(name),
            }
            for name, count in top_kws
        ],
        "files": file_list[:30],
    }


def compute_source_library_distribution(base_path: str) -> dict:
    """Library import distribution from .robot/.resource source files."""
    libraries = _parse_source_libraries(base_path)

    if not libraries:
        return {"total_libraries": 0, "libraries": []}

    total_files_with_imports = len({f for lib in libraries for f in lib["files"]})

    return {
        "total_libraries": len(libraries),
        "libraries": [
            {
                "library": lib["library_name"],
                "file_count": len(lib["files"]),
                "percentage": round(len(lib["files"]) / total_files_with_imports * 100, 1)
                if total_files_with_imports else 0,
                "files": lib["files"][:10],
            }
            for lib in sorted(libraries, key=lambda x: len(x["files"]), reverse=True)
        ],
    }


# --- Execution KPI Compute Functions ---


def _build_execution_query(
    session: Session,
    repo_id: int | None,
    dt_from: datetime | None,
    dt_to: datetime | None,
):
    """Build base query for TestResult with optional filters."""
    query = select(TestResult)
    if repo_id:
        query = (
            query.join(Report, TestResult.report_id == Report.id)
            .join(ExecutionRun, Report.execution_run_id == ExecutionRun.id)
            .where(ExecutionRun.repository_id == repo_id)
        )
    if dt_from:
        query = query.where(TestResult.start_time >= str(dt_from))
    if dt_to:
        query = query.where(TestResult.start_time <= str(dt_to))
    return query


def compute_test_pass_rate_trend(
    session: Session,
    repo_id: int | None,
    dt_from: datetime | None,
    dt_to: datetime | None,
) -> dict:
    """Pass/fail rate per test across runs. Shows which tests are consistently failing."""
    query = _build_execution_query(session, repo_id, dt_from, dt_to)
    results = session.execute(query).scalars().all()

    test_stats: dict[str, dict] = {}
    for tr in results:
        key = tr.test_name
        if key not in test_stats:
            test_stats[key] = {
                "test_name": tr.test_name,
                "suite_name": tr.suite_name,
                "pass_count": 0,
                "fail_count": 0,
                "skip_count": 0,
                "total_count": 0,
            }
        test_stats[key]["total_count"] += 1
        if tr.status == "PASS":
            test_stats[key]["pass_count"] += 1
        elif tr.status == "FAIL":
            test_stats[key]["fail_count"] += 1
        else:
            test_stats[key]["skip_count"] += 1

    # Sort by worst pass rate (lowest first)
    tests = sorted(
        test_stats.values(),
        key=lambda t: t["pass_count"] / max(t["total_count"], 1),
    )

    for t in tests:
        total = max(t["total_count"], 1)
        t["pass_rate"] = round(t["pass_count"] / total * 100, 1)

    return {
        "total_tests": len(tests),
        "tests": tests[:50],
    }


def compute_slowest_tests(
    session: Session,
    repo_id: int | None,
    dt_from: datetime | None,
    dt_to: datetime | None,
) -> dict:
    """Top 20 slowest tests by average duration with min/max range."""
    query = _build_execution_query(session, repo_id, dt_from, dt_to)
    results = session.execute(query).scalars().all()

    duration_map: dict[str, list[float]] = {}
    suite_map: dict[str, str] = {}
    for tr in results:
        if tr.duration_seconds is None:
            continue
        key = tr.test_name
        if key not in duration_map:
            duration_map[key] = []
            suite_map[key] = tr.suite_name
        duration_map[key].append(tr.duration_seconds)

    tests = []
    for name, durations in duration_map.items():
        avg_d = sum(durations) / len(durations)
        tests.append({
            "test_name": name,
            "suite_name": suite_map[name],
            "avg_duration": round(avg_d, 2),
            "min_duration": round(min(durations), 2),
            "max_duration": round(max(durations), 2),
            "run_count": len(durations),
        })

    tests.sort(key=lambda t: t["avg_duration"], reverse=True)
    return {
        "total_tests": len(tests),
        "tests": tests[:20],
    }


def compute_flakiness_score(
    session: Session,
    repo_id: int | None,
    dt_from: datetime | None,
    dt_to: datetime | None,
) -> dict:
    """Tests that flip between PASS and FAIL, ranked by flakiness score."""
    query = _build_execution_query(session, repo_id, dt_from, dt_to)
    results = session.execute(query).scalars().all()

    # Group results by test name, ordered by start_time
    test_runs: dict[str, list[dict]] = defaultdict(list)
    suite_map: dict[str, str] = {}
    for tr in results:
        test_runs[tr.test_name].append({
            "status": tr.status,
            "start_time": tr.start_time or "",
        })
        suite_map[tr.test_name] = tr.suite_name

    tests = []
    for name, runs in test_runs.items():
        if len(runs) < 2:
            continue
        # Sort by start_time
        runs.sort(key=lambda r: r["start_time"])
        statuses = [r["status"] for r in runs]

        # Count transitions (PASS→FAIL or FAIL→PASS)
        transitions = 0
        for i in range(1, len(statuses)):
            prev, curr = statuses[i - 1], statuses[i]
            if (prev == "PASS" and curr == "FAIL") or (prev == "FAIL" and curr == "PASS"):
                transitions += 1

        score = round(transitions / (len(runs) - 1), 3) if len(runs) > 1 else 0.0

        # Build status timeline (last 20 runs)
        timeline = [
            {"status": r["status"]} for r in runs[-20:]
        ]

        tests.append({
            "test_name": name,
            "suite_name": suite_map.get(name, ""),
            "total_runs": len(runs),
            "transitions": transitions,
            "flakiness_score": score,
            "timeline": timeline,
        })

    tests.sort(key=lambda t: t["flakiness_score"], reverse=True)
    return {
        "total_tests": len(tests),
        "tests": [t for t in tests[:30] if t["flakiness_score"] > 0],
    }


def compute_failure_heatmap(
    session: Session,
    repo_id: int | None,
    dt_from: datetime | None,
    dt_to: datetime | None,
) -> dict:
    """Matrix of tests x dates showing pass/fail status per day."""
    # Get test results joined with execution run for dates
    base_query = (
        select(
            TestResult.test_name,
            TestResult.status,
            ExecutionRun.created_at,
        )
        .join(Report, TestResult.report_id == Report.id)
        .join(ExecutionRun, Report.execution_run_id == ExecutionRun.id)
    )
    if repo_id:
        base_query = base_query.where(ExecutionRun.repository_id == repo_id)
    if dt_from:
        base_query = base_query.where(ExecutionRun.created_at >= dt_from)
    if dt_to:
        base_query = base_query.where(ExecutionRun.created_at <= dt_to)

    rows = session.execute(base_query).all()

    # Group by (test_name, date)
    cell_data: dict[tuple[str, str], dict] = {}
    test_fail_counts: Counter = Counter()

    for row in rows:
        run_date = row.created_at
        if hasattr(run_date, "date"):
            day_str = run_date.date().isoformat()
        else:
            day_str = str(run_date)[:10]

        key = (row.test_name, day_str)
        if key not in cell_data:
            cell_data[key] = {"status": row.status}
        elif row.status == "FAIL":
            cell_data[key]["status"] = "FAIL"

        if row.status == "FAIL":
            test_fail_counts[row.test_name] += 1

    # Pick top-N most-failing tests
    top_tests = [name for name, _ in test_fail_counts.most_common(20)]

    # Collect unique dates
    all_dates = sorted({k[1] for k in cell_data.keys()})

    # Build matrix
    matrix = []
    for test_name in top_tests:
        row_cells = []
        for d in all_dates:
            key = (test_name, d)
            if key in cell_data:
                row_cells.append({"date": d, "status": cell_data[key]["status"]})
            else:
                row_cells.append({"date": d, "status": "NONE"})
        matrix.append({
            "test_name": test_name,
            "cells": row_cells,
        })

    return {
        "dates": all_dates,
        "tests": matrix,
    }


def compute_suite_duration_treemap(
    session: Session,
    repo_id: int | None,
    dt_from: datetime | None,
    dt_to: datetime | None,
) -> dict:
    """Duration breakdown by test suite — which suites consume the most execution time."""
    query = _build_execution_query(session, repo_id, dt_from, dt_to)
    results = session.execute(query).scalars().all()

    suite_data: dict[str, dict] = {}
    for tr in results:
        suite = tr.suite_name or "Unknown"
        if suite not in suite_data:
            suite_data[suite] = {"suite_name": suite, "total_duration": 0.0, "test_count": 0}
        suite_data[suite]["total_duration"] += tr.duration_seconds or 0.0
        suite_data[suite]["test_count"] += 1

    suites = sorted(suite_data.values(), key=lambda s: s["total_duration"], reverse=True)
    total = sum(s["total_duration"] for s in suites) or 1.0

    for s in suites:
        s["total_duration"] = round(s["total_duration"], 2)
        s["percentage"] = round(s["total_duration"] / total * 100, 1)

    return {
        "total_duration": round(total, 2),
        "suites": suites[:30],
    }


# --- Orchestrator ---


def run_analysis(analysis_id: int) -> None:
    """Run analysis computation in background thread."""
    with _get_sync_session() as session:
        analysis = session.get(AnalysisReport, analysis_id)
        if not analysis:
            logger.error("Analysis %d not found", analysis_id)
            return

        try:
            analysis.status = "running"
            analysis.started_at = datetime.utcnow()
            analysis.progress = 0
            session.commit()

            try:
                _broadcast_analysis_status(analysis_id, "running", 0)
            except Exception:
                logger.debug("Could not broadcast running status for analysis %d", analysis_id)

            selected = json.loads(analysis.selected_kpis)

            # Convert date filters to proper datetime objects
            dt_from = (
                datetime.combine(analysis.date_from, time.min)
                if analysis.date_from else None
            )
            dt_to = (
                datetime.combine(analysis.date_to, time.max)
                if analysis.date_to else None
            )

            # Query reports matching filters
            query = select(Report)
            if analysis.repository_id:
                query = (
                    query.join(ExecutionRun, Report.execution_run_id == ExecutionRun.id)
                    .where(ExecutionRun.repository_id == analysis.repository_id)
                )
            if dt_from:
                query = query.where(Report.created_at >= dt_from)
            if dt_to:
                query = query.where(Report.created_at <= dt_to)

            reports = session.execute(query).scalars().all()
            total_reports = len(reports)

            all_suites: list[dict] = []
            parsed_count = 0

            for i, report in enumerate(reports):
                try:
                    if report.output_xml_path:
                        deep = parse_output_xml_deep(report.output_xml_path)
                        all_suites.extend(deep.get("suites", []))
                        parsed_count += 1
                except Exception as e:
                    logger.warning(
                        "Skipping report %d (%s): %s",
                        report.id, report.output_xml_path, e,
                    )

                analysis.progress = int((i + 1) / max(total_reports, 1) * 80)
                analysis.reports_analyzed = parsed_count
                session.commit()

            # Flatten data and enrich library info
            all_keywords = _flatten_keywords(all_suites)
            _enrich_keyword_libraries(all_keywords)
            all_tests = _flatten_tests(all_suites)

            # Also load DB test results for tag_coverage / error_patterns
            # Determine which KPIs need DB test results
            needs_db_results = {"tag_coverage", "error_patterns",
                                "test_pass_rate_trend", "slowest_tests",
                                "flakiness_score", "failure_heatmap",
                                "suite_duration_treemap"}
            if needs_db_results & set(selected):
                tr_query = select(TestResult)
                if analysis.repository_id:
                    tr_query = (
                        tr_query.join(Report, TestResult.report_id == Report.id)
                        .join(ExecutionRun, Report.execution_run_id == ExecutionRun.id)
                        .where(ExecutionRun.repository_id == analysis.repository_id)
                    )
                if dt_from:
                    tr_query = tr_query.where(TestResult.start_time >= str(dt_from))
                if dt_to:
                    tr_query = tr_query.where(TestResult.start_time <= str(dt_to))

                db_results = session.execute(tr_query).scalars().all()

                # Supplement XML tests with DB data for missing tags/errors
                if not all_tests and db_results:
                    for tr in db_results:
                        all_tests.append({
                            "name": tr.test_name,
                            "suite": tr.suite_name,
                            "status": tr.status,
                            "duration": tr.duration_seconds,
                            "tags": tr.tags.split(",") if tr.tags else [],
                            "error_message": tr.error_message or "",
                            "keywords": [],
                        })

            analysis.progress = 85
            session.commit()

            # Resolve repo local_path for source analysis KPIs
            repo_local_path: str | None = None
            if analysis.repository_id:
                from src.repos.models import Repository
                repo = session.get(Repository, analysis.repository_id)
                if repo and repo.local_path:
                    repo_local_path = repo.local_path

            # Compute selected KPIs
            compute_map = {
                "keyword_frequency": lambda: compute_keyword_frequency(all_keywords),
                "keyword_duration_impact": lambda: compute_keyword_duration_impact(all_keywords),
                "library_distribution": lambda: compute_library_distribution(all_keywords),
                "test_complexity": lambda: compute_test_complexity(all_tests),
                "assertion_density": lambda: compute_assertion_density(all_tests),
                "tag_coverage": lambda: compute_tag_coverage(all_tests),
                "error_patterns": lambda: compute_error_patterns(all_tests),
                "redundancy_detection": lambda: compute_redundancy_detection(all_tests),
            }

            # Execution KPIs (query DB test results directly)
            compute_map["test_pass_rate_trend"] = lambda: compute_test_pass_rate_trend(
                session, analysis.repository_id, dt_from, dt_to,
            )
            compute_map["slowest_tests"] = lambda: compute_slowest_tests(
                session, analysis.repository_id, dt_from, dt_to,
            )
            compute_map["flakiness_score"] = lambda: compute_flakiness_score(
                session, analysis.repository_id, dt_from, dt_to,
            )
            compute_map["failure_heatmap"] = lambda: compute_failure_heatmap(
                session, analysis.repository_id, dt_from, dt_to,
            )
            compute_map["suite_duration_treemap"] = lambda: compute_suite_duration_treemap(
                session, analysis.repository_id, dt_from, dt_to,
            )

            # Source analysis KPIs (require repo with local_path)
            if repo_local_path:
                _path = repo_local_path  # capture for lambda
                compute_map["source_test_stats"] = lambda p=_path: compute_source_test_stats(p)
                compute_map["source_library_distribution"] = (
                    lambda p=_path: compute_source_library_distribution(p)
                )

            results = {}
            for kpi_id in selected:
                if kpi_id in compute_map:
                    try:
                        results[kpi_id] = compute_map[kpi_id]()
                    except Exception as e:
                        logger.exception("Error computing KPI %s", kpi_id)
                        results[kpi_id] = {"error": str(e)}

            analysis.progress = 100
            analysis.results = json.dumps(results)
            analysis.status = "completed"
            analysis.completed_at = datetime.utcnow()
            session.commit()

            # Broadcast WebSocket notification
            try:
                _broadcast_analysis_status(analysis_id, "completed", 100)
            except Exception:
                logger.debug("Could not broadcast WS notification for analysis %d", analysis_id)

            logger.info("Analysis %d completed: %d reports, %d KPIs", analysis_id, parsed_count, len(results))

        except Exception as e:
            logger.exception("Analysis %d failed", analysis_id)
            analysis.status = "error"
            analysis.error_message = str(e)[:500]
            analysis.completed_at = datetime.utcnow()
            session.commit()
