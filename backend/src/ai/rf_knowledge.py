"""Optional rf-mcp bridge for Robot Framework domain knowledge.

Integrates rf-mcp (https://github.com/manykarim/rf-mcp) by Many Kasiriha —
a Model Context Protocol server that provides Robot Framework keyword
documentation, library recommendations, and scenario analysis.

If the rf-mcp server is configured (RF_MCP_URL), this module provides keyword
lookup, library recommendations, and scenario analysis to enrich LLM prompts.

If not configured, all functions return empty results gracefully.

Uses the MCP Streamable HTTP transport protocol which requires:
1. Session initialization handshake (initialize → notifications/initialized)
2. Accept: application/json, text/event-stream on all requests
3. Mcp-Session-Id header after initialization
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger("roboscope.ai.rf_knowledge")

_REQUEST_ID_COUNTER = 0

# Cached MCP session state (reset on server restart)
_session_id: str | None = None
_session_url: str | None = None  # URL the session was created against

# Track which repos have had their keywords scanned
_imported_repos: set[int] = set()
_repo_keywords_cache: dict[int, list[dict]] = {}

# Cache for library keywords resolved via robot.libdocpkg
# Key: (frozenset of library names, venv_path)
_library_keywords_cache: dict[tuple[frozenset[str], str], list[dict]] = {}

_MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

_CLIENT_INFO = {
    "name": "RoboScope",
    "version": "1.0.0",
}


def _next_request_id() -> int:
    global _REQUEST_ID_COUNTER
    _REQUEST_ID_COUNTER += 1
    return _REQUEST_ID_COUNTER


def _parse_sse_response(text: str) -> dict | None:
    """Parse an SSE response and extract the JSON-RPC result message.

    SSE format:
        event: message
        data: {"jsonrpc":"2.0","id":1,"result":{...}}

    Returns the parsed JSON-RPC message dict, or None if no result found.
    """
    result_msg = None
    for line in text.splitlines():
        if line.startswith("data: "):
            data_str = line[6:]
            try:
                msg = json.loads(data_str)
                # Keep the last message that has an "id" (= JSON-RPC response, not notification)
                if isinstance(msg, dict) and "id" in msg:
                    result_msg = msg
            except (json.JSONDecodeError, TypeError):
                continue
    return result_msg


def _parse_response(response: httpx.Response) -> dict | None:
    """Parse an MCP HTTP response (either JSON or SSE)."""
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        return _parse_sse_response(response.text)
    # Plain JSON response
    try:
        return response.json()
    except Exception:
        return None


async def _ensure_session(client: httpx.AsyncClient, url: str) -> str | None:
    """Ensure we have a valid MCP session. Returns session ID or None."""
    global _session_id, _session_url

    # Reuse existing session if URL hasn't changed
    if _session_id and _session_url == url:
        return _session_id

    # Reset
    _session_id = None
    _session_url = None

    # Step 1: initialize
    init_payload = {
        "jsonrpc": "2.0",
        "id": _next_request_id(),
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": _CLIENT_INFO,
        },
    }

    try:
        resp = await client.post(url, json=init_payload, headers=_MCP_HEADERS)
        resp.raise_for_status()
    except Exception:
        logger.warning("rf-mcp initialize request failed")
        return None

    session_id = resp.headers.get("mcp-session-id")
    if not session_id:
        logger.warning("rf-mcp server did not return Mcp-Session-Id header")
        return None

    # Step 2: notifications/initialized
    notif_payload = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }
    headers = {**_MCP_HEADERS, "Mcp-Session-Id": session_id}

    try:
        resp = await client.post(url, json=notif_payload, headers=headers)
        # 202 Accepted is expected for notifications
    except Exception:
        logger.warning("rf-mcp initialized notification failed")
        return None

    _session_id = session_id
    _session_url = url
    logger.info("MCP session established: %s", session_id[:16])
    return session_id


def reset_session() -> None:
    """Reset the cached MCP session (e.g. when the server restarts)."""
    global _session_id, _session_url, _imported_repos, _repo_keywords_cache, _library_keywords_cache
    _session_id = None
    _session_url = None
    _imported_repos = set()
    _repo_keywords_cache = {}
    _library_keywords_cache = {}


async def _call_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Call an rf-mcp tool via MCP Streamable HTTP transport.

    Handles session initialization, proper headers, and SSE response parsing.
    Returns the tool result or None on any failure.
    """
    from src.ai.rf_mcp_manager import get_effective_url

    url = get_effective_url()
    if not url:
        return None

    try:
        async with httpx.AsyncClient(timeout=settings.RF_MCP_TIMEOUT) as client:
            # Ensure we have a valid session
            session_id = await _ensure_session(client, url)
            if not session_id:
                return None

            # Send tools/call
            payload = {
                "jsonrpc": "2.0",
                "id": _next_request_id(),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments or {},
                },
            }
            headers = {**_MCP_HEADERS, "Mcp-Session-Id": session_id}

            response = await client.post(url, json=payload, headers=headers)

            # If session expired, retry with new session
            if response.status_code in (400, 404):
                reset_session()
                session_id = await _ensure_session(client, url)
                if not session_id:
                    return None
                headers = {**_MCP_HEADERS, "Mcp-Session-Id": session_id}
                response = await client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            data = _parse_response(response)

            if data is None:
                logger.warning("rf-mcp: could not parse response for %s", tool_name)
                return None

            if "error" in data:
                logger.warning("rf-mcp error for %s: %s", tool_name, data["error"])
                return None

            result = data.get("result")
            # MCP tools/call returns {content: [{type, text}]}
            if isinstance(result, dict) and "content" in result:
                contents = result["content"]
                if isinstance(contents, list) and contents:
                    first = contents[0]
                    if isinstance(first, dict) and "text" in first:
                        try:
                            return json.loads(first["text"])
                        except (json.JSONDecodeError, TypeError):
                            return first["text"]
            return result

    except httpx.TimeoutException:
        logger.warning("rf-mcp timeout calling %s", tool_name)
        return None
    except httpx.HTTPStatusError as e:
        logger.warning("rf-mcp HTTP error calling %s: %s", tool_name, e)
        return None
    except Exception:
        logger.exception("rf-mcp unexpected error calling %s", tool_name)
        return None


