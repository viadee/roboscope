# Story 2.1: OIDC Authorization Code Flow Initiation

Status: done

Epic: 2 — SSO User Access
Story Key: `2-1-oidc-authorization-code-flow-initiation`

## Story

As a User,
I want to click an SSO button and be redirected to my identity provider with a secure authorization request,
So that I can authenticate with my corporate credentials.

## Acceptance Criteria

1. **AC1 — Public providers list.** `GET /api/v1/auth/sso/providers` (no auth required) returns a JSON array of enabled IdPs with fields `id`, `name`, `provider_type` only. Disabled IdPs, draft IdPs, and any secret/internal fields are excluded.

2. **AC2 — OIDC flow initiation.** `GET /api/v1/auth/sso/{idp_id}/login?return_to=/reports/42` (replacing the Story 1-10 501 stub):
   - Validates `return_to` — already done in sso_router.py (Story 1-10). No new validation needed here.
   - Looks up the IdP and confirms `is_enabled=True` — already done. No change.
   - Fetches OIDC discovery document via `get_or_fetch_discovery(db, idp)` from `src/auth/oidc_discovery.py`.
   - If discovery unavailable → raise `HTTPException(503, detail={"code": "idp.unreachable", "message": "..."})`.
   - Generates cryptographically random `state`, `nonce`, `pkce_verifier` via `secrets.token_urlsafe(32)` (32 bytes → 43-char base64url string → 256 bits entropy, ≥ NFR6 requirement of 128 bits).
   - Computes PKCE `code_challenge = base64url(sha256(pkce_verifier.encode('ascii')))` (S256 method).
   - Creates an `OidcLoginAttempt` row with `expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)`.
   - Builds authorization URL from `discovery_doc["authorization_endpoint"]` with query params: `response_type=code`, `client_id`, `redirect_uri`, `scope`, `state`, `nonce`, `code_challenge`, `code_challenge_method=S256`.
   - Returns `RedirectResponse(url=auth_url, status_code=302)`.

3. **AC3 — return_to default.** `return_to` absent → stored as `"/"` in OidcLoginAttempt (existing `validate_return_to` handles this; Story 2-1 must call `validate_return_to` not `is_valid_return_to` when creating the attempt row, to get the safe value).

4. **AC4 — No audit log.** No `AuditLog` entry is written for the initiation request (pre-identity — user has not authenticated yet).

5. **AC5 — redirect_uri.** The `redirect_uri` sent to the IdP is the single shared callback URL: `str(request.base_url).rstrip('/') + '/api/v1/auth/sso/callback'`. This matches the single-callback architecture (AR9).

## Tasks / Subtasks

- [ ] **Task 1: `SsoProviderPublic` schema + `GET /auth/sso/providers` endpoint** [MOD schemas.py, MOD sso_router.py]
  - [ ] Add `SsoProviderPublic(id: int, name: str, provider_type: str)` Pydantic schema to `backend/src/auth/schemas.py` with `model_config = ConfigDict(from_attributes=True)`
  - [ ] Add `GET /providers` route to `sso_router.py` (registered at `/api/v1/auth/sso/providers`) — no auth dependency
  - [ ] Query: `db.query(IdentityProvider).filter(IdentityProvider.is_enabled == True).all()`
  - [ ] Return `list[SsoProviderPublic]`

- [ ] **Task 2: `backend/src/auth/oidc_service.py`** [NEW]
  - [ ] Function `initiate_sso_login(db: Session, idp: IdentityProvider, safe_return_to: str, redirect_uri: str) -> str`
  - [ ] Fetch discovery: `discovery = get_or_fetch_discovery(db, idp)` — raise `HTTPException(503, ...)` if `None`
  - [ ] Generate `state = secrets.token_urlsafe(32)`, `nonce = secrets.token_urlsafe(32)`, `pkce_verifier = secrets.token_urlsafe(32)`
  - [ ] Compute `code_challenge`: `base64.urlsafe_b64encode(hashlib.sha256(pkce_verifier.encode('ascii')).digest()).rstrip(b'=').decode()`
  - [ ] Create `OidcLoginAttempt(state=state, nonce=nonce, pkce_verifier=pkce_verifier, idp_id=idp.id, return_to=safe_return_to, expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))`, add to db, flush (do NOT commit — caller commits or the FastAPI session handles it)
  - [ ] Build authorization URL: `authorization_endpoint + '?' + urlencode({response_type, client_id, redirect_uri, scope, state, nonce, code_challenge, code_challenge_method})`
  - [ ] `scope` = `idp.scopes` (space-delimited string already on the model, defaults `"openid profile email"` if empty)
  - [ ] Return authorization URL string

