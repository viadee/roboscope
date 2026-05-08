# Source Tree Analysis — Phase 4 Scope

_Annotated backend source tree focused on modules relevant to Phase 4 (SSO + Teams). For full repo structure see CLAUDE.md._

```
backend/src/
├── auth/                        # ← Phase 4 primary target
│   ├── models.py                # User table (email, hashed_password, role, is_active, last_login_at)
│   ├── constants.py             # Role StrEnum + ROLE_HIERARCHY + error messages
│   ├── schemas.py               # LoginRequest, RegisterRequest, TokenResponse, UserResponse, UserUpdate
│   ├── service.py               # authenticate_user, create_token_response, hash/verify_password, decode_token
│   ├── dependencies.py          # get_current_user (JWT OR rbs_ API token), require_role(min_role) factory
│   └── router.py                # /login, /refresh, /me + admin /users CRUD + in-memory login rate limiter
│
├── webhooks/                    # ← Phase 1 artefacts; Phase 4 affects API token scoping
│   ├── models.py                # ApiToken, Webhook, WebhookDelivery
│   ├── service.py               # hash_token, verify_token, get_token_by_hash, update_token_last_used
│   └── router.py                # /tokens (create/list/delete), /hooks (CRUD + test + deliveries), /git inbound
│
├── repos/                       # ← Phase 4 secondary target (ProjectMember lives here)
│   ├── models.py                # Repository + ProjectMember (user_id, repository_id, role)
│   └── router.py                # /repos CRUD + /repos/{id}/members CRUD + /repos/{id}/sync + /branches
│
├── audit/                       # ← Phase 4 consumes this; minimal changes expected
│   ├── models.py                # AuditLog (user_id, action, resource_type, resource_id, detail, ip, timestamp)
│   ├── middleware.py            # AuditMiddleware (auto-logs POST/PUT/PATCH/DELETE in a daemon thread)
│   ├── service.py               # log_audit helper
│   ├── retention.py             # APScheduler job (24h interval) — enforces report_retention_days
│   └── router.py                # /audit (list, filters), /audit/export (CSV), /audit/retention/run
│
├── settings/                    # ← Phase 4 target (IdP config lives here)
│   ├── models.py                # AppSetting (key, value, value_type, category, description)
│   └── router.py                # /settings GET + PATCH (ADMIN only), /settings/docker-status
│
├── encryption.py                # ← Phase 4 consumer (IdP client_secret encryption)
│                                # Fernet derived from SECRET_KEY; encrypt_value / decrypt_value
│                                # Legacy plaintext still decrypts (graceful degradation)
│
├── database.py                  # get_db (route Depends), get_sync_session (bg threads), Base, TimestampMixin
│
├── api/v1/router.py             # SOLE router aggregation point — new SSO router mounts here
│
└── main.py                      # App factory, lifespan, _event_loop capture, AuditMiddleware registration
```

## Phase 4 surface area in this tree

- **New file likely needed**: `backend/src/auth/sso/` subdirectory
  - `providers.py` — Azure AD / Google / GitHub / (optional) SAML adapters
  - `router.py` — `/auth/sso/{provider}/authorize`, `/auth/sso/{provider}/callback`
  - `models.py` — `UserIdentity` (user_id, provider, external_id, external_email, last_login_at)
  - `service.py` — provider-agnostic login orchestration, JIT provisioning rules
- **New file likely needed**: `backend/src/teams/`
  - `models.py` — `Team` (name, description), `TeamMember` (team_id, user_id, role)
  - `schemas.py`, `service.py`, `router.py`
- **Model changes**:
  - `User.hashed_password` → nullable (SSO-only users have no password)
  - `Repository` gains `team_id` FK (nullable; NULL = user-owned repo)
  - `ProjectMember.role` resolution rules updated to respect Team inheritance
- **Alembic migrations**: at minimum two new migration files (one for `UserIdentity`, one for `Team`/`TeamMember` + `Repository.team_id`)
- **Settings keys** (new, ADMIN-only):
  - `sso.enabled`, `sso.provider`, `sso.client_id`, `sso.client_secret` (encrypted), `sso.tenant_id`, `sso.allowed_domains`, `sso.default_role`

## Entry points unchanged

No changes required to `main.py`, `api/v1/router.py` aggregation, `AuditMiddleware`, or the `dispatch_task` contract. Phase 4 is additive, not invasive.
