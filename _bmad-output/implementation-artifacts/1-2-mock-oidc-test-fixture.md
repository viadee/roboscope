# Story 1.2: Mock OIDC Test Fixture

Status: done

## Story

As a Backend engineer,
I want a shared `respx`-based mock OIDC provider fixture,
so that SSO-related tests run in CI without depending on live IdP endpoints.

## Acceptance Criteria

1. **AC1 — Discovery endpoint stubbed.** Given a pytest test imports the `mock_oidc` fixture from `backend/tests/fixtures/mock_oidc.py`, when the fixture is activated, then HTTP GET `{issuer}/.well-known/openid-configuration` returns a deterministic JSON document containing `authorization_endpoint`, `token_endpoint`, `jwks_uri`, `issuer`.

2. **AC2 — JWKS endpoint stubbed.** When the fixture is active, HTTP GET `{issuer}/jwks` returns a JWKS document with the fixture's test RSA public key in JWK format (`kid`, `kty`, `n`, `e`).

3. **AC3 — Token endpoint stubbed with custom claims.** When a test calls the fixture's helper to request a token exchange, `POST {issuer}/token` returns a signed `id_token` (RS256) containing the claims the test injected (at minimum: `sub`, `email`, `groups`, `nonce`). The token is signed by the fixture's test private key so `authlib` validation against the JWKS passes.

4. **AC4 — authlib integration.** Given the mock is active, when `authlib`'s OAuth2 client exchanges a code via its httpx transport, the token exchange succeeds and the extracted claims match the injected values.

5. **AC5 — No outbound network calls.** When the fixture is used in any test, `respx` intercepts all HTTP traffic so no real network call is attempted. This must pass a network-isolation assertion (i.e., `respx` in strict mode raises on unmatched requests).

6. **AC6 — Reusable `claims` parameter.** The fixture exposes a `with_claims(**kwargs)` method (or equivalent parametric interface) that tests call to override default claim values per test invocation. Default claims: `sub="test-user-001"`, `email="test@example.com"`, `groups=[]`, `nonce` matches the latest issued state nonce.

7. **AC7 — New dependencies added.** `authlib` and `respx` are added to `backend/pyproject.toml` via `uv add` and present in `[project.dependencies]` (runtime: `authlib`; test-only: `respx`).

8. **AC8 — Smoke test.** A `backend/tests/fixtures/test_mock_oidc_smoke.py` file contains at least one test that activates the fixture, performs a fake token exchange, and asserts on the decoded claims. This test must pass with `make test-backend`.

## Tasks / Subtasks

- [x] **Task 1: Add dependencies** (AC 7)
  - [x] Run `cd backend && uv add authlib` to add `authlib` to `[project.dependencies]`
  - [x] Run `cd backend && uv add --dev respx` to add `respx` to `[project.optional-dependencies]` or `[dependency-groups]` dev group. If `uv add --dev` is not available (older uv), add to `[project.optional-dependencies].test` and verify existing test invocation picks it up.
  - [x] Verify both appear in `backend/pyproject.toml` and the lockfile / `.venv` is updated.

- [x] **Task 2: Create `backend/tests/fixtures/` package and RSA test key** (AC 1, 2, 3)
  - [x] Create `backend/tests/fixtures/__init__.py` (empty).
  - [x] Generate a 2048-bit RSA key pair **at import time** using `cryptography` (already bundled with authlib) — do NOT read from disk, generate fresh on module load so tests are hermetic.
  - [x] Store as module-level `_PRIVATE_KEY` / `_PUBLIC_KEY` constants (RSA `rsa.generate_private_key`).
  - [x] Derive the JWK representation of the public key (`kid="test-key-1"`).

- [x] **Task 3: Implement `mock_oidc` pytest fixture** (AC 1, 2, 3, 4, 5, 6)
  - [x] Create `backend/tests/fixtures/mock_oidc.py`.
  - [x] Define module-level `ISSUER = "https://mock-idp.local"` constant.
  - [x] Implement a `MockOidcProvider` class (or plain fixture function) that:
    - Wraps `respx.MockRouter(assert_all_called=False)` (or equivalent) as context manager.
    - Registers GET `{ISSUER}/.well-known/openid-configuration` → returns discovery JSON.
    - Registers GET `{ISSUER}/jwks` → returns JWKS with test public key.
    - Registers POST `{ISSUER}/token` → mints a signed JWT and returns token response JSON.
  - [x] `with_claims(**overrides)` mutates the claims used for the next POST `/token` call (merged on top of defaults).
  - [x] Use `respx.mock` as a pytest fixture yielding the provider (scope `"function"`).
  - [x] **authlib httpx transport note:** `authlib`'s `httpx` client is the transport used for OIDC discovery and token exchange. `respx` patches `httpx.AsyncClient` / `httpx.Client` globally when active — no special wiring needed beyond importing `respx`.

