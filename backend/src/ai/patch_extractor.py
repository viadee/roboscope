"""Story AI-2 — parse `suggested_patches` out of an analysis job's
`result_preview` markdown.

The analyze system prompt (see `prompts.SYSTEM_PROMPT_ANALYZE`) asks the
LLM to embed unified-diff patches in ```` ```patch ```` fenced blocks
whose bodies begin with standard `--- a/<path>` / `+++ b/<path>` headers.
This module extracts those blocks at read time so the API can return
structured patches alongside the prose `result_preview`, without ever
persisting the structured form — the markdown stays the source of truth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class _Patch:
    file_path: str
    unified_diff: str


# Opens a ```patch fence, captures body up to the next ``` on its own
# line. Language label must be exactly `patch` to avoid grabbing plain
# code samples the LLM sprinkles elsewhere in the prose.
_FENCE_RE = re.compile(
    r"```patch\s*\n(?P<body>.*?)\n```",
    flags=re.DOTALL | re.IGNORECASE,
)

# Unified-diff header — tolerates `--- a/path` and plain `--- path`.
_HEADER_RE = re.compile(r"^---\s+(?:a/)?(?P<path>.+?)\s*$", flags=re.MULTILINE)


def extract_patch_suggestions(markdown: str | None) -> list[dict]:
    """Return a list of `{file_path, unified_diff}` dicts from the given
    markdown. Missing / empty input yields `[]`; malformed patch blocks
    (no `---` header) are silently skipped so a bad block never corrupts
    the whole response."""
    if not markdown:
        return []

    out: list[dict] = []
    for match in _FENCE_RE.finditer(markdown):
        body = match.group("body").strip()
        if not body:
            continue
        header = _HEADER_RE.search(body)
        if not header:
            # Not a real unified diff — skip rather than hallucinate a path.
            continue
        file_path = header.group("path").strip()
        # Strip obvious noise patterns the LLM sometimes emits.
        if file_path.startswith("./"):
            file_path = file_path[2:]
        if not file_path or file_path in ("/dev/null",):
            continue
        out.append({"file_path": file_path, "unified_diff": body})
    return out
