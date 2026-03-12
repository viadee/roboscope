"""Tests for execution tasks: cancel_active_run and runner registry."""

import threading
from unittest.mock import MagicMock

from src.execution.tasks import (
    _active_runners,
    _active_runners_lock,
    cancel_active_run,
)


def _clear_registry():
    """Helper to reset the global runner registry between tests."""
    with _active_runners_lock:
        _active_runners.clear()


class TestRunnerRegistry:
    """Tests for the _active_runners registry and its thread-safe operations."""

    def setup_method(self):
        _clear_registry()

    def teardown_method(self):
        _clear_registry()

    def test_register_and_unregister_runner(self):
        runner = MagicMock()
        with _active_runners_lock:
            _active_runners[42] = runner
        assert 42 in _active_runners

        with _active_runners_lock:
            removed = _active_runners.pop(42, None)
        assert removed is runner
        assert 42 not in _active_runners

    def test_register_multiple_runners(self):
        runners = {i: MagicMock() for i in range(5)}
        with _active_runners_lock:
            _active_runners.update(runners)
        assert len(_active_runners) == 5
        for run_id, runner in runners.items():
            assert _active_runners[run_id] is runner

    def test_pop_nonexistent_returns_none(self):
        with _active_runners_lock:
            result = _active_runners.pop(99999, None)
        assert result is None

    def test_thread_safety_concurrent_register(self):
        """Multiple threads registering runners concurrently should not corrupt state."""
        errors = []

        def register(run_id):
            try:
                runner = MagicMock()
                with _active_runners_lock:
                    _active_runners[run_id] = runner
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(_active_runners) == 50

    def test_thread_safety_concurrent_register_and_unregister(self):
        """Concurrent register and unregister operations should not raise."""
        # Pre-populate some runners
        for i in range(20):
            _active_runners[i] = MagicMock()

        errors = []

        def unregister(run_id):
            try:
                with _active_runners_lock:
                    _active_runners.pop(run_id, None)
            except Exception as e:
                errors.append(e)

        def register(run_id):
            try:
                with _active_runners_lock:
                    _active_runners[run_id] = MagicMock()
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(20):
            threads.append(threading.Thread(target=unregister, args=(i,)))
        for i in range(20, 40):
            threads.append(threading.Thread(target=register, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Original 0-19 should be removed, 20-39 should be added
        for i in range(20):
            assert i not in _active_runners
        for i in range(20, 40):
            assert i in _active_runners


class TestCancelActiveRun:
    """Tests for cancel_active_run()."""

    def setup_method(self):
        _clear_registry()

    def teardown_method(self):
        _clear_registry()

    def test_cancel_registered_runner(self):
        runner = MagicMock()
        with _active_runners_lock:
            _active_runners[10] = runner

        result = cancel_active_run(10)

        assert result is True
        runner.cancel.assert_called_once()

    def test_cancel_unknown_run_id_returns_false(self):
        result = cancel_active_run(99999)
        assert result is False

    def test_cancel_does_not_remove_runner_from_registry(self):
        """cancel_active_run only calls cancel(), it does not unregister the runner.
        Cleanup happens in the finally block of execute_test_run."""
        runner = MagicMock()
        with _active_runners_lock:
            _active_runners[10] = runner

        cancel_active_run(10)

        # Runner should still be in registry (removed by finally block, not cancel)
        assert 10 in _active_runners

    def test_cancel_multiple_runners_independently(self):
        runners = {}
        for i in range(3):
            runners[i] = MagicMock()
            with _active_runners_lock:
                _active_runners[i] = runners[i]

        # Cancel only run 1
        assert cancel_active_run(1) is True
        runners[1].cancel.assert_called_once()

        # Others should not be cancelled
        runners[0].cancel.assert_not_called()
        runners[2].cancel.assert_not_called()

    def test_cancel_same_run_twice(self):
        runner = MagicMock()
        with _active_runners_lock:
            _active_runners[5] = runner

        assert cancel_active_run(5) is True
        assert cancel_active_run(5) is True
        assert runner.cancel.call_count == 2


class TestEnrichErrorWithHints:
    """Tests for _enrich_error_with_hints helper."""

    def test_no_hint_for_normal_error(self):
        from src.execution.tasks import _enrich_error_with_hints

        result = _enrich_error_with_hints("some error", "normal output", "subprocess")
        assert result == "some error"
        assert "Hint" not in result

    def test_adds_hint_for_playwright_error(self):
        from src.execution.tasks import _enrich_error_with_hints

        result = _enrich_error_with_hints(
            "could not connect to the playwright process",
            "",
            "subprocess",
        )
        assert "Hint" in result
        assert "rfbrowser init" in result

    def test_adds_docker_hint_for_docker_runner(self):
        from src.execution.tasks import _enrich_error_with_hints

        result = _enrich_error_with_hints(
            "rfbrowser failed",
            "",
            "docker",
        )
        assert "Docker" in result
        assert "Rebuild" in result

    def test_hint_detected_in_combined_output(self):
        from src.execution.tasks import _enrich_error_with_hints

        result = _enrich_error_with_hints(
            "test failed",
            "stderr: ECONNREFUSED when connecting",
            "subprocess",
        )
        assert "Hint" in result

    def test_no_hint_for_empty_strings(self):
        from src.execution.tasks import _enrich_error_with_hints

        result = _enrich_error_with_hints("", "", "subprocess")
        assert result == ""


class TestGetRunner:
    """Tests for the _get_runner factory function."""

    def test_subprocess_runner_default(self):
        from src.execution.tasks import _get_runner

        runner = _get_runner("subprocess")
        from src.execution.runners.subprocess_runner import SubprocessRunner

        assert isinstance(runner, SubprocessRunner)

    def test_subprocess_runner_with_venv(self):
        from src.execution.tasks import _get_runner

        runner = _get_runner("subprocess", {"venv_path": "/tmp/venv"})
        assert runner.venv_path == "/tmp/venv"

    def test_subprocess_runner_with_none_config(self):
        from src.execution.tasks import _get_runner

        runner = _get_runner("subprocess", None)
        from src.execution.runners.subprocess_runner import SubprocessRunner

        assert isinstance(runner, SubprocessRunner)
