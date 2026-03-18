"""Pydantic schemas for audit log."""

from datetime import datetime

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None = None
    username: str | None = None
    action: str
    resource_type: str
    resource_id: int | None = None
    detail: str | None = None
    ip_address: str | None = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
