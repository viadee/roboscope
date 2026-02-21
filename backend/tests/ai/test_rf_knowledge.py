"""Unit tests for the rf-mcp knowledge bridge (mocked httpx)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai import rf_knowledge


def _make_mcp_response(result_data):
    """Create a mock httpx response with JSON-RPC result."""
    response = MagicMock()
    response.json.return_value = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [
                {"type": "text", "text": json.dumps(result_data)}
            ]
        },
    }
    response.raise_for_status = MagicMock()
    return response


def _mock_httpx_client(mock_response):
    """Patch httpx.AsyncClient to return a mock that yields mock_response on post()."""
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


MCP_URL = "http://localhost:9090/mcp"


class TestIsAvailable:
    def test_available_when_url_set(self):
        with patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL):
            assert rf_knowledge.is_available() is True

    def test_unavailable_when_url_empty(self):
        with patch("src.ai.rf_mcp_manager.get_effective_url", return_value=""):
            assert rf_knowledge.is_available() is False


class TestSearchKeywords:
    @pytest.mark.asyncio
    async def test_returns_empty_when_unavailable(self):
        with patch("src.ai.rf_mcp_manager.get_effective_url", return_value=""):
            result = await rf_knowledge.search_keywords("click")
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_results_from_mcp(self):
        keywords = [
            {"name": "Click Element", "library": "SeleniumLibrary", "doc": "Clicks an element"},
            {"name": "Click Button", "library": "SeleniumLibrary", "doc": "Clicks a button"},
        ]
        mock_resp = _make_mcp_response(keywords)

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=_mock_httpx_client(mock_resp)),
        ):
            mock_settings.RF_MCP_TIMEOUT = 10
            result = await rf_knowledge.search_keywords("click")
            assert len(result) == 2
            assert result[0]["name"] == "Click Element"


class TestGetKeywordDocs:
    @pytest.mark.asyncio
    async def test_returns_none_when_unavailable(self):
        with patch("src.ai.rf_mcp_manager.get_effective_url", return_value=""):
            result = await rf_knowledge.get_keyword_docs("Click Element")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_doc_string(self):
        mock_resp = _make_mcp_response({"doc": "Clicks the element identified by locator."})

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=_mock_httpx_client(mock_resp)),
        ):
            mock_settings.RF_MCP_TIMEOUT = 10
            result = await rf_knowledge.get_keyword_docs("Click Element")
            assert result == "Clicks the element identified by locator."


class TestRecommendLibraries:
    @pytest.mark.asyncio
    async def test_returns_empty_when_unavailable(self):
        with patch("src.ai.rf_mcp_manager.get_effective_url", return_value=""):
            result = await rf_knowledge.recommend_libraries("web testing")
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_library_list(self):
        mock_resp = _make_mcp_response(["SeleniumLibrary", "Browser"])

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=_mock_httpx_client(mock_resp)),
        ):
            mock_settings.RF_MCP_TIMEOUT = 10
            result = await rf_knowledge.recommend_libraries("web testing")
            assert result == ["SeleniumLibrary", "Browser"]


class TestAnalyzeScenario:
    @pytest.mark.asyncio
    async def test_returns_empty_when_unavailable(self):
        with patch("src.ai.rf_mcp_manager.get_effective_url", return_value=""):
            result = await rf_knowledge.analyze_scenario(["Click login button"])
            assert result == []


class TestMcpToolGracefulFailure:
    @pytest.mark.asyncio
    async def test_timeout_returns_none(self):
        """MCP call should return None on timeout."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_client)
        cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=cm),
        ):
            mock_settings.RF_MCP_TIMEOUT = 1
            result = await rf_knowledge._call_mcp_tool("test_tool")
            assert result is None

    @pytest.mark.asyncio
    async def test_mcp_error_response_returns_none(self):
        """MCP error response should return None gracefully."""
        response = MagicMock()
        response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "Invalid Request"},
        }
        response.raise_for_status = MagicMock()

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=_mock_httpx_client(response)),
        ):
            mock_settings.RF_MCP_TIMEOUT = 10
            result = await rf_knowledge._call_mcp_tool("test_tool")
            assert result is None
