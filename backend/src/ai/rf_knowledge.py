"""Optional rf-mcp bridge for Robot Framework domain knowledge.

If the rf-mcp server is configured, this module provides keyword lookup,
library recommendations, and scenario analysis to enrich LLM prompts.

If not configured, all functions return empty results gracefully.
"""

import logging

logger = logging.getLogger("roboscope.ai.rf_knowledge")

# rf-mcp integration is optional; will be implemented in Phase 3.
# For now, provide stub functions so the rest of the module can reference them.


def is_available() -> bool:
    """Check if rf-mcp is configured and accessible."""
    return False


def search_keywords(query: str) -> list[dict]:
    """Search for Robot Framework keywords matching a query."""
    return []


def get_keyword_docs(keyword_name: str) -> str | None:
    """Get documentation for a specific keyword."""
    return None


def recommend_libraries(description: str) -> list[str]:
    """Suggest libraries based on test description."""
    return []


def analyze_scenario(steps: list[str]) -> list[dict]:
    """Pre-process natural language steps via rf-mcp."""
    return []
