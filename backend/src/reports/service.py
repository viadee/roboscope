"""Report service: CRUD, comparison, test history."""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.reports.models import Report, TestResult
from src.reports.schemas import (
    MissingLibrariesResponse,
    MissingLibraryItem,
    ReportCompareResponse,
    ReportResponse,
    TestHistoryPoint,
    TestHistoryResponse,
    UniqueTestResponse,
)


def get_report(db: Session, report_id: int) -> Report | None:
    """Get a report by ID."""
    result = db.execute(select(Report).where(Report.id == report_id))
    return result.scalar_one_or_none()


def get_report_by_run(db: Session, run_id: int) -> Report | None:
    """Get a report by execution run ID."""
    result = db.execute(
        select(Report).where(Report.execution_run_id == run_id)
    )
    return result.scalar_one_or_none()


def list_reports(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    repository_id: int | None = None,
) -> tuple[list[Report], int]:
    """List reports with pagination."""
    query = select(Report).order_by(Report.created_at.desc())

    if repository_id:
        from src.execution.models import ExecutionRun
        query = query.join(ExecutionRun, Report.execution_run_id == ExecutionRun.id).where(
            ExecutionRun.repository_id == repository_id
        )

    count_query = select(func.count()).select_from(query.subquery())
    total_result = db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = db.execute(query)
    reports = list(result.scalars().all())

    return reports, total


def get_test_results(db: Session, report_id: int) -> list[TestResult]:
    """Get all test results for a report."""
    result = db.execute(
        select(TestResult)
        .where(TestResult.report_id == report_id)
        .order_by(TestResult.suite_name, TestResult.test_name)
    )
    return list(result.scalars().all())


def compare_reports(db: Session, report_a_id: int, report_b_id: int) -> ReportCompareResponse:
    """Compare two reports to find differences."""
    report_a = get_report(db, report_a_id)
    report_b = get_report(db, report_b_id)

    if report_a is None or report_b is None:
        raise ValueError("One or both reports not found")

    results_a = get_test_results(db, report_a_id)
    results_b = get_test_results(db, report_b_id)

    # Build test maps: name -> status
    map_a = {r.test_name: r.status for r in results_a}
    map_b = {r.test_name: r.status for r in results_b}

    # Find differences
    new_failures = []
    fixed_tests = []
    consistent_failures = []

    all_tests = set(map_a.keys()) | set(map_b.keys())
    for test_name in sorted(all_tests):
        status_a = map_a.get(test_name)
        status_b = map_b.get(test_name)

        if status_a == "PASS" and status_b == "FAIL":
            new_failures.append(test_name)
        elif status_a == "FAIL" and status_b == "PASS":
            fixed_tests.append(test_name)
        elif status_a == "FAIL" and status_b == "FAIL":
            consistent_failures.append(test_name)

    return ReportCompareResponse(
        report_a=ReportResponse.model_validate(report_a),
        report_b=ReportResponse.model_validate(report_b),
        new_failures=new_failures,
        fixed_tests=fixed_tests,
        consistent_failures=consistent_failures,
        duration_diff_seconds=report_b.total_duration_seconds - report_a.total_duration_seconds,
    )


def create_report_from_parsed(
    db: Session,
    run_id: int,
    output_xml_path: str,
    log_html_path: str | None,
    report_html_path: str | None,
    total_tests: int,
    passed_tests: int,
    failed_tests: int,
    skipped_tests: int,
    total_duration_seconds: float,
    test_results_data: list[dict],
) -> Report:
    """Create a report and its test results from parsed data."""
    report = Report(
        execution_run_id=run_id,
        output_xml_path=output_xml_path,
        log_html_path=log_html_path,
        report_html_path=report_html_path,
        total_tests=total_tests,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        skipped_tests=skipped_tests,
        total_duration_seconds=total_duration_seconds,
    )
    db.add(report)
    db.flush()
    db.refresh(report)

    # Create test results
    for tr_data in test_results_data:
        test_result = TestResult(
            report_id=report.id,
            suite_name=tr_data.get("suite_name", ""),
            test_name=tr_data.get("test_name", ""),
            status=tr_data.get("status", "FAIL"),
            duration_seconds=tr_data.get("duration_seconds", 0.0),
            error_message=tr_data.get("error_message"),
            tags=",".join(tr_data.get("tags", [])) if tr_data.get("tags") else None,
            start_time=tr_data.get("start_time"),
            end_time=tr_data.get("end_time"),
        )
        db.add(test_result)

    db.flush()
    return report


