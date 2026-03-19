"""Audit log service — write and query audit entries."""

import csv
import io
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.audit.models import AuditLog

logger = logging.getLogger("roboscope.audit")


def log_audit(
    db: Session,
    *,
    user_id: int | None = None,
    username: str | None = None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    detail: dict | str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Create an audit log entry."""
    detail_str = None
    if detail is not None:
        detail_str = json.dumps(detail, default=str) if isinstance(detail, dict) else str(detail)

    entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail_str,
        ip_address=ip_address,
    )
    db.add(entry)
    db.flush()
    return entry


def list_audit_logs(
    db: Session,
    page: int = 1,
    page_size: int = 50,
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[AuditLog], int]:
    """List audit logs with pagination and filters."""
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))

    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
        count_stmt = count_stmt.where(AuditLog.resource_type == resource_type)
    if date_from:
        stmt = stmt.where(AuditLog.timestamp >= date_from)
        count_stmt = count_stmt.where(AuditLog.timestamp >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.timestamp <= date_to)
        count_stmt = count_stmt.where(AuditLog.timestamp <= date_to)

    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.order_by(AuditLog.timestamp.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = db.execute(stmt)

    return list(result.scalars().all()), total


def export_audit_csv(
    db: Session,
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> str:
    """Export audit logs as CSV string."""
    logs, _ = list_audit_logs(
        db,
        page=1,
        page_size=10000,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "user_id", "username", "action", "resource_type", "resource_id", "detail", "ip_address"])
    for log in logs:
        writer.writerow([
            log.timestamp.isoformat() if log.timestamp else "",
            log.user_id or "",
            log.username or "",
            log.action,
            log.resource_type,
            log.resource_id or "",
            log.detail or "",
            log.ip_address or "",
        ])
    return output.getvalue()


def get_distinct_actions(db: Session) -> list[str]:
    """Get all unique action values."""
    result = db.execute(select(AuditLog.action).distinct().order_by(AuditLog.action))
    return [r[0] for r in result.all()]


def get_distinct_resource_types(db: Session) -> list[str]:
    """Get all unique resource_type values."""
    result = db.execute(
        select(AuditLog.resource_type).distinct().order_by(AuditLog.resource_type)
    )
    return [r[0] for r in result.all()]
