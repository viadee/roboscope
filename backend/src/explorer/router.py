"""Explorer API endpoints for browsing test files."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.explorer.schemas import (
    FileContent,
    FileCreateRequest,
    FileOpenRequest,
    FileRenameRequest,
    FileSaveRequest,
    LibraryCheckItem,
    LibraryCheckResponse,
    SearchResult,
    TestCaseInfo,
    TreeNode,
)
from src.explorer.service import (
    build_tree,
    check_libraries_against_env,
    create_file,
    delete_file,
    list_all_testcases,
    open_in_editor,
    open_in_file_browser,
    read_file,
    rename_file,
    search_in_repo,
    write_file,
)
from src.environments.service import get_environment, pip_list_installed
from src.repos.service import get_repository

router = APIRouter()


@router.get("/{repo_id}/tree", response_model=TreeNode)
def get_tree(
    repo_id: int,
    path: str = Query(default="", description="Relative path within repo"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get the file tree for a repository."""
    repo = get_repository(db, repo_id)
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
def get_file(
    repo_id: int,
    path: str = Query(..., description="Relative file path within repo"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Read a file's content."""
    repo = get_repository(db, repo_id)
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
def search(
    repo_id: int,
    q: str = Query(..., min_length=1, description="Search query"),
    file_type: str | None = Query(default=None, description="Filter by file type"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Search for test cases, keywords, and files."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    return search_in_repo(repo.local_path, q, file_type)


@router.get("/{repo_id}/testcases", response_model=list[TestCaseInfo])
def get_testcases(
    repo_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all test cases in a repository."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    return list_all_testcases(repo.local_path)


@router.get("/{repo_id}/library-check", response_model=LibraryCheckResponse)
def library_check(
    repo_id: int,
    environment_id: int = Query(..., description="Environment ID to check against"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Check which libraries used in the repo are installed in the given environment."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    env = get_environment(db, environment_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    installed_packages = pip_list_installed(env.venv_path)
    results = check_libraries_against_env(repo.local_path, installed_packages)

    libraries = [LibraryCheckItem(**r) for r in results]
    missing_count = sum(1 for lib in libraries if lib.status == "missing")
    installed_count = sum(1 for lib in libraries if lib.status == "installed")
    builtin_count = sum(1 for lib in libraries if lib.status == "builtin")

    return LibraryCheckResponse(
        repo_id=repo_id,
        environment_id=environment_id,
        environment_name=env.name,
        total_libraries=len(libraries),
        missing_count=missing_count,
        installed_count=installed_count,
        builtin_count=builtin_count,
        libraries=libraries,
    )


# ---------------------------------------------------------------------------
# File operations (create, save, delete, rename, open)
# ---------------------------------------------------------------------------


@router.post("/{repo_id}/file", response_model=FileContent, status_code=status.HTTP_201_CREATED)
def create_new_file(
    repo_id: int,
    body: FileCreateRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Create a new file in the repository."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    try:
        return create_file(repo.local_path, body.path, body.content)
    except FileExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path traversal not allowed")


@router.put("/{repo_id}/file", response_model=FileContent)
def save_file(
    repo_id: int,
    body: FileSaveRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Save (overwrite) a file's content."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    try:
        return write_file(repo.local_path, body.path, body.content)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path traversal not allowed")


@router.delete("/{repo_id}/file", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_file(
    repo_id: int,
    path: str = Query(..., description="Relative path of the file to delete"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Delete a file from the repository."""
    repo = get_repository(db, repo_id)
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
def rename_existing_file(
    repo_id: int,
    body: FileRenameRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Rename or move a file within the repository."""
    repo = get_repository(db, repo_id)
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
def open_file_in_editor(
    repo_id: int,
    body: FileOpenRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Open a file in the system's default editor."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    try:
        open_in_editor(repo.local_path, body.path)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path traversal not allowed")


@router.post("/{repo_id}/folder/open", status_code=status.HTTP_204_NO_CONTENT)
def open_folder_in_file_browser(
    repo_id: int,
    body: FileOpenRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Open a folder in the system's file browser (Finder/Explorer/Nautilus)."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    try:
        open_in_file_browser(repo.local_path, body.path)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path traversal not allowed")
