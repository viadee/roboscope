# Story EXEC.10: Curated & org-extensible execution modifiers + admin code-loading levers

Status: done

Epic: EXEC — RF Execution Configuration
Story Key: `exec-10-curated-org-modifiers-and-code-levers`
Depends on: EXEC.1 (resolver seam), EXEC.2 (advanced_config + flags), EXEC.3 (advanced UI), EXEC.7 (prerun_modifier channel)

## Story

As an organization deploying RoboScope (and as an ADMIN / power user within it),
I want curated, org-extensible, audited channels for execution modifiers (pre- and
post-execution) plus repo-confined code-loading levers,
so that we can wire in our own vetted modifiers — e.g. to update our test-management system or
emit custom reports after a run — and use safe advanced levers, without anyone being able to
smuggle arbitrary code through the generic advanced-args field.

## Hard invariant (non-negotiable)

`resolver.validate_advanced_args` stays **absolute and role-independent** — every lever here is a
**separate typed channel on `ResolvedRunSpec`**, emitted through the resolver like the existing
`prerun_modifiers`, NEVER a relaxation or role-conditional branch of the Z3 deny-list. No
"if ADMIN, allow anything" path is introduced. (Carried from NFR1 + the 2026-06-24 code review.)

## Modifier trust tiers (the curation model)

A single **modifier registry** is the source of truth. A registry entry is
`{key, class_path, kind: prerun|prerebot, label, args_schema, tier, i18n_key}`. The gate routes by
registry membership, never by free-typed class path:

- **Tier A — Vendor-curated:** RoboScope ships the modifier class in-repo (`quarantine_listener.py`
  precedent — vetted, offline). Selectable by EDITOR.
- **Tier B — Org/deployment-registered:** the operator registers their own modifier class(es) via
  backend configuration, NOT the UI — trust established at deploy time. Two offline-friendly
  mechanisms: (1) the `roboscope.modifiers` Python entry-point group (self-registering installed
  package), (2) a `ROBOSCOPE_MODIFIERS_CONFIG` YAML/TOML file. Usable by EDITOR once registered.
  Org modifiers are NOT repo-confined (operator-installed packages, deliberately trusted).
- **Tier C — Runtime user-code:** an end user names an arbitrary class path at run time → ADMIN-only
  `executionPreRunModifierUserCode` flag + explicit consent. Escape hatch, never the default.

## Acceptance Criteria

1. **AC1 — Registry + Tier-A vendor modifiers.** `src/execution/modifiers/` exposes a registry of
   `ModifierEntry` records and ships at least one Tier-A vendor modifier (e.g. a tag-stamping
   `prerun` modifier) so the picker is non-empty. `get_available_modifiers()` returns the entries a
   given user/role may use. Pinned by a registry test.
2. **AC2 — Tier-B org registration (backend config, no UI).** The registry loads org entries at
   startup from (a) the `roboscope.modifiers` entry-point group and (b) the
   `ROBOSCOPE_MODIFIERS_CONFIG` file. Each entry is validated (importable; correct RF modifier base
   class / signature). A bad/un-importable entry is logged and skipped — never a boot failure.
   Org entries become EDITOR-usable curated picker entries. Pinned by a loader test (both
   mechanisms + bad-entry skip).
3. **AC3 — Curated vs user-code routing.** `gate_advanced_execution` treats a modifier reference
   that IS a registry key as curated (Tier A/B → `executionAdvancedArgs` + EDITOR) and one that is
   NOT (a free class path) as Tier-C user-code (`executionPreRunModifierUserCode` + ADMIN +
   consent). Pinned by gate tests.
4. **AC4 — prerun + prerebot channels.** `ResolvedRunSpec` carries `prerun_modifiers` and new
   `prerebot_modifiers`; `robot_flag_args` emits `--prerunmodifier` (running model, before exec)
   and `--prerebotmodifier` (result model, after exec — the "update reports / TMS" hook). Both are
   typed channels that bypass the Z3 deny-list; never the freeform field. Pinned in resolver tests.
5. **AC5 — Repo-confined `--pythonpath`.** New default-OFF ADMIN-only `executionPythonPath` flag.
   The resolver emits validated, **repo-confined** paths as `--pythonpath` (reuse `_safe_resolve`;
   a path escaping the repo tree raises `AdvancedArgError` → 422). Own typed channel, never read
   from the Z3 field.
6. **AC6 — Repo-confined `--variablefile`.** New default-OFF ADMIN-only `executionVariableFile`
   flag. Resolver emits a repo-confined variable-file path as `--variablefile`, same
   path-confinement + explicit arbitrary-code consent.
7. **AC7 — Audit (NFR4).** Any run using these levers (allowed or blocked) audits the resolved argv
   incl. modifier class paths + tier; block path writes its own `AuditLog` + commits before raising.
   Pinned in the advanced-run audit test.
