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

    root_node = TreeNode(
        name=root.name,
        path=relative_path or ".",
        type="directory",
        children=children,
        test_count=sum(c.test_count for c in children),
    )
    return root_node



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


def extract_libraries(base_path: str) -> list[dict]:
    """Scan all .robot/.resource files and extract Library imports from *** Settings ***."""
    base = Path(base_path)
    library_map: dict[str, set[str]] = {}  # library_name -> set of files

    for file_path in base.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in {".robot", ".resource"}:
            continue
        if any(part in IGNORE_DIRS for part in file_path.parts):
            continue

        rel_path = str(file_path.relative_to(base))

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            in_settings = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.lower().startswith("*** settings") or stripped.lower().startswith("*** setting"):
                    in_settings = True
                    continue
                if stripped.startswith("***"):
                    in_settings = False
                    continue
                if not in_settings:
                    continue
                if not stripped or stripped.startswith("#"):
                    continue

                # Split on 2+ spaces or tabs
                parts = re.split(r"  +|\t+", stripped)
                if parts and parts[0].lower() == "library" and len(parts) > 1:
                    lib_name = parts[1].strip()
                    if lib_name:
                        if lib_name not in library_map:
                            library_map[lib_name] = set()
                        library_map[lib_name].add(rel_path)
        except Exception:
            continue

    return [
        {"library_name": name, "files": sorted(files)}
        for name, files in sorted(library_map.items())
    ]


def check_libraries_against_env(
    base_path: str, installed_packages: list[dict]
) -> list[dict]:
    """Check extracted libraries against installed packages in an environment.

    Args:
        base_path: Repository local path.
        installed_packages: List of dicts with 'name' and 'version' keys from pip list.

    Returns:
        List of dicts with library_name, pypi_package, status, installed_version, files.
    """
    from src.explorer.library_mapping import BUILTIN_LIBRARIES, resolve_pypi_package

    libraries = extract_libraries(base_path)

    # Normalize installed packages for lookup: lower + replace - with _
    installed_map: dict[str, str] = {}
    for pkg in installed_packages:
        normalized = pkg.get("name", "").lower().replace("-", "_")
        installed_map[normalized] = pkg.get("version", "")

    results: list[dict] = []
    for lib in libraries:
        lib_name = lib["library_name"]

        if lib_name in BUILTIN_LIBRARIES:
            results.append({
                "library_name": lib_name,
                "pypi_package": None,
                "status": "builtin",
                "installed_version": None,
                "files": lib["files"],
            })
            continue

        pypi_package = resolve_pypi_package(lib_name)
        if pypi_package is None:
            # Path-based or relative import, treat as builtin/skip
            results.append({
                "library_name": lib_name,
                "pypi_package": None,
                "status": "builtin",
                "installed_version": None,
                "files": lib["files"],
            })
            continue

        # Check if installed (normalize pypi_package for comparison)
        normalized_pypi = pypi_package.lower().replace("-", "_")
        if normalized_pypi in installed_map:
            results.append({
                "library_name": lib_name,
                "pypi_package": pypi_package,
                "status": "installed",
                "installed_version": installed_map[normalized_pypi],
                "files": lib["files"],
            })
        else:
            results.append({
                "library_name": lib_name,
                "pypi_package": pypi_package,
                "status": "missing",
                "installed_version": None,
                "files": lib["files"],
            })

    return results


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


def open_in_file_browser(base_path: str, relative_path: str) -> None:
    """Open a folder in the system's file browser (Finder/Explorer/Nautilus)."""
    target = _safe_resolve(base_path, relative_path)
    if not target.exists():
        raise FileNotFoundError(f"Not found: {relative_path}")
    # For files, open the containing directory
    folder = target if target.is_dir() else target.parent
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", str(folder)])
    elif system == "Windows":
        subprocess.Popen(["explorer", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])
