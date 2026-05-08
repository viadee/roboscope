# Story 1.5: Encrypted client_secret Storage

Status: done

Epic: 1 — Enterprise Identity Foundation
Story Key: `1-5-encrypted-client-secret-storage`

## Story

As a Security engineer,
I want OIDC client secrets stored encrypted at rest using Fernet via the existing `is_secret=True` pattern,
So that a database dump does not expose plaintext IdP credentials.

## Acceptance Criteria

1. **AC1 — At-rest encryption.** Given I create or update an IdP configuration with a `client_secret`, when the record is persisted, then `identity_providers.client_secret_encrypted` contains a Fernet-encrypted value (stored as `LargeBinary` bytes) and the plaintext value is never written to the database, any application log file, or any API response body.

2. **AC2 — In-memory decrypt for token exchange.** Given the backend needs to perform an OIDC token exchange, when it loads the IdP configuration, then the client_secret is decrypted in-memory via `src/encryption.py` and the plaintext is used only for the outbound HTTPS request — never logged, never serialized in a response, never persisted to a file.

3. **AC3 — Legacy plaintext graceful-decrypt fallback.** Given `SECRET_KEY` has been rotated or the row was written before encryption was in place, when an IdP is read from the DB and the `client_secret_encrypted` bytes are not a valid Fernet token, then the value is treated as legacy plaintext (UTF-8 decode and return as-is) — consistent with the Phase-2 secret handling pattern in `src/environments/service.py:237-243`.

4. **AC4 — Response schema never exposes secret.** `IdentityProviderResponse` (and any other IdP response schema) must never include `client_secret`, `client_secret_encrypted`, or any derived plaintext. Regression-tested.

5. **AC5 — Audit middleware does not log the request body.** The audit middleware must continue to log only `{method, path, status_code}` (not request JSON body), so a POST/PATCH carrying `client_secret` never writes the plaintext into the `audit_logs.detail` column. Regression-tested.

6. **AC6 — Existing tests green.** Full backend test suite (959+ tests) remains green after all changes.

## Tasks / Subtasks

- [x] **Task 1: Add `get_decrypted_client_secret()` helper** (AC 2, 3)
  - [x] Added to `src/auth/idp_service.py`. Uses `decrypt_value()` via try/except; on `InvalidToken` returns the stored string as-is (legacy plaintext fallback).
  - [x] No logging of plaintext.

- [x] **Task 2: Verify at-rest encryption for create + update paths** (AC 1)
  - [x] `create_identity_provider` / `update_identity_provider` (Story 1.3) already call `encrypt_value(...).encode()` before writing. No bypass path found.
  - [x] `IdentityProviderResponse` has no `client_secret*` field.
  - [x] All IdP response endpoints use `IdentityProviderResponse`.

- [x] **Task 3: Audit middleware regression guard** (AC 5)
  - [x] Structural regression test added: `test_audit_middleware_does_not_capture_request_body` inspects `src/audit/middleware.py` source and asserts no `request.body`/`request.json`/`.body()`/`request.stream` invocation. Positive check that detail is limited to `method + path + status_code`.
  - [x] Runtime log-capture test added: `test_client_secret_not_in_logs` uses `caplog` at DEBUG across all loggers and asserts the plaintext secret never appears. Note: the middleware's background thread uses a separate `SessionLocal`, so direct DB assertion on `audit_logs` rows from the test session is unreliable — structural inspection is the authoritative guarantee.

- [x] **Task 4: Write tests** (AC 1–5)
  - [x] Created `backend/tests/auth/test_idp_client_secret.py` with 6 tests:
    - `test_client_secret_encrypted_at_rest` — plaintext bytes are NOT in `client_secret_encrypted`; `is_encrypted()` returns True for the stored ciphertext.
    - `test_client_secret_not_in_response_body` — POST/GET/LIST/PATCH responses never contain `"client_secret"`, `"client_secret_encrypted"`, or the plaintext string.
    - `test_get_decrypted_client_secret_roundtrip` — helper returns the original plaintext.
    - `test_get_decrypted_client_secret_legacy_plaintext_fallback` — raw-bytes (non-Fernet) `client_secret_encrypted` is returned as UTF-8 plaintext.
    - `test_audit_middleware_does_not_capture_request_body` — structural regression guard (inspects middleware source).
    - `test_client_secret_not_in_logs` — `caplog` at DEBUG; plaintext never appears in any captured log record.

- [x] **Task 5: Run full suite + lint** (AC 6)
  - [x] `pytest` → **965 passed** (959 existing + 6 new), 9 warnings (pre-existing).
  - [x] No new ruff violations. (Pre-existing `pyproject.toml` config warning unrelated.)

### Review Findings