- [ ] **Task 3: Replace 501 stub in `sso_router.py`** [MOD sso_router.py]
  - [ ] Import `validate_return_to` from `src.auth.return_to` (to get the safe fallback value for storing in OidcLoginAttempt)
  - [ ] Import `initiate_sso_login` from `src.auth.oidc_service`
  - [ ] In `sso_login_initiate`: compute `safe_return_to = validate_return_to(return_to, str(request.base_url))`
  - [ ] Compute `redirect_uri = str(request.base_url).rstrip('/') + '/api/v1/auth/sso/callback'`
  - [ ] Call `auth_url = initiate_sso_login(db, idp, safe_return_to, redirect_uri)`
  - [ ] Return `RedirectResponse(url=auth_url, status_code=302)`
  - [ ] The existing return_to validation (400 for external URLs) and IdP lookup (404) remain unchanged before this call
  - [ ] Return type annotation changes from `None` to `RedirectResponse`

- [ ] **Task 4: Tests** [NEW `backend/tests/auth/test_sso_initiation.py`]
  - [ ] Fixture `seeded_idp(db_session)` — creates enabled IdP with `issuer_url=ISSUER` (from mock_oidc.ISSUER), pre-seeded `discovery_cache_json` so HTTP calls are bypassed
  - [ ] `test_providers_list_returns_enabled_only` — GET /providers returns 1 item when 1 enabled IdP exists
  - [ ] `test_providers_list_excludes_disabled` — disabled IdP does not appear
  - [ ] `test_providers_list_excludes_secret_fields` — response body does not contain `client_secret`, `issuer_url`, `client_secret_encrypted`
  - [ ] `test_login_returns_302` — GET /{idp_id}/login returns 302
  - [ ] `test_login_redirect_contains_required_params` — Location header has `state`, `nonce`, `code_challenge`, `code_challenge_method=S256`, `redirect_uri`, `client_id`
  - [ ] `test_login_creates_oidc_attempt` — OidcLoginAttempt row exists in DB after call
  - [ ] `test_login_attempt_has_correct_return_to` — `/reports/42` stored in OidcLoginAttempt.return_to
  - [ ] `test_login_attempt_expires_in_10_min` — `expires_at - created_at ≈ 600s`
  - [ ] `test_missing_return_to_defaults_to_slash` — no return_to param → OidcLoginAttempt.return_to == "/"
  - [ ] `test_discovery_unavailable_returns_503` — idp with no cache + no HTTP → 503 with code=idp.unreachable
  - [ ] `test_state_nonce_entropy` — state, nonce, pkce_verifier are each ≥ 32 chars (43 chars from token_urlsafe(32))

## Dev Notes

### Architecture Constraints (MUST FOLLOW)

1. **`authlib` is in pyproject.toml (`>=1.6.10`) but do NOT use `authlib`'s OAuth2 client for URL construction in this story.** Build the authorization URL manually with `urllib.parse.urlencode`. The authlib `OAuth2Client` / `StarletteOAuth2Client` is for the token exchange in Story 2-2, which is async and uses respx. Mixing sync httpx with authlib's OIDC client in this story would couple the code incorrectly.

2. **Single shared callback URL (AR9).** The `redirect_uri` is always `{base_url}/api/v1/auth/sso/callback`. Do NOT use a per-IdP redirect URI. The IdP is identified via the `state` → `OidcLoginAttempt` lookup in Story 2-2.

3. **No auth dependency on public SSO routes (AR architecture).** `GET /providers` and `GET /{idp_id}/login` must NOT have `get_current_user` as a dependency. These are pre-authentication endpoints.

4. **DB flush, not commit in `oidc_service.py`.** `initiate_sso_login` calls `db.flush()` after adding the `OidcLoginAttempt`, NOT `db.commit()`. FastAPI's `get_db` context manager handles the commit/rollback lifecycle. This follows the project pattern.

5. **PKCE S256 implementation.** The `code_challenge` computation must be:
   ```python
   import base64, hashlib
   digest = hashlib.sha256(pkce_verifier.encode('ascii')).digest()
   code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
   ```
   This is the RFC 7636 S256 method exactly. Do NOT use authlib's PKCE helpers (they may use different encoding).