def get_test_history(
    db: Session,
    test_name: str,
    suite_name: str | None = None,
    days: int = 90,
) -> TestHistoryResponse:
    """Get pass/fail history for a specific test across all reports."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(TestResult, Report.created_at)
        .join(Report, TestResult.report_id == Report.id)
        .where(TestResult.test_name == test_name)
        .where(Report.created_at >= cutoff)
        .order_by(Report.created_at.asc())
    )

    if suite_name:
        query = query.where(TestResult.suite_name == suite_name)

    result = db.execute(query)
    rows = list(result.all())

    history = []
    pass_count = 0
    fail_count = 0
    actual_suite = suite_name or ""

    for test_result, report_created_at in rows:
        history.append(
            TestHistoryPoint(
                report_id=test_result.report_id,
                date=report_created_at,
                status=test_result.status,
                duration_seconds=test_result.duration_seconds,
                error_message=test_result.error_message,
            )
        )
        if test_result.status == "PASS":
            pass_count += 1
        elif test_result.status == "FAIL":
            fail_count += 1
        if not actual_suite:
            actual_suite = test_result.suite_name

    total = len(history)
    return TestHistoryResponse(
        test_name=test_name,
        suite_name=actual_suite,
        history=history,
        total_runs=total,
        pass_count=pass_count,
        fail_count=fail_count,
        pass_rate=round((pass_count / total * 100) if total > 0 else 0, 1),
    )


def list_unique_tests(
    db: Session,
    search: str | None = None,
    limit: int = 50,
) -> list[UniqueTestResponse]:
    """List unique test names with their latest status and run count."""
    # Subquery: latest report_id per test_name
    latest_sub = (
        select(
            TestResult.test_name,
            TestResult.suite_name,
            func.max(TestResult.report_id).label("latest_report_id"),
            func.count(TestResult.id).label("run_count"),
        )
        .group_by(TestResult.test_name, TestResult.suite_name)
    )

    if search:
        latest_sub = latest_sub.where(TestResult.test_name.ilike(f"%{search}%"))

    latest_sub = latest_sub.limit(limit).subquery()

    # Join back to get the status from the latest run
    query = (
        select(
            latest_sub.c.test_name,
            latest_sub.c.suite_name,
            latest_sub.c.run_count,
            TestResult.status.label("last_status"),
        )
        .join(
            TestResult,
            (TestResult.test_name == latest_sub.c.test_name)
            & (TestResult.suite_name == latest_sub.c.suite_name)
            & (TestResult.report_id == latest_sub.c.latest_report_id),
        )
        .order_by(latest_sub.c.run_count.desc())
    )

    result = db.execute(query)
    return [
        UniqueTestResponse(
            test_name=row.test_name,
            suite_name=row.suite_name,
            last_status=row.last_status,
            run_count=row.run_count,
        )
        for row in result.all()
    ]


# --- Missing library detection ---

MISSING_LIB_PATTERNS = [
    re.compile(r"Importing (?:test )?library '(\w+)' failed", re.IGNORECASE),
    re.compile(r"No module named '([\w.]+)'", re.IGNORECASE),
]


def detect_missing_libraries(db: Session, report_id: int) -> MissingLibrariesResponse:
    """Detect missing libraries from failed test error messages in a report.

    Extracts library names via regex, maps to PyPI packages, and resolves
    the environment from the associated execution run.
    """
    from src.environments.models import Environment
    from src.execution.models import ExecutionRun
    from src.explorer.library_mapping import BUILTIN_LIBRARIES, resolve_pypi_package

    report = get_report(db, report_id)
    if report is None:
        return MissingLibrariesResponse(libraries=[])

    # Get failed test results
    failed = db.execute(
        select(TestResult)
        .where(TestResult.report_id == report_id, TestResult.status == "FAIL")
    ).scalars().all()

    # Extract library names from error messages
    seen: set[str] = set()
    libraries: list[MissingLibraryItem] = []

    for tr in failed:
        if not tr.error_message:
            continue
        for pattern in MISSING_LIB_PATTERNS:
            for match in pattern.finditer(tr.error_message):
                lib_name = match.group(1)
                # Take the top-level module for dotted imports
                top_module = lib_name.split(".")[0]
                if top_module in seen or top_module in BUILTIN_LIBRARIES:
                    continue
                pypi = resolve_pypi_package(top_module)
                if pypi:
                    seen.add(top_module)
                    libraries.append(MissingLibraryItem(
                        library_name=top_module,
                        pypi_package=pypi,
                    ))

    # Resolve environment from execution run
    env_id: int | None = None
    env_name: str | None = None

    if report.execution_run_id:
        run = db.execute(
            select(ExecutionRun).where(ExecutionRun.id == report.execution_run_id)
        ).scalar_one_or_none()
        if run and run.environment_id:
            env_id = run.environment_id
            env = db.execute(
                select(Environment).where(Environment.id == run.environment_id)
            ).scalar_one_or_none()
            if env:
                env_name = env.name

    return MissingLibrariesResponse(
        environment_id=env_id,
        environment_name=env_name,
        libraries=libraries,
    )
