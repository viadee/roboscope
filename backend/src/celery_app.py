"""In-process task executor for background work.

Uses a ThreadPoolExecutor with max_workers=1 so only one task runs at
a time while additional submissions queue up. No external dependencies
(Redis, Celery) are required.

All task functions are plain Python callables — no decorators needed.
"""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger("mateox.executor")


class TaskDispatchError(Exception):
    """Raised when a task cannot be submitted to the executor."""

    pass


class TaskResult:
    """Minimal result object returned when a task is submitted."""

    def __init__(self) -> None:
        self.id = str(uuid.uuid4())


# Single-worker executor: tasks queue up, run one at a time.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mateox-task")


def dispatch_task(func: Callable[..., Any], *args: Any, **kwargs: Any) -> TaskResult:
    """Submit a task to the background executor.

    The function runs in a background thread. Only one task executes at
    a time; additional submissions wait in a FIFO queue.

    Returns a TaskResult with a unique ``id``.
    Raises TaskDispatchError if the submission itself fails.
    """
    result = TaskResult()
    task_name = getattr(func, "__name__", str(func))

    def _run() -> None:
        try:
            logger.info("Starting task '%s' (id=%s)", task_name, result.id)
            func(*args, **kwargs)
            logger.info("Task '%s' (id=%s) completed", task_name, result.id)
        except Exception:
            logger.exception("Task '%s' (id=%s) failed", task_name, result.id)

    try:
        _executor.submit(_run)
        logger.info("Queued task '%s' (id=%s)", task_name, result.id)
        return result
    except Exception as e:
        msg = f"Failed to submit task '{task_name}': {e}"
        logger.error(msg)
        raise TaskDispatchError(msg) from e
