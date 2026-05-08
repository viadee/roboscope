"""Repository management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import (
    get_current_user,
    require_effective_role,
    require_role,
)
from src.auth.models import User
from src.task_executor import TaskDispatchError, dispatch_task
from src.database import get_db
from src.repos.schemas import (
    BranchResponse,
    CommitRequest,
    CommitResponse,
    ProjectMemberCreate,
    ProjectMemberResponse,
    ProjectMemberUpdate,
    PublishResponse,
    PushResponse,
    RepoCreate,
    RepoResponse,
    RepoStatusResponse,
    RepoTeamAssignRequest,
    RepoUpdate,
    SyncResponse,
)
from src.repos.service import (
    GitOperationError,
    add_project_member,
    checkout_branch,
    commit_changes,
    create_repository,
    delete_repository,
    get_repo_status,
    get_repository,
    get_repository_by_name,
    list_branches,
    list_project_members,
    list_remote_branches,
    list_repositories,
    publish_changes,
    push_branch,
    remove_project_member,
    update_project_member_role,
    update_repository,
)

logger = logging.getLogger("roboscope.repos")

router = APIRouter()


@router.get("", response_model=list[RepoResponse])
def get_repos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List repositories visible to the current user."""
    is_admin = current_user.role == Role.ADMIN
    return list_repositories(db, user_id=current_user.id, is_admin=is_admin)


@router.post("/validate-branch")
def validate_branch(
    git_url: str,
    branch: str = "main",
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Check if a branch exists on a remote git repository.

    Returns the branch if valid, or suggests main/master fallbacks.
    """
    remote_branches = list_remote_branches(git_url)
    if not remote_branches:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not connect to repository or no branches found",
        )
    if branch in remote_branches:
        return {"valid": True, "branch": branch, "available_branches": remote_branches}

    # Branch not found — suggest fallbacks
    fallbacks = [b for b in ["main", "master"] if b in remote_branches and b != branch]
    return {
        "valid": False,
        "branch": branch,
        "fallbacks": fallbacks,
        "available_branches": remote_branches,
    }


@router.post("", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
def add_repo(
    data: RepoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Add a new repository."""
    existing = get_repository_by_name(db, data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository with this name already exists",
        )
    repo = create_repository(db, data, current_user.id)
    # Auto-add creator as editor member
    add_project_member(db, repo.id, current_user.id, role="editor")
    db.commit()
    # Trigger async clone only for git repos
    if repo.repo_type == "git":
        try:
            from src.repos.tasks import clone_repo

            dispatch_task(clone_repo, repo.id)
        except TaskDispatchError as e:
            logger.error("Failed to dispatch clone for repo %d: %s", repo.id, e)
            repo.sync_status = "error"
            repo.sync_error = f"Task dispatch failed: {e}"
            db.flush()
            db.refresh(repo)
    return repo


@router.get("/{repo_id}", response_model=RepoResponse)
def get_repo(
    repo_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get repository details."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return repo


@router.patch("/{repo_id}", response_model=RepoResponse)
def patch_repo(
    repo_id: int,
    data: RepoUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_effective_role(Role.EDITOR)),
):
    """Update repository settings."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return update_repository(db, repo, data)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_repo(
    repo_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_effective_role(Role.ADMIN)),
):
    """Delete a repository."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    delete_repository(db, repo)


@router.put("/{repo_id}/team", response_model=RepoResponse)
def assign_team(
    repo_id: int,
    data: RepoTeamAssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_effective_role(Role.ADMIN)),
):
    """Assign (or clear with team_id=null) the owning team of a repository.

    Story 3-2: repository → team assignment. ADMIN-only; emits
    `repository.team_assigned` / `repository.team_unassigned` audit events.
    """
    from src.audit.event_types import AuditEventType
    from src.audit.service import log_event
    from src.teams.models import Team

    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
        )

    if data.team_id is not None:
        team = db.get(Team, data.team_id)
        if team is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
            )

    previous_team_id = repo.team_id
    repo.team_id = data.team_id
    db.flush()

    ip = request.client.host if request.client else None
    event_type = (
        AuditEventType.REPOSITORY_TEAM_ASSIGNED
        if data.team_id is not None
        else AuditEventType.REPOSITORY_TEAM_UNASSIGNED
    )
    log_event(
        db,
        event_type,
        user_id=current_user.id,
        resource_id=repo.id,
        detail={"team_id": data.team_id, "previous_team_id": previous_team_id},
        ip_address=ip,
    )
    db.commit()
    db.refresh(repo)
    return repo


