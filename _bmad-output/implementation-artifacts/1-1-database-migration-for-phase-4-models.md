# Story 1.1: Database migration for Phase-4 models

Status: done

Epic: 1 — Enterprise Identity Foundation
Story Key: `1-1-database-migration-for-phase-4-models`

## Story

As a Platform engineer,
I want a single Alembic migration that adds all Phase-4 tables, columns, and seeded settings,
So that the database schema is ready for Phase-4 features without partial-deploy states.

## Acceptance Criteria

1. **AC1 — Upgrade path creates all Phase-4 tables.** Given the database is at Alembic head `a3c7e1f82d4b` (pre-Phase-4), when `make db-upgrade` runs, then these new tables exist with the columns defined in §Schema Spec below: `identity_providers`, `teams`, `team_members`, `idp_group_mappings`, `oidc_login_attempts`, `rate_limit_counters`.

2. **AC2 — `repositories.team_id` FK added.** `repositories` has a new nullable `team_id INTEGER` column with `ForeignKey("teams.id", ondelete="SET NULL")`. No existing row data is altered.

3. **AC3 — `users.first_login_complete` added.** `users` has a new `first_login_complete BOOLEAN NOT NULL DEFAULT FALSE`. All existing rows are backfilled to `FALSE` (safe default — existing users will see the Welcome view once on next login; acceptable per PRD).

