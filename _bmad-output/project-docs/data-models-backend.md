# Backend Data Models — Phase 4 Relevant Subset

_Scoped to Phase 4 (SSO + Teams). Full schema lives in `backend/src/*/models.py` + `backend/migrations/versions/`. This doc captures what the PRD must not break and where new tables fit._

## Tables the PRD touches

### `users` (unchanged schema; one column becomes nullable)

Source: `backend/src/auth/models.py`

```
users
├─ id                 PK autoincrement
├─ email              String(255)  UNIQUE NOT NULL  (external id for login)
├─ username           String(100)  UNIQUE NOT NULL  (display name)
├─ hashed_password    String(255)  NOT NULL ← Phase 4: becomes NULLable
├─ role               String(20)   DEFAULT 'runner' (viewer|runner|editor|admin)
├─ is_active          bool         DEFAULT true
├─ last_login_at      datetime NULL
├─ created_at         datetime     (TimestampMixin)
└─ updated_at         datetime     (TimestampMixin)
```

**FKs that reference `users.id`** (don't break these):
- `api_tokens.user_id` — scoped API token ownership
- `webhooks.created_by` — outbound webhook audit trail
- `audit_logs.user_id` — compliance
- `project_members.user_id` — per-project role override
- `execution_runs.triggered_by` — run attribution
- `repositories.created_by` — repo owner

### `project_members` (Phase 4 interacts; does not modify)

Source: `backend/src/repos/models.py`

```
project_members
├─ id             PK autoincrement
├─ user_id        FK users.id          ON DELETE CASCADE, INDEXED
├─ repository_id  FK repositories.id   ON DELETE CASCADE, INDEXED
├─ role           String(20) DEFAULT 'viewer'
├─ created_at, updated_at
└─ UNIQUE(user_id, repository_id)     ← uq_project_member
```

This is the existing per-project role override primitive. Phase 4 Teams layers **above** this, doesn't replace it.

### `repositories` (gets one new FK)

Source: `backend/src/repos/models.py`

```
repositories
├─ id                    PK
├─ name                  String(255) UNIQUE
├─ repo_type             String(20) DEFAULT 'git'
├─ git_url               String(500) NULL
├─ default_branch        String(100) DEFAULT 'main'
├─ local_path            String(500)
├─ last_synced_at        datetime NULL
├─ auto_sync             bool DEFAULT true
├─ sync_interval_minutes int  DEFAULT 15
├─ sync_status           String(20) DEFAULT 'idle'
├─ sync_error            Text NULL
├─ created_by            FK users.id
├─ environment_id        FK environments.id ON DELETE SET NULL, NULL
└─ team_id               FK teams.id        ON DELETE SET NULL, NULL ← Phase 4 NEW
```

**Migration note**: `team_id` must be NULLable (existing repos are personally-owned and stay that way).

## New tables Phase 4 introduces

### `user_identities` — links a User to one or more external IdPs

```
user_identities
├─ id                PK
├─ user_id           FK users.id ON DELETE CASCADE, INDEXED
├─ provider          String(32)  ('azure_ad' | 'google' | 'github' | 'saml:<entity_id>')
├─ external_id       String(255) (provider's stable subject / sub claim)
├─ external_email    String(255)
├─ provider_data     Text (JSON; raw claims for future reference)
├─ last_login_at     datetime NULL
├─ created_at, updated_at
└─ UNIQUE(provider, external_id)
```

Rationale for a separate table (vs adding columns to `users`):
- Supports multi-IdP linking per user
- Clean separation of password auth (`users.hashed_password`) and federated auth
- Per-identity `last_login_at` is useful for audit / dormant-IdP-session cleanup

### `teams`

```
teams
├─ id          PK
├─ name        String(255) UNIQUE NOT NULL
├─ description Text NULL
├─ created_by  FK users.id NOT NULL
└─ created_at, updated_at
```

### `team_members`

```
team_members
├─ id         PK
├─ team_id    FK teams.id        ON DELETE CASCADE, INDEXED
├─ user_id    FK users.id        ON DELETE CASCADE, INDEXED
├─ role       String(20) DEFAULT 'viewer' (viewer|runner|editor|admin)
├─ created_at, updated_at
└─ UNIQUE(team_id, user_id)
```

## Alembic migration plan

Two migrations, ordered:

**1. `add_user_identities.py`** (SSO-first deploy)
- Create `user_identities`
- Alter `users.hashed_password` → NULLable
- Safe backward-compatible: existing users keep passwords, SSO users can coexist

**2. `add_teams.py`** (Teams second)
- Create `teams`
- Create `team_members`
- Add `repositories.team_id` column + FK
- Safe backward-compatible: NULL `team_id` = personal repo (matches pre-migration state)

Both must pass on **SQLite and PostgreSQL**. Postgres-specific syntax (partial indexes, etc.) must be rewritten portably or skipped.

## Tables unchanged but referenced by Phase 4

### `api_tokens`

Phase 4 must preserve the scope-narrowing invariant: `effective_role = min(token.role, user.effective_role)`. "User's effective role" under Teams becomes a function, not a column read. The dependency in `auth/dependencies.py::_authenticate_api_token` needs updating to resolve user's effective role **at request time** if the token is scoped to a team-owned resource.

### `audit_logs`

Phase 4 must add audit entries for:
- SSO login (`action=login`, `resource_type=auth`, `detail={provider, external_email}`)
- JIT provisioning (`action=create`, `resource_type=user`, `detail={via=sso, provider}`)
- Team create/update/delete (`resource_type=team`)
- Team membership changes (`resource_type=team_member`)
- Repo ownership transfer to team (`resource_type=repository`, `detail={team_id}`)

Middleware auto-handles most; add entries to `_RESOURCE_MAP` in `audit/middleware.py` for `/api/v1/teams` and `/api/v1/auth/sso`.

### `app_settings`

New keys under `category='sso'`:
- `sso.enabled` (value_type=bool)
- `sso.providers` (value_type=json) — list of provider configs, secrets Fernet-encrypted
- `sso.default_role` (value_type=string, enum-like)
- `sso.allowed_email_domains` (value_type=json) — array of domain strings, empty = any

Use existing `encryption.py` `encrypt_value()` / `decrypt_value()` for `client_secret` fields. Graceful plaintext fallback already handled.

## Indexes the PRD should plan for

- `user_identities (provider, external_id)` — UNIQUE, becomes the IdP lookup index
- `user_identities (user_id)` — look up "what IdPs has this user linked"
- `team_members (user_id)` — look up "what teams am I in" (hot path for auth)
- `team_members (team_id, user_id)` — UNIQUE, already the composite for membership lookup
- `repositories (team_id)` — list repos owned by a team

`user_identities (external_email)` is tempting for conflict detection, but email is not guaranteed stable across IdPs (users change email at Google, provider sends new email claim). Keep `external_id` as the canonical lookup.
