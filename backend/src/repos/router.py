"""Repository management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from src.celery_app import TaskDispatchError, dispatch_task
from src.database import get_db
from src.repos.schemas import (
    BranchResponse,
    ProjectMemberCreate,
    ProjectMemberResponse,
    ProjectMemberUpdate,
    RepoCreate,
    RepoResponse,
    RepoUpdate,
    SyncResponse,
)
from src.repos.service import (
    add_project_member,
    create_repository,
    delete_repository,
    get_repository,
    get_repository_by_name,
    list_branches,
    list_project_members,
    list_repositories,
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
    _current_user: User = Depends(require_role(Role.EDITOR)),
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
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Delete a repository."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    delete_repository(db, repo)


@router.post("/{repo_id}/sync", response_model=SyncResponse)
def sync_repo(
    repo_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
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
    _current_user: User = Depends(require_role(Role.EDITOR)),
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
    _current_user: User = Depends(require_role(Role.EDITOR)),
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
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Remove a user from a project."""
    if not remove_project_member(db, member_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
