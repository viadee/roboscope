# Story 1.4: Dry-Run Probe Endpoint

Status: done

Epic: 1 — Enterprise Identity Foundation
Story Key: `1-4-dry-run-probe-endpoint`

## Story

As a RoboScope admin,
I want to validate an IdP configuration by probing its OIDC discovery and JWKS endpoints,
So that I know the configuration is correct before enabling it.

## Acceptance Criteria

1. **AC1 — Probe endpoint.** Given I have the ADMIN role and an existing IdP, when I POST to `/api/v1/auth/idp-providers/{id}/dry-run`, then the backend fetches `{issuer_url}/.well-known/openid-configuration`, validates it contains `authorization_endpoint`, `token_endpoint`, `jwks_uri`, and fetches the JWKS. The response returns a structured report with rows: `issuer_reachable`, `discovery_valid`, `jwks_fetched`, each with `status` (`passed`/`warning`/`failed`) and `detail` message, plus `elapsed_ms` and `overall_status` (`passed`/`failed`).

2. **AC2 — Timeout enforcement.** The entire probe completes within 10 seconds or returns a `failed` result with detail naming the failing phase (`timeout:discovery` or `timeout:jwks`).

3. **AC3 — Unreachable issuer.** Given the issuer URL is unreachable, when I run dry-run, then the response includes `issuer_reachable: failed` with detail "Cannot reach {issuer_url}. Check firewall and egress rules.".

4. **AC4 — Discovery cache populated.** Given a successful probe, then `discovery_cache_json` and `discovery_cached_at` are updated on the IdP row. Given a failed probe, then `discovery_cache_json` is NOT updated (preserve any previous cache).

5. **AC5 — Dry-run status tracked.** After every probe (pass or fail), `last_dry_run_at` is set to current time and `last_dry_run_status` is set to `"passed"` or `"failed"`.

6. **AC6 — RBAC enforcement.** Given I have a role less than ADMIN, when I attempt to run dry-run, then the response is 403 Forbidden.

7. **AC7 — IdP not found.** Given an invalid `idp_id`, when I POST dry-run, then the response is 404.

8. **AC8 — Existing tests green.** The full backend test suite (951+ tests) remains green after all changes.

## Tasks / Subtasks

- [x] **Task 1: Create dry-run response schemas** (AC 1)
  - [x] Added `DryRunCheckRow` and `DryRunProbeResponse` to `src/auth/schemas.py`.

- [x] **Task 2: Create OIDC discovery service** (AC 1, 2, 3, 4, 5)
  - [x] Created `src/auth/oidc_discovery.py` with `probe_idp_discovery()`.
  - [x] Three-phase probe: issuer_reachable → discovery_valid → jwks_fetched.
  - [x] `httpx.Client(timeout=httpx.Timeout(5.0, connect=5.0))` per phase.
  - [x] Updates `last_dry_run_at`/`last_dry_run_status` always, caches discovery only on success.
  - [x] `db.flush()` + `db.refresh(idp)` after updates.

- [x] **Task 3: Add dry-run endpoint to IdP router** (AC 1, 6, 7)
  - [x] Added `POST /{idp_id}/dry-run` with `require_role(Role.ADMIN)`, 404 guard, `db.commit()`.

- [x] **Task 4: Write dry-run tests** (AC 1, 2, 3, 4, 5, 6, 7, 8)
  - [x] Created `tests/auth/test_idp_dry_run.py` with 8 tests — all passing.
  - [x] Fixed respx mock pattern: must use `router.get(...)` inside `with respx.mock() as router:`, not `respx.get(...)` (global router is separate from context manager router).

- [x] **Task 5: Run full test suite + lint** (AC 8)
  - [x] 959 tests passed (951 existing + 8 new). Ruff clean.

### Review Findings

