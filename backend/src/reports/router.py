"""Report API endpoints."""

import io
import logging
import mimetypes
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from src.auth.service import decode_token, get_user_by_id
from src.database import get_db

optional_bearer = HTTPBearer(auto_error=False)
from src.reports.models import Report, TestResult
from src.config import settings
from src.reports.parser import parse_output_xml, parse_output_xml_deep
from src.reports.schemas import (
    ReportCompareResponse,
    ReportDetailResponse,
    ReportResponse,
    TestHistoryResponse,
    TestResultResponse,
    UniqueTestResponse,
    XmlReportDataResponse,
)
from src.reports.service import (
    compare_reports,
    get_report,
    get_test_history,
    get_test_results,
    list_reports,
    list_unique_tests,
)

logger = logging.getLogger("mateox.reports")

router = APIRouter()


def _authenticate_flexible(
    token: str | None,
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> User:
    """Authenticate via query param token or Bearer header. Raises 401 if neither works."""
    # Try query param token first (for iframe/download URLs)
    raw_token = token
    if not raw_token and credentials:
        raw_token = credentials.credentials

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        payload = decode_token(raw_token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id = int(payload["sub"])
        user = get_user_by_id(db, user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive user",
            )
        return user
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


@router.get("", response_model=list[ReportResponse])
def get_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repository_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List reports with pagination."""
    reports, total = list_reports(db, page, page_size, repository_id)
    return [ReportResponse.model_validate(r) for r in reports]


@router.delete("/all", status_code=status.HTTP_200_OK)
def delete_all_reports(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Delete all reports, test results, and associated files on disk."""
    # Get all reports to find output dirs
    result = db.execute(select(Report))
    reports = list(result.scalars().all())

    # Delete files from disk
    deleted_dirs = 0
    for report in reports:
        if report.output_xml_path:
            output_dir = Path(report.output_xml_path).parent
            if output_dir.exists():
                try:
                    shutil.rmtree(output_dir)
                    deleted_dirs += 1
                except Exception as e:
                    logger.warning("Failed to delete %s: %s", output_dir, e)

    # Delete all test results first (FK constraint)
    db.execute(delete(TestResult))
    # Delete all reports
    count = len(reports)
    db.execute(delete(Report))
    db.flush()

    logger.info("Deleted %d reports and %d output directories", count, deleted_dirs)
    return {"deleted": count, "dirs_cleaned": deleted_dirs}


@router.post("/upload", response_model=ReportDetailResponse, status_code=status.HTTP_201_CREATED)
def upload_archive(
    file: UploadFile,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Upload a Robot Framework report ZIP for offline analysis.

    The ZIP must contain an output.xml file. Optionally includes report.html
    and log.html for HTML report viewing.
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a .zip archive",
        )

    # Read and validate ZIP
    try:
        content = file.file.read()
        if not zipfile.is_zipfile(io.BytesIO(content)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is not a valid ZIP archive",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error reading uploaded file: {e}",
        )

    # Extract to a unique directory under REPORTS_DIR/archives/
    import uuid

    archive_id = uuid.uuid4().hex[:12]
    archive_name = Path(file.filename).stem
    extract_dir = Path(settings.REPORTS_DIR) / "archives" / f"{archive_name}_{archive_id}"
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            zf.extractall(extract_dir)
    except Exception as e:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error extracting ZIP: {e}",
        )

    # Find output.xml (may be at root or one level deep)
    output_xml = None
    report_html = None
    log_html = None

    for xml_path in extract_dir.rglob("output.xml"):
        output_xml = xml_path
        break

    if output_xml is None:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No output.xml found in the uploaded archive",
        )

    # Look for report.html and log.html near output.xml
    xml_dir = output_xml.parent
    for html_candidate in xml_dir.glob("report.html"):
        report_html = html_candidate
    for html_candidate in xml_dir.glob("log.html"):
        log_html = html_candidate

    # Parse output.xml
    try:
        parsed = parse_output_xml(str(output_xml))
    except Exception as e:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error parsing output.xml: {e}",
        )

    # Create Report record (no execution_run_id for archives)
    report = Report(
        execution_run_id=None,
        archive_name=archive_name,
        output_xml_path=str(output_xml),
        log_html_path=str(log_html) if log_html else None,
        report_html_path=str(report_html) if report_html else None,
        total_tests=parsed.total_tests,
        passed_tests=parsed.passed_tests,
        failed_tests=parsed.failed_tests,
        skipped_tests=parsed.skipped_tests,
        total_duration_seconds=parsed.total_duration_seconds,
    )
    db.add(report)
    db.flush()
    db.refresh(report)

    # Create TestResult records
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
        db.add(test_result)
    db.flush()

    logger.info(
        "Archive uploaded: %s — %d tests (%d passed, %d failed)",
        archive_name, parsed.total_tests, parsed.passed_tests, parsed.failed_tests,
    )

    results = get_test_results(db, report.id)
    return ReportDetailResponse(
        report=ReportResponse.model_validate(report),
        test_results=[TestResultResponse.model_validate(r) for r in results],
    )


