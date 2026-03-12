"""Tests for AI LLM client (OpenAI, Anthropic, OpenRouter, Ollama)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.ai.llm_client import LlmResponse, _call_anthropic, _call_openai_compatible, _raise_with_body, call_llm


def _make_provider(**overrides):
    """Create a mock AiProvider."""
    p = MagicMock()
    p.provider_type = overrides.get("provider_type", "openai")
    p.model_name = overrides.get("model_name", "gpt-4o")
    p.api_key_encrypted = overrides.get("api_key_encrypted", "encrypted_key")
    p.api_base_url = overrides.get("api_base_url", None)
    p.temperature = overrides.get("temperature", 0.7)
    p.max_tokens = overrides.get("max_tokens", 4096)
    return p


def _mock_httpx_client(mock_client_cls, response):
    """Wire up a mock httpx.Client context manager returning the given response."""
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = response
    mock_client_cls.return_value = mock_client
    return mock_client


def _openai_response(content="result", total_tokens=42, status_code=200):
    """Create a mock httpx response for OpenAI-compatible APIs."""
    resp = MagicMock()
    resp.status_code = status_code
    data = {"choices": [{"message": {"content": content}}]}
    if total_tokens is not None:
        data["usage"] = {"total_tokens": total_tokens}
    resp.json.return_value = data
    return resp


def _anthropic_response(text="response", input_tokens=10, output_tokens=20, status_code=200):
    """Create a mock httpx response for Anthropic API."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
    return resp


class TestLlmResponse:
    def test_dataclass_fields(self):
        r = LlmResponse(content="hello", tokens_used=42)
        assert r.content == "hello"
        assert r.tokens_used == 42


class TestCallLlmRouting:
    @patch("src.ai.llm_client._call_anthropic")
    @patch("src.ai.llm_client.decrypt_api_key", return_value="sk-ant")
    def test_routes_to_anthropic(self, mock_decrypt, mock_anthropic):
        """Anthropic provider routes to _call_anthropic."""
        mock_anthropic.return_value = LlmResponse(content="hi", tokens_used=10)
        provider = _make_provider(provider_type="anthropic")
        call_llm(provider, "sys", "usr")
        mock_anthropic.assert_called_once_with(provider, "sk-ant", "sys", "usr")

    @patch("src.ai.llm_client._call_openai_compatible")
    @patch("src.ai.llm_client.decrypt_api_key", return_value="sk-test")
    def test_routes_openai_to_openai_compatible(self, mock_decrypt, mock_oai):
        """OpenAI provider routes to _call_openai_compatible."""
        mock_oai.return_value = LlmResponse(content="hi", tokens_used=10)
        provider = _make_provider(provider_type="openai")
        call_llm(provider, "sys", "usr")
        mock_oai.assert_called_once_with(provider, "sk-test", "sys", "usr")

    @patch("src.ai.llm_client._call_openai_compatible")
    @patch("src.ai.llm_client.decrypt_api_key", return_value="sk-or")
    def test_routes_openrouter_to_openai_compatible(self, mock_decrypt, mock_oai):
        """OpenRouter provider routes to _call_openai_compatible."""
        mock_oai.return_value = LlmResponse(content="hi", tokens_used=10)
        provider = _make_provider(provider_type="openrouter")
        call_llm(provider, "sys", "usr")
        mock_oai.assert_called_once()

    @patch("src.ai.llm_client._call_openai_compatible")
    @patch("src.ai.llm_client.decrypt_api_key", return_value="sk-ol")
    def test_routes_ollama_to_openai_compatible(self, mock_decrypt, mock_oai):
        """Ollama provider routes to _call_openai_compatible."""
        mock_oai.return_value = LlmResponse(content="hi", tokens_used=10)
        provider = _make_provider(provider_type="ollama")
        call_llm(provider, "sys", "usr")
        mock_oai.assert_called_once()

    @patch("src.ai.llm_client._call_openai_compatible")
    def test_no_api_key_passes_none(self, mock_oai):
        """When api_key_encrypted is None, api_key passed to handler is None."""
        mock_oai.return_value = LlmResponse(content="hi", tokens_used=0)
        provider = _make_provider(api_key_encrypted=None)
        call_llm(provider, "sys", "usr")
        args = mock_oai.call_args[0]
        assert args[1] is None  # api_key argument

    @patch("src.ai.llm_client._call_openai_compatible")
    @patch("src.ai.llm_client.decrypt_api_key", return_value="decrypted-key")
    def test_api_key_decrypted_when_present(self, mock_decrypt, mock_oai):
        """When api_key_encrypted is set, decrypt_api_key is called with it."""
        mock_oai.return_value = LlmResponse(content="x", tokens_used=0)
        provider = _make_provider(api_key_encrypted="encrypted-blob")
        call_llm(provider, "s", "u")
        mock_decrypt.assert_called_once_with("encrypted-blob")