- [x] [Review][Decision→Patch] D1: SSRF policy — Resolved: **HTTPS-only unless `ALLOW_INSECURE_IDP=true` env flag is set.** Applies to both `issuer_url` and discovery-returned `jwks_uri`. Implemented via `_validate_https()` helper at module scope (on-prem IdPs over plain HTTP remain supported via the env flag).
- [x] [Review][Decision→Dismiss] D2: `warning`→`failed` overall mapping — Resolved: keep current behavior (warning-only probe returns `overall_status="failed"`). No code change.
- [x] [Review][Decision→Patch] D3: Response-size cap — Resolved: **Add 1 MB cap.** Implemented via `_MAX_RESPONSE_SIZE = 1_000_000` in the new `_fetch_json_object()` helper; bodies exceeding the cap emit a `failed` check row instead of being parsed.
- [x] [Review][Patch] P1: Non-JSON response now caught — `_fetch_json_object()` wraps `resp.json()` in `try/except (json.JSONDecodeError, ValueError)` and emits a `failed` check row with detail "Invalid JSON response: ...". [`oidc_discovery.py`]
- [x] [Review][Patch] P2: Non-dict/non-list JSON guarded — `_fetch_json_object()` asserts `isinstance(parsed, dict)` before returning; Phase 3 uses `isinstance(jwks_uri, str)` and `isinstance(jwks_data.get("keys"), list)` guards. [`oidc_discovery.py`]
- [x] [Review][Patch] P3: Per-phase timeout reduced from 5s to 4s — `_TIMEOUT_SECONDS = 4.0`. Worst-case 2 network phases × 4s = 8s, leaving ≥2s headroom under the AC2 10s ceiling. [`oidc_discovery.py:23`]
- [x] [Review][Patch] P4: Timeout detail strings now use spec tokens — `timeout:discovery — {url} did not respond within 4s` and `timeout:jwks — {jwks_uri} did not respond within 4s`. [`oidc_discovery.py`]
- [x] [Review][Patch] P5: Cache-preservation test strengthened — `test_dry_run_failed_preserves_existing_cache` now seeds `discovery_cache_json` + `discovery_cached_at` on the IdP before the failing probe and asserts both are preserved. [`tests/auth/test_idp_dry_run.py`]
- [x] [Review][Patch] P6: `db.refresh(idp)` removed from probe — unnecessary re-SELECT after writing fields we already know. [`oidc_discovery.py`]
- [x] [Review][Defer] W1: Service/router persistence split (flush+refresh in service, commit in router) [`oidc_discovery.py:168-169`, `idp_router.py:133-134`] — deferred, project-wide convention
- [x] [Review][Defer] W2: No rate limiting on probe endpoint [`idp_router.py:121-135`] — deferred, cross-cutting policy (Story 2.8)
- [x] [Review][Defer] W3: RBAC test uses id=1 without seeding IdP [`test_idp_dry_run.py:195-203`] — deferred, project pattern
- [x] [Review][Defer] W4: `except httpx.HTTPError` emits "Check firewall" for `InvalidURL`/`UnsupportedProtocol` [`oidc_discovery.py:68-76`] — deferred, Pydantic validates URL format
- [x] [Review][Defer] W5: `issuer_url` whitespace/newline not stripped by Pydantic validator [`schemas.py:76-81`] — deferred, low-risk legacy-data edge

## Dev Notes

### CRITICAL GOTCHAS

1. **`mock_oidc` fixture uses `ISSUER = "https://mock-idp.local"`.** The IdP created in tests MUST use this as `issuer_url` for respx to intercept the calls. Import `ISSUER` from `tests.fixtures.mock_oidc`.

2. **`mock_oidc` uses `respx.mock(assert_all_called=False)`** — not all routes need to be called in every test. For dry-run tests, only discovery and JWKS endpoints are hit (not token endpoint).

3. **Discovery doc required keys from the fixture:**
   ```python
   {"issuer", "authorization_endpoint", "token_endpoint", "jwks_uri",
    "response_types_supported", "subject_types_supported",
    "id_token_signing_alg_values_supported"}
   ```
   The dry-run should validate at minimum: `authorization_endpoint`, `token_endpoint`, `jwks_uri`.

4. **`httpx` is a main dependency** (`httpx>=0.28.0` in pyproject.toml). No need to add it. Use `httpx.Client` (sync), not `AsyncClient` — routes are sync.

5. **Encryption API**: `encrypt_value()` returns `str`, `client_secret_encrypted` is `LargeBinary` (bytes). Decrypt: `decrypt_value(idp.client_secret_encrypted.decode())`. Note: dry-run does NOT need the client secret — it only fetches public endpoints (discovery, JWKS). Do NOT decrypt the secret unnecessarily.

6. **Service uses `flush()`, router does `commit()`.** The dry-run writes to `last_dry_run_at`, `last_dry_run_status`, and optionally `discovery_cache_json`/`discovery_cached_at`, so `db.commit()` IS needed in the router (this is NOT a read-only operation).

7. **Audit middleware auto-logs POST requests.** No explicit audit event needed — the existing middleware at `src/audit/middleware.py` auto-logs all POST/PUT/PATCH/DELETE with user/IP/detail.

