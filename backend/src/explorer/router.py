"""Explorer API endpoints for browsing test files."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.explorer.schemas import (
    FileContent,
    FileCreateRequest,
    FileOpenRequest,
    FileRenameRequest,
    FileSaveRequest,
    SearchResult,
    TestCaseInfo,
    TreeNode,
)
from src.explorer.service import (
    build_tree,
    create_file,
    delete_file,
    list_all_testcases,
    open_in_editor,
    read_file,
    rename_file,
    search_in_repo,
    write_file,
)
from src.repos.service import get_repository

router = APIRouter()


@router.get("/{repo_id}/tree", response_model=TreeNode)
async def get_tree(
    repo_id: int,
    path: str = Query(default="", description="Relative path within repo"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get the file tree for a repository."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    try:
        tree = build_tree(repo.local_path, path)
        return tree
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error building tree: {e}",
        )


@router.get("/{repo_id}/file", response_model=FileContent)
async def get_file(
    repo_id: int,
    path: str = Query(..., description="Relative file path within repo"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Read a file's content."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    try:
        return read_file(repo.local_path, path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Path traversal not allowed",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")


@router.get("/{repo_id}/search", response_model=list[SearchResult])
async def search(
    repo_id: int,
    q: str = Query(..., min_length=1, description="Search query"),
    file_type: str | None = Query(default=None, description="Filter by file type"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Search for test cases, keywords, and files."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    return search_in_repo(repo.local_path, q, file_type)


@router.get("/{repo_id}/testcases", response_model=list[TestCaseInfo])
async def get_testcases(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all test cases in a repository."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    return list_all_testcases(repo.local_path)


# ---------------------------------------------------------------------------
# File operations (create, save, delete, rename, open)
# ---------------------------------------------------------------------------


@router.post("/{repo_id}/file", response_model=FileContent, status_code=status.HTTP_201_CREATED)
async def create_new_file(
    repo_id: int,
    body: FileCreateRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Create a new file in the repository."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    try:
        return create_file(repo.local_path, body.path, body.content)
    except FileExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path traversal not allowed")


@router.put("/{repo_id}/file", response_model=FileContent)
async def save_file(
    repo_id: int,
    body: FileSaveRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Save (overwrite) a file's content."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    try:
        return write_file(repo.local_path, body.path, body.content)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path traversal not allowed")


@router.delete("/{repo_id}/file", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_file(
    repo_id: int,
    path: str = Query(..., description="Relative path of the file to delete"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Delete a file from the repository."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    try:
        delete_file(repo.local_path, path)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path traversal not allowed")


@router.post("/{repo_id}/file/rename", response_model=FileContent)
async def rename_existing_file(
    repo_id: int,
    body: FileRenameRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Rename or move a file within the repository."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    try:
        return rename_file(repo.local_path, body.old_path, body.new_path)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source file not found")
    except FileExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path traversal not allowed")


@router.post("/{repo_id}/file/open", status_code=status.HTTP_204_NO_CONTENT)
async def open_file_in_editor(
    repo_id: int,
    body: FileOpenRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Open a file in the system's default editor."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    try:
        open_in_editor(repo.local_path, body.path)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path traversal not allowed")
