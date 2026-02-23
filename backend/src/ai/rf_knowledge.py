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
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger("roboscope.ai.rf_knowledge")

_REQUEST_ID_COUNTER = 0

# Cached MCP session state (reset on server restart)
_session_id: str | None = None
_session_url: str | None = None  # URL the session was created against

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
    global _session_id, _session_url
    _session_id = None
    _session_url = None


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


async def search_keywords(query: str) -> list[dict]:
    """Search for Robot Framework keywords matching a query.

    Returns a list of dicts with keys: name, library, doc (or empty list).
    """
    if not is_available():
        return []

    result = await _call_mcp_tool("search_keyword", {"query": query})
    if isinstance(result, list):
        return result
    if isinstance(result, dict) and "results" in result:
        return result["results"]
    return []


async def get_keyword_docs(keyword_name: str) -> str | None:
    """Get documentation for a specific keyword.

    Returns the documentation string or None.
    """
    if not is_available():
        return None

    result = await _call_mcp_tool("get_keyword_doc", {"keyword": keyword_name})
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
