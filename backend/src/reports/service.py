"""Report service: CRUD, comparison."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.reports.models import Report, TestResult
from src.reports.schemas import ReportCompareResponse, ReportResponse


async def get_report(db: AsyncSession, report_id: int) -> Report | None:
    """Get a report by ID."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    return result.scalar_one_or_none()


async def get_report_by_run(db: AsyncSession, run_id: int) -> Report | None:
    """Get a report by execution run ID."""
    result = await db.execute(
        select(Report).where(Report.execution_run_id == run_id)
    )
    return result.scalar_one_or_none()


async def list_reports(
    db: AsyncSession,
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
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    reports = list(result.scalars().all())

    return reports, total


async def get_test_results(db: AsyncSession, report_id: int) -> list[TestResult]:
    """Get all test results for a report."""
    result = await db.execute(
        select(TestResult)
        .where(TestResult.report_id == report_id)
        .order_by(TestResult.suite_name, TestResult.test_name)
    )
    return list(result.scalars().all())


async def compare_reports(db: AsyncSession, report_a_id: int, report_b_id: int) -> ReportCompareResponse:
    """Compare two reports to find differences."""
    report_a = await get_report(db, report_a_id)
    report_b = await get_report(db, report_b_id)

    if report_a is None or report_b is None:
        raise ValueError("One or both reports not found")

    results_a = await get_test_results(db, report_a_id)
    results_b = await get_test_results(db, report_b_id)

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


async def create_report_from_parsed(
    db: AsyncSession,
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
    await db.flush()
    await db.refresh(report)

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

    await db.flush()
    return report