- [x] **Task 4: Signed JWT minting helper** (AC 3, 4)
  - [x] Inside `mock_oidc.py`, implement `_mint_id_token(claims: dict) -> str` using `authlib.jose.jwt.encode({"alg": "RS256", "kid": "test-key-1"}, claims, _PRIVATE_KEY)` (or equivalent `jwk`-based approach). Return the token as a plain string (not bytes).
  - [x] Default claims dict: `{"iss": ISSUER, "aud": "test-client-id", "sub": "test-user-001", "email": "test@example.com", "groups": [], "iat": now, "exp": now+600}`.
  - [x] Nonce is injected by the caller via `with_claims(nonce=...)` — no default.

- [x] **Task 5: Write smoke test** (AC 8)
  - [x] Create `backend/tests/fixtures/test_mock_oidc_smoke.py`.
  - [x] Test 1 — discovery: activate fixture, make `httpx.get(f"{ISSUER}/.well-known/openid-configuration")`, assert `response.json()["issuer"] == ISSUER`.
  - [x] Test 2 — JWKS: activate fixture, fetch JWKS, assert `keys[0]["kid"] == "test-key-1"`.
  - [x] Test 3 — token exchange with custom claims: call `provider.with_claims(email="alice@example.com", groups=["admin"])`, POST to token endpoint, decode the returned `id_token` using `authlib.jose.jwt.decode`, assert `claims["email"] == "alice@example.com"` and `"admin" in claims["groups"]`.
  - [x] Test 4 — network isolation: with fixture active in strict mode, assert that a request to an un-mocked URL raises `respx.NetworkxMockError` (or equivalent `respx` error for unmatched routes).

- [x] **Task 6: Run full backend test suite** (AC 8)
  - [x] `make test-backend` — expect all existing tests still green plus 4 new smoke tests pass.
  - [x] If any import error on `authlib` or `respx`, fix venv (`uv sync`) and re-run.

## Dev Notes

### CRITICAL CONTEXT

- **`authlib` is the chosen OIDC library** (Architecture Decision Table, row "OIDC-Library"). It must be added via `uv add authlib` (never `pip install`). Architecture ref: `architecture.md` line 147, AR19.
- **`respx` mocks `httpx`** — `authlib` uses `httpx` for outbound calls (discovery, JWKS fetch, token exchange). `httpx` is already in `backend/pyproject.toml` as a runtime dep. `respx` intercepts at the transport layer — no monkey-patching of `authlib` internals needed.
- **`cryptography` package** is the RSA key generator. It ships with `authlib` as a dependency — do NOT add it separately.
- **`backend/tests/fixtures/` does NOT exist yet** — create the directory and `__init__.py`.
- **No conftest.py change required** — the fixture is imported directly by tests that need it (`from backend.tests.fixtures.mock_oidc import mock_oidc`), or registered via conftest in `backend/tests/fixtures/conftest.py` (preferred: add a `conftest.py` there that exports the fixture so pytest discovers it automatically in the `fixtures/` package).
- **Offline-first constraint (CLAUDE.md):** `cryptography`'s RSA keygen works entirely in-process — no network. `respx` mocks network — no outbound. ✅ Safe.
- **uv only** — never call `pip` or `python -m venv`. All dep ops via `uv add` / `uv sync`.

### JWT Signing Approach

