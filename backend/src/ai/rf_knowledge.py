"""Optional rf-mcp bridge for Robot Framework domain knowledge.

Integrates rf-mcp (https://github.com/manykarim/rf-mcp) by Many Kasiriha —
a Model Context Protocol server that provides Robot Framework keyword
documentation, library recommendations, and scenario analysis.

If the rf-mcp server is configured (RF_MCP_URL), this module provides keyword
lookup, library recommendations, and scenario analysis to enrich LLM prompts.

If not configured, all functions return empty results gracefully.
"""

import logging
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger("roboscope.ai.rf_knowledge")

_REQUEST_ID_COUNTER = 0


def _next_request_id() -> int:
    global _REQUEST_ID_COUNTER
    _REQUEST_ID_COUNTER += 1
    return _REQUEST_ID_COUNTER


async def _call_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Call an rf-mcp tool via JSON-RPC 2.0 over HTTP.

    Returns the tool result or None on any failure.
    """
    from src.ai.rf_mcp_manager import get_effective_url

    url = get_effective_url()
    if not url:
        return None

    payload = {
        "jsonrpc": "2.0",
        "id": _next_request_id(),
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {},
        },
    }

    try:
        async with httpx.AsyncClient(timeout=settings.RF_MCP_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                logger.warning("rf-mcp error for %s: %s", tool_name, data["error"])
                return None

            result = data.get("result")
            # MCP tools/call returns {content: [{type, text}]}
            if isinstance(result, dict) and "content" in result:
                contents = result["content"]
                if isinstance(contents, list) and contents:
                    # Return text from first content block
                    first = contents[0]
                    if isinstance(first, dict) and "text" in first:
                        import json
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
