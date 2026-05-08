"""Story SH-2 — runtime self-healing for Robot Framework `Browser` keywords.

Importing this package is side-effect-free. The Robot-Framework-visible
surface lives in `library.RoboScopeHeal`; users add
``Library    RoboScopeHeal`` to their `.robot` file to opt in.

See `_bmad-output/implementation-artifacts/sh-2-runtime-self-healing-selectors.md`
for the full safety envelope.
"""

from src.recording.heal.candidate_finder import (
    HealCandidate,
    find_heal_candidates,
    transpose_selector,
)
from src.recording.heal.heal_report import (
    HealAuditEntry,
    HealReport,
    parse_heal_audit,
)

__all__ = [
    "HealCandidate",
    "find_heal_candidates",
    "transpose_selector",
    "HealAuditEntry",
    "HealReport",
    "parse_heal_audit",
]
