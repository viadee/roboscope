"""Apply a unified-diff patch to a file's text.

The LLM failure-analysis returns fix suggestions as fenced ``patch`` blocks
(see ``prompts.py`` / ``patch_extractor.py``). To let the user accept a fix
with one click we need to APPLY that diff to the on-disk ``.robot`` file.

No third-party patch library is available (RoboScope is offline-only and ships
a minimal dependency set), so this is a small, dependency-free applier. It is
deliberately *context-driven* rather than line-number-driven: an LLM's `@@`
line numbers are frequently off by a few lines, so we locate each hunk by its
context + removed lines and ignore the stated offsets (using them only as a
tie-breaker hint when the same block appears more than once). If a hunk cannot
be located unambiguously the whole apply fails with ``PatchApplyError`` — we
never write a partially- or wrongly-applied file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class PatchApplyError(ValueError):
    """Raised when a unified diff cannot be applied cleanly."""


@dataclass
class _Hunk:
    old_start: int  # 1-based line in the original the hunk targets (hint only)
    before: list[str]  # context + removed lines (the text we expect to find)
    after: list[str]  # context + added lines (what it becomes)


def _parse_hunks(diff: str) -> list[_Hunk]:
    lines = diff.splitlines()
    hunks: list[_Hunk] = []
    i = 0
    while i < len(lines):
        m = _HUNK_RE.match(lines[i])
        if not m:
            i += 1
            continue
        old_start = int(m.group(1))
        before: list[str] = []
        after: list[str] = []
        i += 1
        while i < len(lines) and not lines[i].startswith("@@"):
            line = lines[i]
            # Stop if we hit the start of another file's diff header.
            if line.startswith(("--- ", "+++ ", "diff ", "index ")):
                break
            if line.startswith("\\"):  # "\ No newline at end of file"
                i += 1
                continue
            tag, body = (line[:1], line[1:]) if line else (" ", "")
            if tag == " ":
                before.append(body)
                after.append(body)
            elif tag == "-":
                before.append(body)
            elif tag == "+":
                after.append(body)
            else:
                # Unrecognised line inside a hunk → malformed diff.
                raise PatchApplyError(f"Unexpected line in hunk: {line!r}")
            i += 1
        hunks.append(_Hunk(old_start=old_start, before=before, after=after))
    if not hunks:
        raise PatchApplyError("No hunks found in diff")
    return hunks


def _find_block(haystack: list[str], needle: list[str], hint: int) -> int:
    """Return the index where `needle` occurs in `haystack`, choosing the
    occurrence closest to `hint` when there are several. -1 if not found."""
    if not needle:
        # Pure insertion: anchor at the hint line (clamped).
        return max(0, min(hint, len(haystack)))
    matches: list[int] = []
    last = len(haystack) - len(needle)
    for start in range(0, last + 1):
        if haystack[start : start + len(needle)] == needle:
            matches.append(start)
    if not matches:
        return -1
    return min(matches, key=lambda idx: abs(idx - hint))


def apply_unified_diff(original: str, diff: str) -> str:
    """Apply `diff` (a unified diff) to `original`, returning the patched text.

    Raises ``PatchApplyError`` if any hunk cannot be located, so callers can
    treat a failed apply as "not safe to auto-fix" and fall back to manual.
    """
    hunks = _parse_hunks(diff)

    # Preserve a trailing newline across the round-trip: split/strip the final
    # empty element and re-add it on join.
    had_trailing_nl = original.endswith("\n")
    lines = original.split("\n")
    if had_trailing_nl:
        lines.pop()  # drop the empty tail from the trailing "\n"

    for hunk in hunks:
        hint = max(0, hunk.old_start - 1)
        idx = _find_block(lines, hunk.before, hint)
        if idx < 0:
            raise PatchApplyError(
                "Could not locate the context for a hunk — the file has "
                "changed since the analysis. Apply the patch manually."
            )
        lines[idx : idx + len(hunk.before)] = hunk.after

    result = "\n".join(lines)
    if had_trailing_nl:
        result += "\n"
    return result
