"""Pydantic schemas for reports."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: int
    execution_run_id: int
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    total_duration_seconds: float
    created_at: datetime

    model_config = {"from_attributes": True}


class TestResultResponse(BaseModel):
    id: int
    report_id: int
    suite_name: str
    test_name: str
    status: str
    duration_seconds: float
    error_message: str | None = None
    tags: str | None = None
    start_time: str | None = None
    end_time: str | None = None

    model_config = {"from_attributes": True}


class ReportDetailResponse(BaseModel):
    report: ReportResponse
    test_results: list[TestResultResponse]


class TestHistoryPoint(BaseModel):
    report_id: int
    date: datetime
    status: str
    duration_seconds: float
    error_message: str | None = None


class TestHistoryResponse(BaseModel):
    test_name: str
    suite_name: str
    history: list[TestHistoryPoint]
    total_runs: int
    pass_count: int
    fail_count: int
    pass_rate: float


class UniqueTestResponse(BaseModel):
    test_name: str
    suite_name: str
    last_status: str
    run_count: int


class ReportCompareResponse(BaseModel):
    report_a: ReportResponse
    report_b: ReportResponse
    new_failures: list[str] = []
    fixed_tests: list[str] = []
    consistent_failures: list[str] = []
    duration_diff_seconds: float = 0.0


# --- Deep XML data schemas ---


class XmlMessageResponse(BaseModel):
    timestamp: str = ""
    level: str = "INFO"
    text: str = ""


class XmlKeywordResponse(BaseModel):
    name: str = ""
    type: str = "kw"
    library: str = ""
    status: str = "UNKNOWN"
    start_time: str = ""
    end_time: str = ""
    duration: float = 0.0
    doc: str = ""
    arguments: list[str] = []
    messages: list[XmlMessageResponse] = []
    keywords: list[XmlKeywordResponse] = []


class XmlTestResponse(BaseModel):
    name: str = ""
    status: str = "FAIL"
    start_time: str = ""
    end_time: str = ""
    duration: float = 0.0
    doc: str = ""
    tags: list[str] = []
    error_message: str = ""
    keywords: list[XmlKeywordResponse] = []


class XmlSuiteResponse(BaseModel):
    name: str = ""
    source: str = ""
    status: str = "UNKNOWN"
    start_time: str = ""
    end_time: str = ""
    duration: float = 0.0
    doc: str = ""
    suites: list[XmlSuiteResponse] = []
    tests: list[XmlTestResponse] = []


class XmlReportDataResponse(BaseModel):
    suites: list[XmlSuiteResponse] = []
    statistics: dict = {}
    generated: str = ""


# Rebuild models for forward references
XmlKeywordResponse.model_rebuild()
XmlSuiteResponse.model_rebuild()