def is_available() -> bool:
    """Check if rf-mcp is available (managed server running or URL configured)."""
    from src.ai.rf_mcp_manager import get_effective_url

    return bool(get_effective_url())


_RF_BUILTINS = frozenset({
    "builtin", "collections", "datetime", "dialogs", "operatingsystem",
    "process", "string", "telnet", "xml",
})


def _scan_repo_files(repo_id: int) -> tuple[list[dict], set[str]]:
    """Scan a repo's .robot/.resource files.

    Returns (user_keywords, library_imports).
    Cached per repo_id.
    """
    global _imported_repos

    if repo_id in _imported_repos:
        return _repo_keywords_cache.get(repo_id, ([], set()))

    from sqlalchemy import select

    import src.auth.models  # noqa: F401
    from src.database import get_sync_session
    from src.repos.models import Repository

    with get_sync_session() as session:
        repo = session.execute(
            select(Repository).where(Repository.id == repo_id)
        ).scalar_one_or_none()
        if not repo or not repo.local_path:
            _imported_repos.add(repo_id)
            return [], set()
        local_path = repo.local_path

    repo_dir = Path(local_path)
    if not repo_dir.is_dir():
        _imported_repos.add(repo_id)
        return [], set()

    files = list(repo_dir.rglob("*.resource")) + list(repo_dir.rglob("*.robot"))
    keywords: list[dict] = []
    library_imports: set[str] = set()
    seen_kw: set[str] = set()

    for f in files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        in_settings = False
        in_keywords = False
        current_kw: dict | None = None

        for line in content.splitlines():
            stripped = line.strip()

            if stripped.startswith("***"):
                lower = stripped.lower().replace("*", "").strip()
                # Flush pending keyword
                if current_kw and current_kw["name"].lower() not in seen_kw:
                    seen_kw.add(current_kw["name"].lower())
                    keywords.append(current_kw)
                current_kw = None
                in_settings = lower in ("settings", "setting")
                in_keywords = lower in ("keywords", "keyword")
                continue

            # Parse Library imports from Settings
            if in_settings and stripped.lower().startswith("library"):
                parts = stripped.split(None, 1)
                if len(parts) >= 2:
                    lib_name = parts[1].split("  ")[0].split("\t")[0].strip()
                    if lib_name and lib_name.lower() not in _RF_BUILTINS:
                        library_imports.add(lib_name)

            # Parse Keywords
            if not in_keywords:
                continue
            if stripped and not line[0].isspace():
                if current_kw and current_kw["name"].lower() not in seen_kw:
                    seen_kw.add(current_kw["name"].lower())
                    keywords.append(current_kw)
                current_kw = {"name": stripped, "library": f.stem, "doc": "", "args": []}
            elif current_kw and stripped.lower().startswith("[documentation]"):
                doc = stripped.split("]", 1)[1].strip() if "]" in stripped else ""
                current_kw["doc"] = doc[:200]
            elif current_kw and stripped.lower().startswith("[arguments]"):
                args_str = stripped.split("]", 1)[1].strip() if "]" in stripped else ""
                if args_str:
                    # Split on 2+ spaces or tabs (RF cell separator)
                    parts = args_str.replace("\t", "  ").split("  ")
                    current_kw["args"] = [a.strip() for a in parts if a.strip()]

        if current_kw and current_kw["name"].lower() not in seen_kw:
            seen_kw.add(current_kw["name"].lower())
            keywords.append(current_kw)

    _repo_keywords_cache[repo_id] = (keywords, library_imports)
    _imported_repos.add(repo_id)
    logger.info(
        "Scanned repo %d: %d keywords, %d library imports from %d files",
        repo_id, len(keywords), len(library_imports), len(files),
    )
    return keywords, library_imports