@router.post("/{repo_id}/sync", response_model=SyncResponse)
def sync_repo(
    repo_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_effective_role(Role.EDITOR)),
):
    """Trigger git sync for a repository."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    if repo.repo_type == "local":
        return SyncResponse(status="skipped", message="Local repositories do not require sync")

    try:
        from src.repos.tasks import sync_repo

        result = dispatch_task(sync_repo, repo.id)
        return SyncResponse(status="syncing", message="Sync started", task_id=result.id)
    except TaskDispatchError as e:
        logger.error("Failed to dispatch sync for repo %d: %s", repo.id, e)
        repo.sync_status = "error"
        repo.sync_error = f"Task dispatch failed: {e}"
        db.flush()
        return SyncResponse(status="error", message=f"Task dispatch failed: {e}")


# ---------------------------------------------------------------------------
# Story REPO-1 — non-Git-user save loop (status / commit / push / publish)
# ---------------------------------------------------------------------------


def _gitop_to_http(e: GitOperationError) -> HTTPException:
    """Map a service-layer `GitOperationError` to the right HTTP status."""
    if e.kind == "not_a_repo":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if e.kind == "nothing_to_commit":
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if e.kind == "non_fast_forward":
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if e.kind == "auth":
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{repo_id}/status", response_model=RepoStatusResponse)
def get_status(
    repo_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Snapshot of the working tree + tracking-branch divergence.

    Polled by the Explorer to render the "Save N changes" badge.
    Read-only — intentionally not behind `require_effective_role` so
    every user can SEE the state; gating happens on the write paths.
    """
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.repo_type == "local":
        return RepoStatusResponse()
    return RepoStatusResponse(**get_repo_status(repo.local_path))


@router.post("/{repo_id}/commit", response_model=CommitResponse)
def commit(
    repo_id: int,
    body: CommitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_effective_role(Role.EDITOR)),
):
    """Stage `body.paths` (or all dirty paths) and commit with the
    logged-in user's identity."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.repo_type == "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local repositories have no remote — commit / push not supported.",
        )
    try:
        result = commit_changes(
            repo.local_path,
            body.message,
            body.paths,
            current_user.username,
            current_user.email,
        )
    except GitOperationError as e:
        raise _gitop_to_http(e) from e
    return CommitResponse(**result)


@router.post("/{repo_id}/push", response_model=PushResponse)
def push(
    repo_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_effective_role(Role.EDITOR)),
):
    """Push the current branch to its tracked upstream."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.repo_type == "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local repositories have no remote — commit / push not supported.",
        )
    try:
        result = push_branch(repo.local_path)
    except GitOperationError as e:
        raise _gitop_to_http(e) from e
    return PushResponse(**result)


@router.post("/{repo_id}/publish", response_model=PublishResponse)
def publish(
    repo_id: int,
    body: CommitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_effective_role(Role.EDITOR)),
):
    """Combined commit + push — the typical "Save to repository" call.

    On non-fast-forward push: returns HTTP 409 with the LOCAL commit
    hash so the client can offer "Pull latest and retry" without
    losing the just-made commit.
    """
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.repo_type == "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local repositories have no remote — commit / push not supported.",
        )
    try:
        result = publish_changes(
            repo.local_path,
            body.message,
            body.paths,
            current_user.username,
            current_user.email,
        )
    except GitOperationError as e:
        # Commit succeeded but push failed → return 409 with the
        # commit metadata so the user knows their work is safe
        # locally. The exception type now declares these fields
        # (story TYPE-7) so we read them as attributes directly.
        if e.commit_hash is not None and e.kind == "non_fast_forward":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "commit_hash": e.commit_hash,
                    "files": e.committed_files or [],
                    "message": body.message,
                    "pushed": False,
                    "conflict": True,
                    "reason": str(e),
                },
            ) from e
        raise _gitop_to_http(e) from e
    return PublishResponse(**result)


@router.get("/{repo_id}/branches", response_model=list[BranchResponse])
def get_branches(
    repo_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List branches for a repository."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    branches = list_branches(repo.local_path)
    return [BranchResponse(**b) for b in branches]


@router.post("/{repo_id}/checkout")
def checkout_branch_endpoint(
    repo_id: int,
    branch: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_effective_role(Role.EDITOR)),
):
    """Checkout a branch and update default_branch."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.repo_type != "git":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Branch checkout is only available for Git repositories",
        )
    result = checkout_branch(repo.local_path, branch)
    if result.startswith("error:"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result,
        )
    repo.default_branch = branch
    db.flush()
    db.refresh(repo)
    return {"status": "success", "branch": branch}


# ---------------------------------------------------------------------------
# Project Members
# ---------------------------------------------------------------------------


@router.get("/{repo_id}/members", response_model=list[ProjectMemberResponse])
def get_members(
    repo_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all members of a project."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return list_project_members(db, repo_id)


@router.post(
    "/{repo_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    repo_id: int,
    data: ProjectMemberCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_effective_role(Role.EDITOR)),
):
    """Add a user to a project."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    from src.auth.service import get_user_by_id

    user = get_user_by_id(db, data.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    member = add_project_member(db, repo_id, data.user_id, data.role)
    return {
        **{c.key: getattr(member, c.key) for c in member.__table__.columns},
        "username": user.username,
        "email": user.email,
    }


@router.patch("/{repo_id}/members/{member_id}", response_model=ProjectMemberResponse)
def patch_member(
    repo_id: int,
    member_id: int,
    data: ProjectMemberUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_effective_role(Role.EDITOR)),
):
    """Update a project member's role."""
    member = update_project_member_role(db, member_id, data.role)
    if member is None or member.repository_id != repo_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    from src.auth.service import get_user_by_id

    user = get_user_by_id(db, member.user_id)
    return {
        **{c.key: getattr(member, c.key) for c in member.__table__.columns},
        "username": user.username if user else "",
        "email": user.email if user else "",
    }


@router.delete("/{repo_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(
    repo_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_effective_role(Role.EDITOR)),
):
    """Remove a user from a project."""
    if not remove_project_member(db, member_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