8. **AC8 — Runner parity + flags-off.** `test_runner_parity` covers the new channels; each new flag
   resolves OFF by default (`test_exec_flags_default_off`).
9. **AC9 — Docker FLAKY-3.** On docker, levers/modifiers that cannot apply in-container (e.g. an org
   modifier installed only in the backend venv) are disabled/clearly warned, mirroring the existing
   listener-parity handling.
10. **AC10 — i18n.** EN/DE/FR/ES (+ ZH overlay) entries under `execution.advanced.*` (Gate 8 green).
11. **AC11 — Application documentation.** A thorough description lands in the **in-app docs**
    (`frontend/src/docs/content/{en,de,fr,es}.ts`), as a dedicated subsection under `execution`
    (all 4 locales; `de.ts` keeps its `execution-` id prefix). Covers: the three trust tiers; the
    registry shape; both org-registration mechanisms with a worked `prerebot`→TMS example; the
    pre- vs post-execution distinction; the `--pythonpath`/`--variablefile` levers; and the explicit
    statement that these are curated channels, NOT a Z3 deny-list override.

## Tasks / Subtasks

- [x] **T1 — Modifier registry + Tier-A vendor modifier** (AC1)
  - [ ] `src/execution/modifiers/__init__.py` + `registry.py`: `ModifierEntry` + registry singleton
  - [ ] `src/execution/modifiers/builtin.py`: a Tier-A `prerun` modifier (tag-stamp) as a real RF SuiteVisitor
  - [ ] `get_available_modifiers(kind=None)` accessor
- [x] **T2 — Tier-B loader (entry-point + config file)** (AC2)
  - [ ] entry-point discovery (`importlib.metadata.entry_points(group="roboscope.modifiers")`)
  - [ ] `ROBOSCOPE_MODIFIERS_CONFIG` YAML/TOML loader
  - [ ] validate (importable + base-class) → log+skip bad entries, never crash boot
- [x] **T3 — Resolver channels** (AC4, AC5, AC6)
  - [ ] add `prerebot_modifiers`, `python_paths`, `variable_files` to `ResolvedRunSpec`
  - [ ] `robot_flag_args` emits `--prerebotmodifier` / `--pythonpath` / `--variablefile`
  - [ ] `_confine_to_repo(path, repo_root)` helper → `AdvancedArgError` on escape
  - [ ] `resolve_run_spec(...)` accepts + validates the new params
- [x] **T4 — Flags** (AC5, AC6, AC8): register `executionPythonPath`, `executionVariableFile` (False) in `governance/flags.py`
- [x] **T5 — Gate routing** (AC3, AC7): `gate_advanced_execution` — registry-key→curated/EDITOR vs free-path→user-code/ADMIN; pythonpath/variablefile→ADMIN flag + path-confine; audit incl. tier
- [x] **T6 — tasks.py threading**: resolve registry keys→class paths; thread prerebot/pythonpath/variablefile into `resolve_run_spec` + runners
- [x] **T7 — API**: `GET /execution/modifiers` returns the curated registry entries for the picker
- [x] **T8 — Backend tests** (AC1-AC8): resolver (prerebot + confine reject), flags-off, audit (tier), parity, registry-loader (entry-point + config + bad-skip), gate routing; full exec/gov/explorer sweep green
- [x] **T9 — Frontend** (AC10): `AdvancedRunConfig.vue` pickers (prerun/prerebot by key) + consent + pythonpath/variablefile inputs, flag-gated; api client + types; i18n EN/DE/FR/ES/ZH; vue-tsc + unit + i18n parity green
- [x] **T10 — Docker guard** (AC9): disable/warn modifiers+levers on docker per FLAKY-3
- [x] **T11 — In-app docs** (AC11): extend `execution` doc subsection in all 4 locales; Gate 8 green
- [x] **T12 — bmad-code-review + fixes**, then mark story `done` + sprint-status sync

## Out of scope / explicitly deferred

`--argumentfile` (strictly worse than the typed channels); custom `--listener` support (split into
EXEC.11, which extends this registry with a `listener` kind); relaxing the Z3 deny-list in any form.

## Dev notes (anchors)

`execution/resolver.py` (new typed channels + `robot_flag_args`; deny-list untouched), NEW
`execution/modifiers/` (registry + Tier-A vendor classes + entry-point/config-file loader),
`governance/flags.py` (new flags, `False`), `governance/dependencies.py::gate_advanced_execution`
(tier routing + consent + audit), `execution/tasks.py` (thread channels like `prerun_modifiers`),
`execution/router.py` (`GET /execution/modifiers`),
`components/execution/AdvancedRunConfig.vue` (pickers + consent, flag-gated via `useFeatureFlags`).

