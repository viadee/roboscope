"""Per-request log correlation.

Story LOGGING-1 — the `add_request_id` middleware in `main.py`
generates an `X-Request-ID` per HTTP request, but its value never
made it into log records. This module bridges the gap:

  * `request_id_var` holds the ID for the duration of the request
    via Python's `contextvars` (async-task-aware).
  * `RequestIdFilter` is attached to the root logger handler. It
    stamps `record.request_id` on every log record, so the JSON
    formatter picks it up automatically.

Usage:

    # In an HTTP middleware:
    token = request_id_var.set(req_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)

    # In any logger anywhere in the app — no changes required.
    logger.info("doing the thing")     # → "request_id": "<the-id>"
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

# `None` outside an HTTP request → the filter omits the field rather
# than emitting a phantom `null`.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Stamp `request_id` on every log record from the current context.

    Attached once to the root handler so every logger in the app
    inherits the behaviour — no per-call boilerplate.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        rid = request_id_var.get()
        if rid is not None:
            record.request_id = rid
        return True