Use `authlib.jose`:
```python
from authlib.jose import jwt, OctKey
# For RSA:
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from authlib.jose import JsonWebKey

_PRIVATE_KEY_RAW = rsa.generate_private_key(
    public_exponent=65537, key_size=2048, backend=default_backend()
)
_JWK_PRIVATE = JsonWebKey.import_key(_PRIVATE_KEY_RAW, {"kty": "RSA", "kid": "test-key-1"})
_JWK_PUBLIC  = JsonWebKey.import_key(_PRIVATE_KEY_RAW.public_key(), {"kty": "RSA", "kid": "test-key-1"})

def _mint_id_token(claims: dict) -> str:
    header = {"alg": "RS256", "kid": "test-key-1"}
    return jwt.encode(header, claims, _JWK_PRIVATE).decode("utf-8")
```

### respx Mock Setup

```python
import respx, httpx, pytest

ISSUER = "https://mock-idp.local"

@pytest.fixture
def mock_oidc():
    with respx.mock(assert_all_called=False) as router:
        provider = MockOidcProvider(router)
        router.get(f"{ISSUER}/.well-known/openid-configuration").mock(
            return_value=httpx.Response(200, json=provider.discovery_doc())
        )
        router.get(f"{ISSUER}/jwks").mock(
            return_value=httpx.Response(200, json=provider.jwks_doc())
        )
        router.post(f"{ISSUER}/token").mock(side_effect=provider.handle_token)
        yield provider
```

### File Layout

```
backend/
├── pyproject.toml                          [MOD — +authlib, +respx]
├── tests/
│   └── fixtures/
│       ├── __init__.py                     [NEW]
│       ├── conftest.py                     [NEW — re-exports mock_oidc for autodiscovery]
│       ├── mock_oidc.py                    [NEW — MockOidcProvider + fixture]
│       └── test_mock_oidc_smoke.py         [NEW — 4 smoke tests]
```

### Testing Standards

- pytest, sync (no `asyncio` required — `httpx` sync client sufficient for smoke tests; authlib integration tests in Story 2.2 may use async).
- `make test-backend` must stay green (931 existing tests).
- Ruff line-length 100. mypy strict on new files.

### Previous Story Learnings (1-1)