@router.get("/compare", response_model=ReportCompareResponse)
def compare(
    report_a: int = Query(..., description="First report ID"),
    report_b: int = Query(..., description="Second report ID"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Compare two reports."""
    try:
        return compare_reports(db, report_a, report_b)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/tests/unique", response_model=list[UniqueTestResponse])
def get_unique_tests(
    search: str | None = Query(default=None, description="Filter by test name"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List unique test names with latest status and run count."""
    return list_unique_tests(db, search=search, limit=limit)


@router.get("/tests/history", response_model=TestHistoryResponse)
def get_test_history_endpoint(
    test_name: str = Query(..., description="Exact test name"),
    suite_name: str | None = Query(default=None, description="Filter by suite name"),
    days: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get pass/fail history for a specific test over time."""
    return get_test_history(db, test_name=test_name, suite_name=suite_name, days=days)


@router.get("/{report_id}", response_model=ReportDetailResponse)
def get_report_detail(
    report_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get report with all test results."""
    report = get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    results = get_test_results(db, report_id)
    return ReportDetailResponse(
        report=ReportResponse.model_validate(report),
        test_results=[TestResultResponse.model_validate(r) for r in results],
    )


@router.get("/{report_id}/html")
def get_report_html(
    report_id: int,
    token: str | None = Query(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    db: Session = Depends(get_db),
):
    """Serve the original Robot Framework HTML report with injected base tag."""
    _authenticate_flexible(token, credentials, db)

    report = get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if not report.report_html_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HTML report not available",
        )

    html_path = Path(report.report_html_path)
    if not html_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HTML report file not found on disk",
        )

    # Read and inject <base> tag so relative asset references resolve to the asset endpoint.
    # Also inject a script to fix fragment-only links (href="#...") which would otherwise
    # navigate to the base URL + fragment, causing 404 errors.
    html_content = html_path.read_text(encoding="utf-8", errors="replace")
    base_tag = f'<base href="/api/v1/reports/{report_id}/assets/">'
    fragment_fix_script = (
        "<script>"
        "document.addEventListener('click',function(e){"
        "var a=e.target.closest('a[href^=\"#\"]');"
        "if(a){e.preventDefault();"
        "var hash=a.getAttribute('href');"
        "if(a.onclick)a.onclick(e);"
        "window.location.hash=hash.substring(1);}"
        "});"
        "</script>"
    )
    injected = base_tag + fragment_fix_script
    if "<head>" in html_content:
        html_content = html_content.replace("<head>", f"<head>{injected}", 1)
    elif "<HEAD>" in html_content:
        html_content = html_content.replace("<HEAD>", f"<HEAD>{injected}", 1)
    else:
        # Prepend if no <head> tag found
        html_content = injected + html_content

    return Response(content=html_content, media_type="text/html")


@router.get("/{report_id}/assets/{file_path:path}")
def get_report_asset(
    report_id: int,
    file_path: str,
    db: Session = Depends(get_db),
):
    """Serve a file from the report's output directory (screenshots, etc.).

    No auth required — assets are scoped by report ID with path traversal protection.
    This allows the iframe'd HTML report to load resources without token forwarding.
    """
    report = get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if not report.output_xml_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report output directory not available",
        )

    output_dir = Path(report.output_xml_path).parent.resolve()
    requested_path = (output_dir / file_path).resolve()

    # Security: prevent path traversal
    try:
        requested_path.relative_to(output_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: path traversal detected",
        )

    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_path}",
        )

    media_type = mimetypes.guess_type(str(requested_path))[0] or "application/octet-stream"
    return FileResponse(str(requested_path), media_type=media_type)


@router.get("/{report_id}/zip")
def get_report_zip(
    report_id: int,
    token: str | None = Query(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    db: Session = Depends(get_db),
):
    """Download the entire report directory as a ZIP archive."""
    _authenticate_flexible(token, credentials, db)
    report = get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if not report.output_xml_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report output directory not available",
        )

    output_dir = Path(report.output_xml_path).parent
    if not output_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report output directory not found on disk",
        )

    # Create in-memory ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(output_dir)
                zf.write(file_path, arcname)

    zip_buffer.seek(0)
    zip_filename = f"report_{report_id}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )


@router.get("/{report_id}/xml-data", response_model=XmlReportDataResponse)
def get_report_xml_data(
    report_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get deep-parsed XML data with full keyword-level hierarchy."""
    report = get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if not report.output_xml_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report output XML not available",
        )

    xml_path = Path(report.output_xml_path)
    if not xml_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="output.xml not found on disk",
        )

    try:
        data = parse_output_xml_deep(str(xml_path))
    except Exception as e:
        logger.error("Failed to parse output.xml for report %d: %s", report_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse output.xml: {e}",
        )

    return data


@router.get("/{report_id}/tests", response_model=list[TestResultResponse])
def get_report_tests(
    report_id: int,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get individual test results for a report."""
    report = get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    results = get_test_results(db, report_id)
    if status_filter:
        results = [r for r in results if r.status == status_filter.upper()]

    return [TestResultResponse.model_validate(r) for r in results]
