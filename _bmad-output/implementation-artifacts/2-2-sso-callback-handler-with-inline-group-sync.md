# Story 2.2: SSO Callback Handler with Inline Group Sync

Status: done

Epic: 2 — SSO User Access
Story Key: `2-2-sso-callback-handler-with-inline-group-sync`

## Story

As a User,
I want the post-IdP redirect to complete my login and land me in RoboScope with a valid session and up-to-date team membership,
So that I am immediately usable without a second request.

## Acceptance Criteria

1. **AC1 — State lookup & single-use consumption.** `GET /api/v1/auth/sso/callback?code=<>&state=<>` (no auth dep):
   - Looks up `OidcLoginAttempt` by `state`; unknown or already-deleted → redirect to `/sso-error?code=state.unknown` + audit `sso.login.failure`.
   - If `expires_at <= now` → redirect to `/sso-error?code=state.expired` + audit failure; do not delete the row (retained for debugging until APScheduler reaper in Story 5-5).
   - If state is valid and unexpired, the attempt row is **consumed** on success path before JWT issuance (see AC5). Concurrent callbacks for the same state → the second transaction sees the row missing → `state.unknown`.

2. **AC2 — Token exchange with PKCE.** Uses `authlib`'s OAuth2Session (or sync `OAuth2Client`) to POST to `discovery["token_endpoint"]` with `grant_type=authorization_code`, `code`, `redirect_uri`, `client_id`, `client_secret`, `code_verifier` (decrypted from `attempt.pkce_verifier` via `decrypt_value`). Timeout 4s connect + 4s read. On HTTP error / timeout → redirect to `/sso-error?code=idp.unreachable` + audit failure with structured detail `{"reason": "token_exchange_failed", "idp_id": ..., "http_status": ...}`.

3. **AC3 — id_token validation.** The token-endpoint response's `id_token` is verified against the cached JWKS (from `idp.discovery_cache_json → discovery["jwks_uri"]`, fetched once at callback time and cached on the IdP row for the discovery TTL):
   - Signature valid (RS256 via authlib `jwt.decode(id_token, jwk_set)`).
   - `iss == idp.issuer_url` (stripped of trailing slash).
   - `aud == idp.client_id`.
   - `exp > now`.
   - `nonce == attempt.nonce` (exact string match).
   Any failure → redirect to `/sso-error?code=token.invalid` + audit failure with specific reason. The raw `id_token` string is **never persisted** and the local variable is unbound (`del id_token_str`) after claim extraction (NFR9).

4. **AC4 — Claim extraction and user upsert.** From the validated id_token claims:
   - Extract `sub` (mandatory, else `claims.missing_sub`), `email` (mandatory, else `claims.missing_email`), and the configured group claim (`idp.group_claim_name`, default `"groups"`; absent or non-list → treated as empty `[]`).
   - User matching by `email` (case-insensitive): existing → update `last_login_at`, **preserve `role`** (do NOT downgrade or upgrade based on IdP); new → create with `role=Role.VIEWER`, `hashed_password=""` (SSO-only account, local login blocked by empty hash), `is_active=True`.
   - Skip `first_login_complete` handling here — Story 4-1 owns first-login semantics.

5. **AC5 — Inline group sync in the same transaction (NFR3).** In the same DB session, **before commit**:
   - Fetch all `IdPGroupMapping` rows for `attempt.idp_id`; build `{group_claim_value: (team_id, role)}`.
   - For each group name in the IdP-reported list that has a mapping: upsert `TeamMember(team_id, user_id=user.id, role=mapped_role, source='idp_group_sync')`. If the row already exists with `source='idp_group_sync'`, update `role` if changed. If it exists with `source='manual'`, leave untouched (FR20).
   - For each existing `TeamMember(user_id=user.id, source='idp_group_sync')` whose team is no longer in the IdP-reported list: delete.
   - Emit one `team.member.synced_from_idp` audit event with `detail={"user_id": ..., "idp_id": ..., "added": [...], "removed": [...], "updated": [...]}`.
   - The sync must add ≤ 500 ms for a user with up to 50 groups (AC from epic — functional, not a hard test gate for Story 2-2).

6. **AC6 — Commit, JWT, redirect, cleanup.** In order:
   1. `db.delete(attempt)` (single-use; row gone even if JWT issuance fails afterwards — acceptable because user would just re-initiate).
   2. `db.commit()`.
   3. `create_token_response(user)` — produces `TokenResponse(access_token, refresh_token, expires_in)` with identical shape to local-login JWT (FR11, NFR9).
   4. Audit `sso.login.success` with `detail={"idp_id": ..., "email": ..., "teams_synced": N}`.
   5. Build `RedirectResponse(url=<safe_return_to>, status_code=302)` with:
      - `Set-Cookie: roboscope_sso_access_token=<access_token>; Path=/; Max-Age=60; Secure; SameSite=Lax` (HttpOnly=**false** — frontend Story 2-3 reads it and migrates to localStorage, then clears it).
      - `Set-Cookie: roboscope_sso_refresh_token=<refresh_token>; Path=/; Max-Age=60; Secure; SameSite=Lax; HttpOnly=false`.
      - `Cache-Control: no-store` header.

