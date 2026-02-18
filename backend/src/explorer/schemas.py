"""Pydantic schemas for the test explorer."""

from pydantic import BaseModel


class TreeNode(BaseModel):
    """A node in the file tree."""

    name: str
    path: str
    type: str  # "file" or "directory"
    extension: str | None = None
    children: list["TreeNode"] | None = None
    test_count: int = 0


class FileContent(BaseModel):
    """Content of a file."""

    path: str
    name: str
    content: str
    extension: str | None = None
    line_count: int = 0


class TestCaseInfo(BaseModel):
    """Information about a single test case."""

    name: str
    file_path: str
    suite_name: str
    tags: list[str] = []
    documentation: str = ""
    line_number: int = 0


class SearchResult(BaseModel):
    """Search result item."""

    type: str  # "testcase", "keyword", "file"
    name: str
    file_path: str
    line_number: int = 0
    context: str = ""


class ExplorerQuery(BaseModel):
    """Query parameters for explorer search."""

    q: str
    file_type: str | None = None  # "robot", "resource", "library", "variable"
    tags: list[str] | None = None


class FileCreateRequest(BaseModel):
    """Request to create a new file."""

    path: str
    content: str = ""


class FileSaveRequest(BaseModel):
    """Request to save file content."""

    path: str
    content: str


class FileRenameRequest(BaseModel):
    """Request to rename a file."""

    old_path: str
    new_path: str


class FileOpenRequest(BaseModel):
    """Request to open a file in the system editor."""

    path: str
