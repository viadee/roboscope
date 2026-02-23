"""Unit tests for the rf-mcp knowledge bridge (mocked httpx)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.ai import rf_knowledge

MCP_URL = "http://localhost:9090/mcp"
SESSION_ID = "test-session-abc123"


def _make_init_response():
    """Create a mock response for the MCP initialize handshake."""
    response = MagicMock()
    response.status_code = 200
    response.headers = {"mcp-session-id": SESSION_ID, "content-type": "application/json"}
    response.json.return_value = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "rf-mcp", "version": "1.0.0"},
        },
    }
    response.raise_for_status = MagicMock()
    return response


def _make_notif_response():
    """Create a mock 202 response for notifications/initialized."""
    response = MagicMock()
    response.status_code = 202
    response.raise_for_status = MagicMock()
    return response


def _make_tool_response(result_data):
    """Create a mock httpx response for a tools/call JSON-RPC result."""
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    response.json.return_value = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [
                {"type": "text", "text": json.dumps(result_data)}
            ]
        },
    }
    response.raise_for_status = MagicMock()
    return response


def _make_tool_error_response():
    """Create a mock JSON-RPC error response."""
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    response.json.return_value = {
        "jsonrpc": "2.0",
        "id": 2,
        "error": {"code": -32600, "message": "Invalid Request"},
    }
    response.raise_for_status = MagicMock()
    return response


def _make_sse_tool_response(result_data):
    """Create a mock SSE-formatted response for tools/call."""
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "text/event-stream"}
    json_result = json.dumps({
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [
                {"type": "text", "text": json.dumps(result_data)}
            ]
        },
    })
    response.text = f"event: message\ndata: {json_result}\n\n"
    response.raise_for_status = MagicMock()
    return response


def _mock_client_with_responses(*responses):
    """Create an httpx.AsyncClient mock that returns responses in sequence."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=list(responses))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, mock_client


@pytest.fixture(autouse=True)
def _reset_session():
    """Reset MCP session state before each test."""
    rf_knowledge.reset_session()
    yield
    rf_knowledge.reset_session()


class TestIsAvailable:
    def test_available_when_url_set(self):
        with patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL):
            assert rf_knowledge.is_available() is True

    def test_unavailable_when_url_empty(self):
        with patch("src.ai.rf_mcp_manager.get_effective_url", return_value=""):
            assert rf_knowledge.is_available() is False


class TestResetSession:
    def test_reset_clears_state(self):
        rf_knowledge._session_id = "old-session"
        rf_knowledge._session_url = "http://old"
        rf_knowledge.reset_session()
        assert rf_knowledge._session_id is None
        assert rf_knowledge._session_url is None


class TestParseSSEResponse:
    def test_parses_single_event(self):
        text = 'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n'
        result = rf_knowledge._parse_sse_response(text)
        assert result == {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}

    def test_ignores_notifications(self):
        text = (
            'event: message\ndata: {"jsonrpc":"2.0","method":"notifications/progress","params":{}}\n\n'
            'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"done":true}}\n\n'
        )
        result = rf_knowledge._parse_sse_response(text)
        # Should return the message with "id" (response), not the notification
        assert result["id"] == 1
        assert result["result"] == {"done": True}

    def test_returns_none_for_empty(self):
        assert rf_knowledge._parse_sse_response("") is None

    def test_handles_malformed_json(self):
        text = "event: message\ndata: not-json\n\n"
        assert rf_knowledge._parse_sse_response(text) is None


class TestEnsureSession:
    @pytest.mark.asyncio
    async def test_creates_session(self):
        cm, mock_client = _mock_client_with_responses(
            _make_init_response(),
            _make_notif_response(),
        )
        async with cm as client:
            session_id = await rf_knowledge._ensure_session(client, MCP_URL)
            assert session_id == SESSION_ID
            assert rf_knowledge._session_id == SESSION_ID
            assert rf_knowledge._session_url == MCP_URL

    @pytest.mark.asyncio
    async def test_reuses_cached_session(self):
        rf_knowledge._session_id = SESSION_ID
        rf_knowledge._session_url = MCP_URL

        mock_client = AsyncMock()
        session_id = await rf_knowledge._ensure_session(mock_client, MCP_URL)
        assert session_id == SESSION_ID
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_reinitializes_on_url_change(self):
        rf_knowledge._session_id = "old-session"
        rf_knowledge._session_url = "http://old:9090/mcp"

        cm, mock_client = _mock_client_with_responses(
            _make_init_response(),
            _make_notif_response(),
        )
        async with cm as client:
            session_id = await rf_knowledge._ensure_session(client, MCP_URL)
            assert session_id == SESSION_ID
            assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_on_init_failure(self):
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("refused")

        session_id = await rf_knowledge._ensure_session(mock_client, MCP_URL)
        assert session_id is None
        assert rf_knowledge._session_id is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_session_header(self):
        response = MagicMock()
        response.status_code = 200
        response.headers = {}  # No mcp-session-id
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)

        session_id = await rf_knowledge._ensure_session(mock_client, MCP_URL)
        assert session_id is None


