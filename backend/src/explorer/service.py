"""Explorer service: filesystem traversal, Robot file parsing, file operations."""

import platform
import re
import subprocess
from pathlib import Path

from src.explorer.schemas import FileContent, SearchResult, TestCaseInfo, TreeNode

# Directories and files to skip in the tree
IGNORE_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".tox", ".pytest_cache", ".mypy_cache"}
IGNORE_FILES = {".gitignore", ".DS_Store", "Thumbs.db"}

# Robot Framework file extensions
ROBOT_EXTENSIONS = {".robot", ".resource", ".py", ".yaml", ".yml"}


def build_tree(base_path: str, relative_path: str = "") -> TreeNode:
    """Build a file tree from a directory, filtering irrelevant files."""
    root = Path(base_path) / relative_path if relative_path else Path(base_path)

    if not root.exists() or not root.is_dir():
        return TreeNode(name=root.name, path=relative_path, type="directory", children=[])

    children: list[TreeNode] = []

    for item in sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if item.name in IGNORE_DIRS or item.name in IGNORE_FILES:
            continue
        if item.name.startswith(".") and item.is_dir():
            continue

        rel = str(item.relative_to(Path(base_path)))

        if item.is_dir():
            child = build_tree(base_path, rel)
            # Count tests recursively
            child.test_count = _count_tests_in_tree(child)
            children.append(child)
        else:
            ext = item.suffix.lower()
            test_count = 0
            if ext == ".robot":
                test_count = _count_tests_in_file(str(item))
            children.append(
                TreeNode(
                    name=item.name,
                    path=rel,
                    type="file",
                    extension=ext,
                    test_count=test_count,
                )
            )

    return TreeNode(
        name=root.name,
        path=relative_path or ".",
        type="directory",
        children=children,
    )


def _count_tests_in_tree(node: TreeNode) -> int:
    """Count total tests in a tree node recursively."""
    count = node.test_count
    if node.children:
        for child in node.children:
            count += _count_tests_in_tree(child) if child.type == "directory" else child.test_count
    return count


def _count_tests_in_file(file_path: str) -> int:
    """Count test cases in a robot file."""
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        in_test_section = False
        count = 0
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("*** test case"):
                in_test_section = True
                continue
            if stripped.startswith("***"):
                in_test_section = False
                continue
            if in_test_section and stripped and not stripped.startswith("#") and not line.startswith((" ", "\t")):
                count += 1
        return count
    except Exception:
        return 0


def read_file(base_path: str, relative_path: str) -> FileContent:
    """Read a file's content safely (preventing path traversal)."""
    base = Path(base_path).resolve()
    target = (base / relative_path).resolve()

    # Path traversal protection
    if not str(target).startswith(str(base)):
        raise ValueError("Path traversal detected")

    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"File not found: {relative_path}")

    content = target.read_text(encoding="utf-8", errors="replace")
    return FileContent(
        path=relative_path,
        name=target.name,
        content=content,
        extension=target.suffix.lower(),
        line_count=len(content.splitlines()),
    )


def parse_robot_testcases(base_path: str, relative_path: str) -> list[TestCaseInfo]:
    """Parse test cases from a .robot file."""
    full_path = Path(base_path) / relative_path
    if not full_path.exists():
        return []

    content = full_path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    suite_name = full_path.stem

    testcases: list[TestCaseInfo] = []
    in_test_section = False
    current_test: dict | None = None

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        if stripped.lower().startswith("*** test case"):
            in_test_section = True
            continue
        if stripped.startswith("***"):
            if current_test:
                testcases.append(TestCaseInfo(**current_test))
                current_test = None
            in_test_section = False
            continue

        if not in_test_section:
            continue

        if stripped and not line.startswith((" ", "\t")) and not stripped.startswith("#"):
            # New test case
            if current_test:
                testcases.append(TestCaseInfo(**current_test))
            current_test = {
                "name": stripped,
                "file_path": relative_path,
                "suite_name": suite_name,
                "tags": [],
                "documentation": "",
                "line_number": i,
            }
        elif current_test and stripped.lower().startswith("[tags]"):
            tags_str = stripped[6:].strip()
            current_test["tags"] = [t.strip() for t in tags_str.split("    ") if t.strip()]
        elif current_test and stripped.lower().startswith("[documentation]"):
            current_test["documentation"] = stripped[15:].strip()

    if current_test:
        testcases.append(TestCaseInfo(**current_test))

    return testcases


