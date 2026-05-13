"""Tests for `execution.diagnostics.detect_report_diagnostic`.

The detector pattern-matches finished-run error blobs and returns
a UI-actionable diagnostic when a known failure mode is recognised.
The Playwright-browser-missing detector is the only one registered
today; tests here pin its detection AND its gating conditions
(runner_type, environment_id) so the banner doesn't show up when
the action wouldn't help.
"""

from __future__ import annotations

from src.execution.diagnostics import detect_report_diagnostic
from src.execution.models import ExecutionRun, RunnerType
from src.reports.models import TestResult


def _make_run(
    *,
    runner_type: str = RunnerType.SUBPROCESS,
    environment_id: int | None = 7,
    error_message: str | None = None,
) -> ExecutionRun:
    return ExecutionRun(
        id=1,
        repository_id=1,
        environment_id=environment_id,
        runner_type=runner_type,
        target_path="tests/foo.robot",
        triggered_by=1,
        error_message=error_message,
    )


def _make_test(error_message: str | None) -> TestResult:
    return TestResult(
        id=1,
        report_id=1,
        suite_name="Suite",
        test_name="Test",
        status="FAIL",
        duration_seconds=0.0,
        error_message=error_message,
    )


# ---- The exact error blob the user pastes when Browser launch fails.
# Pulled verbatim from a real heise.de run to pin the regex against
# the live phrasing — Playwright tweaks the wording occasionally and
# we want CI to catch that. -------------------------------------
_REAL_PLAYWRIGHT_ERROR = """\
Error: browserType.launch: Executable doesn't exist at \
/Users/rat/.roboscope/venvs/roboscope-default/lib/python3.12/site-packages/\
Browser/wrapper/node_modules/playwright-core/.local-browsers/chromium-1217/\
chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     npx playwright install                                 ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝
"""


class TestPlaywrightBrowserMissingDetection:
    """Match the literal error blob the Browser library emits when
    Chromium binaries are absent."""

    def test_matches_real_error_in_test_result(self) -> None:
        run = _make_run()
        results = [_make_test(_REAL_PLAYWRIGHT_ERROR)]
        diag = detect_report_diagnostic(run, results)
        assert diag is not None
        assert diag["code"] == "playwright_browser_missing"

    def test_matches_when_error_is_at_run_level_not_per_test(self) -> None:
        """If the runner failed BEFORE producing any test results
        (e.g. the suite import itself raised), the error lands on
        ExecutionRun.error_message, not TestResult. Detector still
        needs to find it."""
        run = _make_run(error_message=_REAL_PLAYWRIGHT_ERROR)
        diag = detect_report_diagnostic(run, [])
        assert diag is not None
        assert diag["code"] == "playwright_browser_missing"

    def test_action_payload_carries_env_id_and_endpoint(self) -> None:
        run = _make_run(environment_id=42)
        results = [_make_test(_REAL_PLAYWRIGHT_ERROR)]
        diag = detect_report_diagnostic(run, results)
        assert diag is not None
        action = diag["action"]
        assert action["type"] == "rfbrowser_init"
        assert action["env_id"] == 42
        assert action["endpoint"] == "/environments/42/rfbrowser-init"
        assert action["method"] == "POST"

    def test_unrelated_failure_yields_no_diagnostic(self) -> None:
        run = _make_run()
        results = [_make_test("AssertionError: 1 != 2")]
        assert detect_report_diagnostic(run, results) is None

    def test_empty_results_and_no_run_error_yields_none(self) -> None:
        run = _make_run()
        assert detect_report_diagnostic(run, []) is None


class TestDetectorGatingConditions:
    """Even when the failure pattern matches, the banner only shows
    when the suggested fix can actually help."""

    def test_docker_runner_yields_no_diagnostic(self) -> None:
        """`rfbrowser init` operates on the host venv — for docker
        runs the browser provisioning lives in the image, so the
        button would point at the wrong target."""
        run = _make_run(runner_type=RunnerType.DOCKER)
        results = [_make_test(_REAL_PLAYWRIGHT_ERROR)]
        assert detect_report_diagnostic(run, results) is None

    def test_no_environment_id_yields_no_diagnostic(self) -> None:
        """Subprocess runs without an explicit environment don't
        have a venv we can `rfbrowser init` against."""
        run = _make_run(environment_id=None)
        results = [_make_test(_REAL_PLAYWRIGHT_ERROR)]
        assert detect_report_diagnostic(run, results) is None

    def test_none_run_yields_none(self) -> None:
        results = [_make_test(_REAL_PLAYWRIGHT_ERROR)]
        assert detect_report_diagnostic(None, results) is None


class TestPatternRobustness:
    """The regex matches the stable substrings, not the exact
    formatting — so Playwright minor-version changes to the ASCII
    box or the path don't silently break the diagnostic."""

    def test_executable_doesnt_exist_alone_matches(self) -> None:
        run = _make_run()
        msg = "browserType.launch: Executable doesn't exist at /some/path"
        results = [_make_test(msg)]
        assert detect_report_diagnostic(run, results) is not None

    def test_just_looks_like_playwright_banner_matches(self) -> None:
        """In some Browser-library versions the ASCII box arrives
        without the leading `Executable doesn't exist` line — the
        OR branch in the regex covers that case."""
        run = _make_run()
        msg = "Looks like Playwright was just installed or updated."
        results = [_make_test(msg)]
        assert detect_report_diagnostic(run, results) is not None

    def test_case_insensitive(self) -> None:
        """Be tolerant to a future RF / Browser library that
        capitalises the error differently."""
        run = _make_run()
        msg = "BROWSERTYPE.LAUNCH: EXECUTABLE DOESN'T EXIST at X"
        results = [_make_test(msg)]
        assert detect_report_diagnostic(run, results) is not None
