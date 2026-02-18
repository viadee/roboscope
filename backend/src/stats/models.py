"""KPI and statistics models."""

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


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
