"""End-to-end regression for cross-origin iframe capture.

Sourcepoint / OneTrust / TCF consent banners are virtually always in
cross-origin iframes. The original v2 recorder aborted in non-top
frames — every cookie-accept click was silently dropped, leaving the
recording with the user's later page-level clicks but no consent
step. heise.de reproduced this exactly.

This test pins the new pipeline:

1. `_frame_url_from_payload` returns None for top-frame events and the
   iframe URL otherwise — so existing top-frame recordings keep
   behaving identically.
2. `translate_payload` propagates `frame_url` onto the command for
   element-bearing kinds (click/type/scroll/drag_drop/custom_action)
   but NOT for global ones (`Go To` / `Switch Page` — those don't
   target a frame).
3. `_emit_command` wraps the active selector with the Browser-library
   composite locator `iframe[src*="<host>"] >>> <inner>` when
   `frame_url` is set.
"""

from __future__ import annotations

from src.recording.robot_emit import _emit_command, _iframe_locator_from_url
from src.recording.selector_schema import RecordedCommand, SelectorCandidate
from src.recording.v2_payload_translator import (
    _frame_url_from_payload,
    _is_ad_iframe,
    translate_payload,
)


# ─── _frame_url_from_payload ─────────────────────────────────────────────


def test_frame_url_top_frame_returns_none() -> None:
    payload = {"is_top_frame": True, "frame_url": "https://www.heise.de/"}
    assert _frame_url_from_payload(payload) is None


def test_frame_url_iframe_returns_url() -> None:
    payload = {
        "is_top_frame": False,
        "frame_url": "https://message-eu.sp-prod.net/index.html?id=xxx",
    }
    assert _frame_url_from_payload(payload) == (
        "https://message-eu.sp-prod.net/index.html?id=xxx"
    )


def test_frame_url_about_blank_in_iframe_returns_none() -> None:
    """Iframes can briefly hold `about:blank` between document swaps —
    don't tag commands with it; the emitter wouldn't be able to
    extract a host anyway."""
    assert _frame_url_from_payload(
        {"is_top_frame": False, "frame_url": "about:blank"}
    ) is None


def test_frame_url_legacy_payload_without_flags_returns_none() -> None:
    """Recordings made before this story shipped don't have
    `is_top_frame` or `frame_url` — they must keep behaving as
    top-frame so historical sidecars round-trip unchanged."""
    assert _frame_url_from_payload({}) is None


def test_frame_url_iframe_with_empty_string_url_returns_none() -> None:
    """``is_top_frame=False`` but no actual URL — degrade silently
    rather than emit a broken ``iframe[src*=""]`` wrapper that
    would match every iframe on the page."""
    assert _frame_url_from_payload(
        {"is_top_frame": False, "frame_url": ""}
    ) is None


def test_frame_url_iframe_with_null_url_returns_none() -> None:
    """JSON null in ``frame_url`` — same safe-degrade path."""
    assert _frame_url_from_payload(
        {"is_top_frame": False, "frame_url": None}
    ) is None


def test_frame_url_iframe_with_non_string_url_returns_none() -> None:
    """Type confusion (`frame_url: 42`) — must not crash, must not
    surface a stringified value through ``isinstance(url, str)``."""
    assert _frame_url_from_payload(
        {"is_top_frame": False, "frame_url": 42}
    ) is None


def test_frame_url_iframe_with_about_srcdoc_returns_none() -> None:
    """Other ``about:`` schemes (srcdoc, blank) — same filter."""
    for u in ("about:blank", "about:srcdoc", "about:newtab"):
        assert _frame_url_from_payload(
            {"is_top_frame": False, "frame_url": u}
        ) is None, f"{u!r} should be filtered"


def test_frame_url_iframe_missing_frame_url_key_returns_none() -> None:
    """``is_top_frame=False`` but no ``frame_url`` field at all —
    a defensive code path; never observed in production payloads
    from the capture script (which always tags both fields), but
    a stray test stub or a future protocol bump could trip it."""
    assert _frame_url_from_payload({"is_top_frame": False}) is None


# ─── translate_payload ───────────────────────────────────────────────────


def test_translate_iframe_click_carries_frame_url_to_command() -> None:
    payload = {
        "kind": "click",
        "is_top_frame": False,
        "frame_url": "https://message-eu.sp-prod.net/i?id=xxx",
        "element": {
            "tag": "button",
            "attributes": {"id": "alle_akzeptieren"},
            "text": "Akzeptieren",
            "ancestors": [],
        },
        "modifiers": {},
    }
    cmd = translate_payload(payload, index=0)
    assert cmd is not None
    assert cmd.frame_url == "https://message-eu.sp-prod.net/i?id=xxx"


def test_translate_top_frame_click_leaves_frame_url_none() -> None:
    payload = {
        "kind": "click",
        "is_top_frame": True,
        "frame_url": "https://www.heise.de/",
        "element": {
            "tag": "a",
            "attributes": {"href": "/entertainment/"},
            "text": "Entertainment",
            "ancestors": [],
        },
        "modifiers": {},
    }
    cmd = translate_payload(payload, index=0)
    assert cmd is not None
    assert cmd.frame_url is None


# ─── _iframe_locator_from_url ───────────────────────────────────────────


def test_iframe_locator_from_consent_url() -> None:
    out = _iframe_locator_from_url(
        "https://message-eu.sp-prod.net/index.html?id=xxx"
    )
    assert out == 'iframe[src*="message-eu.sp-prod.net"]'


def test_iframe_locator_handles_port_and_subdomain() -> None:
    assert _iframe_locator_from_url(
        "https://consent.cookieinformation.com:8443/path"
    ) == 'iframe[src*="consent.cookieinformation.com:8443"]'


