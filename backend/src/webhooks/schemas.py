"""Pydantic schemas for API tokens and webhooks."""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from src.auth.constants import Role

# --- API Token Schemas ---

VALID_EVENTS = [
    "run.started",
    "run.passed",
    "run.failed",
    "run.error",
    "run.cancelled",
    "run.timeout",
]


class ApiTokenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: Role = Role.RUNNER
    expires_in_days: int | None = Field(
        default=None, ge=1, le=365, description="Days until expiry (null = never)",
    )


class ApiTokenResponse(BaseModel):
    id: int
    name: str
    prefix: str
    role: Role
    user_id: int
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiTokenCreated(ApiTokenResponse):
    """Returned only on creation — includes the full plaintext token."""

    token: str


# --- Webhook Schemas ---


class WebhookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=1000)
    secret: str | None = Field(default=None, max_length=255)
    events: list[str] = Field(default_factory=lambda: list(VALID_EVENTS))
    is_active: bool = True
    repository_id: int | None = None


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    secret: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None
    repository_id: int | None = None


class WebhookResponse(BaseModel):
    id: int
    name: str
    url: str
    has_secret: bool
    events: list[str]
    is_active: bool
    repository_id: int | None = None
    created_by: int
    last_triggered_at: datetime | None = None
    last_status_code: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryResponse(BaseModel):
    id: int
    webhook_id: int
    event: str
    status_code: int | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookTestResponse(BaseModel):
    success: bool
    status_code: int | None = None
    error: str | None = None