6. **`get_or_fetch_discovery` is in `src.auth.oidc_discovery`** — already imported correctly in sso_router.py context. In `oidc_service.py`, import it from there.

7. **`OidcLoginAttempt.expires_at` — use timezone-aware datetime.** The project stores `datetime.now(timezone.utc)` for timestamps (see discovery_refresh.py). Use `datetime.now(timezone.utc) + timedelta(minutes=10)`.

8. **`idp.scopes` defaults.** If `idp.scopes` is empty string or None, default to `"openid profile email"`. The authorization URL MUST always include at least `openid` scope per OIDC spec.

9. **`validate_return_to` vs `is_valid_return_to`.** The existing `sso_login_initiate` calls `is_valid_return_to` for the 400 check, but the value stored in `OidcLoginAttempt.return_to` must be the SAFE value (defaulting to "/" for None/empty). Use `validate_return_to(return_to, base_url)` to get the safe value separately from the validation check.

10. **`SsoProviderPublic` schema.** Keep it minimal: `id`, `name`, `provider_type` only. The frontend only needs these to render the button label and select the correct icon. Do NOT include `issuer_url`, `client_id`, `scopes`, `is_enabled`, or any secret.

### Discovery Cache Pre-seeding for Tests

Tests must bypass HTTP calls. Pre-seed `discovery_cache_json` on the IdP fixture:

```python
import json
from tests.fixtures.mock_oidc import ISSUER

idp = IdentityProvider(
    name="test-sso",
    provider_type="generic",
    issuer_url=ISSUER,
    client_id="test-client-id",
    client_secret_encrypted=encrypt_value("secret").encode(),
    is_enabled=True,
    discovery_cache_json=json.dumps({
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/jwks",
    }),
    discovery_cached_at=datetime.now(timezone.utc),
)
```

This ensures `get_or_fetch_discovery` returns the cached doc without hitting the network.

### Reference Implementation — `oidc_service.py`

```python
"""OIDC authorization code flow initiation (Story 2-1)."""
from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.auth.models import IdentityProvider, OidcLoginAttempt
from src.auth.oidc_discovery import get_or_fetch_discovery

_ATTEMPT_TTL_MINUTES = 10
_DEFAULT_SCOPE = "openid profile email"


def initiate_sso_login(
    db: Session,
    idp: IdentityProvider,
    safe_return_to: str,
    redirect_uri: str,
) -> str:
    """Create OidcLoginAttempt and return the IdP authorization URL."""
    discovery = get_or_fetch_discovery(db, idp)
    if discovery is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "idp.unreachable",
                "message": (
                    f"Cannot reach {idp.issuer_url}. "
                    "Check firewall and egress rules, or try again later."
                ),
            },
        )

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    pkce_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(pkce_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    now = datetime.now(timezone.utc)
    attempt = OidcLoginAttempt(
        state=state,
        nonce=nonce,
        pkce_verifier=pkce_verifier,
        idp_id=idp.id,
        return_to=safe_return_to,
        expires_at=now + timedelta(minutes=_ATTEMPT_TTL_MINUTES),
    )
    db.add(attempt)
    db.flush()

    scope = (idp.scopes or "").strip() or _DEFAULT_SCOPE
    params = urlencode({
        "response_type": "code",
        "client_id": idp.client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    auth_endpoint = discovery["authorization_endpoint"]
    return f"{auth_endpoint}?{params}"
```

### Reference Implementation — `sso_router.py` updated route

```python
from fastapi.responses import RedirectResponse
from src.auth.oidc_service import initiate_sso_login
from src.auth.return_to import is_valid_return_to, validate_return_to

@router.get("/{idp_id}/login")
def sso_login_initiate(
    idp_id: int,
    request: Request,
    return_to: str | None = Query(None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    base_url = str(request.base_url)
    if return_to and not is_valid_return_to(return_to, base_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "return_to.invalid",
                "message": "return_to must be a same-origin URL",
                "localization_key": "auth.error.returnToInvalid",
            },
        )
    idp = get_identity_provider(db, idp_id)
    if not idp or not idp.is_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, ...)
    safe_return_to = validate_return_to(return_to, base_url)
    redirect_uri = base_url.rstrip("/") + "/api/v1/auth/sso/callback"
    auth_url = initiate_sso_login(db, idp, safe_return_to, redirect_uri)
    return RedirectResponse(url=auth_url, status_code=302)
```

