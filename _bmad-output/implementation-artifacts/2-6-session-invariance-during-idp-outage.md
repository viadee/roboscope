# Story 2.6: Session invariance during IdP outage

Status: done

Epic: 2 — SSO User Access
Story Key: `2-6-session-invariance-during-idp-outage`

## Story

As a User with an active session,
I want my existing login session to remain valid even when the IdP is unreachable,
so that a transient outage doesn't force me to re-authenticate unnecessarily.

## Context

- `get_current_user()` in `backend/src/auth/dependencies.py:26-72`
  already decodes JWTs locally and looks up the user via
  `get_user_by_id()`. There is no per-request IdP roundtrip.
- The SSO init/callback routes (Story 2-1/2-2) are the only code
  paths that reach the IdP; once a user has a JWT, subsequent
  requests bypass the IdP entirely.
- **Gap 1**: AC3 specifies `401` for deactivated users; the current
  implementation returns `403` (line 66-70). The semantic the story
  prefers is *"please re-auth"* (401), not *"you are authenticated
  but not allowed"* (403). Align the status to 401 and document
  the rationale.
- **Gap 2**: there is no explicit test that proves session invariance
  — i.e., that `get_current_user` succeeds when the IdP is
  unreachable. Codify this with a test that mocks `httpx` to always
  raise and asserts the JWT path still works.

## Acceptance Criteria

1. **AC1 — JWT validation is IdP-free.** A request with a valid
   JWT succeeds even when the IdP is unreachable. Verified by a
   pytest that patches `httpx.AsyncClient.get` / `.post` to raise
   `httpx.ConnectError("simulated outage")` and then calls a
   protected endpoint (`GET /api/v1/auth/me`); asserts `200`.

2. **AC2 — `User.is_active` is re-checked on every request.**
   Deactivating a user between two requests (mutating the DB row,
   no new JWT issued) causes the second request to be rejected.
   Verified by a pytest that issues one successful request, flips
   `user.is_active = False` and commits, then issues a second
   request and asserts the deactivation-rejection response.

3. **AC3 — Deactivated users receive `401 Unauthorized`.**
   `get_current_user` returns 401 for inactive users (consistency
   with "please re-authenticate" semantic — a deactivated user is
   effectively no longer authenticated in our trust model).
   Verified by a pytest.

4. **AC4 — API-token path parity.** The API-token flow
   (`_authenticate_api_token`) also returns 401 when the token's
   user is deactivated (it already did — this AC asserts it with
   a test so we don't regress).

5. **AC5 — No regression of auth dependencies.** All existing
   `backend/tests/auth/` tests continue to pass.

## Tasks / Subtasks

### Task 1: Align deactivated-user status code to 401 (AC3)

- [x] MOD `backend/src/auth/dependencies.py` — in
  `get_current_user`, change the `if not user.is_active` branch
  from `HTTP_403_FORBIDDEN` to `HTTP_401_UNAUTHORIZED`. Keep the
  `ERR_INACTIVE_USER` detail message so clients can distinguish
  the reason. Document the rationale with a short comment:
  *"A deactivated user has no session; 401 prompts the client
  to re-authenticate, which is correct semantic for admins
  wanting immediate enforcement (Story 2-6 AC3)."*

### Task 2: Tests (AC1–AC4)

- [x] NEW `backend/tests/auth/test_session_invariance.py`:
  - `test_valid_jwt_succeeds_during_idp_outage`: patch
    `httpx.AsyncClient.post` / `.get` to raise `ConnectError`,
    GET `/api/v1/auth/me`, assert 200.
  - `test_deactivated_user_returns_401`: mutate `user.is_active`
    in a separate session, GET with the old JWT, assert 401 and
    detail `ERR_INACTIVE_USER`.
  - `test_is_active_rechecked_on_every_request`: two successive
    calls, deactivation between them, assert first=200 and
    second=401.
  - `test_api_token_deactivated_user_returns_401`: same check
    for the API-token flow.

### Task 3: Regression (AC5)

- [x] Run `pytest backend/tests/auth/ -v` — all green.

## Non-goals

- Implementing the frontend SsoErrorView — that's Story 2-7.
- Adding a background job that caches JWKS or probes the IdP —
  unnecessary since JWT validation is already stateless.
- Changing the 401 semantic for completely-missing tokens — only
  the deactivated-user branch is touched.

## Dev Notes

- The 403→401 change is technically breaking for any client that
  specifically catches 403 for this reason. Searching the codebase
  and tests turned up zero call sites asserting 403 for the
  deactivation path, so this is safe.
- The `fetchCurrentUser` store path on the frontend already
  treats both 401 and 403 as "clear session and send to /login",
  so there is no observable UX difference.
