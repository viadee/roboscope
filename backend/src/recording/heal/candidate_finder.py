"""Story SH-2 — find replacement selectors for a failed locator.

Two complementary sources:

1. **Sidecar lookup** (fast path) — if the `.robot` file has a sibling
   `<name>.rbs.json` from the v2 recorder, it carries ranked
   `SelectorCandidate` lists per step. Matching the failed selector
   against the `value` fields surfaces the alternatives the recorder
   already synthesised.

2. **Transposition** (hand-written tests) — given a failed selector
   like ``id=submit``, generate equivalent candidates by changing the
   strategy but preserving the semantic value: ``[data-testid=submit]``,
   ``text=submit``, ``css=input#submit``, etc. Cheap, deterministic,
   no DOM walk needed. Candidates get verified against the live page
   via a `verify` callback — only candidates that match exactly one
   element survive.

The output is a ranked list of `HealCandidate`s. Callers pick the
highest-confidence one that exceeds the configured threshold.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


# Higher is more stable. Mirrors (loosely) the recorder's strategy
# scoring in `selector_synthesis.py` so heal rankings don't contradict
# what the recorder would have originally ranked.
_STRATEGY_BASE_CONFIDENCE: dict[str, float] = {
    "testid": 0.95,
    "aria": 0.85,
    "pw_locator": 0.80,
    "text": 0.70,
    "css": 0.55,
    "xpath": 0.35,
    "name": 0.60,
    "id": 0.50,  # Present IDs can still drift; trust testid higher.
}


@dataclass(frozen=True)
class HealCandidate:
    """A proposed replacement selector with provenance info."""

    value: str
    strategy: str
    confidence: float
    source: str  # "sidecar" | "transposition"


# ---------------------------------------------------------------------------
# Selector parsing
# ---------------------------------------------------------------------------


_STRATEGY_PREFIX_RE = re.compile(
    r"^(?P<strategy>id|css|xpath|text|data-testid|testid|aria|role|name)\s*=\s*(?P<value>.+)$",
    flags=re.IGNORECASE,
)


def _parse_selector(selector: str) -> tuple[str, str]:
    """Return (strategy, raw_value) best-effort. Unprefixed → css."""
    s = (selector or "").strip()
    if not s:
        return ("css", "")
    m = _STRATEGY_PREFIX_RE.match(s)
    if m:
        strat = m.group("strategy").lower()
        # Normalise a couple of synonyms to the recorder's vocabulary.
        if strat == "data-testid":
            strat = "testid"
        return (strat, m.group("value").strip())
    # CSS-style attribute selector that semantically means testid.
    testid_css = re.match(
        r"^\[data-testid\s*=\s*['\"]?(?P<v>[^'\"\]]+)['\"]?\]$",
        s,
    )
    if testid_css:
        return ("testid", testid_css.group("v").strip())
    # Selector without a recognised strategy prefix — treat as CSS.
    return ("css", s)


# ---------------------------------------------------------------------------
# Transposition: strategy-space siblings of the failed selector
# ---------------------------------------------------------------------------


def transpose_selector(failed: str) -> list[HealCandidate]:
    """Return strategy-sibling candidates for a failed selector, sorted by
    base strategy confidence. The caller is responsible for verifying
    each against the live page before using it."""
    strat, value = _parse_selector(failed)
    if not value:
        return []

    alternates: list[tuple[str, str]] = []

    # Rule set per originating strategy. We conservatively generate a
    # handful of sensible transpositions rather than brute-force every
    # combination — lower recall, far lower false-positive rate.
    if strat == "id":
        alternates += [
            ("testid", f"[data-testid={_css_escape(value)}]"),
            ("aria", f"role=button[name={_quote_for_role(value)}]"),
            ("text", f"text={value}"),
            ("css", f"input#{_css_escape(value)}"),
            ("css", f"button#{_css_escape(value)}"),
            ("css", f"[id={_css_escape(value)}]"),
            ("name", f"[name={_css_escape(value)}]"),
        ]
    elif strat in ("testid",):
        # From testid, try id-fallback + text-fallback.
        clean = value.strip("[]").split("=", 1)[-1] if "=" in value else value
        clean = clean.strip("\"'")
        alternates += [
            ("id", f"id={clean}"),
            ("css", f"#{_css_escape(clean)}"),
            ("aria", f"role=button[name={_quote_for_role(clean)}]"),
            ("text", f"text={clean}"),
        ]
    elif strat == "name":
        alternates += [
            ("testid", f"[data-testid={_css_escape(value)}]"),
            ("id", f"id={value}"),
            ("css", f"[name={_css_escape(value)}]"),
            ("css", f"input[name={_css_escape(value)}]"),
        ]
    elif strat == "text":
        alternates += [
            ("text", f"text=/{re.escape(value)}/i"),      # case-insensitive regex
            ("text", f"text={value.strip()}"),            # normalised whitespace
            ("aria", f"role=button[name={_quote_for_role(value)}]"),
            ("aria", f"role=link[name={_quote_for_role(value)}]"),
        ]
    elif strat == "css":
        # For raw CSS we don't know the semantic — try the simplest
        # "use the same selector as a text anchor" heuristic + strip
        # trailing `:nth-child` indices that often break after list
        # reorderings.
        base = re.sub(r":nth-child\(\d+\)", "", value)
        if base != value:
            alternates += [("css", base)]
        # `#foo-bar-123` — try the bare id without trailing digits
        id_match = re.match(r"^#([A-Za-z_][\w-]*?)-?\d+$", value)
        if id_match:
            alternates += [("css", f"#{id_match.group(1)}")]
    elif strat == "xpath":
        # XPath transposition is high-risk; at best we can drop trailing
        # position predicates.
        stripped = re.sub(r"\[\d+\]$", "", value)
        if stripped != value:
            alternates += [("xpath", f"xpath={stripped}")]
    elif strat in ("role", "aria"):
        # Role-based selectors tend to be stable; not much to transpose.
        # Drop any `[name=...]` predicate as a last-resort fallback.
        stripped = re.sub(r"\[name=['\"].*?['\"]\]", "", value)
        if stripped != value:
            alternates += [("aria", stripped)]

    seen: set[str] = {failed}
    out: list[HealCandidate] = []
    for alt_strat, alt_value in alternates:
        if alt_value in seen:
            continue
        seen.add(alt_value)
        out.append(
            HealCandidate(
                value=alt_value,
                strategy=alt_strat,
                confidence=_STRATEGY_BASE_CONFIDENCE.get(alt_strat, 0.4),
                source="transposition",
            )
        )
    # Stable sort: higher confidence first.
    out.sort(key=lambda c: c.confidence, reverse=True)
    return out


def _css_escape(s: str) -> str:
    """Minimal CSS-ish escaping — quote if the value contains anything
    other than `[A-Za-z0-9_-]`."""
    if re.match(r"^[A-Za-z_][\w-]*$", s):
        return s
    # Fallback: wrap in quotes for attribute-selector bodies that need
    # it. Won't survive raw identifier positions; acceptable trade-off.
    return f'"{s}"'


def _quote_for_role(s: str) -> str:
    return f'"{s}"'


# ---------------------------------------------------------------------------
# Sidecar lookup
# ---------------------------------------------------------------------------


def _sidecar_candidates(failed_selector: str, sidecar_path: Path) -> list[HealCandidate]:
    try:
        data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    commands = data.get("commands") or []
    for cmd in commands:
        cands = cmd.get("selector_candidates") or []
        active_idx = cmd.get("active_candidate_index", 0)
        # Match by value OR by string-equality-within-trimmed-quotes
        match_idx = None
        for i, c in enumerate(cands):
            if (c.get("value") or "").strip() == failed_selector.strip():
                match_idx = i
                break
        if match_idx is None:
            continue
        # Other candidates from this step, excluding the one that failed.
        out: list[HealCandidate] = []
        for i, c in enumerate(cands):
            if i == match_idx:
                continue
            value = c.get("value")
            strategy = c.get("strategy")
            if not value or not strategy:
                continue
            quality = c.get("quality_score")
            conf = float(quality) if isinstance(quality, (int, float)) else \
                _STRATEGY_BASE_CONFIDENCE.get(strategy, 0.5)
            out.append(
                HealCandidate(
                    value=value,
                    strategy=strategy,
                    confidence=conf,
                    source="sidecar",
                )
            )
        # Recorder's own ranking: if active_candidate_index == match_idx,
        # the next-best candidates are already ordered by quality_score
        # in the candidate list.
        out.sort(key=lambda c: c.confidence, reverse=True)
        return out
    return []


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def find_heal_candidates(
    failed_selector: str,
    *,
    sidecar_path: Path | None = None,
    verify: Callable[[str], int] | None = None,
) -> list[HealCandidate]:
    """Return ranked replacement candidates for `failed_selector`.

    Args:
        failed_selector: the selector that just timed out / missed.
        sidecar_path: path to a `<name>.rbs.json` if the running test
            was emitted from the v2 recorder. Lookups are best-effort —
            a missing or malformed file is silently skipped.
        verify: optional callable invoked with each candidate value;
            returns how many DOM elements match. Used to drop candidates
            that would resolve to zero or many elements on the live
            page. Without a verify callback, all candidates are kept
            and the caller is responsible for live-page validation.

    Ordering: sidecar matches first (recorder's original ranking), then
    transposition matches (generic strategy fallbacks). Within each
    group, higher confidence first. Candidates are de-duplicated by
    their `value`.
    """
    buckets: list[HealCandidate] = []
    if sidecar_path is not None and sidecar_path.is_file():
        buckets.extend(_sidecar_candidates(failed_selector, sidecar_path))
    buckets.extend(transpose_selector(failed_selector))

    seen: set[str] = set()
    deduped: list[HealCandidate] = []
    for c in buckets:
        if c.value in seen:
            continue
        seen.add(c.value)
        deduped.append(c)

    if verify is None:
        return deduped

    out: list[HealCandidate] = []
    for c in deduped:
        try:
            count = verify(c.value)
        except Exception:
            continue
        if count == 1:
            out.append(c)
        # count==0 or count>1 → drop silently
    return out


def pick_best_candidate(
    candidates: Iterable[HealCandidate],
    *,
    threshold: float,
) -> HealCandidate | None:
    """Return the highest-confidence candidate that meets the threshold,
    or None if nothing qualifies. Never guesses."""
    best: HealCandidate | None = None
    for c in candidates:
        if c.confidence < threshold:
            continue
        if best is None or c.confidence > best.confidence:
            best = c
    return best