### `GET /providers` route

```python
@router.get("/providers", response_model=list[SsoProviderPublic])
def list_sso_providers(db: Session = Depends(get_db)) -> list[IdentityProvider]:
    return db.query(IdentityProvider).filter(IdentityProvider.is_enabled.is_(True)).all()
```

### Previous Story Learnings (1-10)

- `encrypt_value()` returns `str` — must `.encode()` for `LargeBinary` field `client_secret_encrypted` in test fixtures
- `encrypt_value` is at `src.encryption`, not `src.auth.encryption`
- Return type annotations on FastAPI routes matter — update from `None` to `RedirectResponse`
- `sso_router.py` is registered at prefix `/auth/sso` in `src/api/v1/router.py` → full path is `/api/v1/auth/sso/...`
- Mock OIDC fixture uses `ISSUER = "https://mock-idp.local"` — pre-seed `discovery_cache_json` on IdP to bypass HTTP
- Test baseline: 1036 backend (1016 from Story 1-10 + 20 from review patches) — keep all green

### File Layout

```
backend/
├── src/
│   ├── auth/
│   │   ├── oidc_service.py     [NEW — initiate_sso_login()]
│   │   ├── sso_router.py       [MOD — replace 501, add /providers route]
│   │   └── schemas.py          [MOD — add SsoProviderPublic]
└── tests/
    └── auth/
        └── test_sso_initiation.py  [NEW — ~12 tests]
```

### References

- `get_or_fetch_discovery`: `backend/src/auth/oidc_discovery.py:275`
- `OidcLoginAttempt` model: `backend/src/auth/models.py:72`
- `IdentityProvider` model: `backend/src/auth/models.py` (name, provider_type, client_id, scopes, issuer_url, is_enabled, discovery_cache_json, discovery_cached_at)
- Existing sso_router.py stub: `backend/src/auth/sso_router.py`
- Mock OIDC fixture: `backend/tests/fixtures/mock_oidc.py`
- `validate_return_to`: `backend/src/auth/return_to.py:38`
- Router registration: `backend/src/api/v1/router.py` (sso_router at prefix `/auth/sso`)
- PKCE RFC 7636 S256: SHA-256 of ASCII verifier, base64url-encoded, no padding
- NFR6: state/nonce/pkce_verifier ≥ 128 bits; `secrets.token_urlsafe(32)` = 256 bits ✓

## Dev Agent Record

### Agent Model Used

_to be filled_

### Debug Log References

_none yet_

### Completion Notes List

- D1 accepted: `pkce_verifier` now Fernet-encrypted at rest. Column widened from `String(128)` → `String(512)` in model and migration `b4d2e1a9c3f7` to fit the encrypted token (~140 chars + headroom). Story 2-2 callback must `decrypt_value(attempt.pkce_verifier)` before the token exchange.
- 10 patches applied (P1–P10): `?`/`&` join on auth endpoint, `openid` scope auto-enforced, `authorization_endpoint` type validation (KeyError → 503 idp.unreachable), `return_to` length cap aligned with `String(500)` column (450 char soft cap in validator), scope whitespace normalization, `Cache-Control: no-store` + `Pragma: no-cache` on redirect, plus 4 new tests for TTL/entropy/client_id+scope params/no-audit-log.
- 9 items deferred to `deferred-work.md` (operational retention in Story 5-5, architectural cleanup of `get_or_fetch_discovery` inner commit, handoff generator path mismatch, cross-cutting timezone issue, etc.).
- Total: 34 tests in `test_sso_initiation.py` (was 14 at review time); 6 in `test_return_to_validation.py` (was 38); all green.

### Change Log

_none yet_

### File List

- `backend/src/auth/oidc_service.py` (NEW)
- `backend/src/auth/sso_router.py` (replaced Story 1-10 501 stub)
- `backend/src/auth/schemas.py` (added `SsoProviderPublic`)
- `backend/tests/auth/test_sso_initiation.py` (NEW, 14 tests)
- `backend/tests/auth/test_sso_stub.py` (removed 2 `== 501` assertions)

### Review Findings

**Decision Needed**

