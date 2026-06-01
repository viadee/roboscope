"""Run-result diagnostics — pattern-match common failure modes
on a finished test run and surface an actionable fix in the
ReportDetail UI.

Each diagnostic is purely DERIVED from already-persisted run data
(no extra columns, no schema migration); the report-detail
endpoint calls `detect_report_diagnostic` at response time and
the frontend renders a banner above the failed tests with a
one-click action button.

Today the only registered diagnostic is
`playwright_browser_missing` — the Browser library tries to
launch Chromium but the Playwright `.local-browsers` directory
was never populated because `rfbrowser init` didn't run (or
half-ran and crashed). The fix surfaced to the UI is "press
this button to run rfbrowser init in this env's venv".

Adding more diagnostics later: append a detector function that
takes the run + test results and returns a `Diagnostic | None`,
then list it in `_DETECTORS`. First match wins.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from src.execution.models import ExecutionRun, RunnerType
from src.reports.models import TestResult

# ------------------------------------------------------------------
# Detector registry — each entry: (code, fn(run, results) -> dict | None)
# A detector returns a `dict` shaped like a `RunDiagnostic` payload
# OR None when it doesn't apply. The first non-None wins.
# ------------------------------------------------------------------


# `browserType.launch: Executable doesn't exist at .../chromium-NNNN/...`
# (anchored on the `Executable doesn't exist` substring which is the
# stable part — the path is venv- and version-specific).
#
# The companion `Looks like Playwright was just installed` ASCII box
# Playwright prints AFTER the error is captured too, but matching the
# first message is enough — and slightly faster on long error blobs.
_PLAYWRIGHT_MISSING_RE = re.compile(
    r"browserType\.launch.*Executable doesn'?t exist|"
    r"Looks like Playwright was just installed",
    re.IGNORECASE | re.DOTALL,
)


def _detect_playwright_browser_missing(
    run: ExecutionRun,
    results: Sequence[TestResult],
) -> dict[str, Any] | None:
    """Match the "Playwright browser binaries missing" failure pattern.

    The fix (`rfbrowser init`) is only meaningful when:

    1. The runner was `subprocess` — the docker runner has its own
       browser provisioning baked into the image, and triggering
       `rfbrowser init` in the host venv wouldn't help the container.
    2. The run has an `environment_id` — `rfbrowser init` operates
       on a specific env's venv; without one there is no target.

    Outside those conditions, we still detected the failure pattern
    but the action button has nowhere to go, so we report nothing
    (the user sees the bare error and falls back to manual fix).
    """
    if run.runner_type != RunnerType.SUBPROCESS:
        return None
    if run.environment_id is None:
        return None
    blob = _gather_error_text(run, results)
    if not blob or not _PLAYWRIGHT_MISSING_RE.search(blob):
        return None
    return {
        "code": "playwright_browser_missing",
        "action": {
            "type": "rfbrowser_init",
            "env_id": run.environment_id,
            "endpoint": f"/environments/{run.environment_id}/rfbrowser-init",
            "method": "POST",
        },
    }


def _gather_error_text(
    run: ExecutionRun, results: Sequence[TestResult],
) -> str:
    """Concatenate all places the Playwright error message can land:
    the run-level `error_message` (for runs that crashed before
    producing test results) AND every test result's `error_message`
    (for runs that produced a report with failing tests)."""
    parts: list[str] = []
    if run.error_message:
        parts.append(run.error_message)
    for r in results:
        if r.error_message:
            parts.append(r.error_message)
    return "\n".join(parts)


_DETECTORS = (
    _detect_playwright_browser_missing,
)


def detect_report_diagnostic(
    run: ExecutionRun | None,
    results: Sequence[TestResult],
) -> dict[str, Any] | None:
    """Run every registered detector against the run + results and
    return the first match. None means "no actionable diagnostic"
    (UI shows the raw error verbatim, no banner)."""
    if run is None:
        return None
    for detector in _DETECTORS:
        match = detector(run, results)
        if match is not None:
            return match
    return None
