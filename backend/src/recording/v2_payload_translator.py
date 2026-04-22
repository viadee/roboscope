"""Story W.1 full — translate capture-script / context-menu payloads into
the Python `RecordedCommand` shape the SSE queue + save endpoint consume.

Pure function. The injected JS (W.3 + W.4 + W.5) emits loose dicts
shaped by the `kind` field; this module decides which Robot-Framework
keyword each corresponds to, synthesises selector candidates using
Story S.2's library, and returns a `RecordedCommand`.

No browser, no DB, no file I/O — fully unit-testable.
"""

from __future__ import annotations

from typing import Any

from src.recording.selector_schema import RecordedCommand, SelectorCandidate
from src.recording.selector_synthesis import (
    AncestorRef,
    ElementSnapshot,
    synthesise_selectors,
)


def _element_from_payload(raw: dict[str, Any] | None) -> ElementSnapshot | None:
    if not raw:
        return None
    ancestors = [
        AncestorRef(tag=a.get("tag", ""), attributes=dict(a.get("attributes") or {}))
        for a in (raw.get("ancestors") or [])
    ]
    return ElementSnapshot(
        tag=raw.get("tag", ""),
        attributes=dict(raw.get("attributes") or {}),
        text=raw.get("text") or "",
        aria_role=raw.get("aria_role"),
        aria_name=raw.get("aria_name"),
        ancestors=ancestors,
    )


def _candidates_for(el: ElementSnapshot | None) -> list[SelectorCandidate]:
    if el is None:
        return []
    return synthesise_selectors(el)


# Map the JS `kind` discriminator to the Robot keyword the v2 emitter
# understands. Global keywords (Go To) carry no selector; targeted
# keywords get one from the element snapshot.
_KIND_TO_KEYWORD: dict[str, str] = {
    "click": "Click",
    "dblclick": "Double Click",
    "type": "Type Text",
    "press": "Press Keys",
    "scroll": "Scroll To Element",
    "drag_drop": "Drag And Drop",  # custom two-target shape, handled separately
    "navigate": "Go To",
}


def translate_payload(
    payload: dict[str, Any], index: int
) -> RecordedCommand | None:
    """Return a `RecordedCommand` for the given JS payload, or None if the
    payload is not convertible (e.g. unknown kind). Never raises.
    """
    kind = payload.get("kind")
    if not isinstance(kind, str):
        return None

    # Custom action emitted by the context-menu overlay (Story W.5).
    if kind == "custom_action":
        keyword = payload.get("keyword")
        if not isinstance(keyword, str) or not keyword:
            return None
        args = dict(payload.get("args") or {})
        el = _element_from_payload(payload.get("element"))
        return RecordedCommand(
            index=index,
            keyword=keyword,
            args=args,
            selector_candidates=_candidates_for(el),
            active_candidate_index=0,
        )

    if kind == "drag_drop":
        # Two snapshots: from / to. Emit a single `Drag And Drop` keyword
        # with the `from` selector active and the `to` selector stashed
        # in args so the Robot emitter can serialise both.
        from_el = _element_from_payload(payload.get("from"))
        to_el = _element_from_payload(payload.get("to"))
        from_cands = _candidates_for(from_el)
        to_cands = _candidates_for(to_el)
        target_value = to_cands[0].value if to_cands else ""
        return RecordedCommand(
            index=index,
            keyword="Drag And Drop",
            args={"value": target_value},
            selector_candidates=from_cands,
            active_candidate_index=0,
        )

    if kind == "navigate":
        url = payload.get("url")
        if not isinstance(url, str) or not url:
            return None
        return RecordedCommand(
            index=index,
            keyword="Go To",
            args={"url": url},
            selector_candidates=[],
            active_candidate_index=0,
        )

    if kind not in _KIND_TO_KEYWORD:
        return None

    keyword = _KIND_TO_KEYWORD[kind]
    el = _element_from_payload(payload.get("element"))

    args: dict[str, Any] = {}
    if kind == "type":
        text = payload.get("text")
        if isinstance(text, str):
            args["text"] = text
    elif kind == "press":
        key = payload.get("key")
        if isinstance(key, str):
            args["key"] = key
    elif kind == "scroll":
        # scroll event is noisy — emit only if the element snapshot gave
        # us something stable enough. Scroll-on-document is treated as a
        # global no-target command.
        if el is None:
            return RecordedCommand(
                index=index,
                keyword="Scroll To Element",
                args={"target": "page"},
                selector_candidates=[],
                active_candidate_index=0,
            )

    return RecordedCommand(
        index=index,
        keyword=keyword,
        args=args,
        selector_candidates=_candidates_for(el),
        active_candidate_index=0,
    )