class TestCallMcpTool:
    @pytest.mark.asyncio
    async def test_full_handshake_and_tool_call(self):
        """Full flow: initialize → initialized → tools/call."""
        tool_result = [{"name": "Click Element", "library": "SeleniumLibrary"}]
        cm, mock_client = _mock_client_with_responses(
            _make_init_response(),
            _make_notif_response(),
            _make_tool_response(tool_result),
        )

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=cm),
        ):
            mock_settings.RF_MCP_TIMEOUT = 10
            result = await rf_knowledge._call_mcp_tool("search_keyword", {"query": "click"})
            assert result == tool_result
            assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_reuses_session_on_second_call(self):
        """Second call should skip initialization."""
        # Pre-set session
        rf_knowledge._session_id = SESSION_ID
        rf_knowledge._session_url = MCP_URL

        tool_result = {"doc": "Clicks element"}
        cm, mock_client = _mock_client_with_responses(
            _make_tool_response(tool_result),
        )

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=cm),
        ):
            mock_settings.RF_MCP_TIMEOUT = 10
            result = await rf_knowledge._call_mcp_tool("get_keyword_doc", {"keyword": "Click"})
            assert result == {"doc": "Clicks element"}
            # Only 1 call (tools/call), no init handshake
            assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_handles_sse_response(self):
        """Handles SSE-formatted response from tools/call."""
        rf_knowledge._session_id = SESSION_ID
        rf_knowledge._session_url = MCP_URL

        tool_result = ["SeleniumLibrary", "Browser"]
        cm, mock_client = _mock_client_with_responses(
            _make_sse_tool_response(tool_result),
        )

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=cm),
        ):
            mock_settings.RF_MCP_TIMEOUT = 10
            result = await rf_knowledge._call_mcp_tool("recommend_libraries", {"description": "web"})
            assert result == ["SeleniumLibrary", "Browser"]

    @pytest.mark.asyncio
    async def test_session_retry_on_400(self):
        """400 triggers session reset and retry."""
        rf_knowledge._session_id = "stale-session"
        rf_knowledge._session_url = MCP_URL

        expired_resp = MagicMock()
        expired_resp.status_code = 400

        tool_result = {"ok": True}
        cm, mock_client = _mock_client_with_responses(
            expired_resp,                   # 1st tools/call → 400
            _make_init_response(),          # re-init
            _make_notif_response(),         # re-init notification
            _make_tool_response(tool_result),  # retry tools/call
        )

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=cm),
        ):
            mock_settings.RF_MCP_TIMEOUT = 10
            result = await rf_knowledge._call_mcp_tool("test_tool")
            assert result == {"ok": True}
            # 4 calls: bad tools/call, init, notif, retry tools/call
            assert mock_client.post.call_count == 4

    @pytest.mark.asyncio
    async def test_returns_none_when_unavailable(self):
        with patch("src.ai.rf_mcp_manager.get_effective_url", return_value=""):
            result = await rf_knowledge._call_mcp_tool("test_tool")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_init_failure(self):
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("refused")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_client)
        cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=cm),
        ):
            mock_settings.RF_MCP_TIMEOUT = 10
            result = await rf_knowledge._call_mcp_tool("test_tool")
            assert result is None

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self):
        rf_knowledge._session_id = SESSION_ID
        rf_knowledge._session_url = MCP_URL

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
        rf_knowledge._session_id = SESSION_ID
        rf_knowledge._session_url = MCP_URL

        cm, mock_client = _mock_client_with_responses(
            _make_tool_error_response(),
        )

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=cm),
        ):
            mock_settings.RF_MCP_TIMEOUT = 10
            result = await rf_knowledge._call_mcp_tool("test_tool")
            assert result is None


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
        rf_knowledge._session_id = SESSION_ID
        rf_knowledge._session_url = MCP_URL

        cm, _ = _mock_client_with_responses(_make_tool_response(keywords))

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=cm),
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
        rf_knowledge._session_id = SESSION_ID
        rf_knowledge._session_url = MCP_URL

        cm, _ = _mock_client_with_responses(
            _make_tool_response({"doc": "Clicks the element identified by locator."}),
        )

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=cm),
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
        rf_knowledge._session_id = SESSION_ID
        rf_knowledge._session_url = MCP_URL

        cm, _ = _mock_client_with_responses(
            _make_tool_response(["SeleniumLibrary", "Browser"]),
        )

        with (
            patch("src.ai.rf_mcp_manager.get_effective_url", return_value=MCP_URL),
            patch("src.ai.rf_knowledge.settings") as mock_settings,
            patch("httpx.AsyncClient", return_value=cm),
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
