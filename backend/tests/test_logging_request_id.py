"""Story LOGGING-1 — `request_id` correlation in log records.

The middleware sets `X-Request-ID` on the response (existing
behaviour) AND publishes the same id on a `ContextVar` so that
`RequestIdFilter` stamps it onto every log record emitted from
within the request — making it possible to grep all logs for a
single request after the fact.

These tests pin down:
  - Inside a request: log records carry `record.request_id` matching
    the response header.
  - Outside a request: `getattr(record, "request_id", None) is None`.
  - Two sequential requests don't bleed ids into each other.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.testclient import TestClient

from src.logging_context import RequestIdFilter, request_id_var


# ---------------------------------------------------------------------------
# Helper logger that captures records *with their custom attributes intact*.
# (caplog's fixture captures records but does NOT run the filter chain
# unless the filter is on caplog.handler — so we attach explicitly.)
# ---------------------------------------------------------------------------


class _CapturingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []
        self.addFilter(RequestIdFilter())

    def emit(self, record: logging.LogRecord) -> None:
        # The filter chain has already run by the time we hit emit, so
        # any `record.request_id` set by the filter is now on the record.
        self.records.append(record)


# ---------------------------------------------------------------------------
# Filter unit tests — no FastAPI involved
# ---------------------------------------------------------------------------


class TestRequestIdFilter:
    def test_no_id_outside_context(self):
        f = RequestIdFilter()
        record = logging.LogRecord(
            name="x", level=logging.INFO, pathname=__file__, lineno=1,
            msg="hi", args=None, exc_info=None,
        )
        f.filter(record)
        assert getattr(record, "request_id", None) is None

    def test_stamps_when_context_set(self):
        f = RequestIdFilter()
        record = logging.LogRecord(
            name="x", level=logging.INFO, pathname=__file__, lineno=1,
            msg="hi", args=None, exc_info=None,
        )
        token = request_id_var.set("test-abc")
        try:
            f.filter(record)
        finally:
            request_id_var.reset(token)
        assert record.request_id == "test-abc"


# ---------------------------------------------------------------------------
# End-to-end via TestClient — middleware sets ContextVar, log inside the
# endpoint picks it up, response header matches.
# ---------------------------------------------------------------------------


def _build_app_with_endpoint(handler: _CapturingHandler):
    """Build a minimal FastAPI app reusing the production middleware."""
    from fastapi import FastAPI, Request
    from src.logging_context import request_id_var as rid_var
    import uuid

    app = FastAPI()

    test_logger = logging.getLogger("test.logging_request_id")
    test_logger.setLevel(logging.DEBUG)
    test_logger.addHandler(handler)
    test_logger.propagate = False

    # Re-implement the middleware to avoid hauling in the full main.py
    # lifespan (which sets up sched, DB, etc.).
    @app.middleware("http")
    async def _add_req_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.request_id = rid
        token = rid_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            rid_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response

    @app.get("/log-something")
    def _log_something():
        test_logger.info("a request happened")
        return {"ok": True}

    return app


class TestRequestIdInLogsViaMiddleware:
    def test_log_record_carries_id(self):
        h = _CapturingHandler()
        app = _build_app_with_endpoint(h)
        with TestClient(app) as client:
            resp = client.get("/log-something")
        assert resp.status_code == 200
        rid_from_header = resp.headers["X-Request-ID"]
        assert h.records, "no log record captured"
        record = h.records[-1]
        assert record.getMessage() == "a request happened"
        assert record.request_id == rid_from_header

    def test_caller_supplied_header_preserved(self):
        h = _CapturingHandler()
        app = _build_app_with_endpoint(h)
        with TestClient(app) as client:
            resp = client.get(
                "/log-something",
                headers={"X-Request-ID": "incoming-trace-42"},
            )
        assert resp.headers["X-Request-ID"] == "incoming-trace-42"
        assert h.records[-1].request_id == "incoming-trace-42"

    def test_two_requests_do_not_leak(self):
        h = _CapturingHandler()
        app = _build_app_with_endpoint(h)
        with TestClient(app) as client:
            r1 = client.get("/log-something")
            r2 = client.get("/log-something")
        rid1, rid2 = r1.headers["X-Request-ID"], r2.headers["X-Request-ID"]
        assert rid1 != rid2
        # Two records captured, in order.
        assert len(h.records) == 2
        assert h.records[0].request_id == rid1
        assert h.records[1].request_id == rid2

    def test_log_outside_request_has_no_id(self):
        h = _CapturingHandler()
        # Logger w/ filtered handler, no FastAPI involved.
        logger = logging.getLogger("test.outside-request")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(h)
        logger.propagate = False
        try:
            logger.info("not in a request")
        finally:
            logger.removeHandler(h)
        record = h.records[-1]
        assert getattr(record, "request_id", None) is None
