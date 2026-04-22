"""Pydantic schemas for authentication."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from src.auth.constants import Role

ProviderType = Literal["oidc_azure_ad", "oidc_google", "oidc_github", "oidc_generic"]


# --- Request Schemas ---


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)
    role: Role = Role.RUNNER


class RefreshRequest(BaseModel):
    refresh_token: str


# --- Response Schemas ---


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    email: str | None = None
    username: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=6, max_length=128)


# --- Identity Provider Schemas ---


class IdentityProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider_type: ProviderType
    issuer_url: str = Field(..., min_length=1, max_length=500)
    client_id: str = Field(..., min_length=1, max_length=255)
    client_secret: str = Field(..., min_length=1, max_length=500)
    scopes: str = Field(default="openid profile email", max_length=500)
    group_claim_name: str = Field(default="groups", max_length=100)

    @field_validator("issuer_url")
    @classmethod
    def validate_issuer_url(cls, v: str) -> str:
        if not v.startswith(("https://", "http://")):
            raise ValueError("issuer_url must be an HTTP(S) URL")
        return v


class IdentityProviderUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    provider_type: ProviderType | None = None
    issuer_url: str | None = Field(None, min_length=1, max_length=500)
    client_id: str | None = Field(None, min_length=1, max_length=255)
    client_secret: str | None = Field(None, min_length=1, max_length=500)
    scopes: str | None = Field(None, max_length=500)
    group_claim_name: str | None = Field(None, max_length=100)
    is_enabled: bool | None = None

    @field_validator("issuer_url")
    @classmethod
    def validate_issuer_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("https://", "http://")):
            raise ValueError("issuer_url must be an HTTP(S) URL")
        return v

    @model_validator(mode="after")
    def reject_null_client_secret(self) -> IdentityProviderUpdate:
        if "client_secret" in self.model_fields_set and self.client_secret is None:
            raise ValueError(
                "client_secret cannot be null; omit the field to keep"
                " the existing value"
            )
        return self


class IdentityProviderResponse(BaseModel):
    id: int
    name: str
    provider_type: str
    issuer_url: str
    client_id: str
    scopes: str
    group_claim_name: str
    is_enabled: bool
    last_dry_run_at: datetime | None = None
    last_dry_run_status: str | None = None
    discovery_cached_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DiscoveryCacheRefreshResponse(BaseModel):
    status: Literal["completed"]
    refreshed: int
    failed: int
    skipped: int


# --- Dry-Run Probe Schemas ---


class DryRunCheckRow(BaseModel):
    check_name: str
    status: Literal["passed", "warning", "failed"]
    detail: str


class DryRunProbeResponse(BaseModel):
    overall_status: Literal["passed", "failed"]
    checks: list[DryRunCheckRow]
    elapsed_ms: int


# --- SSO Public Schemas (Story 2-1) ---


class SsoProviderPublic(BaseModel):
    """Public-safe identity provider row — exposed on the unauthenticated
    `GET /auth/sso/providers` endpoint. Intentionally narrow: only fields
    the login view needs to render a provider button.
    """

    id: int
    name: str
    provider_type: str

    model_config = {"from_attributes": True}
