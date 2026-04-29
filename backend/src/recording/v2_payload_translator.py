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


# RECORDER-FRAMES-DENY — well-known ad / tracker / analytics iframe
# hosts that fire spurious clicks the user never made. Cross-origin
# iframe capture (story RECORDER-FRAMES) is intentionally permissive
# so consent banners (Sourcepoint / OneTrust / TCF) get captured;
# this deny-list claws back the noise from networks that aren't
# user-interactive at all.
#
# Match policy: SUBSTRING on the parsed host. Conservative on purpose
# — every entry must be a network that's PURELY ad/tracker, never
# hosting user-meaningful widgets. Excluded by design:
#   - googletagmanager.com (sometimes loads legit widgets)
#   - google.com / gstatic.com (reCAPTCHA, OAuth)
#   - facebook.com (FB login widget, social plugins)
#   - stripe.com / paypal.com (payment iframes — user interacts with them)
#
# When in doubt, leave the host OUT of this list — the user sees the
# captured row in the live view (with the iframe-host chip from
# c1b0feb) and can delete it before saving. False-positive
# suppression is harder to recover from than false-positive capture.
_AD_IFRAME_HOST_SUBSTRINGS: frozenset[str] = frozenset({
    # Google ad networks
    "doubleclick.net",
    "googlesyndication.com",
    "2mdn.net",
    "googleadservices.com",
    # Major ad exchanges / DSPs
    "adnxs.com",       # AppNexus / Xandr
    "pubmatic.com",
    "rubiconproject.com",
    "openx.net",
    "adsrvr.org",      # The Trade Desk
    "criteo.com",
    "criteo.net",
    "amazon-adsystem.com",
    "yieldlab.com",
    "yieldmo.com",
    # Recommendation / native-ad widgets (no user-meaningful interaction)
    "taboola.com",
    "outbrain.com",
    # Analytics / measurement
    "scorecardresearch.com",
    "chartbeat.com",
    "quantserve.com",
    "moatads.com",
})


def _is_ad_iframe(frame_url: str) -> bool:
    """True if `frame_url`'s host is in the ad/tracker deny-list.

    Substring match against `urlparse(frame_url).netloc.lower()`. The
    host comparison handles the typical sub-domain pattern of ad
    networks (`pagead2.googlesyndication.com`, `cdn.taboola.com`)
    without enumerating every CDN flavour.
    """
    from urllib.parse import urlparse
    try:
        host = urlparse(frame_url).netloc.lower()
    except Exception:
        return False
    if not host:
        return False
    return any(needle in host for needle in _AD_IFRAME_HOST_SUBSTRINGS)


def _frame_url_from_payload(payload: dict[str, Any]) -> str | None:
    """Extract the originating frame URL when the event came from an
    iframe. Top-frame events return None — the emitter omits the
    `iframe[...] >>>` composite-locator wrapper for those.

    Capture script tags every payload with `frame_url` (location.href)
    and `is_top_frame` (window.top === window). We only treat
    `is_top_frame === false` AND a non-empty URL as iframe-scoped.
    Anything else (including missing fields from older payloads) maps
    to None so existing recordings keep behaving as top-frame.
    """
    if payload.get("is_top_frame", True):
        return None
    url = payload.get("frame_url")
    if isinstance(url, str) and url and not url.startswith("about:"):
        return url
    return None


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
    "switch_page": "Switch Page",
}


def translate_payload(
    payload: dict[str, Any], index: int
) -> RecordedCommand | None:
    """Return a `RecordedCommand` for the given JS payload, or None if the
    payload is not convertible (e.g. unknown kind). Never raises.

    Returns None and logs a `recording.iframe.suppressed` line when the
    event came from a known ad/tracker iframe (`_AD_IFRAME_HOST_SUBSTRINGS`).
    The capture script runs in every frame for cookie-banner support;
    this is the noise filter that keeps doubleclick / criteo / taboola
    impressions from polluting the recording.
    """
    kind = payload.get("kind")
    if not isinstance(kind, str):
        return None

    frame_url = _frame_url_from_payload(payload)
    if frame_url is not None and _is_ad_iframe(frame_url):
        # Logged at debug; the live view never sees this command, so
        # the user has no UI signal — that's intentional, the noise
        # would defeat the point.
        import logging
        logging.getLogger("roboscope.recording").debug(
            "recording.iframe.suppressed kind=%s frame=%s",
            kind, frame_url,
        )
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
            frame_url=frame_url,
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
            frame_url=frame_url,
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

    if kind == "switch_page":
        # RECORDER-1A: emitted by the recorder task when the context
        # acquires a new page (popup, target=_blank link, programmatic
        # window.open). The `NEW` token tells RF Browser to focus the
        # most recently opened page; the URL — when present — is
        # surfaced in args for replay debugging.
        url = payload.get("url")
        args: dict[str, Any] = {"page": "NEW"}
        if isinstance(url, str) and url and not url.startswith("about:"):
            args["url"] = url
        return RecordedCommand(
            index=index,
            keyword="Switch Page",
            args=args,
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
                frame_url=frame_url,
            )

    return RecordedCommand(
        index=index,
        keyword=keyword,
        args=args,
        selector_candidates=_candidates_for(el),
        active_candidate_index=0,
        frame_url=frame_url,
    )
