"""Unit tests for _enrich_error_with_hints in execution tasks."""

from src.execution.models import RunnerType
from src.execution.tasks import _enrich_error_with_hints


class TestEnrichErrorWithHints:
    def test_playwright_connection_error_adds_hint(self):
        error = "Test execution failed"
        output = "Could not connect to the playwright process at 127.0.0.1:63815"
        result = _enrich_error_with_hints(error, output, RunnerType.SUBPROCESS)

        assert "Test execution failed" in result
        assert "Node.js 18+" in result
        assert "rfbrowser init" in result

    def test_playwright_listener_error_adds_hint(self):
        error = "Execution error"
        output = "Calling method '_end_test' of listener 'Browser' failed: ConnectionError"
        result = _enrich_error_with_hints(error, output, RunnerType.SUBPROCESS)

        assert "Hint:" in result
        assert "rfbrowser init" in result

    def test_docker_runner_adds_rebuild_hint(self):
        error = "Test execution failed"
        output = "Could not connect to the playwright process at 127.0.0.1:63815"
        result = _enrich_error_with_hints(error, output, RunnerType.DOCKER)

        assert "Node.js 18+" in result
        assert "Docker" in result
        assert "Package Manager" in result

    def test_unrelated_error_no_hint(self):
        error = "AssertionError: expected 5 but got 3"
        output = "FAIL test_something\nAssertionError: expected 5 but got 3"
        result = _enrich_error_with_hints(error, output, RunnerType.SUBPROCESS)

        assert result == error

    def test_empty_error_with_playwright_in_output(self):
        error = ""
        output = "stderr: ECONNREFUSED 127.0.0.1:63815"
        result = _enrich_error_with_hints(error, output, RunnerType.SUBPROCESS)

        assert "Hint:" in result
        assert "rfbrowser init" in result
        # Empty error_msg should not produce leading separator
        assert not result.startswith(" | ")

    def test_rfbrowser_keyword_in_output(self):
        error = "Suite setup failed"
        output = "Initializing rfbrowser failed: no node binary found"
        result = _enrich_error_with_hints(error, output, RunnerType.SUBPROCESS)

        assert "Hint:" in result
        assert "Node.js 18+" in result

    def test_case_insensitive_matching(self):
        error = "Failed"
        output = "COULD NOT CONNECT TO THE PLAYWRIGHT PROCESS"
        result = _enrich_error_with_hints(error, output, RunnerType.SUBPROCESS)

        assert "Hint:" in result

    def test_result_truncated_to_1000_chars_at_call_site(self):
        """Verify the hint function itself doesn't truncate — that's the caller's job."""
        error = "x" * 500
        output = "Could not connect to the playwright process"
        result = _enrich_error_with_hints(error, output, RunnerType.DOCKER)

        # Function returns full string; caller truncates with [:1000]
        assert len(result) > 500
