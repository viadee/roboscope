"""Audit log API endpoints (Admin only)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import require_role
from src.auth.models import User
from src.audit.schemas import AuditLogListResponse, AuditLogResponse
from src.audit.service import (
    export_audit_csv,
    get_distinct_actions,
    get_distinct_resource_types,
    list_audit_logs,
)
from src.database import get_db

router = APIRouter()


@router.get("", response_model=AuditLogListResponse)
def get_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """List audit logs with pagination and filtering (admin only)."""
    logs, total = list_audit_logs(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/export")
def export_audit(
    user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Export audit logs as CSV (admin only)."""
    csv_content = export_audit_csv(
        db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
    )
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-log.csv"},
    )


@router.get("/filters")
def get_filter_options(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Get available filter values for the audit log UI."""
    return {
        "actions": get_distinct_actions(db),
        "resource_types": get_distinct_resource_types(db),
    }
