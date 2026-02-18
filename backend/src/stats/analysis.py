"""Core KPI computation engine for on-demand analysis."""

import json
import logging
import re
from collections import Counter
from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.config import settings

import src.auth.models  # noqa: F401
import src.repos.models  # noqa: F401
import src.execution.models  # noqa: F401

from src.reports.models import Report, TestResult
from src.reports.parser import parse_output_xml_deep
from src.stats.models import AnalysisReport

logger = logging.getLogger("mateox.stats.analysis")

_sync_url = settings.sync_database_url
_sync_engine = create_engine(_sync_url)


def _get_sync_session() -> Session:
    return Session(_sync_engine)


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

            selected = json.loads(analysis.selected_kpis)

            # Query reports matching filters
            query = select(Report)
            if analysis.repository_id:
                from src.execution.models import ExecutionRun
                query = (
                    query.join(ExecutionRun, Report.execution_run_id == ExecutionRun.id)
                    .where(ExecutionRun.repository_id == analysis.repository_id)
                )
            if analysis.date_from:
                query = query.where(Report.created_at >= str(analysis.date_from))
            if analysis.date_to:
                query = query.where(Report.created_at <= str(analysis.date_to))

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

            # Flatten data
            all_keywords = _flatten_keywords(all_suites)
            all_tests = _flatten_tests(all_suites)

            # Also load DB test results for tag_coverage / error_patterns
            if "tag_coverage" in selected or "error_patterns" in selected:
                tr_query = select(TestResult)
                if analysis.repository_id:
                    from src.execution.models import ExecutionRun
                    tr_query = (
                        tr_query.join(Report, TestResult.report_id == Report.id)
                        .join(ExecutionRun, Report.execution_run_id == ExecutionRun.id)
                        .where(ExecutionRun.repository_id == analysis.repository_id)
                    )
                if analysis.date_from:
                    tr_query = tr_query.where(TestResult.start_time >= str(analysis.date_from))
                if analysis.date_to:
                    tr_query = tr_query.where(TestResult.start_time <= str(analysis.date_to))

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
                import asyncio
                from src.websocket.manager import ws_manager
                asyncio.run(ws_manager.broadcast({
                    "type": "analysis_status_changed",
                    "analysis_id": analysis_id,
                    "status": "completed",
                    "progress": 100,
                }))
            except Exception:
                logger.debug("Could not broadcast WS notification for analysis %d", analysis_id)

            logger.info("Analysis %d completed: %d reports, %d KPIs", analysis_id, parsed_count, len(results))

        except Exception as e:
            logger.exception("Analysis %d failed", analysis_id)
            analysis.status = "error"
            analysis.error_message = str(e)[:500]
            analysis.completed_at = datetime.utcnow()
            session.commit()