- [x] [Review][Decision→Patch] D1/P6: SECRET_KEY rotation handling — Resolved: **(b) Emit `logger.warning` on fallback with IdP ID**, no value logged. Implemented via `logger = logging.getLogger("roboscope.auth.idp")` + warning in the fallback branch of `get_decrypted_client_secret`.
- [x] [Review][Patch] P1: Exception catch broadened — Switched to `is_encrypted()`-first preflight (matches `src/environments/service.py:237-243` pattern exactly). No more narrow `except InvalidToken`; malformed-ciphertext and rotation scenarios all route through the same legacy-plaintext branch. [`backend/src/auth/idp_service.py`]
- [x] [Review][Patch] P2: None / empty / non-UTF-8 guard added — `get_decrypted_client_secret` now raises `ValueError` for None/empty bytes (DB drift signal) and for non-UTF-8 bytes (cannot interpret). Decode moved inside a try/except-UnicodeDecodeError block. [`backend/src/auth/idp_service.py`]
- [x] [Review][Patch] P3: Rotation-scenario test added — `test_rotated_secret_key_falls_back_with_warning` encrypts under a temporarily-patched `SECRET_KEY`, restores, asserts fallback is taken AND a warning log record is emitted. [`backend/tests/auth/test_idp_client_secret.py`]
- [x] [Review][Patch] P4: 422-validation-error hygiene test added — `test_422_validation_error_does_not_echo_client_secret` sends POST with invalid `issuer_url`/valid secret; asserts plaintext not in 422 body. [`backend/tests/auth/test_idp_client_secret.py`]
- [x] [Review][Patch] P5: Audit-middleware body-blind guard tightened — Forbidden list extended with `request.form`, `request.receive`, `request._body`, `request.scope`. [`backend/tests/auth/test_idp_client_secret.py`]
- [x] [Review][Patch] P2-bonus: DB-drift regression test — `test_null_or_empty_client_secret_raises` asserts `ValueError` on empty bytes (guard works). [`backend/tests/auth/test_idp_client_secret.py`]
- [x] [Review][Defer] W1: Response-body test uses top-level key check — brittle but schema is flat; `SECRET not in resp.text` already catches leaks — deferred, low value now.
- [x] [Review][Defer] W2: No logging/metric when fallback fires [tied to D1] — deferred, revisit with SECRET_KEY rotation tooling
- [x] [Review][Defer] W3: caplog may miss daemon-thread / non-propagating logger records — deferred, no current leak vector
- [x] [Review][Defer] W4: No sanity test that audit middleware row actually writes — deferred, separate audit-middleware health concern
- [x] [Review][Defer] W5: Legacy-fallback test doesn't assert stored bytes stay plaintext post-commit — deferred, no re-encrypt event handler exists

## Dev Notes

### CRITICAL GOTCHAS

1. **Encryption is ALREADY implemented** in Story 1.3's `idp_service.py:39, 58` — `encrypt_value(data.client_secret).encode()` runs on every create/update. This story's job is (a) add the **decrypt** helper for Story 2.1 to consume, (b) add the **legacy-plaintext fallback**, and (c) add **regression tests** proving secret never leaks. Do NOT re-implement encryption.

2. **`client_secret_encrypted` column is `LargeBinary`** (bytes), not `Text`. `encrypt_value()` returns `str`, so the create/update code calls `.encode()` to convert. The decrypt helper must symmetrically `.decode()` before passing to `decrypt_value()`.

3. **Phase-2 legacy-plaintext pattern** lives in `src/environments/service.py:237-243`:
   ```python
   from src.encryption import decrypt_value, is_encrypted
   if is_encrypted(var.value):
       return decrypt_value(var.value)
   return var.value  # Legacy plaintext secret — return as-is
   ```
   Mirror this shape in `get_decrypted_client_secret`. Note: `is_encrypted()` in `src/encryption.py:36-43` returns True only if Fernet decrypt succeeds; it catches `(InvalidToken, Exception)` broadly.

4. **Audit middleware is body-blind.** `src/audit/middleware.py:121` composes `detail` from `method + path + status` only. The Story 1.3 review's W1 deferred item ("Audit middleware logs `client_secret` in plaintext") was based on a misreading — this story CONFIRMS by regression test that no body ever lands in `audit_logs.detail`. Do NOT add body capture.

5. **Never log the secret.** `get_decrypted_client_secret()` must not call `logger.info()`/`logger.debug()` with the plaintext. If you want a diagnostic log, log a boolean ("fernet" vs "legacy-plaintext") — NOT the value.

6. **`IdentityProviderResponse` does NOT include any secret field.** It currently exposes: `id, name, provider_type, issuer_url, client_id, scopes, group_claim_name, is_enabled, last_dry_run_at, last_dry_run_status, created_at, updated_at`. Keep it that way.

7. **Test client_secret values should be realistic-looking** (e.g., `"s3cret-v4lu3"`, not just `"secret"`) — a 6-char substring is more likely to produce false positives in a response body / log search.

8. **`caplog` and log propagation** — the project uses named loggers (`roboscope`, `roboscope.audit`, etc.). To capture across all, use `caplog.set_level(logging.DEBUG)` with no logger filter. Verify test scope is right.

9. **SECRET_KEY rotation scenario** is tested by inserting a row whose `client_secret_encrypted` is NOT a valid Fernet token for the current key. The cleanest way: write raw bytes (e.g., `b"plain-legacy-secret"`) that cannot be interpreted as Fernet ciphertext. Fernet decrypt raises `InvalidToken`; fallback kicks in.

