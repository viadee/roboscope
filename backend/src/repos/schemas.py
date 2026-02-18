"""Pydantic schemas for repository management."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RepoCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    repo_type: Literal["git", "local"] = "git"
    git_url: str | None = Field(default=None, max_length=500)
    local_path: str | None = Field(default=None, max_length=500)
    default_branch: str = Field(default="main", max_length=100)
    auto_sync: bool = True
    sync_interval_minutes: int = Field(default=15, ge=1, le=1440)

    @model_validator(mode="after")
    def validate_type_fields(self):
        if self.repo_type == "git" and not self.git_url:
            raise ValueError("git_url is required for git repositories")
        if self.repo_type == "local" and not self.local_path:
            raise ValueError("local_path is required for local repositories")
        return self


class RepoUpdate(BaseModel):
    name: str | None = None
    default_branch: str | None = None
    auto_sync: bool | None = None
    sync_interval_minutes: int | None = None


class RepoResponse(BaseModel):
    id: int
    name: str
    repo_type: str
    git_url: str | None = None
    default_branch: str
    local_path: str
    last_synced_at: datetime | None = None
    auto_sync: bool
    sync_interval_minutes: int
    sync_status: str | None = "idle"
    sync_error: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BranchResponse(BaseModel):
    name: str
    is_active: bool = False


class SyncResponse(BaseModel):
    status: str
    message: str
    task_id: str | None = None
