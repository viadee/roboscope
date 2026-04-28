# Story LOGGING-1: Propagate the request ID into every log record

Status: done

Epic: OBSERVABILITY — backlog from CLAUDE.md "Known open issues"
Story Key: `logging-1-request-id-correlation`

## Reported

CLAUDE.md "Known open issues" lists:

> plaintext logging only

The literal claim is no longer accurate — `pythonjsonlogger.JsonFormatter`
has been wired into the root handler in `main.py:lifespan` for a while
already. What's still missing is **request correlation**: a request
travels through routers, services, and background-task hand-offs, but
nothing in those log lines tells you which HTTP request triggered the
work. Operators end up grepping by timestamp ± user, which is brittle.

The existing `add_request_id` middleware (`main.py:259`) generates a
`X-Request-ID` and stores it on `request.state`, but the value never
makes it into log records.

## The fix

1. New `src/logging_context.py` module:
   - `request_id_var: ContextVar[str | None]` — async-aware storage.
   - `class RequestIdFilter(logging.Filter)` — pulls the ContextVar
     and stamps `record.request_id = ...` on every log record.

2. The middleware sets the ContextVar at the top of the request
   (and resets it at the end via the `Token` returned by `set()`).

3. The JsonFormatter is updated to include `request_id` whenever
   present (default-omitted when not — i.e. background tasks
   without an HTTP origin won't get a phantom field).

4. The `RequestIdFilter` is attached to the root handler so EVERY
   logger in the app (`roboscope.repos`, `roboscope.execution`,
   `roboscope.auth`, …) inherits it.

## Acceptance Criteria

1. **AC1 — `request_id` in every log line under a request.** A
   handler that emits `logger.info("...")` produces a JSON record
   with `"request_id": "<id>"` matching the response's
   `X-Request-ID` header.

2. **AC2 — `request_id` absent outside HTTP requests.**
   Background-task threads / startup / shutdown logs have no
   `request_id` field (rather than `null` or empty string).

3. **AC3 — Caller-supplied IDs preserved.** When the client passes
   `X-Request-ID: abc-123`, that exact value lands in both the
   response header AND the log record.

4. **AC4 — UUID prefix when client omits the header.** Same 12-char
   UUID hex prefix the existing middleware already uses
   (no breaking change).

5. **AC5 — Tests.**
   - `test_request_id_propagates_to_logs` — caplog assertion that
     a log emitted inside an endpoint has `record.request_id`
     matching the response header.
   - `test_request_id_isolated_between_requests` — two sequential
     requests; assert each log line carries that request's id only.
   - `test_request_id_unset_outside_request` — a log emitted on a
     thread without the ContextVar set produces a record where
     `getattr(record, "request_id", None) is None`.

## Out of scope (V1)

- **Trace context propagation (W3C Trace Context, OpenTelemetry).**
  A separate, larger story. We don't pretend to do distributed
  tracing here — just intra-process correlation.
- **Cross-thread propagation to background tasks.**
  `task_executor` runs jobs in a separate thread that doesn't
  inherit the request's ContextVar. To carry the id across, we'd
  need to capture+restore at submit time. Out of scope; if needed,
  pass the id explicitly as a task arg.
- **Filtering high-cardinality fields out of metrics**. We log,
  we don't aggregate.

## Risk notes

- **`ContextVar` semantics.** `set()` returns a `Token` that
  `reset()` consumes; the middleware MUST reset on the way out
  (in a `finally` block) or the var leaks across the connection's
  next request (uvicorn reuses worker tasks for keep-alive).
- **Test isolation.** `caplog.records` see the filter-stamped
  attribute only if the test goes through the same handler chain.
  The fixture installs the filter once per test session.