7. **AC7 — Error envelope uniformity.** Every failure branch in this callback produces a 302 to `/sso-error?code=<machine_code>` (frontend-owned view, Story 2-7). The response body is empty; the error code is the only signal. No IdP-internal details leak to the user. All specific reasons go to the `sso.login.failure` audit event's `detail`.

8. **AC8 — Local-login path untouched.** The existing `POST /auth/login` endpoint, JWT issuance, `/auth/me` dependency, and bearer-token flow all behave identically for non-SSO users. No regression in `tests/auth/test_login.py` or equivalent.

## Tasks / Subtasks

### Task 1: `AuditEventType` StrEnum + audit-service integration

- [x] NEW `backend/src/audit/event_types.py`:
  ```python
  from enum import StrEnum

  class AuditEventType(StrEnum):
      SSO_LOGIN_SUCCESS = "sso.login.success"
      SSO_LOGIN_FAILURE = "sso.login.failure"
      TEAM_MEMBER_SYNCED_FROM_IDP = "team.member.synced_from_idp"
  ```
  Only these three types for Story 2-2. Subsequent stories extend the enum.
- [x] Extend `backend/src/audit/service.py` — add a convenience wrapper `log_event(db, event_type: AuditEventType, *, user_id=None, detail: dict | None = None, ip_address=None) -> AuditLog` that passes `action=event_type.value` and a canonical `resource_type` derived from the prefix before the first `.` (`sso`, `team`, `idp`, etc.). Do NOT replace the existing `log_audit(...)` signature — the middleware still uses it.

### Task 2: OIDC callback service

- [x] NEW `backend/src/auth/oidc_callback_service.py` with top-level `handle_sso_callback(db, *, code: str, state: str, safe_return_to_fallback: str = "/") -> tuple[User, str]` returning `(user, return_to)`. Internally:
  - `_lookup_attempt(db, state)` → `OidcLoginAttempt | None`.
  - `_exchange_code(attempt, idp, discovery) -> dict` (token endpoint POST via authlib sync client).
  - `_verify_id_token(id_token_str, idp, discovery) -> dict` (authlib `jwt.decode` with JWKSet).
  - `_extract_claims(id_token_claims, idp) -> dict` ({sub, email, groups}).
  - `_upsert_user(db, email, sub) -> User`.
  - `_sync_team_memberships(db, user, idp_id, groups) -> SyncReport` (added/removed/updated lists).
  - Raises `SsoCallbackError(code: str, detail: dict)` — the router catches, logs audit, and redirects.
- [x] Route the PKCE verifier decrypt at the top of `_exchange_code`:
  ```python
  code_verifier = decrypt_value(attempt.pkce_verifier)
  ```
  (Stored encrypted by Story 2-1.)
- [x] The token-exchange HTTP client uses the same TLS-1.2+ context as `oidc_discovery._TLS_CONTEXT`; honor `ALLOW_INSECURE_IDP` identically.

### Task 3: Callback route in `sso_router.py`

- [x] MOD `backend/src/auth/sso_router.py` — add:
  ```python
  @router.get("/callback")
  def sso_callback(
      code: str = Query(...),
      state: str = Query(...),
      db: Session = Depends(get_db),
  ) -> RedirectResponse:
      ...
  ```
  Wraps `handle_sso_callback` in try/except `SsoCallbackError`. On success: sets cookies + redirects to the `return_to`. On error: emits `sso.login.failure` audit with detail, redirects to `/sso-error?code=<err.code>`.
