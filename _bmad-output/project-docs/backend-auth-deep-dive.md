# Backend Auth Deep-Dive — Phase 4 Grounding

_Written to ground the OAuth2/SSO + Teams PRD. Captures the current state in enough detail that the PRD can be concrete about what changes._

## 1. Identity model (current state)

### 1.1 `User` table

File: `backend/src/auth/models.py`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK autoincrement | |
| `email` | String(255) unique, indexed | **The de-facto external identifier** |
| `username` | String(100) unique, indexed | Display name; not used as login key |
| `hashed_password` | String(255) | bcrypt (`bcrypt.hashpw` / `bcrypt.checkpw`). **Not nullable** today — this is a Phase 4 schema change. |
| `role` | String(20), default `"runner"` | Single global role. Stored as `StrEnum` value. |
| `is_active` | bool, default `true` | Soft-delete via `is_active=False` (see `DELETE /auth/users/{id}`) |
| `last_login_at` | datetime \| None | Updated on successful JWT login. Phase 4 should update on SSO login too. |
| `created_at`, `updated_at` | TimestampMixin | |

**Phase 4 implication**: `hashed_password` must become nullable to support SSO-only accounts. Alternative is a sentinel "unusable hash" — simpler but leaky. Recommend nullable + a `has_password` computed property.

### 1.2 `Role` enum + hierarchy

File: `backend/src/auth/constants.py`

```python
class Role(StrEnum):
    VIEWER = "viewer"
    RUNNER = "runner"
    EDITOR = "editor"
    ADMIN = "admin"

ROLE_HIERARCHY = {Role.VIEWER: 0, Role.RUNNER: 1, Role.EDITOR: 2, Role.ADMIN: 3}
```

Integer hierarchy is the comparison basis. `require_role(min_role)` uses `user_level >= required_level`.

**Phase 4 implication**: role enum is unchanged. Team-level roles reuse the same enum. What's new is *where roles can be stored* (add `TeamMember.role`).

### 1.3 `ProjectMember` table — the Teams primitive that already exists

File: `backend/src/repos/models.py`

```python
class ProjectMember(Base, TimestampMixin):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("user_id", "repository_id"),)
    id: int PK
    user_id: FK users.id, ondelete=CASCADE
    repository_id: FK repositories.id, ondelete=CASCADE
    role: String(20), default "viewer"
```

Endpoints (already wired):
- `GET  /api/v1/repos/{repo_id}/members`
- `POST /api/v1/repos/{repo_id}/members`
- `PATCH /api/v1/repos/{repo_id}/members/{member_id}`
- `DELETE /api/v1/repos/{repo_id}/members/{member_id}`

**Phase 4 is additive, not replacing.** The decision in the PRD is how `Team.role` interacts with `ProjectMember.role` when a repo is owned by a team containing the user.

### 1.4 `ApiToken` — not an identity, a grant

File: `backend/src/webhooks/models.py`

| Column | Notes |
|---|---|
| `token_hash` | SHA256 of `rbs_<hex>`, unique |
| `prefix` | First 8 chars for UI display (`rbs_xxxx…`) |
| `role` | Scoped role — may be narrower than the owning user's role |
| `user_id` | FK users.id — token is owned by a specific user |
| `expires_at`, `last_used_at`, `is_active` | lifecycle |

Scope-narrowing is enforced in `auth/dependencies.py::_authenticate_api_token`:

```python
effective_role = api_token.role if token_role_level <= user_role_level else user.role
```

The `<=` means the token role can narrow but not escalate beyond the user's current role. **This should hold under Teams semantics too** — Phase 4 must not let a team membership escalate an API token's effective role beyond what the user would have interactively.

## 2. Authentication flow (current state)

### 2.1 Password login → JWT

File: `backend/src/auth/router.py::login`

1. `POST /api/v1/auth/login` with `{email, password}`
2. In-memory rate limiter per IP (10 attempts / 5 min, `defaultdict[list]` keyed by `request.client.host`). Known debt: doesn't persist across restart, no shared storage in multi-process deploys.
3. `authenticate_user(db, email, password)` — bcrypt verify, returns `User | None`
4. `create_token_response(user)` — mints access JWT (`type=access`) + refresh JWT (`type=refresh`)
5. Response: `{access_token, refresh_token, token_type: "bearer", expires_in}`

Failed attempts increment the rate-limit window. **Phase 4 SSO callback should share this same `create_token_response` path** so downstream handlers don't care how the session started.

### 2.2 JWT refresh

`POST /api/v1/auth/refresh` with `{refresh_token}` — decode, verify `type==refresh`, load user, mint new token pair.

### 2.3 Bearer auth (JWT or API token)

File: `backend/src/auth/dependencies.py::get_current_user`

The dependency inspects the bearer value:
- Starts with `"rbs_"` → API-token path (`_authenticate_api_token`)
- Otherwise → JWT path (`decode_token` + `payload.type == "access"`)

**Critical for Phase 4**: `get_current_user` returns a `User` regardless of path. SSO plugs in at token **mint** time, not at auth-dependency time. The dependency does not change.

### 2.4 `require_role(min_role)` — RBAC gate factory

Mounted on protected endpoints:
```python
_current_user: User = Depends(require_role(Role.EDITOR))
```

Resolution is global-role-only today. **Phase 4 must decide**: does `require_role` consider Team/ProjectMember roles? Two reasonable paths:
- (a) Keep `require_role` as global-role-only; introduce separate `require_project_role(repo_id, min_role)` for per-project endpoints. Current `/repos/{id}/members` endpoints already imply this pattern is needed.
- (b) Re-implement `require_role` to compute a max over (global, project, team) roles. Simpler at call sites, more opaque at review time.