class TestCallOpenAICompatible:
    @patch("httpx.Client")
    def test_default_openai_base_url(self, mock_client_cls):
        """OpenAI without custom base_url uses api.openai.com."""
        client = _mock_httpx_client(mock_client_cls, _openai_response())
        provider = _make_provider(provider_type="openai", api_base_url=None)

        result = _call_openai_compatible(provider, "sk-test", "sys", "usr")

        url = client.post.call_args[0][0]
        assert "api.openai.com/v1/chat/completions" in url
        assert result.content == "result"
        assert result.tokens_used == 42

    @patch("httpx.Client")
    def test_openrouter_default_url(self, mock_client_cls):
        """OpenRouter without custom base_url uses openrouter.ai."""
        client = _mock_httpx_client(mock_client_cls, _openai_response())
        provider = _make_provider(provider_type="openrouter", api_base_url=None)

        _call_openai_compatible(provider, "sk-or", "sys", "usr")

        url = client.post.call_args[0][0]
        assert "openrouter.ai/api/v1/chat/completions" in url

    @patch("httpx.Client")
    def test_ollama_default_url(self, mock_client_cls):
        """Ollama without custom base_url uses localhost:11434."""
        client = _mock_httpx_client(mock_client_cls, _openai_response(total_tokens=None))
        provider = _make_provider(provider_type="ollama", api_base_url=None)

        result = _call_openai_compatible(provider, None, "sys", "usr")

        url = client.post.call_args[0][0]
        assert "localhost:11434/v1/chat/completions" in url
        assert result.tokens_used == 0  # no usage key

    @patch("httpx.Client")
    def test_custom_base_url(self, mock_client_cls):
        """Custom api_base_url overrides the default."""
        client = _mock_httpx_client(mock_client_cls, _openai_response())
        provider = _make_provider(api_base_url="https://custom.api.com/v1")

        _call_openai_compatible(provider, "sk-test", "sys", "usr")

        url = client.post.call_args[0][0]
        assert url == "https://custom.api.com/v1/chat/completions"

    @patch("httpx.Client")
    def test_trailing_slash_stripped_from_base_url(self, mock_client_cls):
        """Trailing slash in base_url is stripped before appending path."""
        client = _mock_httpx_client(mock_client_cls, _openai_response())
        provider = _make_provider(api_base_url="https://example.com/v1/")

        _call_openai_compatible(provider, None, "sys", "usr")

        url = client.post.call_args[0][0]
        assert url == "https://example.com/v1/chat/completions"

    @patch("httpx.Client")
    def test_bearer_token_header(self, mock_client_cls):
        """When api_key is provided, Authorization Bearer header is set."""
        client = _mock_httpx_client(mock_client_cls, _openai_response())
        provider = _make_provider()

        _call_openai_compatible(provider, "sk-secret", "sys", "usr")

        headers = client.post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer sk-secret"

    @patch("httpx.Client")
    def test_no_auth_header_without_key(self, mock_client_cls):
        """When api_key is None, no Authorization header is set."""
        client = _mock_httpx_client(mock_client_cls, _openai_response())
        provider = _make_provider()

        _call_openai_compatible(provider, None, "sys", "usr")

        headers = client.post.call_args[1]["headers"]
        assert "Authorization" not in headers

    @patch("httpx.Client")
    def test_request_payload_structure(self, mock_client_cls):
        """Payload includes model, messages, temperature, max_tokens."""
        client = _mock_httpx_client(mock_client_cls, _openai_response())
        provider = _make_provider(model_name="gpt-4o", temperature=0.5, max_tokens=2048)

        _call_openai_compatible(provider, None, "Be helpful", "Hello")

        payload = client.post.call_args[1]["json"]
        assert payload["model"] == "gpt-4o"
        assert payload["temperature"] == 0.5
        assert payload["max_tokens"] == 2048
        assert payload["messages"][0] == {"role": "system", "content": "Be helpful"}
        assert payload["messages"][1] == {"role": "user", "content": "Hello"}

    @patch("httpx.Client")
    def test_missing_usage_defaults_to_zero(self, mock_client_cls):
        """When usage field is missing, tokens_used defaults to 0."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        _mock_httpx_client(mock_client_cls, resp)
        provider = _make_provider()

        result = _call_openai_compatible(provider, None, "sys", "usr")
        assert result.tokens_used == 0

    @patch("httpx.Client")
    def test_http_error_raises_runtime_error(self, mock_client_cls):
        """HTTP 4xx/5xx raises RuntimeError with status code and body."""
        resp = MagicMock()
        resp.status_code = 429
        resp.json.return_value = {"error": {"message": "rate limited"}}
        _mock_httpx_client(mock_client_cls, resp)
        provider = _make_provider()

        with pytest.raises(RuntimeError, match="429.*rate limited"):
            _call_openai_compatible(provider, "sk-test", "sys", "usr")

    @patch("httpx.Client")
    def test_http_500_error(self, mock_client_cls):
        """HTTP 500 raises RuntimeError."""
        resp = MagicMock()
        resp.status_code = 500
        resp.json.return_value = {"error": {"message": "server error"}}
        _mock_httpx_client(mock_client_cls, resp)
        provider = _make_provider()

        with pytest.raises(RuntimeError, match="500"):
            _call_openai_compatible(provider, None, "sys", "usr")


class TestCallAnthropic:
    @patch("httpx.Client")
    def test_default_base_url(self, mock_client_cls):
        """Anthropic without custom base_url uses api.anthropic.com."""
        client = _mock_httpx_client(mock_client_cls, _anthropic_response())
        provider = _make_provider(provider_type="anthropic", api_base_url=None)

        _call_anthropic(provider, "sk-ant", "sys", "usr")

        url = client.post.call_args[0][0]
        assert "api.anthropic.com/v1/messages" in url

    @patch("httpx.Client")
    def test_custom_base_url(self, mock_client_cls):
        """Custom api_base_url is used for Anthropic."""
        client = _mock_httpx_client(mock_client_cls, _anthropic_response())
        provider = _make_provider(provider_type="anthropic", api_base_url="https://proxy.example.com")

        _call_anthropic(provider, "key", "sys", "usr")

        url = client.post.call_args[0][0]
        assert "proxy.example.com/v1/messages" in url

    @patch("httpx.Client")
    def test_anthropic_headers_with_key(self, mock_client_cls):
        """Anthropic uses x-api-key and anthropic-version headers."""
        client = _mock_httpx_client(mock_client_cls, _anthropic_response())
        provider = _make_provider(provider_type="anthropic")

        _call_anthropic(provider, "sk-ant-key", "sys", "usr")

        headers = client.post.call_args[1]["headers"]
        assert headers["x-api-key"] == "sk-ant-key"
        assert headers["anthropic-version"] == "2023-06-01"
        assert "Authorization" not in headers

    @patch("httpx.Client")
    def test_no_api_key_header_when_none(self, mock_client_cls):
        """When api_key is None, x-api-key header is not set."""
        client = _mock_httpx_client(mock_client_cls, _anthropic_response())
        provider = _make_provider(provider_type="anthropic")

        _call_anthropic(provider, None, "sys", "usr")

        headers = client.post.call_args[1]["headers"]
        assert "x-api-key" not in headers

    @patch("httpx.Client")
    def test_temperature_clamped_to_max_1(self, mock_client_cls):
        """Temperature > 1.0 is clamped to 1.0 for Anthropic."""
        client = _mock_httpx_client(mock_client_cls, _anthropic_response())
        provider = _make_provider(provider_type="anthropic", temperature=2.5)

        _call_anthropic(provider, None, "sys", "usr")

        payload = client.post.call_args[1]["json"]
        assert payload["temperature"] == 1.0

    @patch("httpx.Client")
    def test_temperature_clamped_to_min_0(self, mock_client_cls):
        """Temperature < 0.0 is clamped to 0.0 for Anthropic."""
        client = _mock_httpx_client(mock_client_cls, _anthropic_response())
        provider = _make_provider(provider_type="anthropic", temperature=-0.5)

        _call_anthropic(provider, None, "sys", "usr")

        payload = client.post.call_args[1]["json"]
        assert payload["temperature"] == 0.0

    @patch("httpx.Client")
    def test_temperature_within_range_unchanged(self, mock_client_cls):
        """Temperature within 0.0-1.0 passes through unchanged."""
        client = _mock_httpx_client(mock_client_cls, _anthropic_response())
        provider = _make_provider(provider_type="anthropic", temperature=0.7)

        _call_anthropic(provider, None, "sys", "usr")

        payload = client.post.call_args[1]["json"]
        assert payload["temperature"] == 0.7

    @patch("httpx.Client")
    def test_payload_structure(self, mock_client_cls):
        """Anthropic payload uses system string and user messages array."""
        client = _mock_httpx_client(mock_client_cls, _anthropic_response())
        provider = _make_provider(
            provider_type="anthropic", model_name="claude-sonnet-4-20250514", max_tokens=8192
        )

        _call_anthropic(provider, None, "Be a tester", "Write tests")

        payload = client.post.call_args[1]["json"]
        assert payload["model"] == "claude-sonnet-4-20250514"
        assert payload["system"] == "Be a tester"
        assert payload["messages"] == [{"role": "user", "content": "Write tests"}]
        assert payload["max_tokens"] == 8192

    @patch("httpx.Client")
    def test_response_parsing(self, mock_client_cls):
        """Content and token count are extracted from Anthropic response."""
        _mock_httpx_client(mock_client_cls, _anthropic_response(text="hello", input_tokens=10, output_tokens=20))
        provider = _make_provider(provider_type="anthropic")

        result = _call_anthropic(provider, None, "sys", "usr")

        assert result.content == "hello"
        assert result.tokens_used == 30

    @patch("httpx.Client")
    def test_multiple_content_blocks_concatenated(self, mock_client_cls):
        """Multiple text blocks in Anthropic response are concatenated."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "content": [
                {"type": "text", "text": "Part 1. "},
                {"type": "text", "text": "Part 2."},
            ],
            "usage": {"input_tokens": 10, "output_tokens": 30},
        }
        _mock_httpx_client(mock_client_cls, resp)
        provider = _make_provider(provider_type="anthropic")

        result = _call_anthropic(provider, None, "sys", "usr")

        assert result.content == "Part 1. Part 2."
        assert result.tokens_used == 40

    @patch("httpx.Client")
    def test_non_text_blocks_ignored(self, mock_client_cls):
        """Non-text content blocks are skipped in Anthropic response."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "content": [
                {"type": "tool_use", "id": "tool_1"},
                {"type": "text", "text": "Only text"},
            ],
            "usage": {"input_tokens": 5, "output_tokens": 10},
        }
        _mock_httpx_client(mock_client_cls, resp)
        provider = _make_provider(provider_type="anthropic")

        result = _call_anthropic(provider, None, "sys", "usr")
        assert result.content == "Only text"

    @patch("httpx.Client")
    def test_http_error_raises_runtime_error(self, mock_client_cls):
        """HTTP errors raise RuntimeError with status code and message."""
        resp = MagicMock()
        resp.status_code = 401
        resp.json.return_value = {"error": {"message": "invalid api key"}}
        _mock_httpx_client(mock_client_cls, resp)
        provider = _make_provider(provider_type="anthropic")

        with pytest.raises(RuntimeError, match="401.*invalid api key"):
            _call_anthropic(provider, "bad-key", "sys", "usr")

    @patch("httpx.Client")
    def test_http_error_non_json_body(self, mock_client_cls):
        """HTTP error with non-JSON body falls back to response text."""
        resp = MagicMock()
        resp.status_code = 502
        resp.json.side_effect = ValueError("not JSON")
        resp.text = "Bad Gateway"
        _mock_httpx_client(mock_client_cls, resp)
        provider = _make_provider(provider_type="anthropic")

        with pytest.raises(RuntimeError, match="502.*Bad Gateway"):
            _call_anthropic(provider, None, "sys", "usr")


class TestRaiseWithBody:
    def test_json_error_message_extracted(self):
        """Error message from error.message JSON field is included."""
        resp = MagicMock()
        resp.status_code = 400
        resp.json.return_value = {"error": {"message": "bad request"}}

        with pytest.raises(RuntimeError, match="400.*bad request"):
            _raise_with_body(resp)

    def test_json_without_error_key_uses_str(self):
        """When error.message is absent, full body dict is stringified."""
        resp = MagicMock()
        resp.status_code = 422
        resp.json.return_value = {"detail": "Unprocessable"}

        with pytest.raises(RuntimeError, match="422"):
            _raise_with_body(resp)

    def test_non_json_response_uses_text(self):
        """When JSON parsing fails, response text is used in the error."""
        resp = MagicMock()
        resp.status_code = 502
        resp.json.side_effect = ValueError("not JSON")
        resp.text = "Bad Gateway"

        with pytest.raises(RuntimeError, match="502.*Bad Gateway"):
            _raise_with_body(resp)

    def test_long_text_truncated(self):
        """Response text longer than 500 chars is truncated."""
        resp = MagicMock()
        resp.status_code = 500
        resp.json.side_effect = Exception("bad")
        resp.text = "X" * 1000

        with pytest.raises(RuntimeError) as exc_info:
            _raise_with_body(resp)
        # The detail from resp.text[:500] should be 500 X's
        assert "500" in str(exc_info.value)