- [x] The callback URL (`/api/v1/auth/sso/callback`) is the **single shared** URL per architecture AR9 — no `{idp_id}` in path; IdP identified via `state` lookup.
- [x] The stored `return_to` from the attempt is trusted as-is (already validated at initiation time by Story 2-1's `is_valid_return_to`).

### Task 4: Tests

- [x] NEW `backend/tests/auth/test_sso_callback.py` — build on `tests/fixtures/mock_oidc.py` (`mock_oidc` fixture + `MockOidcProvider.with_claims(...)`). Seed an IdP fixture with `discovery_cache_json` pre-populated from `mock_oidc.discovery_doc()` and `issuer_url = ISSUER`. Each test creates an `OidcLoginAttempt` manually with a known `pkce_verifier` (encrypted via `encrypt_value`) and `nonce`.
- [x] Cases (≥ 14):
  - `test_callback_happy_path_redirects_to_return_to`
  - `test_callback_sets_access_and_refresh_token_cookies`
  - `test_callback_creates_new_user_with_viewer_role`
  - `test_callback_existing_user_preserves_role` (admin stays admin)
  - `test_callback_updates_last_login_at`
  - `test_callback_unknown_state_redirects_to_error` (302 to `/sso-error?code=state.unknown`)
  - `test_callback_expired_attempt_redirects_to_error` (`state.expired`)
  - `test_callback_consumes_attempt_row` (row deleted on success)
  - `test_callback_token_exchange_timeout_audits_failure` (`idp.unreachable`)
  - `test_callback_invalid_signature_redirects_to_error` (`token.invalid`) — mock_oidc mints a token signed by a *different* key
  - `test_callback_nonce_mismatch_redirects_to_error` (`nonce.mismatch`)
  - `test_callback_missing_email_claim_redirects_to_error` (`claims.missing_email`)
  - `test_callback_inline_group_sync_inserts_new_memberships` — seed `IdPGroupMapping(group_claim_value="eng", team=T1, role=RUNNER)`; IdP returns `groups=["eng"]`; assert `TeamMember(source='idp_group_sync', team_id=T1, role=RUNNER)` exists.
  - `test_callback_inline_group_sync_removes_stale_memberships` — pre-seed a `TeamMember(source='idp_group_sync', team=T_old)`; IdP returns a different group list; assert the old row is deleted.
  - `test_callback_preserves_manual_grants_during_sync` — pre-seed `TeamMember(source='manual', team=T)`; IdP does not return that group; assert manual row remains.
  - `test_callback_success_emits_audit_event` — one `sso.login.success` row, `detail` contains expected fields.
  - `test_callback_failure_emits_audit_event_with_structured_detail`.
  - `test_callback_return_to_cookie_is_not_httponly_so_frontend_can_read` (documents the contract with Story 2-3).
- [x] NEW `backend/tests/audit/test_event_types.py` (2 tests):
  - `test_event_type_enum_values_match_string_literals` — guards against accidental rename of `sso.login.success`, etc.
  - `test_log_event_helper_round_trip` — calling `log_event(db, AuditEventType.SSO_LOGIN_SUCCESS, ...)` produces an `AuditLog` row with `action="sso.login.success"`.

## Dev Notes

### Architecture Constraints (MUST FOLLOW)

1. **Single shared callback URL** (AR9). No per-IdP callback path. IdP is identified via `state` lookup. Do NOT add `{idp_id}` to the callback route.
2. **authlib is the only OIDC library.** Use `authlib.integrations.httpx_client.OAuth2Client` (sync) for token exchange and `authlib.jose.jwt.decode(id_token, JsonWebKey.import_key_set(...))` for signature verification. Do NOT hand-roll JWT validation with `pyjwt` (existing `pyjwt` usage is only for RoboScope-issued local JWTs).
3. **JWT shape is frozen.** `create_token_response(user)` is reused verbatim. No new claims. No `sso=true` marker. The frontend cannot tell whether a token came from local-login or SSO (NFR9, NFR28).
4. **id_token is write-only memory.** The raw `id_token` string is never assigned to a model field, persisted, audit-logged, or returned in a response. Use local variables; after claim extraction, `del id_token_str` explicitly so reviewers can `grep` the codebase and confirm.
5. **Inline sync in one transaction** (NFR3). Do NOT dispatch the group sync via `task_executor`. The architecture example at `architecture.md:420-425` explicitly lists this as an anti-pattern (stale RBAC on first post-login request).
6. **Structured audit detail.** `sso.login.failure` detail keys: `reason` (machine code: `state.unknown`, `state.expired`, `idp.unreachable`, `token.invalid`, `nonce.mismatch`, `claims.missing_email`, `claims.missing_sub`, `sync.failed`), `idp_id` (when known), `http_status` (for IdP HTTP errors), `email` (when claims extracted).
7. **Client secret decrypt** — fetch IdP's `client_secret_encrypted` via existing `decrypt_value(idp.client_secret_encrypted.decode())` pattern (see `idp_service.py`). Do NOT introduce a new decryption helper.
8. **Commit order is load-bearing.** The order in AC6 is intentional: delete attempt → commit → issue JWT → audit → redirect. If JWT issuance were to fail after commit, the attempt row is already consumed — this is acceptable because `create_token_response` never raises in practice (pure JWT encode; no DB I/O).
9. **Error redirect path** — `/sso-error` is a frontend route (Story 2-7). Backend only redirects there; it never renders it.
10. **TLS 1.2+** — the `authlib` `OAuth2Client` must use an `httpx.Client(verify=_TLS_CONTEXT)` with the same context used by discovery (`_TLS_CONTEXT` in `oidc_discovery.py`). Consider hoisting the TLS context into a shared module if reuse spreads further; for now, import it directly.

### Reference Implementation — `oidc_callback_service.py` skeleton

```python
"""OIDC callback handler (Story 2-2): code exchange, id_token verification, inline group sync."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from authlib.integrations.httpx_client import OAuth2Client
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError
from sqlalchemy.orm import Session

from src.audit.event_types import AuditEventType
from src.audit.service import log_event
from src.auth.constants import Role
from src.auth.models import IdentityProvider, IdPGroupMapping, OidcLoginAttempt, User
from src.auth.oidc_discovery import _TLS_CONTEXT, _ALLOW_INSECURE_IDP, get_or_fetch_discovery
from src.encryption import decrypt_value
from src.teams.models import TeamMember

logger = logging.getLogger("roboscope.auth.oidc_callback")


class SsoCallbackError(Exception):
    def __init__(self, code: str, detail: dict | None = None) -> None:
        self.code = code
        self.detail = detail or {}
        super().__init__(code)


@dataclass
class SyncReport:
    added: list[int] = field(default_factory=list)   # team_ids
    removed: list[int] = field(default_factory=list)
    updated: list[int] = field(default_factory=list)


def handle_sso_callback(
    db: Session, *, code: str, state: str
) -> tuple[User, str]:
    attempt = db.query(OidcLoginAttempt).filter_by(state=state).first()
    if attempt is None:
        raise SsoCallbackError("state.unknown")

    now = datetime.now(timezone.utc)
    expires_at = attempt.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise SsoCallbackError("state.expired", {"idp_id": attempt.idp_id})

    idp = db.query(IdentityProvider).filter_by(id=attempt.idp_id).first()
    if idp is None or not idp.is_enabled:
        raise SsoCallbackError("idp.unavailable", {"idp_id": attempt.idp_id})

    discovery = get_or_fetch_discovery(db, idp)
    if discovery is None:
        raise SsoCallbackError("idp.unreachable", {"idp_id": idp.id})

    token_response = _exchange_code(attempt, idp, discovery)
    id_token_str = token_response.get("id_token")
    if not isinstance(id_token_str, str):
        raise SsoCallbackError("token.invalid", {"idp_id": idp.id, "reason": "no_id_token"})

    id_token_claims = _verify_id_token(id_token_str, idp, discovery, expected_nonce=attempt.nonce)
    del id_token_str  # NFR9 — id_token discarded after extraction

    claims = _extract_claims(id_token_claims, idp)
    user = _upsert_user(db, email=claims["email"], sub=claims["sub"])
    sync_report = _sync_team_memberships(db, user, idp.id, claims["groups"])

    log_event(
        db,
        AuditEventType.TEAM_MEMBER_SYNCED_FROM_IDP,
        user_id=user.id,
        detail={
            "idp_id": idp.id,
            "added": sync_report.added,
            "removed": sync_report.removed,
            "updated": sync_report.updated,
        },
    )
    return_to = attempt.return_to or "/"
    db.delete(attempt)
    return user, return_to


def _exchange_code(attempt: OidcLoginAttempt, idp: IdentityProvider, discovery: dict) -> dict:
    token_endpoint = discovery.get("token_endpoint")
    if not isinstance(token_endpoint, str) or not token_endpoint:
        raise SsoCallbackError("idp.unreachable", {"idp_id": idp.id, "reason": "no_token_endpoint"})

    client_secret = decrypt_value(idp.client_secret_encrypted.decode())
    verifier = decrypt_value(attempt.pkce_verifier)
    redirect_uri = _redirect_uri_for(attempt)  # helper — same path as Story 2-1

    verify: bool | object = True if _ALLOW_INSECURE_IDP else _TLS_CONTEXT
    with httpx.Client(timeout=httpx.Timeout(4.0, connect=4.0), verify=verify) as http:
        client = OAuth2Client(
            client_id=idp.client_id,
            client_secret=client_secret,
            token_endpoint_auth_method="client_secret_post",
            transport=httpx.HTTPTransport(verify=verify),
        )
        try:
            resp = client.fetch_token(
                token_endpoint,
                code=attempt.code if hasattr(attempt, "code") else None,
                redirect_uri=redirect_uri,
                code_verifier=verifier,
                client_id=idp.client_id,
                client_secret=client_secret,
            )
        except httpx.TimeoutException as exc:
            raise SsoCallbackError("idp.unreachable", {"idp_id": idp.id, "reason": "timeout"}) from exc
        except httpx.HTTPError as exc:
            raise SsoCallbackError("idp.unreachable", {"idp_id": idp.id, "reason": "http_error"}) from exc
    return dict(resp)


def _verify_id_token(
    id_token_str: str, idp: IdentityProvider, discovery: dict, *, expected_nonce: str
) -> dict:
    jwks_uri = discovery.get("jwks_uri")
    if not isinstance(jwks_uri, str):
        raise SsoCallbackError("token.invalid", {"reason": "no_jwks_uri"})
    # Fetch JWKS inline (cached on IdP-level discovery json already; here we pull fresh
    # only the keys — a future story can cache keys separately).
    verify: bool | object = True if _ALLOW_INSECURE_IDP else _TLS_CONTEXT
    try:
        with httpx.Client(timeout=httpx.Timeout(4.0, connect=4.0), verify=verify) as http:
            jwks_resp = http.get(jwks_uri)
            jwks_resp.raise_for_status()
            jwk_set = JsonWebKey.import_key_set(jwks_resp.json())
    except httpx.HTTPError as exc:
        raise SsoCallbackError("token.invalid", {"reason": "jwks_fetch_failed"}) from exc

    try:
        claims = jwt.decode(id_token_str, jwk_set)
        claims.validate()  # exp, nbf, iat
    except JoseError as exc:
        raise SsoCallbackError("token.invalid", {"reason": "signature_or_claims"}) from exc

    issuer_expected = idp.issuer_url.rstrip("/")
    issuer_actual = str(claims.get("iss", "")).rstrip("/")
    if issuer_actual != issuer_expected:
        raise SsoCallbackError("token.invalid", {"reason": "iss_mismatch"})

    aud = claims.get("aud")
    if isinstance(aud, str):
        aud_ok = aud == idp.client_id
    elif isinstance(aud, list):
        aud_ok = idp.client_id in aud
    else:
        aud_ok = False
    if not aud_ok:
        raise SsoCallbackError("token.invalid", {"reason": "aud_mismatch"})

    if claims.get("nonce") != expected_nonce:
        raise SsoCallbackError("nonce.mismatch", {"reason": "nonce_mismatch"})

    return dict(claims)


def _extract_claims(id_token_claims: dict, idp: IdentityProvider) -> dict:
    sub = id_token_claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise SsoCallbackError("claims.missing_sub")
    email = id_token_claims.get("email")
    if not isinstance(email, str) or not email:
        raise SsoCallbackError("claims.missing_email")
    group_claim = idp.group_claim_name or "groups"
    raw_groups = id_token_claims.get(group_claim)
    groups: list[str] = [g for g in raw_groups if isinstance(g, str)] if isinstance(raw_groups, list) else []
    return {"sub": sub, "email": email.lower(), "groups": groups}


def _upsert_user(db: Session, *, email: str, sub: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email, username=email, hashed_password="", role=Role.VIEWER, is_active=True
        )
        db.add(user)
        db.flush()
        db.refresh(user)
    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    return user


def _sync_team_memberships(
    db: Session, user: User, idp_id: int, groups: list[str]
) -> SyncReport:
    mappings = (
        db.query(IdPGroupMapping).filter(IdPGroupMapping.idp_id == idp_id).all()
    )
    expected: dict[int, str] = {}  # team_id -> role
    for m in mappings:
        if m.group_claim_value in groups:
            expected[m.team_id] = m.role

    current_rows = (
        db.query(TeamMember)
        .filter(TeamMember.user_id == user.id, TeamMember.source == "idp_group_sync")
        .all()
    )
    current: dict[int, TeamMember] = {r.team_id: r for r in current_rows}

    report = SyncReport()
    for team_id, role in expected.items():
        if team_id in current:
            if current[team_id].role != role:
                current[team_id].role = role
                report.updated.append(team_id)
        else:
            # Check if a manual row exists — do not duplicate.
            manual = (
                db.query(TeamMember)
                .filter(
                    TeamMember.team_id == team_id,
                    TeamMember.user_id == user.id,
                    TeamMember.source == "manual",
                )
                .first()
            )
            if manual is None:
                db.add(TeamMember(team_id=team_id, user_id=user.id, role=role, source="idp_group_sync"))
                report.added.append(team_id)
    for team_id, row in current.items():
        if team_id not in expected:
            db.delete(row)
            report.removed.append(team_id)
    db.flush()
    return report
```

### Reference Implementation — `sso_router.py` callback route

```python
from fastapi import HTTPException
from src.audit.event_types import AuditEventType
from src.audit.service import log_event
from src.auth.oidc_callback_service import SsoCallbackError, handle_sso_callback
from src.auth.service import create_token_response


@router.get("/callback")
def sso_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        user, return_to = handle_sso_callback(db, code=code, state=state)
    except SsoCallbackError as err:
        log_event(
            db,
            AuditEventType.SSO_LOGIN_FAILURE,
            detail={"reason": err.code, **err.detail},
        )
        db.commit()
        resp = RedirectResponse(
            url=f"/sso-error?code={err.code}", status_code=status.HTTP_302_FOUND
        )
        resp.headers["Cache-Control"] = "no-store"
        return resp

    tokens = create_token_response(user)
    log_event(
        db,
        AuditEventType.SSO_LOGIN_SUCCESS,
        user_id=user.id,
        detail={"email": user.email, "return_to": return_to},
    )
    db.commit()

    resp = RedirectResponse(url=return_to, status_code=status.HTTP_302_FOUND)
    resp.headers["Cache-Control"] = "no-store"
    # Short-lived (60s) non-HttpOnly cookies — frontend Story 2-3 reads them, migrates
    # to localStorage, and clears them. SameSite=Lax because the redirect arrives
    # cross-site from the IdP.
    resp.set_cookie(
        "roboscope_sso_access_token",
        tokens.access_token,
        max_age=60,
        secure=True,
        samesite="lax",
        httponly=False,
        path="/",
    )
    resp.set_cookie(
        "roboscope_sso_refresh_token",
        tokens.refresh_token,
        max_age=60,
        secure=True,
        samesite="lax",
        httponly=False,
        path="/",
    )
    return resp
```

### Previous Story Learnings (2-1)

- **`pkce_verifier` is Fernet-encrypted at rest** — must `decrypt_value(attempt.pkce_verifier)` before sending to token endpoint. Column is `String(512)` (widened from 128 to fit the Fernet token).
- **`get_or_fetch_discovery(db, idp)` is the single entry point** — do NOT re-fetch inline. Returns `None` on failure; treat as `SsoCallbackError("idp.unreachable")`.
- **`OidcLoginAttempt.return_to` was validated at initiation time** — safe to use as-is for the final redirect. No re-validation needed (callback is a closed loop).
- **Ephemeral row purge is deferred to Story 5-5** — acceptable to leave expired attempt rows behind; the callback must NOT delete expired rows (that's the reaper's job; deletion here loses debugging signal).
- **Authorization endpoint `?`/`&` join pattern** — not relevant here (callback does POST to token_endpoint, not URL construction), but re-check `token_endpoint` may carry a query string (mirror the Story 2-1 handling if `OAuth2Client.fetch_token` fails — unlikely, authlib handles it).
- **Test discovery-cache pre-seeding pattern** — seed `idp.discovery_cache_json = json.dumps(mock_oidc.discovery_doc())` and `idp.discovery_cached_at = datetime.now(timezone.utc)` to skip the discovery HTTP call.

### JWT Delivery Mechanism

Backend writes two short-lived (60s, Secure, SameSite=Lax, non-HttpOnly) cookies: `roboscope_sso_access_token` and `roboscope_sso_refresh_token`. The frontend (Story 2-3) reads them synchronously on first paint after the redirect, migrates them to `localStorage` (matching existing bearer-token storage), and clears both cookies via `document.cookie = "...; Max-Age=0"`. This keeps the JWT shape frozen (NFR28) and requires no changes to `get_current_user` / `/auth/me` / existing auth interceptors. No URL fragment, no handshake endpoint — minimum moving parts.

### File Layout

- NEW: `backend/src/audit/event_types.py`
- NEW: `backend/src/auth/oidc_callback_service.py`
- MOD: `backend/src/audit/service.py` (add `log_event()`)
- MOD: `backend/src/auth/sso_router.py` (add `/callback` route)
- NEW: `backend/tests/auth/test_sso_callback.py`
- NEW: `backend/tests/audit/test_event_types.py`

### References

- Architecture Doc: `_bmad-output/planning-artifacts/architecture.md` §"Communication Patterns (Delta)" (audit event shape), §"Process Patterns (Delta)" (transaction semantics for login-time sync), §"Pattern Examples" (reference snippet).
- Epic: `_bmad-output/planning-artifacts/epics.md` Story 2.2 (lines 698-735).
- Story 2-1 completion notes: `_bmad-output/implementation-artifacts/2-1-oidc-authorization-code-flow-initiation.md`.
- authlib JWT verification: https://docs.authlib.org/en/latest/jose/jwt.html
- authlib OAuth2Client.fetch_token (PKCE): https://docs.authlib.org/en/latest/client/oauth2.html
- RFC 6749 (OAuth 2.0) §4.1.3 Access Token Request.
- RFC 7636 (PKCE) §4.5 Client Verification of Authorization Response.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6 (via bmad-dev-story)

### Debug Log References

_none yet_

### Completion Notes List

- **Task 1** — `AuditEventType` StrEnum created with 3 members (`SSO_LOGIN_SUCCESS`, `SSO_LOGIN_FAILURE`, `TEAM_MEMBER_SYNCED_FROM_IDP`). Helper `resource_type_for()` + `log_event()` wrapper added in `audit/service.py`; existing `log_audit()` signature untouched for middleware compatibility.
- **Task 2** — `oidc_callback_service.py` created with `handle_sso_callback()` + `SsoCallbackError` + `CallbackResult`/`SyncReport` dataclasses. Uses `authlib.integrations.httpx_client.OAuth2Client` for token exchange (sync, PKCE), `authlib.jose.jwt.decode` with `JsonWebKey.import_key_set` for id_token validation, and the same `_TLS_CONTEXT` / `_ALLOW_INSECURE_IDP` as `oidc_discovery.py`. `del id_token_str` explicit after claim extraction (NFR9). Catches `ValueError` in JWT decode path (authlib raises `ValueError("Key not found")` for missing kid).
- **Task 3** — `/callback` route added to `sso_router.py`. Audit detail uses `code` (machine error code) + `reason` (sub-detail) to avoid key collision when spreading `err.detail`. Cookies `roboscope_sso_access_token` / `roboscope_sso_refresh_token` are 60s, Secure, SameSite=Lax, **non**-HttpOnly (frontend Story 2-3 migrates to localStorage). `Cache-Control: no-store` on every response (success + error branches).
- **Task 4** — 25 callback tests + 4 event-type tests. Covers: happy path + cookies + cache-control + user upsert + role preservation + last_login update + attempt consumption; unknown/expired state + disabled IdP + token exchange timeout + signature/nonce/iss/aud/email/sub failures; group sync insert/remove/update/preserve-manual; audit emission on success + failure; FastAPI 422 on missing query params.
- **JWT delivery contract (for Story 2-3)** — access + refresh tokens arrive as 60-second cookies on the redirect. Frontend reads `document.cookie`, stores values in localStorage matching the existing bearer-token convention, then clears both cookies with `Max-Age=0`.

### Change Log

- 2026-04-21 — initial implementation (Tasks 1–4 complete, 29/29 new tests pass, full regression green).
- 2026-04-21 — code-review pass: 15 patches + 2 decisions applied (D1 = email_verified required, D2 = keep 60s cookies). New failure codes emitted: `user.disabled`, `user.username_conflict`, `claims.email_unverified`, `sync.failed`. Router now uses `reason`/`sub_reason` per Constraint 6. JWT claim validation switched to explicit `JsonWebToken([RS256…])` + essential `claims_options` with 60s leeway; `azp` enforced when `aud` is multi-valued. Test suite expanded (+7 regression tests), transactional test fixture updated to use SAVEPOINT-wrapped nested transaction so handler-internal rollbacks don't clobber setup. `1080/1080` backend tests pass.

### File List

- `backend/src/audit/event_types.py` (NEW)
- `backend/src/audit/service.py` (MOD — added `log_event()` wrapper + imports)
- `backend/src/auth/oidc_callback_service.py` (NEW — post-review: algorithm pinning, claims_options, azp, atomic state claim, IntegrityError handling, sync.failed, dual-source upsert, http_status, email_verified, is_active reject)
- `backend/src/auth/sso_router.py` (MOD — `/callback` route; post-review: reason/sub_reason rename, rollback-before-audit, URL-encoded err.code, return_to re-validation)
- `backend/tests/audit/test_event_types.py` (NEW)
- `backend/tests/auth/test_sso_callback.py` (NEW — 32 tests incl. concurrent-replay, email_verified, user.disabled, sync.failed, http_status, azp regressions)
- `backend/tests/fixtures/mock_oidc.py` (MOD — `email_verified: True` default in minted claims)
- `backend/tests/conftest.py` (MOD — SAVEPOINT-wrapped transactional fixture for handler rollback compatibility)

### Review Findings

**Decision Needed**

- [x] [Review][Decision] **Identity matching: email-only vs `(idp_id, sub)`.** Resolved by auto-accepting option **B** (require `email_verified == true`) per the collaboration-preference to default to the recommended option. Narrow fix, widely supported by enterprise IdPs, keeps the schema. Option C (`UserIdentity` table) remains available for a later hardening story.
- [x] [Review][Decision] **JWT cookie handoff: keep non-HttpOnly 60s cookies vs fragment vs one-time-exchange endpoint.** Resolved by auto-accepting option **A** (keep the 60s non-HttpOnly cookies). Spec-compliant and preserves the Story 2-3 handoff contract. The XSS exposure is bounded by the 60-second TTL; revisiting as a Phase 4 hardening item is tracked in `deferred-work.md`.

**Patches (security-critical)**

- [x] [Review][Patch] `is_active=False` users silently reactivated via SSO [`backend/src/auth/oidc_callback_service.py:249-264`] — add `if not user.is_active: raise SsoCallbackError("user.disabled", …)`.
- [x] [Review][Patch] Pin `jwt.decode` algorithms; reject `HS*` / `none` [`backend/src/auth/oidc_callback_service.py:232`] — `JsonWebToken(["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"])`.
- [x] [Review][Patch] Enforce essential claims via `claims_options` [`backend/src/auth/oidc_callback_service.py:232`] — `iss`/`aud`/`exp`/`iat`/`nonce` must be present; 60s leeway.
- [x] [Review][Patch] Verify `azp` when `aud` is a multi-value array [`backend/src/auth/oidc_callback_service.py:218-222`] — OIDC Core §3.1.3.7 requires `azp == client_id`.
- [x] [Review][Patch] Roll back partial state on failure before audit write [`backend/src/auth/sso_router.py:88-95`] — `db.rollback()` before `log_event(FAILURE)` to prevent committing half-upserted users/memberships.
- [x] [Review][Patch] Atomic state claim before network I/O [`backend/src/auth/oidc_callback_service.py:72-107`] — capture attempt fields then `db.delete(attempt); db.commit()` before discovery/token-exchange so concurrent callbacks see no row.
- [x] [Review][Patch] Handle `IntegrityError` on first-time user insert [`backend/src/auth/oidc_callback_service.py:249-264`] — on race/username collision, re-SELECT or map to `user.username_conflict`.

**Patches (spec-alignment)**

- [x] [Review][Patch] Audit failure detail key must be `reason` per Constraint 6, not `code` [`backend/src/auth/sso_router.py:92`] — rename top-level `code` → `reason`, rename inner `reason` → `sub_reason` to avoid spread collision, update 3 tests.
- [x] [Review][Patch] Capture `http_status` on IdP HTTP errors [`backend/src/auth/oidc_callback_service.py:156-162`] — extract `exc.response.status_code` on `httpx.HTTPStatusError`; regression test `test_callback_token_exchange_http_error_captures_status` added.
- [x] [Review][Patch] Emit `sync.failed` when inline group sync raises [`backend/src/auth/oidc_callback_service.py:267-320`] — wrap in `try/except SQLAlchemyError`, raise `SsoCallbackError("sync.failed", …)`; regression test `test_callback_sync_failure_surfaces_sync_failed_code` added.
- [x] [Review][Patch] Add `idp.unavailable` + `user.disabled` + `user.username_conflict` + `claims.email_unverified` + `sync.failed` to Constraint 6 failure-code enum — additions noted here; formal enum centralization deferred to Story 5-6 (AuditEventType extension).

**Patches (defense-in-depth)**

- [x] [Review][Patch] Add concurrent-replay regression test — `test_callback_replay_same_state_fails_on_second_call` calls `/callback` twice with the same state and asserts second → `/sso-error?code=state.unknown`.
- [x] [Review][Patch] Upsert semantics for dual-source `TeamMember` [`backend/src/auth/oidc_callback_service.py:293-311`] — check any existing `(team_id, user_id)` row (not just `source='manual'`) before insert to avoid `IntegrityError` when an admin manually re-flags a sync row.
- [x] [Review][Patch] Re-validate stored `return_to` at callback [`backend/src/auth/sso_router.py:126-129`] — call `validate_return_to(result.return_to, base_url)` on the success path as defense-in-depth; attempt rows survive across base_url config changes.
- [x] [Review][Patch] URL-encode `err.code` on error redirect [`backend/src/auth/sso_router.py:98`] — `urllib.parse.quote(err.code, safe="")` guards against future codes with control characters.

**Deferred (pre-existing / out-of-scope / hardening follow-ups)**

- [x] [Review][Defer] `get_or_fetch_discovery` inner `db.commit()` leaks transaction control [`backend/src/auth/oidc_discovery.py:300`] — already deferred in Story 2-1 review; re-noted here.
- [x] [Review][Defer] Hardcoded `token_endpoint_auth_method="client_secret_post"` [`backend/src/auth/oidc_callback_service.py:143`] — support `client_secret_basic` and public-client PKCE via per-IdP setting in a later story.
- [x] [Review][Defer] Broad `except Exception` in `_exchange_code` masks programming errors [`backend/src/auth/oidc_callback_service.py:163-167`] — narrow to `OAuthError`/`OAuth2Error` after audit of authlib error taxonomy.
- [x] [Review][Defer] Token response + JWKS response size not capped [`backend/src/auth/oidc_callback_service.py:153,188`] — mirror Story 2-1 `_MAX_RESPONSE_SIZE = 1_000_000` via custom transport; hardening item.
- [x] [Review][Defer] JWKS fetched on every callback (no cache) [`backend/src/auth/oidc_callback_service.py:184-194`] — add per-IdP JWKS cache with TTL and bypass-on-signature-invalid retry.
- [x] [Review][Defer] JWKS rotation mid-flow / 304 Not Modified handling [`backend/src/auth/oidc_callback_service.py:184-194`] — one-shot retry when signature fails; explicit 304 handling.
- [x] [Review][Defer] Group claim dotted paths not supported [`backend/src/auth/oidc_callback_service.py:239-245`] — Keycloak `resource_access.<client>.roles` pattern.
- [x] [Review][Defer] Group value shape variance (string vs list) silently empty [`backend/src/auth/oidc_callback_service.py:241-245`].
- [x] [Review][Defer] N+1 manual-grant lookup in group sync [`backend/src/auth/oidc_callback_service.py:293-302`] — batch SELECT for manual rows per user.
- [x] [Review][Defer] Team FK violation when team is deleted mid-flow [`backend/src/auth/oidc_callback_service.py:304-311`] — JOIN mappings against `teams` or guard at app level.
- [x] [Review][Defer] `IdPGroupMapping` duplicate (same group, same team) role-conflict ordering non-deterministic — pick highest-privilege deterministically.
- [x] [Review][Defer] Email case collision on existing mixed-case users — migration job + `citext` on Postgres.
- [x] [Review][Defer] X-Forwarded-For IP extraction for audit rows — cross-cutting project hardening.
- [x] [Review][Defer] Email PII in `sso.login.success` audit `detail` — consider hashing/omitting under long retention.
- [x] [Review][Defer] Cookies not cleared on failure redirect — `delete_cookie` on failure path.
- [x] [Review][Defer] `Pragma: no-cache` header missing on callback redirect (initiate has it).
- [x] [Review][Defer] `SameSite=Lax` cookies + future `response_mode=form_post` support — document as unsupported for now.
- [x] [Review][Defer] `secure=True` cookies silently dropped over HTTP in dev — detect `X-Forwarded-Proto`, warn.
- [x] [Review][Defer] `TeamMember.source` / `IdPGroupMapping.role` role-string magic values not validated against enum.
- [x] [Review][Defer] Empty `team.member.synced_from_idp` audit event emitted when no changes — log-noise cleanup.
- [x] [Review][Defer] AC6 commit-order numbered-sequence contradicts the spec's own reference snippet — spec author to clarify; impl follows reference.