10. **No migration, no schema change.** The `client_secret_encrypted: LargeBinary NOT NULL` column already exists (Story 1.1). Do not add a new migration.

### Existing Patterns to Follow

**Legacy-plaintext fallback pattern** (from `src/environments/service.py:237-243`):
```python
from src.encryption import decrypt_value, is_encrypted

if is_encrypted(value):
    return decrypt_value(value)
return value  # Legacy plaintext — return as-is
```

**Service-layer decrypt helper** (proposed for this story):
```python
# src/auth/idp_service.py
from cryptography.fernet import InvalidToken

from src.encryption import decrypt_value


def get_decrypted_client_secret(idp: IdentityProvider) -> str:
    """Return the IdP client_secret as plaintext. For outbound OIDC use only."""
    stored = idp.client_secret_encrypted.decode("utf-8")
    try:
        return decrypt_value(stored)
    except InvalidToken:
        # Legacy plaintext (pre-encryption rows or post SECRET_KEY rotation)
        return stored
```

**Create IdP via API test pattern** (from existing `tests/auth/test_idp_crud.py`):
```python
VALID_IDP_DATA = {
    "name": "...",
    "provider_type": "oidc_azure_ad",
    "issuer_url": "https://mock-idp.local",
    "client_id": "...",
    "client_secret": "s3cret-v4lu3",
    "scopes": "openid profile email",
    "group_claim_name": "groups",
}
resp = client.post("/api/v1/auth/idp-providers", json=VALID_IDP_DATA, headers=headers)
```

### Previous Story Learnings

- **Story 1.1**: `IdentityProvider.client_secret_encrypted` is `LargeBinary NOT NULL`. No schema work needed here.
- **Story 1.3**: `create_identity_provider` / `update_identity_provider` already encrypt via `encrypt_value(secret).encode()`. Router commits after `db.flush()` in the service.
- **Story 1.3 review**: `client_secret: null` on PATCH is rejected by `model_validator`. Means test for decrypt helper needs a valid secret string on every update.
- **Story 1.4**: Service/router split established (`db.flush()` in service, `db.commit()` in router). The decrypt helper is read-only, so no flush/commit needed.
- **Story 1.4 review** (**W1 deferred item**): Audit middleware only logs `{method, path, status}` — the deferred concern from Story 1.3 review was based on a misreading; this story formally regression-tests that the plaintext never enters the audit log, closing W1.

### File Layout

```
backend/
├── src/auth/
│   └── idp_service.py                    [MOD — add get_decrypted_client_secret()]
└── tests/
    └── auth/
        └── test_idp_client_secret.py     [NEW — ~6 tests]
```

No new files in `src/`; no new migrations; no router changes.

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md:155` — "Client-Secret-Storage: Fernet-verschlüsselt in `IdentityProvider.client_secret_encrypted: LargeBinary` via existierendem `is_secret=True`-Pattern in `src/encryption.py`"
- Architecture: `_bmad-output/planning-artifacts/architecture.md:71` — "Fernet via `src/encryption.py` und `SECRET_KEY` — `is_secret=True`-Pattern für `IdentityProvider.client_secret_encrypted`"
- PRD: `_bmad-output/planning-artifacts/prd.md` — NFR5 (client secret encryption)
- Epics: `_bmad-output/planning-artifacts/epics.md:518-538` — Story 1.5 section
- Existing encryption helpers: `backend/src/encryption.py`
- Phase-2 precedent: `backend/src/environments/service.py:237-243` — legacy-plaintext fallback
- Existing IdP service: `backend/src/auth/idp_service.py:32-63` (already performs encryption on create/update)
- Audit middleware: `backend/src/audit/middleware.py:77-129` (body-blind)
- Deferred work: `_bmad-output/implementation-artifacts/deferred-work.md` — "Deferred from: code review of 1-3" W1 (addressed by AC5 of this story)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- Audit middleware runs its DB writes in a daemon thread that instantiates a fresh `SessionLocal()` — this session bypasses the test fixture's `dependency_overrides[get_db]`, so test-session queries on `AuditLog` never see middleware rows. Replaced DB-level assertion with structural source inspection for AC5.

### Completion Notes List

- All 6 ACs satisfied. Plaintext never leaks to DB, response bodies, or logs. Decrypt helper provides Fernet + legacy-plaintext fallback consistent with Phase-2 pattern.
- Story 1.3 deferred W1 closed: audit middleware is body-blind by construction and now has a regression test to keep it that way.

### Change Log

- `src/auth/idp_service.py` — Added `get_decrypted_client_secret(idp)` helper with Fernet + legacy-plaintext fallback. New imports: `cryptography.fernet.InvalidToken`, `src.encryption.decrypt_value`.
- `tests/auth/test_idp_client_secret.py` — NEW: 6 tests covering encryption at rest, response hygiene, decrypt roundtrip, legacy fallback, audit-middleware body-blindness, log hygiene.

### File List

- `backend/src/auth/idp_service.py`
- `backend/tests/auth/test_idp_client_secret.py`