Recommend (a) — explicit per-project dependencies where project-scoped permissions matter.

## 3. SSO integration surface

### 3.1 Where SSO plugs in

- **New module**: `backend/src/auth/sso/`
- **New endpoints**:
  - `GET /api/v1/auth/sso/providers` — list configured providers (public; returns `[{provider, login_url}]`)
  - `GET /api/v1/auth/sso/{provider}/authorize` — redirect to IdP with PKCE challenge
  - `GET /api/v1/auth/sso/{provider}/callback?code=…&state=…` — exchange code, verify state, look up or JIT-provision `User` + `UserIdentity`, mint JWT via existing `create_token_response`, redirect to frontend with tokens in URL fragment (not query — avoids referer/log leak)
- **New table**: `UserIdentity`
  ```
  user_id: FK users.id
  provider: String(32)   # 'azure_ad' | 'google' | 'github' | 'saml:<entity_id>'
  external_id: String(255)
  external_email: String(255)
  provider_data: JSON    # sub, tenant, hd, etc.
  last_login_at: datetime
  UNIQUE(provider, external_id)
  ```
- **Settings keys** (store in `AppSetting`, `category="sso"`, ADMIN-only write):
  - `sso.enabled` (bool)
  - `sso.providers` (JSON: `[{id, type, client_id, client_secret_encrypted, tenant_id, discovery_url, allowed_email_domains, default_role, auto_provision}]`)
  - Secrets are Fernet-encrypted via existing `encryption.py` — legacy plaintext fallback already handled.

### 3.2 JIT provisioning rules (to be decided in PRD)

- First login via IdP → create `User` with `role = sso.providers[*].default_role` (default `VIEWER`), create matching `UserIdentity`
- Email domain allowlist: `sso.providers[*].allowed_email_domains` — block IdP users outside the list
- Conflict handling: IdP email matches existing password user → link (create `UserIdentity` for existing user) or block? Recommend **block by default**, let admin explicitly link from the user admin UI.
- Deactivation: if IdP revokes a user mid-session, the JWT still works until expiry. Phase 5 could add a token revocation list; Phase 4 lives with JWT expiry as the ceiling.

### 3.3 SAML (optional)

Spec says "optional SAML 2.0 via python-saml for Enterprise IdPs (Okta, ADFS)". `python-saml` has a `libxml2`/`xmlsec` system dependency that will complicate the **Windows offline archive** (`libxmlsec` is non-trivial on Windows). The PRD should flag this: either mark SAML as a separate optional extra (`pip install roboscope-backend[saml]`) with a documented Windows caveat, or drop SAML from Phase 4 and punt to a later phase.

## 4. Teams integration surface

### 4.1 Schema changes

**New tables**:
```
Team:
  id PK
  name unique
  description Text|None
  created_by FK users.id
  timestamps

TeamMember:
  UNIQUE(team_id, user_id)
  team_id FK teams.id ON DELETE CASCADE
  user_id FK users.id ON DELETE CASCADE
  role String(20) default "viewer"
  timestamps
```

**Repository change**:
```
repositories.team_id FK teams.id ON DELETE SET NULL, nullable
  (NULL = personally-owned repo; NOT NULL = team-owned repo)
```

### 4.2 Role resolution (to be decided in PRD)

When user `U` accesses repository `R`:

1. If `R.team_id IS NOT NULL` and `U` is in `TeamMember(team_id=R.team_id)`: base role = `TeamMember.role`
2. If a `ProjectMember(user_id=U.id, repository_id=R.id)` row exists: override role = `ProjectMember.role`
3. If neither: check `U.role == ADMIN`, else deny

**Recommend**: ProjectMember overrides TeamMember (explicit beats inherited). ADMIN global role still bypasses for support ops.

### 4.3 Endpoints

- `POST /api/v1/teams` — create team (any user; they become team ADMIN)
- `GET /api/v1/teams` — list teams visible to user
- `PATCH /api/v1/teams/{id}` — rename, update description (team ADMIN)
- `DELETE /api/v1/teams/{id}` — delete (team ADMIN; cascades TeamMember)
- `GET/POST/PATCH/DELETE /api/v1/teams/{id}/members` — mirrors `/repos/{id}/members` shape
- `PATCH /api/v1/repos/{repo_id}` — accept `team_id` to transfer ownership (current owner must be team ADMIN or global ADMIN)

## 5. What Phase 4 does NOT need to change

- `AuditMiddleware` — already captures `/auth/login`, `/auth/users`, `/webhooks/tokens`. New SSO paths will be auto-captured if they live under `/auth/sso/*` (add an entry to `_RESOURCE_MAP`).
- `retention.py` — unaffected.
- `task_executor` and `dispatch_task` — unaffected.
- Frontend `stores/auth.store.ts` — gains SSO login initiator, but JWT storage and interceptor logic stay the same.
- The `rbs_` API token flow — unaffected.

## 6. Open decisions for the PRD

1. **SAML in Phase 4 or later?** (Windows offline build constraint)
2. **Password + SSO for the same user**: block, auto-link, or admin-mediated link?
3. **ProjectMember vs TeamMember precedence**: explicit override wins vs max-role wins?
4. **Default role on JIT provisioning**: per-provider config? global default? configurable?
5. **`require_role` semantics**: keep global-only, add `require_project_role(repo_id, min_role)` as new dependency?
6. **Team deletion when team owns repos**: cascade? orphan to personal? block until ownership transferred?
7. **Session-level SSO logout / IdP-initiated logout**: Phase 4 or Phase 5?