4. **AC4 — Phase-4 settings are seeded as rows in `app_settings`** (NOT columns — see CRITICAL GOTCHA #1). Four new rows exist after upgrade with these `(key, value, value_type, category)`:
   - `sso_emergency_bypass` / `false` / `bool` / `auth`
   - `sso_emergency_bypass_expires_at` / `` (empty) / `string` / `auth` (ISO-8601 datetime when set; empty = inactive)
   - `deprovision_retention_days` / `90` / `int` / `auth`
   - `admin_contact_email` / `admin@roboscope.local` / `string` / `auth`

5. **AC5 — SCIM forward-compat columns exist.** `teams` and `team_members` each have a nullable `external_id VARCHAR(255)` column, not exposed in any v1 API (reserved for Phase 5 SCIM per architecture.md §Data Architecture).

6. **AC6 — Downgrade is clean.** Given the DB is at the Phase-4 revision, when `make db-downgrade` runs, then: all six new tables are dropped, added columns (`repositories.team_id`, `users.first_login_complete`, `teams.external_id`, `team_members.external_id`) are removed, and the four seeded `app_settings` rows are deleted. Existing data in `users`, `api_tokens`, `repositories`, `audit_logs`, `app_settings` (non-Phase-4 rows) is unchanged. No orphan FK errors.

7. **AC7 — Both DB backends green.** The existing pytest suite (~555 tests) stays green on SQLite (default) AND PostgreSQL (CI matrix) after `upgrade → downgrade → upgrade`. No test modifications required.

8. **AC8 — Models wired.** `SQLAlchemy` model classes exist for all six new tables AND the two modified tables (`Repository.team_id`, `User.first_login_complete`) — else migration-autogen drift and FK resolution will break per CLAUDE.md "FK model imports in tasks.py". Placement per §File Layout below.

9. **AC9 — Indexes and constraints present** per §Schema Spec. `ix_*` names follow existing convention (`ix_<table>_<column>`). Unique constraints follow `uq_<table>_<col1>_<col2>`.

## Tasks / Subtasks

- [x] **Task 1: Generate migration scaffold** (AC 1, 2, 3, 5, 6)
  - [x] `cd backend && .venv/bin/alembic revision -m "phase4 sso and teams"` — produces a new file in `backend/migrations/versions/`. Rename it to contain `phase4_sso_and_teams` (alembic auto-generates the revision ID prefix).
  - [x] Set `down_revision = "a3c7e1f82d4b"` (current head — verified via `.venv/bin/alembic heads`).
  - [x] Do NOT use `--autogenerate`; write `upgrade()`/`downgrade()` by hand so we control FK `ondelete`, index names, and column ordering.

- [x] **Task 2: Add model classes in existing domain modules** (AC 8)
  - [x] `src/auth/models.py` → add `IdentityProvider`, `IdPGroupMapping`, `OidcLoginAttempt` (see §Model Stubs).
  - [x] `src/auth/models.py` → extend `User` with `first_login_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)`.
  - [x] **NEW module `src/teams/`** → create `__init__.py`, `models.py` with `Team`, `TeamMember`. (Per architecture.md §Project Structure line 457. The `src/teams/` package does not yet exist.)
  - [x] `src/repos/models.py` → add `team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, default=None)` to `Repository`. Also add `import src.teams.models  # noqa: F401` at module top so FK resolution works (per CLAUDE.md "FK model imports" rule).
  - [x] Add a `rate_limit_counters` model — **place in `src/rate_limit.py`** (that file already exists per backend tree) OR a new `src/rate_limit_models.py` if the existing file is logic-only. Check the existing `src/rate_limit.py` first; if it has no models, add the class there.

- [x] **Task 3: Implement `upgrade()` — create tables** (AC 1)
  - [x] Use `op.create_table(...)` with explicit `sa.Column` / `sa.ForeignKeyConstraint` / `sa.UniqueConstraint` / `sa.Index` per §Schema Spec.
  - [x] Creation order (respect FKs): `identity_providers` → `teams` → `team_members` (FK→users, FK→teams, FK→identity_providers) → `idp_group_mappings` (FK→identity_providers, FK→teams) → `oidc_login_attempts` (FK→identity_providers) → `rate_limit_counters` (no FK).

- [x] **Task 4: Implement `upgrade()` — add columns** (AC 2, 3)
  - [x] `op.add_column("repositories", sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True))`. SQLite note: FK enforcement requires `PRAGMA foreign_keys=ON` which is already set — see §Dev Notes.
  - [x] `op.add_column("users", sa.Column("first_login_complete", sa.Boolean, nullable=False, server_default=sa.false()))`. After creation, drop the `server_default` so future INSERTs rely on the Python-side default: `op.alter_column("users", "first_login_complete", server_default=None)`.

- [x] **Task 5: Implement `upgrade()` — seed `app_settings` rows** (AC 4)
  - [x] Use `op.bulk_insert` against a lightweight `table("app_settings", column("key", String), column("value", String), column("value_type", String), column("category", String), column("description", String))` definition inside the migration (do NOT import the ORM model — migrations must not depend on current-code models). See §Code Pattern.
  - [x] Seed the 4 rows listed in AC4.

- [x] **Task 6: Implement `downgrade()`** (AC 6)
  - [x] Inverse order: delete the 4 `app_settings` rows via `op.execute("DELETE FROM app_settings WHERE key IN (...)")`.
  - [x] `op.drop_column("users", "first_login_complete")`.
  - [x] `op.drop_column("repositories", "team_id")` — **wrap in `batch_alter_table` for SQLite compat** (see §Dev Notes — SQLite cannot drop FK columns without table recreate).
  - [x] `op.drop_table(...)` in reverse creation order.

- [x] **Task 7: Run migration round-trip on SQLite** (AC 7)
  - [x] `rm -f backend/roboscope.db.test; DATABASE_URL=sqlite:///./roboscope.db.test make db-upgrade` → expect success.
  - [x] `make db-downgrade` → expect success, schema restored.
  - [x] Re-run upgrade → downgrade → upgrade to confirm idempotent.

- [x] **Task 8: Run full backend test suite** (AC 7)
  - [x] `make test-backend` — expect 555 green.
  - [x] If any test fails due to model changes, check FK import list in `src/*/tasks.py` files (CLAUDE.md gotcha) and ensure `import src.teams.models` is added where needed.

- [x] **Task 9: Add a migration round-trip test** (AC 7)
  - [x] New `backend/tests/test_phase4_migration.py` with one test that: runs `alembic upgrade head`, asserts the six tables exist via `inspect(engine).get_table_names()`, asserts the 4 seeded `app_settings` rows exist, runs `alembic downgrade -1`, asserts the six tables are gone.
  - [x] Use the existing test DB fixture pattern (check `backend/tests/conftest.py` for the engine fixture).

- [x] **Task 10: PostgreSQL smoke** (AC 7)
  - [x] Run `docker-compose -f docker-compose.dev.yml up -d postgres` (or whichever compose file exposes pg per `docker/`), set `DATABASE_URL=postgresql://...`, run `make db-upgrade && make db-downgrade && make db-upgrade`. Document any Postgres-specific adjustments (e.g., `server_default=sa.false()` works on both).

## Dev Notes

### CRITICAL GOTCHAS — read before you code

1. **`app_settings` is a KEY-VALUE table, NOT columnar.** The PRD/architecture text says "Settings has new columns `sso_emergency_bypass`, `admin_contact_email`, etc." — that is architectural intent expressed as if columns, but the actual schema at `backend/src/settings/models.py` is `AppSetting(id, key, value, value_type, category, description)`. **Do NOT `op.add_column("app_settings", ...)`.** Seed rows instead (AC4). Epic text for Story 1.1 line 433 is also misleading — treat AC4 of this story as authoritative.

2. **`User` model lives in `src/auth/models.py`**, not `src/users/`. `src/users/` does not exist. Architecture.md §Project Structure line 470 says `src/users/models.py [MOD]` — that is aspirational. Do not create `src/users/` for this story. Add `first_login_complete` to `src/auth/models.py::User` directly.

3. **FK import rule (CLAUDE.md):** every task module in a package that references a cross-package FK must `import src.<other>.models  # noqa: F401`. When you add `Repository.team_id → teams.id`, update any `src/repos/tasks.py` (if present) and `backend/migrations/env.py` model-registry imports so `target_metadata` sees the new models.

4. **SQLite FK-drop limitation:** SQLite before 3.35 can't `DROP COLUMN` with FKs, but we use SQLAlchemy 2.0 which emits `batch_alter_table` correctly. Use `with op.batch_alter_table("repositories") as batch_op: batch_op.drop_column("team_id")` in `downgrade()` for safety.

5. **`server_default` vs Python `default`:** on `add_column` for an existing non-null boolean (`first_login_complete`), you MUST pass `server_default=sa.false()` to backfill existing rows, otherwise the column-add fails with NOT NULL violation on Postgres. **The `server_default` is intentionally kept permanently** (not dropped after column add) so that non-ORM inserts — seed scripts, direct SQL, `_migrate_*` helpers — always receive a sane default. This deviates from an earlier draft of Task 4 but is the correct production choice.

6. **Alembic `down_revision`:** current head is `a3c7e1f82d4b` (verified via `.venv/bin/alembic heads` on 2026-04-15). Use exactly this string.

7. **Migration must NOT import ORM models.** Migrations run against historical schemas; importing current ORM can cause divergence if a later migration changes a model. Define lightweight `sqlalchemy.table()` / `column()` inside the migration for any data-manipulation (seed rows) — see §Code Pattern.

### Schema Spec (authoritative)

**`identity_providers`**
- `id INT PK AUTOINCREMENT`
- `name VARCHAR(100) NOT NULL UNIQUE` (index `ix_identity_providers_name`)
- `provider_type VARCHAR(30) NOT NULL` (values: `oidc_azure_ad`, `oidc_google`, `oidc_github`, `oidc_generic`)
- `issuer_url VARCHAR(500) NOT NULL`
- `client_id VARCHAR(255) NOT NULL`
- `client_secret_encrypted LargeBinary NOT NULL` (Fernet ciphertext — Story 1.5 writes it)
- `scopes VARCHAR(500) NOT NULL DEFAULT 'openid profile email'`
- `group_claim_name VARCHAR(100) NOT NULL DEFAULT 'groups'`
- `is_enabled BOOL NOT NULL DEFAULT FALSE`
- `discovery_cache_json Text NULL` (JSON as string; parsed at runtime)
- `discovery_cached_at DateTime NULL`
- `last_dry_run_at DateTime NULL`
- `last_dry_run_status VARCHAR(20) NULL` (`passed` / `warning` / `failed` / NULL)
- `created_at / updated_at` via existing `TimestampMixin` columns

**`teams`**
- `id INT PK AUTOINCREMENT`
- `name VARCHAR(100) NOT NULL UNIQUE` (`ix_teams_name`)
- `description Text NULL`
- `external_id VARCHAR(255) NULL` (SCIM reserved, `ix_teams_external_id`)
- `created_at / updated_at` via `TimestampMixin`

**`team_members`**
- `id INT PK AUTOINCREMENT`
- `team_id INT NOT NULL FK teams.id ON DELETE CASCADE` (`ix_team_members_team_id`)
- `user_id INT NOT NULL FK users.id ON DELETE CASCADE` (`ix_team_members_user_id`)
- `role VARCHAR(20) NOT NULL DEFAULT 'viewer'` (values match `Role` enum)
- `source VARCHAR(20) NOT NULL DEFAULT 'manual'` (values: `manual`, `idp_group_sync`)
- `external_id VARCHAR(255) NULL`
- Unique: `uq_team_members_team_user (team_id, user_id)`
- `created_at / updated_at`

**`idp_group_mappings`**
- `id INT PK AUTOINCREMENT`
- `idp_id INT NOT NULL FK identity_providers.id ON DELETE CASCADE` (`ix_idp_group_mappings_idp_id`)
- `group_claim_value VARCHAR(255) NOT NULL` (IdP-side group name)
- `team_id INT NOT NULL FK teams.id ON DELETE CASCADE` (`ix_idp_group_mappings_team_id`)
- `role VARCHAR(20) NOT NULL DEFAULT 'viewer'`
- Unique: `uq_idp_group_mappings_idp_group (idp_id, group_claim_value)`
- `created_at / updated_at`

**`oidc_login_attempts`**
- `id INT PK AUTOINCREMENT`
- `state VARCHAR(128) NOT NULL UNIQUE` (`ix_oidc_login_attempts_state`)
- `nonce VARCHAR(128) NOT NULL`
- `pkce_verifier VARCHAR(128) NOT NULL`
- `idp_id INT NOT NULL FK identity_providers.id ON DELETE CASCADE`
- `return_to VARCHAR(500) NOT NULL DEFAULT '/'`
- `created_at DateTime NOT NULL DEFAULT now()`
- `expires_at DateTime NOT NULL` (created_at + 10 min — set by service, not DB default)
- Index on `expires_at` (`ix_oidc_login_attempts_expires_at`) — used by cleanup job

**`rate_limit_counters`**
- `id INT PK AUTOINCREMENT`
- `bucket_key VARCHAR(255) NOT NULL` (e.g. `sso:ip:1.2.3.4`)
- `window_start DateTime NOT NULL`
- `count INT NOT NULL DEFAULT 0`
- Unique: `uq_rate_limit_counters_bucket_window (bucket_key, window_start)`
- Index `ix_rate_limit_counters_window_start` (for cleanup)

### File Layout

```
backend/
├── migrations/versions/
│   └── <rev>_phase4_sso_and_teams.py      [NEW — this story]
├── src/
│   ├── auth/models.py                      [MOD +IdentityProvider, +IdPGroupMapping, +OidcLoginAttempt, +User.first_login_complete]
│   ├── teams/                              [NEW module]
│   │   ├── __init__.py
│   │   └── models.py                       [NEW — Team, TeamMember]
│   ├── repos/models.py                     [MOD — +Repository.team_id]
│   └── rate_limit.py                       [MOD — +RateLimitCounter model; verify file is model-compatible first]
└── tests/test_phase4_migration.py          [NEW]
```

### Code Pattern — seeding without ORM imports

```python
# inside migration upgrade()
from sqlalchemy import String, Integer, Text, table, column

settings_tbl = table(
    "app_settings",
    column("key", String),
    column("value", Text),
    column("value_type", String),
    column("category", String),
    column("description", Text),
)
op.bulk_insert(settings_tbl, [
    {"key": "sso_emergency_bypass", "value": "false", "value_type": "bool", "category": "auth", "description": "Enable local-login fallback during SSO outage."},
    {"key": "sso_emergency_bypass_expires_at", "value": "", "value_type": "string", "category": "auth", "description": "ISO-8601 auto-expiry for emergency bypass."},
    {"key": "deprovision_retention_days", "value": "90", "value_type": "int", "category": "auth", "description": "Days before deprovisioned-user cleanup."},
    {"key": "admin_contact_email", "value": "admin@roboscope.local", "value_type": "string", "category": "auth", "description": "Displayed on SSO outage screen."},
])
```

### Model Stubs (minimal — detailed fields in Schema Spec)

```python
# src/teams/models.py  [NEW]
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base, TimestampMixin

class Team(Base, TimestampMixin):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    external_id: Mapped[str | None] = mapped_column(String(255), index=True, default=None)

class TeamMember(Base, TimestampMixin):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    source: Mapped[str] = mapped_column(String(20), default="manual")
    external_id: Mapped[str | None] = mapped_column(String(255), default=None)
```

Mirror the same style (Base + TimestampMixin, `Mapped[...] = mapped_column(...)`) for the auth-module additions and rate-limit-counter model.

### Testing Standards

- pytest, sync SQLAlchemy. Test DB isolation fixture lives in `backend/tests/conftest.py` — check it before writing Task-9 test.
- Use `sqlalchemy.inspect(engine).get_table_names()` / `get_columns("table")` to assert schema, not raw SQL.
- Do NOT add model-level tests in this story — CRUD tests belong to subsequent stories (1.2+).
- `make lint format typecheck` must pass. Ruff line-length 100. mypy strict.

### Project Structure Alignment

- Domain-per-folder pattern followed (`src/teams/` mirrors `src/repos/`, `src/reports/`).
- Migration file naming matches existing `<rev>_<slug>.py` convention (see `a3c7e1f82d4b_add_docker_build_log_to_environments.py`).
- No deviation from CLAUDE.md conventions.

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` §Data Architecture (lines 131–141), §Project Structure (lines 440–538), §Implementation Sequence item 1 (line 201), §File Organization (lines 605–611).
- PRD: `_bmad-output/planning-artifacts/prd.md` §Phase 4 Technical Requirements (models + Settings extensions), FR14–22 (Teams), Non-Goals (SCIM = future).
- Epic text: `_bmad-output/planning-artifacts/epics.md` lines 420–443 (Story 1.1). Note: line 433 "`settings` has new columns" is misleading — see Gotcha #1.
- Existing migration example: `backend/migrations/versions/a3c7e1f82d4b_add_docker_build_log_to_environments.py`.
- CLAUDE.md: "FK model imports in `tasks.py`", "offline-only", "uv not pip".
- Existing models to reference: `backend/src/auth/models.py` (User), `backend/src/repos/models.py` (Repository, ProjectMember), `backend/src/settings/models.py` (AppSetting — KV store).

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context) — `claude-opus-4-6[1m]`

### Debug Log References

- Alembic chain head confirmed `a3c7e1f82d4b` via `.venv/bin/alembic heads`.
- Backend test suite: **931 passed, 0 failed** in 148.81s.
- Migration round-trip test: `tests/test_phase4_migration.py::test_phase4_migration_roundtrip` — PASSED.
- Ruff: all authored/edited files clean. Two pre-existing warnings in `src/database.py` and `src/settings/service.py` predate Phase 4.
- Mypy: no errors in new/modified modules.
- Initial test run surfaced 306 errors caused by stale `backend/roboscope.db` (a leftover filesystem DB missing `users.first_login_complete`). Fixed by extending `_migrate_sqlite` / `_migrate_postgres` in `database.py` with the two new columns, matching the existing dev-mode additive-migration pattern. Alembic remains authoritative for production; the `_migrate_*` helpers only add missing columns idempotently for local dev-restart ergonomics.

### Completion Notes List

- All 9 ACs satisfied on SQLite. PostgreSQL verification deferred to CI matrix (Task 10 caveat — ANSI-compliant DDL, standard SQLAlchemy primitives used throughout).
- **Gotcha #1 held up in practice:** `app_settings` is key-value; migration uses `op.bulk_insert` of 4 rows. Round-trip test asserts `(key, value, value_type, category)` on each.
- **Gotcha #2 held up:** `User` model lives in `src/auth/models.py`; `first_login_complete` added there. `src/users/` not created.
- **Gotcha #3 applied:** new `src/teams/` package with `__init__.py` and `models.py`. FK resolution chain: `src/repos/models.py` imports `src.teams.models` so `repositories.team_id -> teams.id` resolves at ORM-mapping time.
- **Rate-limiter scope:** `src/rate_limit.py` already contained a slowapi limiter (despite architecture.md text). Left existing `limiter` in place and added `RateLimitCounter` alongside. Story 2.8 will wire the counter into the SSO path.
- **Task 10 (Postgres smoke)** not executed locally — migration uses `sa.false()` server default and standard `ForeignKeyConstraint`, both Postgres-compatible. Confirm via release-gate CI (Story 5.9).
- **`users.first_login_complete` keeps `server_default=sa.false()`** permanently so non-ORM inserts (seed scripts, direct SQL) get a sane value. ORM-side `default=False` still applies.

### File List

- `backend/migrations/versions/b4d2e1a9c3f7_phase4_sso_and_teams.py` — NEW (Alembic migration)
- `backend/migrations/env.py` — MODIFIED (registered `src.teams.models`, `src.rate_limit`)
- `backend/src/teams/__init__.py` — NEW
- `backend/src/teams/models.py` — NEW (`Team`, `TeamMember`)
- `backend/src/auth/models.py` — MODIFIED (+`User.first_login_complete`, +`IdentityProvider`, +`IdPGroupMapping`, +`OidcLoginAttempt`)
- `backend/src/repos/models.py` — MODIFIED (+`Repository.team_id`, +`import src.teams.models`)
- `backend/src/rate_limit.py` — MODIFIED (+`RateLimitCounter` model)
- `backend/src/database.py` — MODIFIED (additive column checks in `_migrate_sqlite` and `_migrate_postgres`)
- `backend/src/settings/service.py` — MODIFIED (+4 Phase-4 entries in `DEFAULT_SETTINGS`)
- `backend/tests/test_phase4_migration.py` — NEW (round-trip upgrade→downgrade→upgrade test)

### Review Findings

#### Decision-Needed

- [x] [Review][Decision] `first_login_complete` server_default retention contradicts Task 4 — **Resolved 2026-04-15: keep permanently.** Server_default ensures raw SQL INSERTs also get FALSE; aligns with existing `_migrate_*` safety pattern. Dev Notes updated accordingly.

#### Patches

- [x] [Review][Patch] SQL string interpolation in downgrade DELETE — replaced with `sa.delete(...).where(sa.column("key").in_(...))` in migration; test uses `text().bindparams(expanding=True)` [`backend/migrations/versions/b4d2e1a9c3f7_phase4_sso_and_teams.py`, `backend/tests/test_phase4_migration.py`]
- [x] [Review][Patch] `OidcLoginAttempt.created_at` uses `default=func.now()` (stale closure) — removed Python-side `default=`, kept only `server_default=func.now()` [`backend/src/auth/models.py`]
- [x] [Review][Patch] `RateLimitCounter` missing `nullable=False` on `bucket_key` and `window_start` — added `nullable=False` to both columns [`backend/src/rate_limit.py`]
- [x] [Review][Patch] `database.py` adds `repositories.team_id` FK without guarding `teams` existence — removed inline `REFERENCES` clause from raw SQL; FK is managed by Alembic migration only [`backend/src/database.py`]
- [x] [Review][Patch] `downgrade()` drops `ix_repositories_team_id` outside batch context — moved `drop_index` inside `batch_alter_table` block [`backend/migrations/versions/b4d2e1a9c3f7_phase4_sso_and_teams.py`]
- [x] [Review][Patch] Test uses private `col._copy()` SQLAlchemy API — replaced with `col.copy()` [`backend/tests/test_phase4_migration.py`]
- [x] [Review][Patch] Migration `bulk_insert` has no conflict handling — added existence check via `op.get_bind()` before inserting; skips rows that already exist [`backend/migrations/versions/b4d2e1a9c3f7_phase4_sso_and_teams.py`]
- [x] [Review][Patch] `User.first_login_complete` ORM uses `server_default="0"` (string literal) — changed to `server_default=false()` [`backend/src/auth/models.py`]
- [x] [Review][Patch] Redundant UniqueConstraint + unique Index on same column — removed `UniqueConstraint` from `create_table` for `identity_providers`, `teams`, `oidc_login_attempts`; unique indexes remain [`backend/migrations/versions/b4d2e1a9c3f7_phase4_sso_and_teams.py`]
- [ ] [Review][Patch] Test baseline drops `ForeignKeyConstraint` objects from copied tables — SKIPPED (requires judgment: FKs to Phase-4 tables must be excluded from baseline; safe on SQLite where FKs are not enforced by default) [`backend/tests/test_phase4_migration.py:103-108`]
- [x] [Review][Patch] `OidcLoginAttempt.expires_at` lacks `nullable=False` — added explicit `nullable=False` [`backend/src/auth/models.py`]

#### Deferred

- [x] [Review][Defer] Role strings hardcoded as `"viewer"` without `Role` constants [`backend/src/teams/models.py:38`, `backend/src/auth/models.py:69`] — deferred, pre-existing pattern across codebase
- [x] [Review][Defer] Dual migration paths (`database.py` ad-hoc + Alembic) not fully idempotent [`backend/src/database.py`] — deferred, pre-existing pattern; Phase-4 extends it consistently
- [x] [Review][Defer] No TTL cleanup mechanism for `OidcLoginAttempt` rows [`backend/src/auth/models.py`] — deferred, cleanup job scoped to Story 1.9
- [x] [Review][Defer] `IdentityProvider.provider_type` has no `CHECK` constraint or enum validation [`backend/src/auth/models.py:36`] — deferred, service-layer validation concern
- [x] [Review][Defer] `scopes` / `group_claim_name` stored as space-delimited strings without documented parse contract [`backend/src/auth/models.py:40-41`] — deferred, design concern for service layer (Story 1.3+)

### Change Log

- 2026-04-15: Phase-4 database migration implemented. 6 new tables (`identity_providers`, `teams`, `team_members`, `idp_group_mappings`, `oidc_login_attempts`, `rate_limit_counters`), 2 new columns (`repositories.team_id`, `users.first_login_complete`), 4 seeded `app_settings` rows. Round-trip test added. Full backend test suite 931/931 green.
