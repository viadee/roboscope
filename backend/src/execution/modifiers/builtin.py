"""Tier-A vendor execution modifiers — shipped + vetted by RoboScope (EXEC.10).

These classes are referenced by ABSOLUTE FILE PATH at run time (see
``registry.build_modifier_spec``), not as ``src.*`` imports, so Robot Framework
can load them inside ANY environment venv. They therefore import ONLY from
``robot.api`` + the stdlib — never from the backend package.

A modifier class declares its hook via the ``roboscope_kind`` attribute
(``"prerun"`` runs against the running model before execution; ``"prerebot"``
runs against the result model after execution).
"""

from __future__ import annotations

from robot.api import SuiteVisitor


class TagStamper(SuiteVisitor):
    """PreRunModifier: add a fixed tag to every test before the run.

    Spec ``roboscope_tag_stamp:<tag>`` (default ``roboscope``). Lets you mark a
    whole run for later tag-based filtering / reporting without editing suites.
    """

    roboscope_kind = "prerun"
    roboscope_label = "Tag stamper"
    roboscope_description = "Adds a fixed tag to every test in the run."

    def __init__(self, tag: str = "roboscope") -> None:
        self.tag = tag

    def start_suite(self, suite) -> None:  # noqa: D401 - RF visitor hook
        for test in suite.tests:
            test.tags.add(self.tag)


class LiveProgressListener:
    """Tier-A vendor LISTENER (EXEC.11): a compact PASS/FAIL line per test.

    A Robot Framework listener (API v2) receiving live per-event callbacks during
    execution. Safe (stdout only) and a worked example of the `listener` kind —
    org listeners (e.g. a live TMS push) register via the same registry. Spec
    `roboscope_live_progress`.
    """

    ROBOT_LISTENER_API_VERSION = 2
    roboscope_kind = "listener"
    roboscope_label = "Live progress"
    roboscope_description = "Prints a compact PASS/FAIL line per test to the run output."

    def end_test(self, name, attrs) -> None:  # noqa: D401 - RF listener hook
        status = str((attrs or {}).get("status", "?"))
        print(f"[roboscope] {status:<6} {name}")
