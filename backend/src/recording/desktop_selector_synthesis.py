"""Story D.3 — desktop-recorder selector synthesis (Windows UIA tree).

Mirrors Story S.2's web-synthesis surface but over Windows UI Automation
element properties instead of DOM attributes. The caller produces a
`DesktopElementSnapshot` from pywinauto; this module scores the
available locator variants per AR-8 desktop rubric:

  AutomationId  > Name  > ClassName  > XPath-over-UIA  > ancestor-chain

Desktop candidates use the `automation_id`, `uia_name`, `uia_class_name`,
`xpath` strategies from SelectorStrategy (shared with web). The
editor's SelectorPicker (Story S.4) already renders these — the i18n
labels shipped in `recorder.selector.strategy.automation_id` etc.

Pure function, no DB, no UIA runtime. Testable on any host.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.recording.selector_schema import SelectorCandidate

_AUTOGEN_VALUE = re.compile(r"^[A-Za-z0-9_-]{20,}$")


def _looks_autogen(value: str) -> bool:
    if len(value) < 20 or not _AUTOGEN_VALUE.match(value):
        return False
    has_lower = any(c.islower() for c in value)
    has_upper = any(c.isupper() for c in value)
    has_digit = any(c.isdigit() for c in value)
    return sum([has_lower, has_upper, has_digit]) >= 2


def _cap(score: int) -> int:
    return max(0, min(100, score))


@dataclass
class DesktopAncestor:
    """Minimal parent info for ancestor-chain locators on UIA elements."""

    control_type: str
    automation_id: str | None = None
    name: str | None = None


@dataclass
class DesktopElementSnapshot:
    """Serialisable Windows UIA element snapshot.

    `control_type` mirrors pywinauto's UIA control-type (e.g. "Button",
    "Edit"). `name` is the UIA Name property (accessible name). The
    ancestor chain is capped outside this module to bound payload size.
    """

    control_type: str
    automation_id: str | None = None
    name: str | None = None
    class_name: str | None = None
    ancestors: list[DesktopAncestor] = field(default_factory=list)


def _automation_id_candidates(snap: DesktopElementSnapshot) -> list[SelectorCandidate]:
    if not snap.automation_id:
        return []
    score = 92
    if _looks_autogen(snap.automation_id):
        score -= 25
    return [
        SelectorCandidate(
            strategy="automation_id",
            value=snap.automation_id,
            quality_score=_cap(score),
            verified_unique=False,
        )
    ]


def _uia_name_candidates(snap: DesktopElementSnapshot) -> list[SelectorCandidate]:
    if not snap.name:
        return []
    score = 75
    # Numeric-only or time-like names are fragile; same penalty family
    # as the web text strategy. Mutually exclusive — a pure numeric
    # name is hit once, not once per regex branch.
    if re.search(r"^\s*\d+\s*$", snap.name):
        score -= 30
    elif re.search(r"\d{2,}|\d{1,2}:\d{2}", snap.name):
        score -= 15
    return [
        SelectorCandidate(
            strategy="uia_name",
            value=snap.name,
            quality_score=_cap(score),
            verified_unique=False,
        )
    ]


def _uia_class_name_candidates(snap: DesktopElementSnapshot) -> list[SelectorCandidate]:
    if not snap.class_name:
        return []
    score = 50
    # WPF / WinUI often expose generic-looking classes. Keep them but
    # penalise so AutomationId + Name win.
    if snap.class_name in ("TextBox", "Button", "Window", "Panel"):
        score -= 15
    return [
        SelectorCandidate(
            strategy="uia_class_name",
            value=snap.class_name,
            quality_score=_cap(score),
            verified_unique=False,
        )
    ]


def _uia_xpath_candidates(snap: DesktopElementSnapshot) -> list[SelectorCandidate]:
    """Walk the ancestor chain to produce a locator anchored on the
    nearest stable AutomationId / Name. Absolute control-type chain is
    the always-fragile fallback."""
    out: list[SelectorCandidate] = []

    for anc in reversed(snap.ancestors):
        if anc.automation_id and not _looks_autogen(anc.automation_id):
            out.append(
                SelectorCandidate(
                    strategy="xpath",
                    value=f"//*[@AutomationId='{anc.automation_id}']//{snap.control_type}",
                    quality_score=_cap(55),
                    verified_unique=False,
                )
            )
            break
        if anc.name:
            out.append(
                SelectorCandidate(
                    strategy="xpath",
                    value=f"//*[@Name='{anc.name}']//{snap.control_type}",
                    quality_score=_cap(50),
                    verified_unique=False,
                )
            )
            break

    # Absolute control-type chain. Always fragile; last resort.
    chain = [a.control_type for a in snap.ancestors] + [snap.control_type]
    out.append(
        SelectorCandidate(
            strategy="xpath",
            value="/" + "/".join(chain),
            quality_score=_cap(22),
            verified_unique=False,
        )
    )

    return out


_STRATEGIES = (
    _automation_id_candidates,
    _uia_name_candidates,
    _uia_class_name_candidates,
    _uia_xpath_candidates,
)


_QUALITY_FLOOR = 20


def synthesise_desktop_selectors(
    snap: DesktopElementSnapshot,
) -> list[SelectorCandidate]:
    """Return sorted `SelectorCandidate` list for a UIA element."""
    all_candidates: list[SelectorCandidate] = []
    for strategy_fn in _STRATEGIES:
        try:
            all_candidates.extend(strategy_fn(snap))
        except Exception:
            continue

    filtered = [c for c in all_candidates if c.quality_score >= _QUALITY_FLOOR]
    filtered.sort(
        key=lambda c: (c.verified_unique, c.quality_score),
        reverse=True,
    )
    return filtered