8. **Rate limiting** is available via `slowapi` (`src/rate_limit.py`). Consider adding `@limiter.limit("10/minute")` to prevent external network call abuse — but only if the existing router pattern uses it (check first; Story 1.3 endpoints don't use rate limiting).

9. **`discovery_cache_json` stores the full discovery document as JSON string.** Use `json.dumps()` to serialize, `json.loads()` to deserialize. This cache is consumed by Story 1.9 (cache refresh) and Story 2.1 (OIDC flow initiation).

10. **`last_dry_run_status` is `String(20)`** — use short values: `"passed"` or `"failed"`. Do NOT use values longer than 20 chars.

### Schema Spec (authoritative, from Story 1.1)

**Relevant `identity_providers` columns for this story:**
- `discovery_cache_json Text NULL` — populated by successful dry-run
- `discovery_cached_at DateTime NULL` — timestamp of cache population
- `last_dry_run_at DateTime NULL` — set after every dry-run (pass or fail)
- `last_dry_run_status VARCHAR(20) NULL` — `"passed"` or `"failed"`

### Existing Patterns to Follow

**Service pattern** (from `src/auth/idp_service.py`):
```python
from sqlalchemy.orm import Session
from src.auth.models import IdentityProvider

def probe_idp_discovery(db: Session, idp: IdentityProvider) -> DryRunProbeResponse:
    # ... perform HTTP calls ...
    idp.last_dry_run_at = datetime.utcnow()
    idp.last_dry_run_status = overall_status
    db.flush()
    db.refresh(idp)
    return result
```

**Router pattern** (from `src/auth/idp_router.py`):
```python
@router.post("/{idp_id}/dry-run", response_model=DryRunProbeResponse)
def dry_run_idp(
    idp_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    idp = get_identity_provider(db, idp_id)
    if not idp:
        raise HTTPException(status_code=404, detail="Identity provider not found")
    result = probe_idp_discovery(db, idp)
    db.commit()
    return result
```

**Mock OIDC test pattern** (from `tests/fixtures/mock_oidc.py`):
```python
from tests.fixtures.mock_oidc import ISSUER, mock_oidc  # noqa: F401

def test_dry_run_success(client, admin_headers, mock_oidc, db_session):
    # Create IdP with mock issuer URL
    idp_data = {**VALID_IDP_DATA, "issuer_url": ISSUER}
    create_resp = client.post(BASE_URL, json=idp_data, headers=admin_headers)
    idp_id = create_resp.json()["id"]
    # Run dry-run
    resp = client.post(f"{BASE_URL}/{idp_id}/dry-run", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_status"] == "passed"
```

### Previous Story Learnings

- **Story 1.1**: All Phase-4 model columns (`discovery_cache_json`, `last_dry_run_at`, etc.) already exist. No migration needed.
- **Story 1.2**: `mock_oidc` fixture provides `MockOidcProvider` with discovery, JWKS, and token mocks via respx. Import from `tests.fixtures.mock_oidc`.
- **Story 1.3**: IdP CRUD is complete. `get_identity_provider(db, idp_id)` returns `IdentityProvider | None`. Router + service patterns established. `issuer_url` validated to start with `http(s)://`.
- **Story 1.3 review**: `IntegrityError` handling added to `create_idp`. `issuer_url` validation and `client_secret: null` rejection added. Line length kept under 100 chars.

### File Layout

```
backend/
├── src/auth/
│   ├── oidc_discovery.py           [NEW — probe_idp_discovery service function]
│   ├── idp_router.py               [MOD — add POST /{idp_id}/dry-run endpoint]
│   └── schemas.py                  [MOD — add DryRunCheckRow, DryRunProbeResponse]
└── tests/
    └── auth/
        └── test_idp_dry_run.py     [NEW — ~8 dry-run tests]
```

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` — NFR2 (10s timeout), httpx TLS 1.2+ enforcement
- PRD: `_bmad-output/planning-artifacts/prd.md` — FR1-FR6 (IdP validation, dry-run-before-save gate)
- Epics: `_bmad-output/planning-artifacts/epics.md` — Story 1.4 section
- Mock OIDC fixture: `backend/tests/fixtures/mock_oidc.py` — `MockOidcProvider`, `ISSUER` constant
- Existing IdP service: `backend/src/auth/idp_service.py` (patterns)
- Existing IdP router: `backend/src/auth/idp_router.py` (patterns)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- respx 0.23 + httpx 0.28: `respx.get(...)` inside `with respx.mock() as router:` registers on the global router, not the active context manager router. Must use `router.get(...)` for mocks to take effect.

### Completion Notes List

- All 8 ACs satisfied. 8 tests cover happy path, DB field updates, 3 failure modes (unreachable, bad discovery, bad JWKS), 404, RBAC 403, and cache-not-updated-on-failure.
- `datetime.now(timezone.utc)` used instead of deprecated `datetime.utcnow()`.

### Change Log

- `src/auth/schemas.py` — Added `DryRunCheckRow`, `DryRunProbeResponse` schemas
- `src/auth/oidc_discovery.py` — NEW: `probe_idp_discovery()` service function (176 LOC)
- `src/auth/idp_router.py` — Added `POST /{idp_id}/dry-run` endpoint + imports
- `tests/auth/test_idp_dry_run.py` — NEW: 8 tests for dry-run endpoint

### File List

- `backend/src/auth/schemas.py`
- `backend/src/auth/oidc_discovery.py`
- `backend/src/auth/idp_router.py`
- `backend/tests/auth/test_idp_dry_run.py`