def _resolve_library_keywords(library_names: set[str], venv_path: str) -> list[dict]:
    """Resolve keyword names from installed libraries using robot.libdocpkg.

    Runs a subprocess in the environment's Python to introspect libraries.
    Results are cached.
    """
    if not library_names or not venv_path:
        return []

    cache_key = (frozenset(library_names), venv_path)
    if cache_key in _library_keywords_cache:
        return _library_keywords_cache[cache_key]

    from src.environments.venv_utils import get_python_path

    python_path = get_python_path(venv_path)
    if not Path(python_path).exists():
        _library_keywords_cache[cache_key] = []
        return []

    script = (
        "import json, sys\n"
        "results = []\n"
        "for lib_name in sys.argv[1:]:\n"
        "    try:\n"
        "        from robot.libdocpkg import LibraryDocumentation\n"
        "        libdoc = LibraryDocumentation(lib_name)\n"
        "        for kw in libdoc.keywords:\n"
        "            kw_args = [str(a) for a in (kw.args or [])]\n"
        "            results.append({'name': kw.name, 'library': lib_name, 'doc': (kw.doc or '')[:200], 'args': kw_args})\n"
        "    except Exception:\n"
        "        pass\n"
        "print(json.dumps(results))\n"
    )

    try:
        result = subprocess.run(
            [python_path, "-c", script, *library_names],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            kws = json.loads(result.stdout.strip())
            _library_keywords_cache[cache_key] = kws
            logger.info("Resolved %d keywords from %d libraries", len(kws), len(library_names))
            return kws
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        logger.warning("Failed to resolve library keywords: %s", e)

    _library_keywords_cache[cache_key] = []
    return []


def _get_repo_env_venv_path(repo_id: int) -> str | None:
    """Get the venv_path for a repo's assigned environment."""
    from sqlalchemy import select

    import src.auth.models  # noqa: F401
    from src.database import get_sync_session
    from src.repos.models import Repository

    with get_sync_session() as session:
        repo = session.execute(
            select(Repository).where(Repository.id == repo_id)
        ).scalar_one_or_none()
        if not repo or not repo.environment_id:
            return None

        from src.environments.models import Environment
        env = session.execute(
            select(Environment).where(Environment.id == repo.environment_id)
        ).scalar_one_or_none()
        return env.venv_path if env else None


def invalidate_repo_cache(repo_id: int) -> None:
    """Clear keyword cache for a repo so next search re-scans files and libraries."""
    global _imported_repos
    _imported_repos.discard(repo_id)
    _repo_keywords_cache.pop(repo_id, None)
    # Also clear library keyword caches that may include this repo's venv
    venv_path = _get_repo_env_venv_path(repo_id)
    if venv_path:
        stale = [k for k in _library_keywords_cache if k[1] == venv_path]
        for k in stale:
            del _library_keywords_cache[k]
    logger.info("Invalidated keyword cache for repo %d", repo_id)


def _get_env_installed_libraries(venv_path: str) -> set[str]:
    """Discover all RF-related libraries installed in the venv.

    Uses `pip list` output and heuristics to find Robot Framework library packages.
    """
    from src.environments.venv_utils import get_python_path

    python_path = get_python_path(venv_path)
    if not Path(python_path).exists():
        return set()

    # Use robot's own discovery to find all available libraries
    script = (
        "import json, sys, pkgutil, importlib\n"
        "libs = set()\n"
        "# Check common RF library naming patterns from pip\n"
        "try:\n"
        "    import subprocess\n"
        "    result = subprocess.run([sys.executable, '-m', 'pip', 'list', '--format=json'],\n"
        "                            capture_output=True, text=True, timeout=15)\n"
        "    if result.returncode == 0:\n"
        "        for pkg in __import__('json').loads(result.stdout):\n"
        "            name = pkg['name'].lower()\n"
        "            if name.startswith('robotframework-'):\n"
        "                # e.g. robotframework-browser -> Browser\n"
        "                lib = name.replace('robotframework-', '')\n"
        "                # Title-case the library name for RF import\n"
        "                libs.add(lib.title().replace('-', ''))\n"
        "except Exception:\n"
        "    pass\n"
        "print(json.dumps(sorted(libs)))\n"
    )
    try:
        result = subprocess.run(
            [python_path, "-c", script],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode == 0 and result.stdout.strip():
            names = json.loads(result.stdout.strip())
            logger.info("Discovered %d RF libraries in venv %s", len(names), venv_path)
            return set(names)
    except Exception as e:
        logger.warning("Failed to discover installed libraries: %s", e)
    return set()


async def search_keywords(query: str, repo_id: int | None = None) -> list[dict]:
    """Search for Robot Framework keywords matching a query.

    Combines three sources (no rf-mcp needed):
    1. User-defined keywords from repo .robot/.resource files
    2. Library keywords from ALL installed RF packages in the environment
    3. rf-mcp built-in keywords (optional fallback)

    Returns a list of dicts with keys: name, library, doc.
    """
    results: list[dict] = []
    seen: set[str] = set()
    query_lower = query.lower().strip()
    match_all = query_lower in ("*", "")

    if repo_id is not None:
        # 1. Custom keywords from repo files
        custom_keywords, library_imports = _scan_repo_files(repo_id)
        for kw in custom_keywords:
            name_lower = kw["name"].lower()
            if match_all or query_lower in name_lower or name_lower in query_lower:
                seen.add(name_lower)
                results.append(kw)

        # 2. Library keywords — scan ALL installed RF packages, not just imported ones
        venv_path = _get_repo_env_venv_path(repo_id)
        if venv_path:
            # Merge explicitly imported libraries with all installed RF packages
            all_libraries = library_imports | _get_env_installed_libraries(venv_path)
            if all_libraries:
                lib_keywords = _resolve_library_keywords(all_libraries, venv_path)
                for kw in lib_keywords:
                    name_lower = kw["name"].lower()
                    if match_all or query_lower in name_lower or name_lower in query_lower:
                        if name_lower not in seen:
                            seen.add(name_lower)
                            results.append(kw)

    # 3. Optional: rf-mcp for built-in keyword semantic search
    if is_available():
        mcp_result = await _call_mcp_tool("find_keywords", {"query": query})
        if isinstance(mcp_result, dict):
            matches = (
                mcp_result.get("result", {}).get("matches", [])
                if isinstance(mcp_result.get("result"), dict)
                else []
            )
            if not matches:
                matches = mcp_result.get("results", mcp_result.get("matches", []))
            for m in matches if isinstance(matches, list) else []:
                name = m.get("keyword_name", m.get("name", ""))
                if name.lower() not in seen:
                    seen.add(name.lower())
                    results.append({
                        "name": name,
                        "library": m.get("library", ""),
                        "doc": (m.get("documentation", "") or "")[:200],
                    })

    return results


async def get_keyword_docs(keyword_name: str) -> str | None:
    """Get documentation for a specific keyword.

    Returns the documentation string or None.
    """
    if not is_available():
        return None

    result = await _call_mcp_tool("get_keyword_info", {"keyword_name": keyword_name})
    if isinstance(result, str):
        return result
    if isinstance(result, dict) and "doc" in result:
        return result["doc"]
    return None


async def recommend_libraries(description: str) -> list[str]:
    """Suggest RF libraries based on test description.

    Returns a list of library name strings.
    """
    if not is_available():
        return []

    result = await _call_mcp_tool("recommend_libraries", {"description": description})
    if isinstance(result, list):
        return [str(item) for item in result]
    if isinstance(result, dict) and "libraries" in result:
        return [str(item) for item in result["libraries"]]
    return []


async def analyze_scenario(steps: list[str]) -> list[dict]:
    """Pre-process natural language steps via rf-mcp.

    Returns a list of enrichment dicts with keyword suggestions per step.
    """
    if not is_available():
        return []

    result = await _call_mcp_tool("analyze_scenario", {"steps": steps})
    if isinstance(result, list):
        return result
    if isinstance(result, dict) and "steps" in result:
        return result["steps"]
    return []
