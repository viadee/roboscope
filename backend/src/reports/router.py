"""Report API endpoints."""

import io
import logging
import mimetypes
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.constants import Role
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from src.auth.service import decode_token, get_user_by_id
from src.database import get_db

optional_bearer = HTTPBearer(auto_error=False)
from src.reports.models import Report, TestResult
from src.reports.parser import parse_output_xml_deep
from src.reports.schemas import (
    ReportCompareResponse,
    ReportDetailResponse,
    ReportResponse,
    TestResultResponse,
    XmlReportDataResponse,
)
from src.reports.service import (
    compare_reports,
    get_report,
    get_test_results,
    list_reports,
)

logger = logging.getLogger("mateox.reports")

router = APIRouter()


async def _authenticate_flexible(
    token: str | None,
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
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
        user = await get_user_by_id(db, user_id)
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
async def get_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repository_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List reports with pagination."""
    reports, total = await list_reports(db, page, page_size, repository_id)
    return [ReportResponse.model_validate(r) for r in reports]


@router.delete("/all", status_code=status.HTTP_200_OK)
async def delete_all_reports(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Delete all reports, test results, and associated files on disk."""
    # Get all reports to find output dirs
    result = await db.execute(select(Report))
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
    await db.execute(delete(TestResult))
    # Delete all reports
    count = len(reports)
    await db.execute(delete(Report))
    await db.flush()

    logger.info("Deleted %d reports and %d output directories", count, deleted_dirs)
    return {"deleted": count, "dirs_cleaned": deleted_dirs}


@router.get("/compare", response_model=ReportCompareResponse)
async def compare(
    report_a: int = Query(..., description="First report ID"),
    report_b: int = Query(..., description="Second report ID"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Compare two reports."""
    try:
        return await compare_reports(db, report_a, report_b)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{report_id}", response_model=ReportDetailResponse)
async def get_report_detail(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get report with all test results."""
    report = await get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    results = await get_test_results(db, report_id)
    return ReportDetailResponse(
        report=ReportResponse.model_validate(report),
        test_results=[TestResultResponse.model_validate(r) for r in results],
    )


@router.get("/{report_id}/html")
async def get_report_html(
    report_id: int,
    token: str | None = Query(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    db: AsyncSession = Depends(get_db),
):
    """Serve the original Robot Framework HTML report with injected base tag."""
    await _authenticate_flexible(token, credentials, db)

    report = await get_report(db, report_id)
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

    # Read and inject <base> tag so relative asset references resolve to the asset endpoint
    html_content = html_path.read_text(encoding="utf-8", errors="replace")
    base_tag = f'<base href="/api/v1/reports/{report_id}/assets/">'
    if "<head>" in html_content:
        html_content = html_content.replace("<head>", f"<head>{base_tag}", 1)
    elif "<HEAD>" in html_content:
        html_content = html_content.replace("<HEAD>", f"<HEAD>{base_tag}", 1)
    else:
        # Prepend if no <head> tag found
        html_content = base_tag + html_content

    return Response(content=html_content, media_type="text/html")


@router.get("/{report_id}/assets/{file_path:path}")
async def get_report_asset(
    report_id: int,
    file_path: str,
    db: AsyncSession = Depends(get_db),
):
    """Serve a file from the report's output directory (screenshots, etc.).

    No auth required — assets are scoped by report ID with path traversal protection.
    This allows the iframe'd HTML report to load resources without token forwarding.
    """
    report = await get_report(db, report_id)
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
async def get_report_zip(
    report_id: int,
    token: str | None = Query(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    db: AsyncSession = Depends(get_db),
):
    """Download the entire report directory as a ZIP archive."""
    await _authenticate_flexible(token, credentials, db)
    report = await get_report(db, report_id)
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
async def get_report_xml_data(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get deep-parsed XML data with full keyword-level hierarchy."""
    report = await get_report(db, report_id)
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
async def get_report_tests(
    report_id: int,
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get individual test results for a report."""
    report = await get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    results = await get_test_results(db, report_id)
    if status_filter:
        results = [r for r in results if r.status == status_filter.upper()]

    return [TestResultResponse.model_validate(r) for r in results]
