"""Report models."""

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base, TimestampMixin


class Report(Base, TimestampMixin):
    """Parsed test execution report."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    execution_run_id: Mapped[int] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="CASCADE"), unique=True, index=True
    )
    output_xml_path: Mapped[str] = mapped_column(String(500))
    log_html_path: Mapped[str | None] = mapped_column(String(500), default=None)
    report_html_path: Mapped[str | None] = mapped_column(String(500), default=None)
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    passed_tests: Mapped[int] = mapped_column(Integer, default=0)
    failed_tests: Mapped[int] = mapped_column(Integer, default=0)
    skipped_tests: Mapped[int] = mapped_column(Integer, default=0)
    total_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)


class TestResult(Base):
    """Individual test result within a report."""

    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    suite_name: Mapped[str] = mapped_column(String(500))
    test_name: Mapped[str] = mapped_column(String(500), index=True)
    status: Mapped[str] = mapped_column(String(20))  # PASS, FAIL, SKIP
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    tags: Mapped[str | None] = mapped_column(String(500), default=None)
    start_time: Mapped[str | None] = mapped_column(String(50), default=None)
    end_time: Mapped[str | None] = mapped_column(String(50), default=None)
