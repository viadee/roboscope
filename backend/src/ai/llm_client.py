"""Unified LLM client supporting OpenAI, Anthropic, OpenRouter, and Ollama."""

import logging
from dataclasses import dataclass

from src.ai.encryption import decrypt_api_key
from src.ai.models import AiProvider

logger = logging.getLogger("roboscope.ai.llm_client")


@dataclass
class LlmResponse:
    """Response from an LLM call."""

    content: str
    tokens_used: int


def call_llm(provider: AiProvider, system_prompt: str, user_prompt: str) -> LlmResponse:
    """Send a chat completion request to the configured LLM provider.

    Supports: openai, anthropic, openrouter, ollama.
    All except Anthropic use the OpenAI-compatible API format.
    """
    api_key = None
    if provider.api_key_encrypted:
        api_key = decrypt_api_key(provider.api_key_encrypted)

    if provider.provider_type == "anthropic":
        return _call_anthropic(provider, api_key, system_prompt, user_prompt)
    else:
        return _call_openai_compatible(provider, api_key, system_prompt, user_prompt)


def _call_openai_compatible(
    provider: AiProvider,
    api_key: str | None,
    system_prompt: str,
    user_prompt: str,
) -> LlmResponse:
    """Call an OpenAI-compatible API (OpenAI, OpenRouter, Ollama, Azure)."""
    import httpx

    base_url = provider.api_base_url
    if not base_url:
        if provider.provider_type == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
        elif provider.provider_type == "ollama":
            base_url = "http://localhost:11434/v1"
        else:
            base_url = "https://api.openai.com/v1"

    url = f"{base_url.rstrip('/')}/chat/completions"

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": provider.model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": provider.temperature,
        "max_tokens": provider.max_tokens,
    }

    logger.info(
        "Calling %s (%s) model=%s",
        provider.provider_type,
        url,
        provider.model_name,
    )

    with httpx.Client(timeout=300) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    tokens = data.get("usage", {}).get("total_tokens", 0)

    return LlmResponse(content=content, tokens_used=tokens)


def _call_anthropic(
    provider: AiProvider,
    api_key: str | None,
    system_prompt: str,
    user_prompt: str,
) -> LlmResponse:
    """Call the Anthropic Messages API."""
    import httpx

    base_url = provider.api_base_url or "https://api.anthropic.com"
    url = f"{base_url.rstrip('/')}/v1/messages"

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    if api_key:
        headers["x-api-key"] = api_key

    payload = {
        "model": provider.model_name,
        "max_tokens": provider.max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": provider.temperature,
    }

    logger.info(
        "Calling anthropic (%s) model=%s",
        url,
        provider.model_name,
    )

    with httpx.Client(timeout=300) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    content = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            content += block["text"]

    tokens = data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get(
        "output_tokens", 0
    )

    return LlmResponse(content=content, tokens_used=tokens)
