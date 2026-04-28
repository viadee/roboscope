# Story ROBUSTNESS-1: Streaming upload-size guard + deep health-check

Status: done

Epic: SECURITY / OPS — backlog from CLAUDE.md "Known open issues"
Story Key: `robustness-1-stream-upload-and-deep-health`

## Reported

Two related items from CLAUDE.md "Known open issues":

> missing upload size limits

> shallow health-check

### Upload — actual issue

`/reports/upload` *does* have a 500 MB cap, but it reads the **whole
body into memory before** checking the size:

```python
content = file.file.read()             # blocks RAM
if len(content) > MAX_UPLOAD_BYTES:
    raise HTTPException(413, ...)
```

A hostile client posting 10 GB exhausts the worker's RAM long before
the 413 fires. The cap is a *post-hoc* check, not an enforcement.

### Health-check — actual issue

`GET /health` reports `{"status": "healthy"}` without ever touching
the database, the task executor, or the WebSocket loop. A deployment
with a hung DB connection or a crashed in-process task pool still
returns 200 → orchestrators (Kubernetes, ECS, Docker Compose
healthcheck) see "healthy" and don't restart the pod.

## The fix

### SECURITY-2 — stream the upload and abort early

1. Read the upload in 1 MiB chunks.
2. Track `total_bytes`; raise 413 the moment it crosses
   `MAX_UPLOAD_BYTES`.
3. Also reject upfront if the request's `Content-Length` header
   already exceeds the limit (cheap, before any body bytes hit us).
4. Buffer the chunks into a `BytesIO` only if we're under the limit,
   so the existing `zipfile.is_zipfile(io.BytesIO(content))` check
   keeps working.

### OPS-1 — deep health-check

`GET /health` now executes a single `SELECT 1` against the DB. Two
response shapes:

- **200 `{"status": "healthy", ...}`** — DB roundtrip succeeded.
- **503 `{"status": "unhealthy", "reason": "database_unreachable"}`** —
  DB roundtrip raised. Body still includes `version` so log
  consumers can correlate.

Existing fields stay (`version`, `database` flavour,
`task_executor`) so a kubelet's existing `livenessProbe.path: /health`
keeps working unchanged.

## Acceptance Criteria

1. **AC1 — Streaming size guard.** `/reports/upload` rejects oversize
   uploads without ever materialising the full payload in RAM.
   Verified in `tests/reports/test_upload_size.py` by feeding a
   chunked stream that's 600 MB virtually but < 1 MB physically
   (asserts memory usage indirectly via "we never crashed").

2. **AC2 — Content-Length pre-check.** Requests whose
   `Content-Length` header already exceeds the cap are rejected
   *before* the body reads — 413 with no bytes consumed.

3. **AC3 — Health 200 happy path.** `GET /health` returns 200 with
   the existing fields when the DB roundtrip succeeds.

4. **AC4 — Health 503 on DB outage.** When the DB is unreachable
   (simulated by mocking `engine.connect()` to raise),
   `GET /health` returns 503 with
   `{"status": "unhealthy", "reason": "database_unreachable", ...}`.

5. **AC5 — Tests.**
   - `test_upload_rejects_oversize_content_length` — 413 from the
     header before any body is read.
   - `test_upload_rejects_oversize_streamed` — 413 once the chunk
     loop crosses the limit.
   - `test_upload_accepts_under_limit` — small valid ZIP still
     ingests.
   - `test_health_200_when_db_ok` — happy path.
   - `test_health_503_when_db_down` — patched DB.

## Out of scope (V1)

- **Per-tenant upload quotas**. Cap is global. Per-team quotas
  belong with Phase 5 (multi-tenancy) infrastructure.
- **Health-checks for the WebSocket loop / task executor**. Both
  are in-process; if the worker is alive enough to respond at all,
  they're alive. A dedicated `/healthz/deep` could probe them, but
  it's noise for the orchestrator's livenessProbe.
- **Streaming the entire ingest path (zip extraction, file copy)**.
  The fix is only about the upload-receive boundary. Zip extraction
  itself is bounded by the (now-enforced) 500 MB cap.

## Risk notes

- **chunk size = 1 MiB**: a tiny sniff at 4 KiB feels safer but
  costs hundreds of `read()` syscalls per upload. 1 MiB matches the
  default httpcore chunk size and is well below typical worker
  memory headroom.
- **`Content-Length` can be absent or wrong** (chunked-encoded
  uploads, intermediaries). The streaming guard is the real
  enforcement; the header pre-check is purely an optimisation that
  rejects the malicious 10 GB cases without reading a single byte.
- **DB roundtrip latency on /health**. A `SELECT 1` is sub-ms on
  SQLite and Postgres. If the DB is *slow* (not down), the health
  endpoint slows accordingly — orchestrators with aggressive
  liveness timeouts will see flapping. Mitigation: 2 s timeout on
  the connection; if the connect itself blocks, return 503.
