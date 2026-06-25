# Epic GOV — Architecture

**Status**: Planning → ready for implementation
**Date**: 2026-06-18
**Architect**: Winston
**Parent**: [gov-prd.md](./gov-prd.md)

## Guiding principle

Boring technology. We already have a typed key-value `app_settings` table (`settings/service.py::get_setting_value`) and an ordered-role `require_role(min_role)` dependency. The whole epic is a thin resolver + two FastAPI dependencies + one read endpoint + one frontend composable. No new framework, no new table, no migration.

## 1. Flag registry & resolver

New module `backend/src/governance/flags.py`:

```
FEATURE_FLAGS: dict[str, bool] = {
    "packageManagement": True,   # GOV-2: install/uninstall/upgrade/build/rfbrowser-init
}
# Per-op role floor (GOV-4); resolved separately, only consulted when the area is ON.
PACKAGE_OP_ROLE_DEFAULT = Role.EDITOR  # matches today's behavior
```

**Resolution precedence (per flag): ENV > DB > default.**
- ENV: `ROBOSCOPE_FEATURE_<UPPER_SNAKE>` (e.g. `packageManagement` → `ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT`). Parsed as bool (`1/true/yes/on` → true, `0/false/no/off` → false; anything else ignored). Read once at process start into a frozen dict.
- DB: `app_settings` row, `category="features"`, `key=<flag>`, `value_type="bool"`. Read via `get_setting_value`.
- default: `FEATURE_FLAGS[flag]` (ON).

```
def resolve_flag(db, key) -> ResolvedFlag       # {value: bool, locked: bool}
def resolve_all(db) -> dict[str, ResolvedFlag]
```
`locked=True` when the ENV override is set (the UI renders it as "managed by your administrator", non-editable). DB-or-default → `locked=False`.

**Caching:** none in v1. `app_settings` is tiny and reads are indexed; a per-request lookup on a mutating env call is negligible. (If a hot path ever needs it, add a TTL cache invalidated in `update_settings` — noted, not built.)

**Seeding:** extend `seed_default_settings` with the `features` category rows so they appear in the Settings UI as editable toggles (value defaults to the registry default). Idempotent — existing installs get the row on next boot, value ON, behavior unchanged.

## 2. Backend enforcement dependency

New `backend/src/governance/dependencies.py`:

```
def require_feature(flag: str):
    def dep(db = Depends(get_db)):
        if not resolve_flag(db, flag).value:
            raise HTTPException(403, detail="feature_disabled:<flag>")
    return dep

def require_package_op(op: str):
    """Compose flag gate + configurable role floor for a package operation."""
    def dep(db = Depends(get_db), user = Depends(get_current_user)) -> User:
        if not resolve_flag(db, "packageManagement").value:
            raise HTTPException(403, detail="feature_disabled:packageManagement")   # absolute — even ADMIN
        floor = resolve_package_op_role(db, op)   # settings key features.packageManagement.role.<op>, default EDITOR
        if ROLE_RANK[user.role] < ROLE_RANK[floor]:
            raise HTTPException(403, detail="insufficient_role")
        return user
    return dep
```

**Wiring (GOV-2 + GOV-4):** on the mutating env endpoints (`install_package` L529, `upgrade_package` L572, `retry_package_install` L612, `uninstall_package` L694, `docker_build` L264, `rfbrowser-init` L654), replace `Depends(require_role(Role.EDITOR))` with `Depends(require_package_op("<op>"))`. Read endpoints (list/installed/keywords/dockerfile/search/popular) are untouched → stay 200 in locked mode (FR-3). `create`/`clone`/`delete` **environment** are governance-neutral for v1 (the customer concern is *package* mutation on a managed env) — left on `require_role` as today; revisit if needed.

**Order matters:** flag check first (absolute policy), role floor second (permission). A locked deployment 403s before any role consideration.

**Audit (FR-6):** the existing audit middleware already logs every POST/PUT/PATCH/DELETE with user/IP and the response — a 403'd mutation is captured. We add the `feature_disabled` / `insufficient_role` detail string so blocked attempts are greppable; no new audit pipeline.

## 3. Read contract — `GET /config/features`

New tiny router `backend/src/governance/router.py`, mounted on `api_router` → `/api/v1/config/features`:

```
GET /config/features   (auth: any logged-in user)
→ { "flags":  { "packageManagement": true },
    "locked": { "packageManagement": false } }   # locked=true ⇒ set via ENV, UI shows non-editable
```

Admin **editing** flags needs no new endpoint — flags are `app_settings` rows, edited through the existing Settings update path (PUT). GOV-1 only adds the seed rows + this read endpoint + the resolver.

## 4. Frontend — `useFeatureFlags()` composable

`frontend/src/composables/useFeatureFlags.ts` — singleton, mirrors `useUserSettings`/`useBypassStatus` pattern:

- **MUST early-return when `localStorage.getItem('access_token')` is null** (CLAUDE.md redirect-loop gotcha) — it's consumed by global layout.
- Fetches `/config/features` once, caches; exposes `isEnabled(flag): boolean` (default true while loading, so nothing flickers hidden) and `isLocked(flag): boolean`.
- Refetch hook after login + after an admin saves settings.

**Consumption (GOV-2 + GOV-3):** `EnvironmentsView` / package components gate every mutating control (`+ Install`, uninstall ✕, upgrade, Docker build, rfbrowser-init) on `isEnabled('packageManagement')`. When disabled: controls are hidden, and a localized banner renders — "Package management is managed by your administrator" (EN/DE/FR/ES). The package list, versions, and Docker image stay visible (read-only). **GOV-3 is this locked-state UX, not a second flag** — read-only environments == `packageManagement` off. (Simplification vs. PRD's separate sub-mode; one flag is cleaner and covers the requirement.)

## 5. File layout

```
backend/src/governance/
  __init__.py
  flags.py          # registry + resolver (env/db/default)
  dependencies.py   # require_feature, require_package_op
  router.py         # GET /config/features
  schemas.py        # FeaturesResponse
backend/tests/governance/
  test_flags.py             # precedence unit tests
  test_package_lockdown.py  # every mutating env endpoint → 403 when off; role floor
frontend/src/composables/useFeatureFlags.ts
frontend/src/tests/composables/useFeatureFlags.spec.ts
```

## 6. Test strategy (feeds the E2E story)

- **Unit (backend):** precedence (env beats db beats default; bool parsing; locked flag); `require_package_op` 403 paths (flag off → 403 even for ADMIN; role floor below → 403).
- **Endpoint:** parametrized test hitting every mutating env endpoint with flag OFF → 403, and a read endpoint → 200.
- **Unit (frontend):** composable token-guard (no fetch without token), isEnabled/isLocked.
- **E2E (real UI, Playwright):** boot backend with `ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT=false`, log in, open Environments → assert no install/uninstall/build controls, banner visible, package list still rendered; assert a direct API mutation returns 403. Second run with flag unset → controls present (default unchanged).

## 7. Risks / decisions

- **Env read timing:** env flags frozen at process start — changing the env var requires a restart (correct for a deployment-level lock; documented).
- **`create/clone/delete environment` left ungoverned in v1** — scoped to package mutation per the customer's actual concern; trivially extendable by adding `require_feature` later.
- **No new migration** — `app_settings` rows are seeded, not schema'd.

## 8. Handoff
→ **Implementation (Amelia):** GOV-1 (flags module + resolver + `/config/features` + seed + `useFeatureFlags`), then GOV-2 (wire `require_package_op` + UI gating + banner i18n), GOV-3 (locked-state UX polish), GOV-4 (role-floor settings + resolution). Then code review + full UI E2E.