## Dev Agent Record

### Completion Notes

- T1–T11 implemented; T12 (code-review) in progress.
- Registry (`src/execution/modifiers/`): `ModifierEntry` + vendor `TagStamper` (prerun) + Tier-B
  loaders (entry-point group `roboscope.modifiers` + `ROBOSCOPE_MODIFIERS_CONFIG` JSON/TOML/YAML),
  bad-entry-skip, vendor-wins-on-collision. Vendor + org both referenced by module path (the
  quarantine-listener precedent) so they import in the run venv.
- Resolver: `prerebot_modifiers` / `python_paths` / `variable_files` typed channels +
  `_confine_to_repo` (repo-confinement → `AdvancedArgError`/422). Deny-list untouched.
- Gate (`gate_advanced_execution`): registry-membership routing (curated A/B → EDITOR; non-curated
  → user-code ADMIN + `executionPreRunModifierUserCode`); `executionPythonPath` /
  `executionVariableFile` (ADMIN, default-OFF); 403 fail-fast before 422; structured audit.
- Runners + tasks threaded; docker warns (FLAKY-3). `GET /execution/modifiers` for the picker.
- Frontend: `AdvancedRunConfig.vue` modifier pickers (prerun/prerebot, by registry key + args
  schema) + repo-confined pythonpath/variablefile inputs behind explicit consent; flag-gated.
  i18n EN/DE/FR/ES/ZH; in-app docs subsection `execution-modifiers` ×4 locales.
- Tests: 64 targeted green (registry loader, resolver prerebot+confine, gate routing,
  flags-off, parity) + 3 frontend component tests; vue-tsc + Gate-8 + i18n parity green.

## File List

- backend/src/execution/modifiers/__init__.py (NEW)
- backend/src/execution/modifiers/registry.py (NEW)
- backend/src/execution/modifiers/builtin.py (NEW)
- backend/src/execution/resolver.py (MOD)
- backend/src/governance/flags.py (MOD)
- backend/src/governance/dependencies.py (MOD)
- backend/src/execution/tasks.py (MOD)
- backend/src/execution/router.py (MOD)
- backend/src/execution/runners/{base,subprocess_runner,docker_runner}.py (MOD)
- backend/tests/execution/test_modifier_registry.py (NEW)
- backend/tests/execution/{test_resolver_advanced,test_advanced_run_audit,test_runner_parity,test_exec_flags_default_off}.py (MOD)
- frontend/src/api/execution.api.ts (MOD)
- frontend/src/components/execution/AdvancedRunConfig.vue (MOD)
- frontend/src/views/ExecutionView.vue (MOD)
- frontend/src/i18n/locales/{en,de,fr,es,zh}.ts (MOD)
- frontend/src/docs/content/{en,de,fr,es}.ts (MOD)
- frontend/src/tests/components/AdvancedRunConfig.spec.ts (NEW)

## Change Log

- 2026-06-24: EXEC.10 implemented (registry + 3 trust tiers + pre/prerebot + repo-confined
  code-loading levers); 64 backend + 3 frontend tests green. Pending code-review (T12).
- 2026-06-24: code-review (Blind Hunter + Edge Case Hunter + Acceptance Auditor). No
  Critical/High survived verification of the hard invariant (deny-list stays absolute;
  tier routing not spoofable; dual-layer confinement). 11 fixes applied:
  - **Server-side consent** for `--pythonpath`/`--variablefile` (was UI-only) — gate now requires
    `code_load_consent`; frontend sends it; pinned by `test_code_loading_lever_requires_server_consent`.
  - **Curated-key-vanished** → `_format_modifiers` skips on `KeyError` instead of crashing the run.
  - **Docker FLAKY-3** — the new levers are now genuinely DROPPED in `execute()` (mirroring
    listeners), making the docstring true; builder-level parity unchanged.
  - **Kind-mismatch** — a curated modifier in the wrong pre/prerebot list → 422
    (`test_curated_modifier_kind_mismatch_is_422`).
  - **`:` in modifier args** rejected (RF spec separator) → 422 (`test_modifier_arg_with_colon_is_422`).
  - **Non-list advanced_config fields** → 422 (`test_non_list_advanced_field_is_422`).
  - `GET /modifiers` gated behind `executionAdvancedArgs`; `_role_at_least` no longer 500s on a
    legacy role; registry `_cache` lock; registry warmed at startup; audit records resolved
    class_path + tier + consent.
  - Dismissed: variablefile-is-code (by-design, ADMIN+consent+repo-confined), confinement-divergence
    (execution re-confines), minor UX/log items.
  - Post-fix: 92 targeted backend tests + 16 frontend tests green; vue-tsc + ruff clean.
