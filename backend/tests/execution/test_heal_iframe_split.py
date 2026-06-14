"""M5 regression: _split_iframe_wrap must tolerate spacing variants around
the `>>>` frame separator, or iframe-recorded heals silently never fire."""

from __future__ import annotations

from RoboScopeHeal.candidate_finder import _split_iframe_wrap


def test_spaced_separator_unwraps() -> None:
    pre, inner = _split_iframe_wrap('iframe[src*="consent"] >>> button.accept')
    assert inner == "button.accept"
    assert ">>>" in pre and pre.startswith("iframe[")


def test_unspaced_separator_unwraps() -> None:
    # Previously missed (only " >>> " with spaces was handled) → inner kept
    # the whole string and the heal lookup failed.
    pre, inner = _split_iframe_wrap('iframe[src*="consent"]>>>button.accept')
    assert inner == "button.accept"
    assert pre.startswith("iframe[")


def test_nested_iframes_unwrap_all_rungs() -> None:
    pre, inner = _split_iframe_wrap('iframe[id="a"] >>> iframe[id="b"] >>> .inner')
    assert inner == ".inner"
    assert pre.count(">>>") == 2


def test_non_iframe_selector_untouched() -> None:
    pre, inner = _split_iframe_wrap("button.accept >> nth=0")
    assert pre == ""
    assert inner == "button.accept >> nth=0"
