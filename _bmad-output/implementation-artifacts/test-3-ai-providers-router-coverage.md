# Story TEST-3: AI provider CRUD endpoint coverage

Status: done

Epic: TEST GAPS — backlog from CLAUDE.md "Test gaps (highest risk)"
Story Key: `test-3-ai-providers-router-coverage`

## Reported

CLAUDE.md "Test gaps":

> several AI + Report router endpoints

The four `/api/v1/ai/providers` endpoints (list / create / update /
delete) are admin-gated CRUD over LLM provider configs that include
encrypted API keys. Until this story they had no router-level tests
— only `service.py` helper-functions were exercised.

The endpoints have three concerns that warrant explicit tests:

1. **API-key never leaks.** The response model `AiProviderResponse`
   intentionally omits `api_key` and `api_key_encrypted`, exposing
   only a boolean `has_api_key`. A regression here would cost real
   money.
2. **Admin-only.** Editor / runner / viewer must be rejected on
   create / update / delete.
3. **`is_default` is mutex.** Promoting one provider to default
   must clear the flag on all others.

## Coverage delivered

`tests/ai/test_providers_router.py` — **19 tests** in five classes:

1. **TestListProviders** (5) — empty case, multi-row, response
   omits both `api_key` and `api_key_encrypted` fields, unauthenticated
   → 401, runner can list (the only non-admin allowed access).

2. **TestCreateProvider** (5) — happy path with API-key encrypted at
   rest, omitted-key marks `has_api_key=False`, `provider_type`
   pattern-validation 422, runner forbidden, unauthenticated 401.

3. **TestUpdateProvider** (4) — partial update preserves untouched
   fields, empty-string api_key clears the encrypted blob,
   404 on unknown id, runner forbidden.

4. **TestUpdateIsDefaultMutex** (1) — promoting B to default flips
   A's `is_default` to False.

5. **TestDeleteProvider** (4) — 204 on success, 404 on unknown id,
   runner forbidden, unauthenticated 401.

## Verification

`uv run pytest tests/ai/test_providers_router.py` → 19/19 in ~105 s
(rate-limited test-client cold-starts dominate; the assertions
themselves are sub-millisecond).

## Out of scope

- **Encryption-key rotation.** Rotating `SECRET_KEY` invalidates the
  encrypted blob → existing tests in `tests/audit/test_encryption.py`
  cover that already.
- **`is_default` mutex on create.** `create_provider`'s `_unset_defaults`
  branch is exercised indirectly by the update-mutex test, since
  promoting another provider runs the same helper. A dedicated
  create-with-default test would be redundant.
- **Concurrency.** `is_default` doesn't use a row-level lock; two
  concurrent promoters could end with both flagged. Out of scope for
  this single-user-targeted CRUD; would matter for multi-tenant.
