"""Story SH-3 — DOM fingerprint scorer + walker.

Given a `stored` fingerprint (captured at record-time by the v2
recorder) and one or more `live` snapshots from the current DOM,
produce a similarity score in [0, 1]. Callers use the score to pick
the best live-page match even when the originally-recorded selector
string and its transposition siblings have all become invalid.

Weights were picked to make a single strong signal (like a stable
`data-testid`) land around 0.45 — below the 0.6 walker threshold —
so a match requires *multiple* signals to line up. The bar is higher
than transposition on purpose: a fingerprint-level heal is a
substitution across bigger refactorings, so the "wrong element"
blast radius is bigger too.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Fingerprint schema fields:
#   tag        : str       — element tag name, lowercased
#   id         : str | None
#   testid     : str | None — value of data-testid attr
#   classes    : list[str] — CSS class list
#   name       : str | None — form `name` attribute
#   role       : str | None — ARIA role
#   text       : str       — visible text, normalised + truncated
#   ancestors  : list[dict] — last 4 parents, each {tag, id, testid}


# Weights sum to 1.0. Order of magnitude: strongest-single-signal first.
_W_TESTID     = 0.45
_W_ID         = 0.20
_W_ROLE_TAG   = 0.10
_W_CLASSES    = 0.08
_W_TEXT       = 0.10
_W_ANCESTORS  = 0.07

DEFAULT_WALKER_THRESHOLD = 0.6


@dataclass(frozen=True)
class FingerprintMatch:
    """A walker result — a live-page element + its similarity score."""

    selector: str
    score: float


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _jaccard(a: list[str], b: list[str]) -> float:
    sa = {s for s in (a or []) if s}
    sb = {s for s in (b or []) if s}
    if not sa and not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _text_overlap(a: str, b: str) -> float:
    """Cheap char-level Dice coefficient on 3-grams. Good enough for
    the "button label mostly unchanged" case; doesn't punish trailing
    whitespace or capitalisation drift."""
    if not a or not b:
        return 0.0
    a, b = a.lower(), b.lower()
    if a == b:
        return 1.0
    grams_a = {a[i:i + 3] for i in range(max(0, len(a) - 2))}
    grams_b = {b[i:i + 3] for i in range(max(0, len(b) - 2))}
    if not grams_a or not grams_b:
        return 0.0
    overlap = len(grams_a & grams_b)
    return 2 * overlap / (len(grams_a) + len(grams_b))


def _ancestor_overlap(a: list[dict], b: list[dict]) -> float:
    """Overlap of the ancestor chain. Counts a pair as matched if both
    sides share a tag + (id OR testid). Pure tag-only matches are
    too common to carry signal."""
    if not a or not b:
        return 0.0
    matched = 0
    pool_b = list(b)
    for pa in a:
        for i, pb in enumerate(pool_b):
            if pa.get("tag") != pb.get("tag"):
                continue
            same_id = (pa.get("id") and pa.get("id") == pb.get("id"))
            same_testid = (pa.get("testid") and pa.get("testid") == pb.get("testid"))
            if same_id or same_testid or (pa.get("id") is None and pa.get("testid") is None
                                          and pb.get("id") is None and pb.get("testid") is None):
                matched += 1
                pool_b.pop(i)
                break
    return matched / max(len(a), len(b))


def score_fingerprint_similarity(
    stored: dict | None,
    live: dict | None,
) -> float:
    """Return a 0..1 similarity score between two fingerprint dicts."""
    if not stored or not live:
        return 0.0

    total = 0.0

    # Testid — strongest single signal.
    st_testid = _norm(stored.get("testid"))
    lv_testid = _norm(live.get("testid"))
    if st_testid and lv_testid and st_testid == lv_testid:
        total += _W_TESTID

    # Id — second-strongest.
    st_id = _norm(stored.get("id"))
    lv_id = _norm(live.get("id"))
    if st_id and lv_id and st_id == lv_id:
        total += _W_ID

    # Role + tag — only counts when both agree.
    st_tag = _norm(stored.get("tag")).lower()
    lv_tag = _norm(live.get("tag")).lower()
    st_role = _norm(stored.get("role"))
    lv_role = _norm(live.get("role"))
    if st_tag and lv_tag and st_tag == lv_tag:
        # Tag alone gets partial; tag + role agreement gets full.
        if st_role and lv_role and st_role == lv_role:
            total += _W_ROLE_TAG
        else:
            total += _W_ROLE_TAG * 0.5

    # Classes — Jaccard.
    total += _W_CLASSES * _jaccard(
        stored.get("classes") or [],
        live.get("classes") or [],
    )

    # Text overlap (trigram Dice).
    total += _W_TEXT * _text_overlap(
        _norm(stored.get("text")),
        _norm(live.get("text")),
    )

    # Ancestor chain overlap.
    total += _W_ANCESTORS * _ancestor_overlap(
        stored.get("ancestors") or [],
        live.get("ancestors") or [],
    )

    # Clamp — defensive only; weights already sum to 1.
    return max(0.0, min(1.0, total))


def find_best_by_fingerprint(
    stored: dict | None,
    live_candidates: list[tuple[str, dict]],
    *,
    threshold: float = DEFAULT_WALKER_THRESHOLD,
) -> FingerprintMatch | None:
    """Score each `(selector, live_snapshot)` against `stored`. Return
    the best match ABOVE `threshold`, or None. Ties broken by the
    first entry scored (callers can pre-sort to influence this)."""
    if not stored:
        return None

    best: FingerprintMatch | None = None
    for selector, live in live_candidates:
        score = score_fingerprint_similarity(stored, live)
        if score < threshold:
            continue
        if best is None or score > best.score:
            best = FingerprintMatch(selector=selector, score=score)
    return best
