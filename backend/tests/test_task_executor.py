"""Unit tests for the in-process task executor."""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from src.task_executor import (
    TaskDispatchError,
    TaskResult,
    dispatch_task,
    shutdown_executor,
)


class TestTaskResult:
    def test_has_uuid_id(self):
        result = TaskResult()
        # Should be a valid UUID string
        parsed = uuid.UUID(result.id)
        assert str(parsed) == result.id

    def test_unique_ids(self):
        r1 = TaskResult()
        r2 = TaskResult()
        assert r1.id != r2.id


class TestDispatchTask:
    def test_returns_task_result(self):
        result = dispatch_task(lambda: None)
        assert isinstance(result, TaskResult)
        assert result.id  # non-empty

    def test_task_executes_callable(self):
        event = threading.Event()
        dispatch_task(event.set)
        assert event.wait(timeout=5), "Task did not execute within timeout"

    def test_passes_args(self):
        results = []
        event = threading.Event()

        def collect(a, b):
            results.append((a, b))
            event.set()

        dispatch_task(collect, "hello", "world")
        event.wait(timeout=5)
        assert results == [("hello", "world")]

    def test_passes_kwargs(self):
        results = []
        event = threading.Event()

        def collect(x=None, y=None):
            results.append({"x": x, "y": y})
            event.set()

        dispatch_task(collect, x=1, y=2)
        event.wait(timeout=5)
        assert results == [{"x": 1, "y": 2}]

    def test_passes_args_and_kwargs(self):
        results = []
        event = threading.Event()

        def collect(a, b, key=None):
            results.append((a, b, key))
            event.set()

        dispatch_task(collect, "a", "b", key="k")
        event.wait(timeout=5)
        assert results == [("a", "b", "k")]


class TestTaskException:
    def test_task_exception_does_not_propagate(self):
        """A failing task should not crash the executor."""
        event = threading.Event()

        def failing():
            raise ValueError("boom")

        def succeeding():
            event.set()

        # Submit failing task, then a succeeding one
        dispatch_task(failing)
        dispatch_task(succeeding)
        assert event.wait(timeout=5), "Executor stopped after task exception"

    def test_task_exception_is_logged(self):
        event = threading.Event()

        def failing():
            try:
                raise RuntimeError("test error")
            finally:
                event.set()

        with patch("src.task_executor.logger") as mock_logger:
            dispatch_task(failing)
            event.wait(timeout=5)
            # Give a moment for the logger.exception call after the raise
            time.sleep(0.1)
            mock_logger.exception.assert_called()


class TestTaskDispatchError:
    def test_raised_when_executor_shut_down(self):
        """Submitting to a shut-down executor raises TaskDispatchError."""
        import src.task_executor as mod

        original = mod._executor
        # Replace with a permanently shut-down executor
        dead_executor = ThreadPoolExecutor(max_workers=1)
        dead_executor.shutdown(wait=True)
        mod._executor = dead_executor

        try:
            with pytest.raises(TaskDispatchError, match="Failed to submit task"):
                dispatch_task(lambda: None)
        finally:
            # Restore the original executor
            mod._executor = original

    def test_is_exception_subclass(self):
        assert issubclass(TaskDispatchError, Exception)


class TestShutdownExecutor:
    def test_shutdown_completes_running_task(self):
        """shutdown(wait=True) waits for the running task to finish."""
        results = []

        def slow_task():
            time.sleep(0.2)
            results.append("done")

        dispatch_task(slow_task)
        shutdown_executor(wait=True)
        assert results == ["done"]

    def test_executor_works_after_shutdown(self):
        """After shutdown, a fresh executor is created and accepts tasks."""
        shutdown_executor(wait=True)

        event = threading.Event()
        dispatch_task(event.set)
        assert event.wait(timeout=5), "Executor not working after shutdown"

    def test_shutdown_no_wait(self):
        """shutdown(wait=False) returns immediately."""
        shutdown_executor(wait=False)
        # Should still be able to submit new tasks after
        event = threading.Event()
        dispatch_task(event.set)
        assert event.wait(timeout=5)


class TestFIFOOrdering:
    def test_tasks_execute_in_order(self):
        """With max_workers=1, tasks execute in FIFO submission order."""
        order = []
        barrier = threading.Barrier(2, timeout=5)
        done = threading.Event()

        def make_task(label, is_last=False):
            def task():
                order.append(label)
                if is_last:
                    done.set()
            return task

        # Block the executor so we can queue up tasks
        def blocker():
            barrier.wait()

        dispatch_task(blocker)

        # Queue 5 tasks while executor is blocked
        for i in range(4):
            dispatch_task(make_task(i))
        dispatch_task(make_task(4, is_last=True))

        # Release the blocker
        barrier.wait()

        # Wait for all tasks
        assert done.wait(timeout=5), "Tasks did not complete within timeout"
        assert order == [0, 1, 2, 3, 4]
