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
    environment_id: int | None = None

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
    environment_id: int | None = None


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
    environment_id: int | None = None
    team_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RepoTeamAssignRequest(BaseModel):
    """Body of PUT /repos/{id}/team — assign or clear the owning team."""

    team_id: int | None = None


class BranchResponse(BaseModel):
    name: str
    is_active: bool = False


class SyncResponse(BaseModel):
    status: str
    message: str
    task_id: str | None = None


# ---------------------------------------------------------------------------
# Story REPO-1 — non-Git-user save loop schemas
# ---------------------------------------------------------------------------


class RepoStatusResponse(BaseModel):
    """Snapshot of a git repo's working-tree state.

    Returned by `GET /repos/{id}/status`. Lists are repository-relative
    paths. `current_branch` is null when the repo is in detached-HEAD
    state. Non-git repos (`repo_type='local'`) return everything zeroed
    out + `is_dirty=false`.
    """

    current_branch: str | None = None
    ahead: int = 0
    behind: int = 0
    modified: list[str] = []
    staged: list[str] = []
    untracked: list[str] = []
    deleted: list[str] = []
    is_dirty: bool = False


class CommitRequest(BaseModel):
    """Body of `POST /repos/{id}/commit` and `POST /repos/{id}/publish`."""

    message: str = Field(..., min_length=1, max_length=500)
    # When `paths` is omitted, the service stages every dirty path it
    # finds (modified + untracked + deleted). Pass an explicit list to
    # commit a subset.
    paths: list[str] | None = None


class CommitResponse(BaseModel):
    commit_hash: str
    message: str
    files: list[str]


class PushResponse(BaseModel):
    branch: str
    remote_ref: str
    ahead_after: int = 0


class PublishResponse(BaseModel):
    """Returned by the combined `POST /repos/{id}/publish` endpoint
    on full success."""

    commit_hash: str
    message: str
    files: list[str]
    pushed: bool = True
    conflict: bool = False
    remote_ref: str


class PublishConflictResponse(BaseModel):
    """Returned with HTTP 409 when commit succeeded but push didn't.

    The local commit STAYS — the user can resolve the conflict (e.g.
    by hitting `/sync` and then `/push`) without losing their work.
    """

    commit_hash: str
    message: str
    files: list[str]
    pushed: bool = False
    conflict: bool = True
    detail: str


class ProjectMemberCreate(BaseModel):
    user_id: int
    role: Literal["viewer", "runner", "editor"] = "viewer"


class ProjectMemberUpdate(BaseModel):
    role: Literal["viewer", "runner", "editor"]


class ProjectMemberResponse(BaseModel):
    id: int
    user_id: int
    repository_id: int
    role: str
    username: str = ""
    email: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}
