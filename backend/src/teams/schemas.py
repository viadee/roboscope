"""Pydantic schemas for Team and TeamMember endpoints (Story 3-1)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    external_id: str | None
    created_at: datetime
    updated_at: datetime


class TeamMemberCreate(BaseModel):
    user_id: int
    role: str = Field(default="viewer")


class TeamMemberUpdate(BaseModel):
    role: str = Field(min_length=1, max_length=20)


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    user_id: int
    role: str
    source: str
    external_id: str | None
    created_at: datetime
    updated_at: datetime


class TeamMemberDetail(BaseModel):
    """Membership row plus lightweight user profile fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    email: str
    role: str
    source: str


class TeamDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    external_id: str | None
    created_at: datetime
    updated_at: datetime
    members: list[TeamMemberDetail]


class GroupMappingCreate(BaseModel):
    idp_id: int
    group_name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="viewer", min_length=1, max_length=20)


class GroupMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    idp_id: int
    team_id: int
    group_claim_value: str
    role: str
    created_at: datetime
    updated_at: datetime


class GroupMappingUpdate(BaseModel):
    role: str = Field(min_length=1, max_length=20)


class TeamImportRow(BaseModel):
    group_name: str = Field(min_length=1, max_length=255)
    team_name: str = Field(min_length=1, max_length=100)
    role: str = Field(default="viewer", min_length=1, max_length=20)


class TeamImportFromGroupsRequest(BaseModel):
    idp_id: int
    groups: list[TeamImportRow] = Field(min_length=1)


class TeamImportSummary(BaseModel):
    created: int
    skipped: int
    failed: int
    team_ids: list[int]
    errors: list[str]
