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
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


_logger = logging.getLogger("roboscope.recording.heal")


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


# Strategies the synthesizer no longer produces. Their values were
# always Browser-library-incompatible (e.g. `pw_locator` emitted
# Playwright JS API syntax `getByRole(...)`), so promoting one as a
# heal candidate would commit a guaranteed-broken selector. Filter
# them out here so legacy sidecars (saved before commit 0c62c7a
# removed `_pw_locator` from `_STRATEGIES`) can't surface a
# known-broken alternative through the heal path. Verify would also
# drop these in production, but unit tests / no-Browser paths skip
# verify and a 0.80-confidence pw_locator row would otherwise win
# the threshold gate.
_LEGACY_DROPPED_STRATEGIES: frozenset[str] = frozenset({"pw_locator"})


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
            if strategy in _LEGACY_DROPPED_STRATEGIES:
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


def _split_iframe_wrap(selector: str) -> tuple[str, str]:
    """Return ``(prefix, inner)`` where prefix is the full chained
    ``iframe[...] >>> `` qualifier and inner is the deepest selector
    after all iframe steps. ``prefix`` is the empty string when the
    selector has no cross-frame qualifier.

    RECORDER-FRAMES — the recorder emits cross-frame selectors as
    ``iframe[src*="<host>"] >>> <inner>`` (Browser library's
    cross-frame piercing dialect). The sidecar still stores only the
    INNER selector on each candidate (the iframe wrap lives
    separately on ``cmd.frame_url``), so a heal lookup must split off
    the wrap before matching, then re-attach it to every candidate
    so the verify callback (and subsequent ``run_keyword``) targets
    the same frame the recorder captured. Without this split,
    sidecar lookups always miss for iframe-recorded events
    (Sourcepoint / OneTrust / TCF consent banners) and transposition
    candidates run against the top-frame DOM, where the captured
    element doesn't exist — ``verify`` returns 0 and every
    candidate is dropped.
    """
    s = selector.strip()
    prefix_parts: list[str] = []
    while s.startswith("iframe["):
        sep = s.find(" >>> ")
        if sep < 0:
            break
        prefix_parts.append(s[: sep + len(" >>> ")])
        s = s[sep + len(" >>> "):]
    return ("".join(prefix_parts), s)


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

    RECORDER-FRAMES handling: when ``failed_selector`` carries a
    Browser-library cross-frame prefix (``iframe[src*="..."] >>>
    <inner>``), the lookup + transposition run against the inner
    selector and every returned candidate is re-wrapped with the
    same prefix. ``verify`` therefore targets the same frame the
    recorder captured — without this, every candidate would be
    dropped as count==0.
    """
    iframe_prefix, inner_selector = _split_iframe_wrap(failed_selector)

    buckets: list[HealCandidate] = []
    if sidecar_path is not None and sidecar_path.is_file():
        buckets.extend(_sidecar_candidates(inner_selector, sidecar_path))
    buckets.extend(transpose_selector(inner_selector))

    if iframe_prefix:
        # Re-wrap each candidate so verify + run_keyword target the
        # same frame the user originally clicked in. The dataclass is
        # frozen, so build a new instance per candidate rather than
        # mutating in place.
        wrapped: list[HealCandidate] = []
        for c in buckets:
            if c.value.startswith("iframe["):
                # Already wrapped (defensive — sidecar lookups always
                # produce inner selectors today, but a future writer
                # might bake the wrap into the candidate value).
                wrapped.append(c)
                continue
            wrapped.append(
                HealCandidate(
                    value=f"{iframe_prefix}{c.value}",
                    strategy=c.strategy,
                    confidence=c.confidence,
                    source=c.source,
                )
            )
        buckets = wrapped

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
    verify_errors = 0
    for c in deduped:
        try:
            count = verify(c.value)
        except Exception as exc:
            # Two distinct failure shapes both land here:
            #   1. permanent — invalid selector syntax (some xpath /
            #      pw_locator exotica). Right behavior: drop.
            #   2. transient — Browser library timeout, page
            #      navigation mid-verify, network blip. Same drop
            #      action, but an operator looking at why a heal
            #      didn't happen needs visibility into pattern #2.
            # Log per-candidate at debug; emit a single WARNING at
            # the end if ANY verify call threw, so production logs
            # surface "verify keeps failing for run X" without
            # spamming N lines per candidate.
            verify_errors += 1
            _logger.debug(
                "heal-verify exception for candidate %r (%s/%s): %s",
                c.value, c.strategy, c.source, exc,
            )
            continue
        if count == 1:
            out.append(c)
        # count==0 or count>1 → drop silently (expected outcome)

    if verify_errors and not out:
        # All candidates failed and none survived → the heal call
        # will return None and the original failure re-raises. The
        # operator needs to know whether that was "no good
        # alternative existed" (silent OK) vs. "verify itself broke"
        # (warrants investigation). One warning per heal-call, not
        # per candidate.
        _logger.warning(
            "heal-verify dropped all %d candidates due to exceptions "
            "(failed selector: %r) — heal will not happen for this "
            "call; check Browser library / page state",
            verify_errors, failed_selector,
        )
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
