"""KPI and statistics models."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base, TimestampMixin


class KpiRecord(Base):
    """Daily aggregated KPI record."""

    __tablename__ = "kpi_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), index=True)
    branch: Mapped[str | None] = mapped_column(String(100), default=None)
    environment_id: Mapped[int | None] = mapped_column(ForeignKey("environments.id"), default=None)
    total_runs: Mapped[int] = mapped_column(Integer, default=0)
    passed_runs: Mapped[int] = mapped_column(Integer, default=0)
    failed_runs: Mapped[int] = mapped_column(Integer, default=0)
    error_runs: Mapped[int] = mapped_column(Integer, default=0)
    avg_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_tests_run: Mapped[int] = mapped_column(Integer, default=0)
    total_tests_passed: Mapped[int] = mapped_column(Integer, default=0)
    total_tests_failed: Mapped[int] = mapped_column(Integer, default=0)
    flaky_test_count: Mapped[int] = mapped_column(Integer, default=0)


class FlakyQuarantine(Base):
    """Story FLAKY-1 — a manually-marked quarantine entry for a known-flaky
    Robot Framework test. Presence in this table means "don't treat this
    test's outcome as blocking"; runner-side skip-on-execute is tracked
    as follow-up Story FLAKY-2.
    """

    __tablename__ = "flaky_quarantine"
    __table_args__ = (
        UniqueConstraint(
            "repository_id", "suite_name", "test_name",
            name="uq_flaky_quarantine_repo_suite_test",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    suite_name: Mapped[str] = mapped_column(String(500), index=True)
    test_name: Mapped[str] = mapped_column(String(500), index=True)
    reason: Mapped[str | None] = mapped_column(Text, default=None)
    quarantined_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    quarantined_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False,
    )


class AnalysisReport(Base, TimestampMixin):
    """On-demand deep analysis report."""

    __tablename__ = "analysis_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id"), default=None
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    selected_kpis: Mapped[str] = mapped_column(Text, default="[]")
    date_from: Mapped[date | None] = mapped_column(Date, default=None)
    date_to: Mapped[date | None] = mapped_column(Date, default=None)
    results: Mapped[str | None] = mapped_column(Text, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    reports_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    triggered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
