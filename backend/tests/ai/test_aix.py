"""Epic AIX — verbosity directive + LiteLLM base-URL guard."""

from types import SimpleNamespace

import pytest

from src.ai.llm_client import _call_openai_compatible
from src.ai.prompts import verbosity_directive


class TestVerbosityDirective:
    def test_concise(self):
        d = verbosity_directive("concise")
        assert "concise" in d.lower()
        assert d.strip() != ""

    def test_detailed(self):
        assert "thorough" in verbosity_directive("detailed").lower()

    @pytest.mark.parametrize("v", [None, "standard", "weird"])
    def test_standard_or_unknown_is_empty(self, v):
        assert verbosity_directive(v) == ""


class TestLiteLLMGuard:
    def test_litellm_without_base_url_raises(self):
        provider = SimpleNamespace(
            provider_type="litellm",
            api_base_url=None,
            model_name="gpt-4o",
            temperature=0.3,
            max_tokens=1024,
        )
        with pytest.raises(ValueError, match="Base URL"):
            _call_openai_compatible(provider, None, "sys", "user")
