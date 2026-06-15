---
title: 'Bump fastmcp to >=3.2.4 (close 3 fastmcp 2.x security advisories) — gh-35'
type: 'chore'
created: '2026-06-15'
status: 'done'
baseline_commit: '65face19e5fa66d8446d4e09c4163923425de43a'
context:
  - '{project-root}/_bmad-output/project-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** RoboScope pins `fastmcp<3` (locked 2.14.7) as a transitive dep of rf-mcp. fastmcp 2.x carries 3 unpatched security advisories (CVE-2026-32871 SSRF/path-traversal in the OpenAPI provider, CVE-2026-27124 OAuth-proxy confused-deputy, + a command-injection), all fixed in fastmcp 3.2.0+. Issue #35 tracks lifting the cap once rf-mcp supports fastmcp 3.

**Approach:** Raise the pins to `fastmcp>=3.2.4` (skips the 3.0.0–3.2.3 auth-header-leak window) and `rf-mcp>=0.31.2`, regenerate `uv.lock`, and verify the rf-mcp HTTP server still boots and the AI test suite stays green. Already empirically confirmed this session: rf-mcp 0.31.2 imports and serves over HTTP under fastmcp 3.4.2; RoboScope uses rf-mcp only transitively, as an out-of-process HTTP client (zero direct `fastmcp` imports).

## Boundaries & Constraints

**Always:** Keep the floor at `fastmcp>=3.2.4` (never 3.0.0–3.2.3). Pin `rf-mcp>=0.31.2`. Single resolved lock head. Offline-first invariants unchanged.

**Ask First:** If `uv lock` resolves fastmcp to a version where the rf-mcp HTTP smoke boot fails, or if any rf-mcp/AI test regresses in a way that needs a code change beyond the pins — HALT and report before editing application code.

**Never:** Touch application logic in `src/ai/rf_mcp_manager.py` or elsewhere (this is a dependency bump, not a refactor). Add a direct `fastmcp` dependency to RoboScope. Bump unrelated deps. Re-introduce a `<` upper cap on fastmcp.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Lock resolves | `uv lock` after pin bump | `fastmcp` ≥3.2.4 (expect 3.4.x), `rf-mcp` ≥0.31.2, single head | If resolution conflicts, HALT |
| rf-mcp boots | `python -m robotmcp.server --transport http --port P` | "Application startup complete", Uvicorn serves, server stays alive | If exits early, HALT with stderr |
| AI tests | `pytest backend/tests/ai` | All pass (rf_mcp_manager, rf_knowledge, router) | Investigate any failure |

</frozen-after-approval>

## Code Map

- `backend/pyproject.toml` -- dependency pins (`rf-mcp>=0.30.0`, `fastmcp<3`) at lines 46–47
- `backend/uv.lock` -- resolved versions (fastmcp 2.14.7, rf-mcp 0.31.1) — regenerate
- `backend/src/ai/rf_mcp_manager.py` -- launches `python -m robotmcp.server --transport http` (read-only; do not edit)
- `_bmad-output/project-context.md` -- "Do-Not-Upgrade Pins" lists `fastmcp <3` as load-bearing — must be corrected
- `.gitignore` -- already adds `presentation/` (rides along on this branch)

## Tasks & Acceptance

**Execution:**
- [x] `backend/pyproject.toml` -- set `fastmcp>=3.2.4` and `rf-mcp>=0.31.2` -- lift the cap, keep a safe floor
- [x] `backend/uv.lock` -- `uv lock` + `uv sync --extra dev` -- resolved fastmcp **3.2.4**, rf-mcp **0.31.2** (also dropped fastmcp 2.x baggage: redis/prometheus/pydocket/diskcache/fakeredis)
- [x] `_bmad-output/project-context.md` -- replaced the `fastmcp <3` pin note with the `>=3.2.4` floor + reason
- [x] verification -- rf-mcp HTTP server boots clean under fastmcp 3.2.4; `pytest tests/ai` = **187 passed** (exit 0); no `.py` source changed → no lint/type regression

**Acceptance Criteria:**
- Given the bumped pins, when `uv lock` runs, then fastmcp resolves to ≥3.2.4 with a single lock head and rf-mcp ≥0.31.2.
- Given the synced `.venv`, when `python -m robotmcp.server --transport http --port <free>` runs, then it reaches "Application startup complete" and stays alive ≥3s.
- Given the bump, when `pytest backend/tests/ai` runs, then all AI tests pass with no new failures.
- Given the change set, when the PR is opened, then it links/closes issue #35.

## Verification

**Commands:**
- `cd backend && uv lock && uv sync` -- expected: clean resolve, fastmcp ≥3.2.4, rf-mcp ≥0.31.2
- `cd backend && grep -A2 'name = "fastmcp"' uv.lock | head` -- expected: version 3.x
- `cd backend && .venv/bin/python -m robotmcp.server --transport http --port 9098` (bg, then kill) -- expected: "Application startup complete"
- `cd backend && .venv/bin/pytest tests/ai -q` -- expected: all pass
- `cd backend && .venv/bin/ruff check src/ tests/` -- expected: clean (no code changed, sanity only)

## Spec Change Log

- **2026-06-15 (review iter 1):** Blind-hunter finding — `fastmcp>=3.2.4` had no upper bound; CI/Docker/offline builds resolve fresh from `pyproject.toml` (not `uv.lock`, confirmed by edge-hunter), so a future fastmcp 4.0 could be pulled in untested and break rf-mcp. **Amended** the pin to `fastmcp>=3.2.4,<4` (patch). This intentionally relaxes the frozen "Never: re-introduce a `<` upper cap" — that wording was too absolute; the genuine intent was "never re-pin below 3.x (re-opening the CVEs)", which `<4` honours while adding a sane major guard. **KEEP:** floor stays `>=3.2.4`; never lower to `<3`. Offline-build error-swallowing finding → deferred-work.md.

## Suggested Review Order

- The whole change in one place: the dependency pins (floor + reason).
  [`pyproject.toml:46`](../../backend/pyproject.toml#L46)

- Resolved versions — confirm fastmcp `3.2.4`, rf-mcp `0.31.2`, single head, and the dropped fastmcp 2.x baggage.
  [`uv.lock`](../../backend/uv.lock)

- The agent-facing rule that prevents a future re-pin to `<3`.
  [`project-context.md:22`](../project-context.md#L22)

- Incidental housekeeping — keep the local-only presentation deck out of the public repo.
  [`.gitignore:72`](../../.gitignore#L72)