- [x] [Review][Decision] Encrypt `pkce_verifier` at rest? — Currently stored plaintext in `oidc_login_attempts`. Project already uses Fernet for `client_secret_encrypted`. Defense-in-depth gap (DB leak exposes unused-but-active PKCE verifiers bounded by 10-min TTL). Options: (A) encrypt with Fernet, (B) defer to Phase 4 hardening.

**Patches**

- [x] [Review][Patch] Authorization URL `?` concat breaks IdPs whose endpoint already has a query string [`backend/src/auth/oidc_service.py:75-76`] — use `&` separator when `?` already present, or merge via `urlparse`+`parse_qsl`.
- [x] [Review][Patch] Missing-`openid` scope not enforced [`backend/src/auth/oidc_service.py:62`] — auto-add `openid` if admin omitted it: `scopes.add("openid")`.
- [x] [Review][Patch] `discovery["authorization_endpoint"]` raises `KeyError`/`TypeError` on malformed cache [`backend/src/auth/oidc_service.py:75`] — validate `isinstance(auth_endpoint, str)`; raise 503 `idp.unreachable` with specific detail if missing/non-string.
- [x] [Review][Patch] `return_to` length not enforced vs 500-char DB column [`backend/src/auth/return_to.py`, `backend/src/auth/sso_router.py:37`] — reject with 400 `return_to.too_long` when `len > 450`.
- [x] [Review][Patch] `scopes` whitespace/newlines not normalized [`backend/src/auth/oidc_service.py:62`] — use `" ".join(idp.scopes.split())` to collapse internal whitespace.
- [x] [Review][Patch] Missing `Cache-Control: no-store` on auth redirect [`backend/src/auth/sso_router.py:60`] — add `no-store`/`no-cache` headers so intermediaries/browser history don't retain the `state`/`nonce` URL.
- [x] [Review][Patch] Missing test: 10-minute TTL assertion [`backend/tests/auth/test_sso_initiation.py`] — assert `550 < (expires_at - created_at).total_seconds() < 650`.
- [x] [Review][Patch] Missing test: state/nonce/verifier entropy length [`backend/tests/auth/test_sso_initiation.py`] — assert `len(state) >= 43`, `len(nonce) >= 43`, `len(attempt.pkce_verifier) >= 43` (NFR6).
- [x] [Review][Patch] Missing test: `client_id` + `scope` param assertions in `test_login_pkce_params_present` [`backend/tests/auth/test_sso_initiation.py:109`].
- [x] [Review][Patch] Missing test: AC4 no-audit-log regression assertion — add `assert db_session.query(AuditLog).count() == 0` to one login test.

**Deferred (pre-existing / out-of-scope)**

- [x] [Review][Defer] Stale `OidcLoginAttempt` rows never purged [`backend/src/auth/models.py`] — deferred to Story 5-5 (retention APScheduler jobs).
- [x] [Review][Defer] `get_or_fetch_discovery` commits outer session [`backend/src/auth/oidc_discovery.py:300`] — pre-existing Story 1-9 architectural issue; fix touches discovery_refresh scheduler semantics.
- [x] [Review][Defer] Handoff generator emits `/auth/sso/callback` instead of `/api/v1/auth/sso/callback` [`backend/src/auth/handoff_generator.py:220`] — pre-existing Story 1-8 bug; operators registering IdP from handoff artifact get redirect_uri_mismatch.
- [x] [Review][Defer] Naive/aware datetime mixing in discovery cache TTL check [`backend/src/auth/oidc_discovery.py:290-292`] — cross-cutting timezone issue; migration to `DateTime(timezone=True)` columns.
- [x] [Review][Defer] Broad `except Exception` in `get_or_fetch_discovery` [`backend/src/auth/oidc_discovery.py:304`] — hides programming errors as "IdP unreachable".
- [x] [Review][Defer] `request.base_url` used to derive `redirect_uri` (Host header trust) [`backend/src/auth/sso_router.py:35,55`] — matches spec; architectural mitigation via `TrustedHostMiddleware` / `settings.public_base_url` is out of Story 2-1 scope.
- [x] [Review][Defer] `provider_type` typed as `str` rather than `Literal[...]` in `SsoProviderPublic` — schema refinement, not a bug.
- [x] [Review][Defer] `/providers` returns ORM objects; future relationship additions could cause detached-instance issues — project to tuple only if needed.
- [x] [Review][Defer] Route ordering fragility if `idp_id` ever becomes `str` — add regression test only when schema changes.