def test_iframe_locator_unparseable_url_returns_none() -> None:
    assert _iframe_locator_from_url("") is None
    assert _iframe_locator_from_url("not a url") is None
    # Data URLs have no netloc.
    assert _iframe_locator_from_url("data:text/html,<p>hi</p>") is None


# ─── _emit_command ──────────────────────────────────────────────────────


def _click_cmd(value: str, frame_url: str | None) -> RecordedCommand:
    return RecordedCommand(
        index=0,
        keyword="Click",
        selector_candidates=[
            SelectorCandidate(
                strategy="css",
                value=value,
                quality_score=80,
                verified_unique=True,
            ),
        ],
        active_candidate_index=0,
        frame_url=frame_url,
    )


def test_emit_top_frame_click_no_iframe_wrapper() -> None:
    line = _emit_command(_click_cmd("button#login", frame_url=None))
    # Load-bearing: top-frame clicks must NOT get an iframe wrap.
    # (RECORDER-IDMAP appends a trailing `# rbs:<id>` comment to
    # every targeted command — that's expected and tested elsewhere;
    # use a substring assertion so future trailing-metadata changes
    # don't fail this test for the wrong reason.)
    assert "Click    button#login" in line
    assert "iframe" not in line


def test_emit_iframe_click_uses_composite_locator() -> None:
    line = _emit_command(
        _click_cmd(
            "button#alle_akzeptieren",
            frame_url="https://message-eu.sp-prod.net/i?id=xxx",
        )
    )
    # Browser-library composite locator: iframe match + `>>>` piercer
    # + inner selector.
    assert (
        "iframe[src*=\"message-eu.sp-prod.net\"] >>> button#alle_akzeptieren"
        in line
    )


def test_emit_iframe_click_falls_back_to_inner_when_url_unparseable() -> None:
    """If we somehow got a frame_url with no host (data: URL, empty),
    don't emit a broken `iframe[src*=""]` wrapper — fall back to the
    inner selector alone. The replay won't find the iframe but at
    least the command is syntactically valid Robot."""
    line = _emit_command(
        _click_cmd("button.x", frame_url="data:text/html,<p>")
    )
    assert "iframe[" not in line
    assert "button.x" in line


# ─── _is_ad_iframe — noise suppression ──────────────────────────────────


def test_ad_iframe_doubleclick_is_filtered() -> None:
    assert _is_ad_iframe("https://pagead2.googlesyndication.com/pagead/js")
    assert _is_ad_iframe("https://googleads.g.doubleclick.net/pagead/ads")


def test_ad_iframe_taboola_outbrain_filtered() -> None:
    assert _is_ad_iframe("https://cdn.taboola.com/libtrc/widget.html")
    assert _is_ad_iframe("https://widgets.outbrain.com/widget")


def test_consent_banner_NOT_filtered() -> None:
    """Sourcepoint / OneTrust / Cookiebot consent iframes MUST pass
    through — the whole reason iframe capture exists."""
    assert not _is_ad_iframe("https://message-eu.sp-prod.net/index.html")
    assert not _is_ad_iframe("https://cdn.cookielaw.org/consent/abc")
    assert not _is_ad_iframe("https://consent.cookieinformation.com/")


def test_legitimate_third_party_widgets_NOT_filtered() -> None:
    """Payment iframes, OAuth widgets, recaptcha etc. host genuine
    user interactions — must not be in the deny-list."""
    assert not _is_ad_iframe("https://js.stripe.com/v3/elements")
    assert not _is_ad_iframe("https://www.google.com/recaptcha/api2/anchor")
    assert not _is_ad_iframe(
        "https://accounts.google.com/o/oauth2/iframe"
    )


def test_top_frame_url_passthrough_when_in_deny_list_substring() -> None:
    """Substring match shouldn't accidentally hit a top-frame URL —
    the caller (translate_payload) only invokes _is_ad_iframe with
    iframe URLs (via _frame_url_from_payload). Sanity: the function
    itself is purely string-based and would falsely flag e.g.
    `https://blog.doubleclick.net/` if the user actually loaded that
    page top-level. Acceptable trade-off — translate_payload's
    is_top_frame guard prevents this in practice."""
    # Just documenting: substring match on an ad-host top-level URL
    # WOULD match. Leave as-is; it's only invoked for iframes.
    assert _is_ad_iframe("https://blog.doubleclick.net/")


def test_translate_drops_event_from_ad_iframe() -> None:
    """End-to-end: a click in a doubleclick iframe maps to None, no
    command lands in the live view."""
    payload = {
        "kind": "click",
        "is_top_frame": False,
        "frame_url": "https://googleads.g.doubleclick.net/banner",
        "element": {
            "tag": "a",
            "attributes": {"href": "https://advertiser.example/"},
            "ancestors": [],
        },
        "modifiers": {},
    }
    assert translate_payload(payload, index=0) is None


def test_translate_keeps_event_from_consent_iframe() -> None:
    """Smoke check the deny-list isn't over-broad — the original
    bug report (Sourcepoint cookie banner) still translates."""
    payload = {
        "kind": "click",
        "is_top_frame": False,
        "frame_url": "https://message-eu.sp-prod.net/i?id=xxx",
        "element": {
            "tag": "button",
            "attributes": {"id": "alle_akzeptieren"},
            "ancestors": [],
        },
        "modifiers": {},
    }
    cmd = translate_payload(payload, index=0)
    assert cmd is not None
    assert cmd.frame_url == "https://message-eu.sp-prod.net/i?id=xxx"
