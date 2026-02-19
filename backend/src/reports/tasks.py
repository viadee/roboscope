"""Background tasks for report parsing."""

import logging
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.config import settings

import src.auth.models  # noqa: F401
import src.repos.models  # noqa: F401
import src.execution.models  # noqa: F401

from src.reports.models import Report, TestResult
from src.reports.parser import parse_output_xml

logger = logging.getLogger("roboscope.reports.tasks")

_sync_url = settings.sync_database_url
_sync_engine = create_engine(_sync_url)


def _get_sync_session() -> Session:
    return Session(_sync_engine)


def parse_report(run_id: int, output_xml_path: str) -> dict:
    """Parse a Robot Framework output.xml and store as a report."""
    with _get_sync_session() as session:
        # Check if report already exists
        existing = session.execute(
            select(Report).where(Report.execution_run_id == run_id)
        ).scalar_one_or_none()

        if existing:
            return {"status": "skipped", "message": "Report already exists"}

        try:
            parsed = parse_output_xml(output_xml_path)

            # Determine paths for log.html and report.html
            output_dir = str(Path(output_xml_path).parent)
            log_html = str(Path(output_dir) / "log.html")
            report_html = str(Path(output_dir) / "report.html")

            report = Report(
                execution_run_id=run_id,
                output_xml_path=output_xml_path,
                log_html_path=log_html if Path(log_html).exists() else None,
                report_html_path=report_html if Path(report_html).exists() else None,
                total_tests=parsed.total_tests,
                passed_tests=parsed.passed_tests,
                failed_tests=parsed.failed_tests,
                skipped_tests=parsed.skipped_tests,
                total_duration_seconds=parsed.total_duration_seconds,
            )
            session.add(report)
            session.flush()

            # Store individual test results
            for tr in parsed.test_results:
                test_result = TestResult(
                    report_id=report.id,
                    suite_name=tr.suite_name,
                    test_name=tr.test_name,
                    status=tr.status,
                    duration_seconds=tr.duration_seconds,
                    error_message=tr.error_message or None,
                    tags=",".join(tr.tags) if tr.tags else None,
                    start_time=tr.start_time or None,
                    end_time=tr.end_time or None,
                )
                session.add(test_result)

            session.commit()

            logger.info(
                "Report parsed for run %d: %d tests (%d passed, %d failed)",
                run_id, parsed.total_tests, parsed.passed_tests, parsed.failed_tests,
            )

            return {
                "status": "success",
                "report_id": report.id,
                "total": parsed.total_tests,
                "passed": parsed.passed_tests,
                "failed": parsed.failed_tests,
            }

        except FileNotFoundError:
            logger.error("output.xml not found: %s", output_xml_path)
            return {"status": "error", "message": "output.xml not found"}
        except Exception as exc:
            session.rollback()
            logger.exception("Failed to parse report for run %d", run_id)
            return {"status": "error", "message": str(exc)}