def search_in_repo(base_path: str, query: str, file_type: str | None = None) -> list[SearchResult]:
    """Search for test cases, keywords, and files matching a query."""
    results: list[SearchResult] = []
    base = Path(base_path)
    query_lower = query.lower()

    # Determine which extensions to search
    extensions = ROBOT_EXTENSIONS
    if file_type == "robot":
        extensions = {".robot"}
    elif file_type == "resource":
        extensions = {".resource"}
    elif file_type == "library":
        extensions = {".py"}
    elif file_type == "variable":
        extensions = {".yaml", ".yml", ".py"}

    for file_path in base.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in extensions:
            continue
        if any(part in IGNORE_DIRS for part in file_path.parts):
            continue

        rel_path = str(file_path.relative_to(base))

        # Match filename
        if query_lower in file_path.name.lower():
            results.append(SearchResult(
                type="file",
                name=file_path.name,
                file_path=rel_path,
            ))

        # Search file content
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(content.splitlines(), 1):
                if query_lower in line.lower():
                    # Determine type based on context
                    result_type = "file"
                    if file_path.suffix == ".robot":
                        stripped = line.strip()
                        if not line.startswith((" ", "\t")) and stripped and not stripped.startswith(("*", "#")):
                            result_type = "testcase"

                    results.append(SearchResult(
                        type=result_type,
                        name=line.strip()[:100],
                        file_path=rel_path,
                        line_number=i,
                        context=line.strip()[:200],
                    ))
        except Exception:
            continue

        if len(results) >= 100:
            break

    return results


def list_all_testcases(base_path: str) -> list[TestCaseInfo]:
    """List all test cases in a repository."""
    base = Path(base_path)
    testcases: list[TestCaseInfo] = []

    for robot_file in base.rglob("*.robot"):
        if any(part in IGNORE_DIRS for part in robot_file.parts):
            continue
        rel_path = str(robot_file.relative_to(base))
        testcases.extend(parse_robot_testcases(base_path, rel_path))

    return testcases


# ---------------------------------------------------------------------------
# File operations (create, save, delete, rename, open in editor)
# ---------------------------------------------------------------------------


def _safe_resolve(base_path: str, relative_path: str) -> Path:
    """Resolve a path safely, preventing path traversal."""
    base = Path(base_path).resolve()
    target = (base / relative_path).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError("Path traversal detected")
    return target


def create_file(base_path: str, relative_path: str, content: str = "") -> FileContent:
    """Create a new file. Parent directories are created automatically."""
    target = _safe_resolve(base_path, relative_path)
    if target.exists():
        raise FileExistsError(f"File already exists: {relative_path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return FileContent(
        path=relative_path,
        name=target.name,
        content=content,
        extension=target.suffix.lower() if target.suffix else None,
        line_count=len(content.splitlines()),
    )


def write_file(base_path: str, relative_path: str, content: str) -> FileContent:
    """Overwrite an existing file's content."""
    target = _safe_resolve(base_path, relative_path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"File not found: {relative_path}")
    target.write_text(content, encoding="utf-8")
    return FileContent(
        path=relative_path,
        name=target.name,
        content=content,
        extension=target.suffix.lower() if target.suffix else None,
        line_count=len(content.splitlines()),
    )


def delete_file(base_path: str, relative_path: str) -> None:
    """Delete a file or empty directory."""
    target = _safe_resolve(base_path, relative_path)
    if not target.exists():
        raise FileNotFoundError(f"Not found: {relative_path}")
    if target.is_file():
        target.unlink()
    elif target.is_dir():
        # Only delete if empty (safety measure)
        children = list(target.iterdir())
        if children:
            raise PermissionError("Directory is not empty")
        target.rmdir()
    else:
        raise ValueError("Unsupported file type")


def rename_file(base_path: str, old_path: str, new_path: str) -> FileContent:
    """Rename / move a file within the repo."""
    source = _safe_resolve(base_path, old_path)
    dest = _safe_resolve(base_path, new_path)
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {old_path}")
    if dest.exists():
        raise FileExistsError(f"Destination already exists: {new_path}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    source.rename(dest)
    content = dest.read_text(encoding="utf-8", errors="replace") if dest.is_file() else ""
    return FileContent(
        path=new_path,
        name=dest.name,
        content=content,
        extension=dest.suffix.lower() if dest.suffix else None,
        line_count=len(content.splitlines()),
    )


def open_in_editor(base_path: str, relative_path: str) -> None:
    """Open a file in the system's default editor."""
    target = _safe_resolve(base_path, relative_path)
    if not target.exists():
        raise FileNotFoundError(f"File not found: {relative_path}")
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", str(target)])
    elif system == "Windows":
        subprocess.Popen(["start", "", str(target)], shell=True)
    else:
        subprocess.Popen(["xdg-open", str(target)])
