"""Runtime self-healing for Robot Framework `Browser` keywords.

`RoboScopeHeal` is a small Robot Framework library that wraps a curated
set of `Browser`-library keywords with explicit-opt-in self-healing. A
recorded `.robot` test using `Heal Click` / `Heal Fill Text` / … will,
on a selector timeout, automatically try alternative selectors derived
from a sidecar `<test>.rbs.json` file, recording every heal as an
audit entry the user can review and accept (never silently rewriting
the test source).

Usage:

    *** Settings ***
    Library    Browser
    Library    RoboScopeHeal

    *** Test Cases ***
    Login
        New Page    https://example.com/login
        Heal Fill Text    [data-testid="email"]    user@example.com
        Heal Click        [data-testid="submit"]

The library is import-time side-effect free; everything happens when
keywords are invoked.
"""

from __future__ import annotations

from RoboScopeHeal.candidate_finder import (
    HealCandidate,
    find_heal_candidates,
    transpose_selector,
)
from RoboScopeHeal.heal_report import (
    HealAuditEntry,
    HealReport,
    parse_heal_audit,
    append_heal_audit,
)
from RoboScopeHeal.library import RoboScopeHeal

__all__ = [
    # Robot Framework library entry point — resolves `Library RoboScopeHeal`.
    "RoboScopeHeal",
    # Public helpers consumers (test runners, dashboards) reach for.
    "HealCandidate",
    "find_heal_candidates",
    "transpose_selector",
    "HealAuditEntry",
    "HealReport",
    "parse_heal_audit",
    "append_heal_audit",
]

__version__ = "0.2.2"
