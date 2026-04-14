# API Contracts — Phase 4 Relevant Surface

_Current auth-adjacent endpoints + the net-new surface Phase 4 introduces. For full API surface see `http://localhost:8000/api/v1/docs` (Swagger) or `CLAUDE.md`._

## Current endpoints (as of 2026-04-14)

### `/api/v1/auth` — authentication core

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/login` | none | Password login → JWT pair. Rate-limited 10/5min/IP (in-memory). |
| POST | `/auth/refresh` | none (uses refresh JWT) | Refresh access JWT. |
| GET  | `/auth/me` | any | Current user (JWT or API token). |
| GET  | `/auth/users` | ADMIN | List users. |
| POST | `/auth/users` | ADMIN | Create user. |
| GET  | `/auth/users/{user_id}` | ADMIN | Get user. |
| PATCH | `/auth/users/{user_id}` | ADMIN | Update user (incl. password). |
| DELETE | `/auth/users/{user_id}` | ADMIN | Soft-delete (`is_active=false`). |

### `/api/v1/webhooks` — tokens + hooks + inbound

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/webhooks/tokens` | ADMIN | Create API token. Returns plaintext ONCE. |
| GET  | `/webhooks/tokens` | ADMIN | List tokens (prefix only, no plaintext). |
| DELETE | `/webhooks/tokens/{id}` | ADMIN | Revoke. |
| POST | `/webhooks/hooks` | EDITOR+ | Create outbound hook. |
| GET  | `/webhooks/hooks` | EDITOR+ | List. |
| GET  | `/webhooks/hooks/{id}` | EDITOR+ | Detail. |
| PATCH | `/webhooks/hooks/{id}` | EDITOR+ | Update. |
| DELETE | `/webhooks/hooks/{id}` | EDITOR+ | Delete. |
| POST | `/webhooks/hooks/{id}/test` | EDITOR+ | Test-ping with HMAC signature. |
| GET  | `/webhooks/hooks/{id}/deliveries` | EDITOR+ | Delivery log. |
| GET  | `/webhooks/events` | any | List of subscribable event names. |
| POST | `/webhooks/git` | **unauthenticated** | GitHub/GitLab push trigger. HMAC verification required (see security hard rules). |

### `/api/v1/repos/{repo_id}/members` — the Teams primitive already in place

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/repos/{repo_id}/members` | any (member of repo) | List members. |
| POST | `/repos/{repo_id}/members` | project ADMIN or global ADMIN | Add member with role. |
| PATCH | `/repos/{repo_id}/members/{member_id}` | same | Change role. |
| DELETE | `/repos/{repo_id}/members/{member_id}` | same | Remove member. |

### `/api/v1/audit` — compliance read surface

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/audit` | ADMIN | List with filters (action, resource_type, user, date). |
| GET | `/audit/export` | ADMIN | CSV export. |
| GET | `/audit/filters` | ADMIN | Available filter values. |
| POST | `/audit/retention/run` | ADMIN | Manual retention trigger. |

### `/api/v1/settings` — key-value config

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/settings` | ADMIN | Read all keys. |
| PATCH | `/settings` | ADMIN | Write keys (multi-key diff). |

## New endpoints Phase 4 introduces

### `/api/v1/auth/sso` — OAuth2/OIDC login

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/auth/sso/providers` | **public** | List configured providers: `[{id, type, display_name, login_url}]`. Needed for login page. |
| GET | `/auth/sso/{provider}/authorize` | **public** | Redirect to IdP with PKCE challenge. Sets `state` cookie (httpOnly, SameSite=Lax). |
| GET | `/auth/sso/{provider}/callback` | **public** (callback) | Validate state, exchange code, JIT-provision if new, mint JWT via `create_token_response`, redirect to frontend with tokens in URL **fragment** (not query — avoids referer/log leak). |
| POST | `/auth/sso/providers` | ADMIN | Upsert provider config (client_id, client_secret, tenant_id, etc.). Secret Fernet-encrypted. |
| GET | `/auth/sso/providers/admin` | ADMIN | List providers WITH admin-only fields (masked secret). |
| DELETE | `/auth/sso/providers/{id}` | ADMIN | Disable provider. |
| GET | `/auth/users/{user_id}/identities` | ADMIN | List IdP identities linked to a user. |
| DELETE | `/auth/users/{user_id}/identities/{identity_id}` | ADMIN | Unlink an IdP from a user. |

**Security contracts**:
- `state` cookie must be httpOnly + SameSite=Lax + unpredictable (128-bit random).
- Callback MUST validate state matches the cookie, else reject `400`.
- Client secret is never returned (masked `****last4` on GET).
- Redirect URL after callback is restricted to frontend origin; open-redirect is a blocker.
- Provider allowlist on email domain (configurable per provider).

### `/api/v1/teams` — Teams CRUD

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/teams` | any | List teams visible to current user. |
| POST | `/teams` | any (creator becomes team ADMIN) | Create team. |
| GET | `/teams/{id}` | team member or global ADMIN | Team detail with member summary. |
| PATCH | `/teams/{id}` | team ADMIN | Rename, update description. |
| DELETE | `/teams/{id}` | team ADMIN | Delete. Repos owned by this team get `team_id=NULL` (ownership transfers to global ADMIN for reclamation). |
| GET | `/teams/{id}/members` | team member | List. |
| POST | `/teams/{id}/members` | team ADMIN | Add by user id or email. |
| PATCH | `/teams/{id}/members/{member_id}` | team ADMIN | Change role. |
| DELETE | `/teams/{id}/members/{member_id}` | team ADMIN | Remove. |
| GET | `/teams/{id}/repositories` | team member | List repos owned by the team. |

### `/api/v1/repos/{id}` — augment existing endpoint

- `PATCH /repos/{id}` accepts new field `team_id` (int \| null). Transfer semantics:
  - NULL → NULL: no-op.
  - NULL → team_id: caller must be global ADMIN OR current `created_by` user AND team ADMIN of target team.
  - team_id → NULL: caller must be current team ADMIN OR global ADMIN. Repo becomes personal to `created_by`.
  - team_id A → team_id B: caller must be ADMIN of both.

## Request/response shape conventions

Consistent with existing code:
- All response models use `model_config = {"from_attributes": True}` (Pydantic v2).
- `201 Created` for POST that creates.
- `204 No Content` for DELETE.
- `409 Conflict` for unique-violation (email exists, team name taken).
- `422` for Pydantic validation failure.
- Pagination: `?skip=0&limit=100` query params (see existing `/auth/users`).

## Unchanged contracts the PRD must preserve

- `POST /auth/login` request/response shape — frontend login form depends on it.
- `GET /auth/me` response shape — token interceptor reads `role` and `is_active`.
- `rbs_` API token flow — CI/CD consumers must not break.
- `POST /webhooks/git` inbound — HMAC signature header names.
- Audit log auto-middleware — all new write endpoints flow through it by default.

## Swagger

Every new router must mount under `src/api/v1/router.py` with an appropriate `tags=[…]` entry so the Swagger at `/api/v1/docs` reflects the surface. New tags: `SSO`, `Teams`.