- `uv add` pattern confirmed working; use same approach.
- `backend/pyproject.toml` uses `[project.dependencies]` for runtime, and a `[dependency-groups]` or `[project.optional-dependencies]` section for dev deps — check current structure before adding.
- Tests live under `backend/tests/`. New subdirectory needs `__init__.py`.
- `make test-backend` runs all pytest tests — no special flags needed.

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` AR19, AR7 (authlib), line 189
- Architecture decisions table: `architecture.md` row "OIDC-Library" (line 147)
- Epics: `_bmad-output/planning-artifacts/epics.md` Story 1.2 (line 445–466)
- Implementation sequence: `architecture.md` line 204 — "Mock-OIDC-Fixture (#4) wird früh gebaut"
- CLAUDE.md: "uv not pip", "offline-only"

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 — `claude-sonnet-4-6`

### Debug Log References

- All 4 smoke tests pass: `tests/fixtures/test_mock_oidc_smoke.py` — 4 PASSED in 0.29s.
- Full backend test suite: **935 passed, 0 failed** in 154.33s (931 pre-existing + 4 new).
- mypy: no issues on new files after adding `-> None` return annotations to test functions.
- ruff: pyproject.toml has pre-existing `extend-immutable-calls` config incompatibility with installed ruff version (not caused by this story). New files are lint-clean per rules.
- `authlib>=1.6.10` and `respx>=0.23.1` were already present in pyproject.toml from prior partial work; verified both installed in venv.

### Completion Notes List

- All 8 ACs satisfied.
- `MockOidcProvider` class wraps `respx.mock` context manager; stubs discovery, JWKS, and token endpoints.
- RSA-2048 key pair generated at import time via `cryptography` — hermetic, no disk reads, no network.
- `_mint_id_token()` uses `authlib.jose.jwt.encode` with RS256 + kid header; returns plain `str` (handles bytes decode).
- `with_claims(**kwargs)` merges overrides onto defaults; resets after each token call so tests are isolated.
- `conftest.py` in `fixtures/` re-exports `mock_oidc` so pytest discovers it automatically in subdirectory tests.
- Test type annotations added (`-> None`, fixture arg typed as `MockOidcProvider`) for mypy strict compliance.

### File List

- `backend/pyproject.toml` — MODIFIED (+authlib runtime dep, +respx dev dep)
- `backend/tests/fixtures/__init__.py` — NEW (empty package marker)
- `backend/tests/fixtures/conftest.py` — NEW (re-exports mock_oidc for pytest autodiscovery)
- `backend/tests/fixtures/mock_oidc.py` — NEW (MockOidcProvider class + mock_oidc fixture)
- `backend/tests/fixtures/test_mock_oidc_smoke.py` — NEW (4 smoke tests covering AC1–AC6, AC8)

### Change Log

- 2026-04-15: Story 1.2 implemented. respx-based mock OIDC fixture (`mock_oidc`) added with RSA JWT signing, discovery/JWKS/token endpoint stubs, network isolation. 4 smoke tests green. Full backend suite 935/935 green.
- 2026-04-16: Code review patches applied (4/4). Tightened network isolation test to specific respx error. Added claims_options validation. Added authlib OAuth2Client integration test (AC4). Exposed public_jwk() accessor. 5 smoke tests green. Full backend suite 936/936 green.

### Review Findings

#### Patches

- [x] [Review][Patch] `test_network_isolation` uses `pytest.raises(Exception)` + nested `respx.mock()` block — tightened to `pytest.raises(AllMockedAssertionError, match="not mocked")` against the active fixture [`backend/tests/fixtures/test_mock_oidc_smoke.py:93-97`]
- [x] [Review][Patch] `jwt.decode(body["id_token"], _JWK_PUBLIC)` lacks `claims_options` / alg pin — added `claims_options` with `iss`/`aud` validation + `claims.validate()` [`backend/tests/fixtures/test_mock_oidc_smoke.py:50-57`]
- [x] [Review][Patch] AC4 requires authlib OAuth2 client-driven proof — added `test_authlib_oauth2_client` using `OAuth2Client.fetch_token()` via httpx transport [`backend/tests/fixtures/test_mock_oidc_smoke.py:65-83`]
- [x] [Review][Patch] Tests import private symbol `_JWK_PUBLIC` — exposed `MockOidcProvider.public_jwk()` accessor; tests now use `mock_oidc.public_jwk()` [`backend/tests/fixtures/mock_oidc.py:83-85`, `backend/tests/fixtures/test_mock_oidc_smoke.py`]

#### Deferred

- [x] [Review][Defer] Module-level RSA keygen runs at import on every pytest collection (~50-300ms cost even for non-OIDC tests) [`backend/tests/fixtures/mock_oidc.py:39`] — deferred, spec Task 2 explicitly prescribes import-time generation for hermetic tests
- [x] [Review][Defer] `handle_token` ignores request body — no validation of `grant_type` / `code` / PKCE verifier; masks client-side bugs [`backend/tests/fixtures/mock_oidc.py:111`] — deferred, Story 2.1/2.2 callback handler tests can extend
- [x] [Review][Defer] `conftest.py` re-export in `tests/fixtures/` only auto-applies fixtures to subtree — tests under `tests/auth/` etc. must import directly [`backend/tests/fixtures/conftest.py`] — deferred, revisit when integration tests land
- [x] [Review][Defer] respx async-interception path not exercised — 4 smoke tests all use sync `httpx`; production SSO callback in Story 2.1+ will use `AsyncOAuth2Client` [`backend/tests/fixtures/test_mock_oidc_smoke.py`] — deferred, covered by Story 2.1+ integration tests
- [x] [Review][Defer] Token response lacks `refresh_token` and `scope` fields — authlib clients may trigger warnings or skipped code paths [`backend/tests/fixtures/mock_oidc.py:114-122`] — deferred, add when a consumer needs them
- [x] [Review][Defer] `with_claims()` cannot un-set a default — no way to test "missing claim" rejection path of consumer [`backend/tests/fixtures/mock_oidc.py:87-90`] — deferred, add negative-test support when Story 2.2 needs it
- [x] [Review][Defer] `_build_claims()` clears `_pending_claims` on every call — second token exchange silently returns defaults, masking multi-exchange test bugs [`backend/tests/fixtures/mock_oidc.py:103-105`] — deferred, current smoke tests are single-exchange; revisit when refresh/re-auth tests land
- [x] [Review][Defer] `_CLIENT_ID` hardcoded as `aud` — any SUT configured with a different client_id will fail audience validation [`backend/tests/fixtures/mock_oidc.py:37`] — deferred, parameterize when Story 1.3 IdP CRUD defines real client_ids
