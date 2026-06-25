---
stepsCompleted: [1, 2, 3, 4]
status: 'complete'
completedAt: '2026-06-23'
inputDocuments:
  - _bmad-output/planning-artifacts/exec-prd.md
  - _bmad-output/planning-artifacts/exec-architecture.md
  - _bmad-output/planning-artifacts/research/technical-exec7-rf-execution-levers-research-2026-06-23.md
epic: 'EXEC — RF Execution Configuration'
---

# RoboScope — Epic Breakdown: EXEC (RF Execution Configuration)

## Overview

This document decomposes Epic EXEC into implementable stories, derived from `exec-prd.md`,
the completed `exec-architecture.md`, and the EXEC-7 research spike. EXEC-1/EXEC-3 (tag
selection in the run dialog) already shipped in 0.11.0; this breakdown covers the backlog,
sequenced per the architecture's decided order with the `ResolvedRunSpec` resolver as the
foundation all run-time levers build on.

## Requirements Inventory

### Functional Requirements

FR1: Resolve every `robot` invocation through a single service-layer function producing an
     immutable `ResolvedRunSpec` (validated argv + runner + audit payload); runners consume
     only the spec, never raw `RunConfig`.
FR2: subprocess and docker runners build identical `robot` argv from a `ResolvedRunSpec`
     (modulo host/container path mapping); docker gains `--listener` parity.
FR3: Persist advanced execution config (`{args, prerun_modifiers}`) as a nullable JSON
     column on `ExecutionRun`; add the same to `Schedule`, and add the missing `variables`
     column to `Schedule` in the same migration.
FR4: Register three per-lever GOV feature flags — `executionAdvancedArgs`,
     `executionPreRunModifierUserCode`, `executionDataDriver` — explicitly default-OFF.
FR5: Run dialog (and schedule dialog) expose a feature-flag-gated "Advanced" section: a
     variables key/value editor and a freeform `robot` args field (Z3), EDITOR-gated.
FR6: Surface the available tags from a repo's suites (`[Tags]`/`Test Tags`/`Force Tags`/
     `Default Tags`) as a pick-from-list for include/exclude (EXEC-3 discovery).
FR7: Surface each test's long name and structural id (`s1-t1`) read-only in the run/report
     detail view (EXEC-4); no Jira integration (Phase-6).
FR8: Author/edit `__init__.robot` suite-init files in the editor, enforcing the init-file
     constraint (no `*** Test Cases ***` section) on the `robotTextIO.ts` round-trip (EXEC-5).
FR9: Support PreRunModifiers (`--prerunmodifier`): curated RoboScope-provided modifiers by
     default; user-authored modifier code behind the ADMIN-only `executionPreRunModifierUserCode`
     flag (EXEC-2).
FR10: Spike then implement DataDriver dynamic test generation (Listener v3) behind
      `executionDataDriver`, with the wheel vendored offline (EXEC-6).

### NonFunctional Requirements

NFR1 (Security): Three-zone flag taxonomy — Z1 RoboScope-owned (never user-settable:
     `--outputdir/--output/--log/--report/--loglevel/--consolecolors`), Z2 safe-curated,
     Z3 freeform with a hard deny-list of code-loading + path flags
     (`--pythonpath/--listener/--prerunmodifier/--prerebotmodifier/--parser`).
NFR2 (Security): Args always passed as a list to subprocess; never a shell string / `shell=True`.
NFR3 (Governance): Advanced levers gated behind GOV flags (default-OFF, the explicit
     exception to GOV's default-ON convention — `resolve_flag` defaults unknown keys ON).
NFR4 (Audit): Runs carrying advanced args/modifiers serialize the resolved argv to
     `AuditLog` on BOTH success and block (block path writes its own row + commits before
     raising — the GOV ≥400 middleware-skip rule).
NFR5 (Offline-only): EXEC-6 DataDriver wheel (+ XLS extra) vendored + version-pinned like
     `roboscopeheal`; no PyPI at runtime.
NFR6 (Compat): EXEC-1b migration nullable + default NULL, with upgrade AND downgrade; old
     pre-column run rows load without error.
NFR7 (i18n): All new user-facing strings in EN/DE/FR/ES (+ ZH overlay); Gate 8 green.
NFR8 (Role): Z3 args/variables UI requires EDITOR (admin-configurable, `resolve_package_op_role`
     pattern); user-code modifiers are ADMIN-only.

### Additional Requirements

- Brownfield: extends `backend/src/execution/` (`resolver.py` NEW, `flags.py` NEW,
  `models.py`/`schemas.py`/`service.py`/`router.py`/`runners/*` MOD).
- Reuses Epic GOV (`resolve_flag`/`require_feature`), `defusedxml`, audit middleware, the
  `quarantine_listener.py` listener precedent, and the `roboscopeheal` offline-vendoring pattern.
- Four mandated pinning tests/gates: **runner-parity**, **flags-default-off**,
  **blocked-advanced-run audit**, **pre-migration run-load**; plus an offline `import DataDriver` gate.

### UX Design Requirements

(No dedicated EXEC UX spec; UX surfaces are the run/schedule "Advanced" section and the
tag picker, governed by the established run-dialog patterns + feature-flag gating.)

### FR Coverage Map

FR1: Epic EXEC, Story 1 — ResolvedRunSpec resolver seam
FR2: Epic EXEC, Story 1 — runner parity + --listener
FR3: Epic EXEC, Story 2 — advanced_config persistence (ExecutionRun + Schedule + Schedule.variables)
FR4: Epic EXEC, Story 2 — per-lever GOV flags default-OFF
FR5: Epic EXEC, Story 3 — advanced args + variables UI (EDITOR-gated)
FR6: Epic EXEC, Story 4 — tag discovery (resolver-free)
FR7: Epic EXEC, Story 5 — long-name/id surfacing (read-only)
FR8: Epic EXEC, Story 6 — __init__.robot editor
FR9: Epic EXEC, Story 7 — PreRunModifier (curated → ADMIN user-code)
FR10: Epic EXEC, Stories 8 & 9 — DataDriver sub-spike → feature

## Epic List

### Epic EXEC: RF Execution Configuration
Power users can drive Robot Framework the way they actually run it — selecting tests by
discovered tags, passing safe advanced `robot` args and variables, organizing suites, and
generating data-driven tests — all governed and injection-safe. Standalone: delivers
complete value for "configure how RF runs" and depends on no future epic. EXEC-1/EXEC-3
(basic tag selection) already shipped in 0.11.0.

**FRs covered:** FR1–FR10 (NFR1–NFR8 woven as cross-cutting acceptance criteria).
**Story sequence:** S1 resolver+parity → S2 persistence+flags → S3 advanced UI → S4 tag
discovery → S5 long-name/id → S6 __init__.robot → S7 PreRunModifier → S8 DataDriver spike →
S9 DataDriver feature.

## Epic EXEC: RF Execution Configuration

Power users can drive Robot Framework the way they actually run it — governed and
injection-safe. Stories are sequenced so each builds only on previous ones.

### Story EXEC.1: Resolver seam + runner parity

As a RoboScope maintainer,
I want all `robot` arguments built once into an immutable `ResolvedRunSpec` that both runners consume,
So that argument logic and validation can never drift or be bypassed by a runner.

**Acceptance Criteria:**

**Given** a run request with tags/variables
**When** the service layer resolves it
**Then** a single `resolve_run_spec()` produces an immutable `ResolvedRunSpec` (`argv`, `runner_type`, `audit_payload`)
**And** both `subprocess_runner` and `docker_runner` accept ONLY `ResolvedRunSpec` (no raw `RunConfig`); the old `_build_command` is deleted, not duplicated.

**Given** the same `ResolvedRunSpec`
**When** each runner builds its invocation
**Then** subprocess and docker produce identical `argv` modulo host/container path mapping
**And** `docker_runner` now emits `--listener` at parity with subprocess
**And** this is pinned by the **runner-parity test** (`test_runner_parity`), which also asserts both reject a denied spec identically.

**Given** the existing tag/variable handling
**When** the refactor lands
**Then** no regression — existing execution backend tests stay green.

**Dev Agent Record (EXEC.1 — status: review, 2026-06-23):**
- NEW `backend/src/execution/resolver.py` — `ResolvedRunSpec` (frozen), `resolve_run_spec()`, `build_robot_argv()` (single shared builder), `robot_flag_args()`, `validate_advanced_args()`, `AdvancedArgError`, `OWNED_FLAGS`/`DENIED_FLAGS` (Z1/deny scaffolding).
- MOD `runners/subprocess_runner.py` + `runners/docker_runner.py` — both `_build_command`/`_build_robot_command` now delegate to the shared builder (duplication removed); docker kept its string-return contract; builder is `--listener`-capable for parity.
- NEW `tests/execution/test_runner_parity.py` — 8 tests: identical argv modulo path mapping, `--listener` parity, owned-flag server-control, denied-spec rejected identically (both runner types), no-regression on tag/variable order.
- Tests: 36 targeted green post-rename; full `tests/execution` suite 202/202; ruff clean on changed files.
- SCOPED RESIDUAL: docker `execute()` still does not pass host listeners into the container (module not importable in-container) — pre-existing **FLAKY-3**, unchanged here. Parity is at the *builder* level (the anti-drift goal); container-side listener mounting remains FLAKY-3.
- Exception named `AdvancedArgError` (not `…Rejected`) to satisfy project ruff N818 + match the `*Error` convention; docs updated to match.

### Story EXEC.2: advanced_config persistence + per-lever flags

As a RoboScope maintainer,
I want storage and governance scaffolding for advanced execution config,
So that advanced levers can be persisted and gated before any UI exposes them.

**Acceptance Criteria:**

**Given** the `ExecutionRun` and `Schedule` models
**When** the Alembic migration runs
**Then** `ExecutionRun.advanced_config` (nullable JSON Text) is added
**And** `Schedule.advanced_config` AND the previously-missing `Schedule.variables` are added
**And** the migration has both upgrade and downgrade; columns are nullable + default NULL.

**Given** a run row created before this migration
**When** it is loaded after upgrade
**Then** it loads without error (pinned by the **pre-migration run-load test**).

**Given** the GOV flag registry
**When** flags resolve
**Then** `executionAdvancedArgs`, `executionPreRunModifierUserCode`, `executionDataDriver` are explicitly registered with default **False**
**And** each resolves OFF by default despite `resolve_flag`'s unknown-key→True fallback (pinned by the **flags-default-off test**).

**Dev Agent Record (EXEC.2 — status: review, 2026-06-23):**
- MOD `src/execution/models.py` — `ExecutionRun.advanced_config` (Text/JSON, nullable); `Schedule.advanced_config` + `Schedule.variables` (parity; Schedule previously had neither).
- NEW `migrations/versions/e7c1a2b3d4f5_exec_advanced_config.py` — down_revision `f1a2b3c4d5e6`; `batch_alter_table` add/drop (SQLite-safe); nullable, no server default; upgrade AND downgrade. Validated up+down in isolation on a scratch DB stamped at the parent revision (full-chain replay isn't supported in this repo — fresh installs use `create_all`; migrations are incremental, a pre-existing condition).
- MOD `src/governance/flags.py` — registered the 3 EXEC flags explicitly with `False` (the `resolve_flag` fallback defaults unknown keys to `True`, so explicit registration is mandatory for OFF-by-default).
- NEW `tests/execution/test_exec_flags_default_off.py` (6) + `tests/execution/test_premigration_run_load.py` (2). 36 passed incl. full governance regression; zero new ruff errors.
- No UI/runner wiring yet (EXEC.3).

### Story EXEC.3: Advanced args + variables UI (EXEC-1b)

As an EDITOR-or-higher user,
I want a governed advanced section in the run/schedule dialog for custom `robot` args and variables,
So that I can drive robot the way I run it locally without unsafe footguns.

**Acceptance Criteria:**

**Given** `executionAdvancedArgs` is ON and I am ≥EDITOR
**When** I open the run dialog
**Then** an "Advanced" section shows a variables key/value editor and a freeform args field
**And** when the flag is OFF the section is not rendered (`useFeatureFlags()` hide, never render-then-403).

**Given** I submit advanced args
**When** the resolver validates them (three-zone taxonomy)
**Then** Z1 owned flags (`--outputdir/--output/--log/--report/--loglevel/--consolecolors`) and code-loading flags (`--pythonpath/--listener/--prerunmodifier/--prerebotmodifier/--parser`) are rejected with `AdvancedArgError` → 422
**And** args are passed as a list to subprocess, never a shell string.

**Given** an advanced run is submitted (allowed or blocked)
**When** it is processed
**Then** the resolved argv is written to `AuditLog` — on success AND on block (block path writes its own row + `db.commit()` before raising), pinned by the **blocked-advanced-run audit test**.

**Given** new UI strings
**Then** EN/DE/FR/ES (+ ZH overlay) entries exist under `execution.advanced.*` (Gate 8 green).

**Dev Agent Record (EXEC.3 — status: review, 2026-06-23):**
- Backend MOD `schemas.py` (`RunCreate.advanced_config`), `service.py` (persist), `router.py` (`start_run` calls the gate first), `governance/dependencies.py` (NEW `gate_advanced_execution` + generalized `_audit_block` resource_type) — gate order is flag (executionAdvancedArgs, 403) → EDITOR floor (403) → ADMIN/flag for user-code modifiers (403) → three-zone deny on freeform args (422); audit on block AND success. (Order corrected in the docs during code-review 2026-06-24: flag/role fail-fast precedes the 422 deny-check.)
- Frontend NEW `components/execution/AdvancedRunConfig.vue` (pure UI, data-testids); MOD `ExecutionView.vue` (flag-gated `showAdvanced`, parse vars/args on submit, hide-when-off via `useFeatureFlags`).
- i18n `execution.advanced.*` in EN/DE/FR/ES/ZH.
- NEW `tests/execution/test_advanced_run_audit.py` (5: flag-off 403, denied-arg 422, insufficient-role 403, permitted audited, empty no-op). NEW `e2e/tests/run-advanced-config.spec.ts`.
- Verified: backend exec+gov suite **243 passed**; vue-tsc clean; i18n parity **13/13**; prod build green (Gate 1); ruff clean on changed files. (e2e runs in CI — needs the live stack.)

### Story EXEC.4: Tag discovery (EXEC-3 pick-from-list)

As a user selecting what to run,
I want the tags that actually exist in my repo's suites offered as a pick-list,
So that I don't have to remember and free-type tag names.

**Acceptance Criteria:**

**Given** a repo with suites containing `[Tags]`/`Test Tags`/`Force Tags`/`Default Tags`
**When** I open the include/exclude tag controls
**Then** the distinct discovered tags are offered as selectable options
**And** I can still free-type a tag not yet present.

**Given** discovery
**When** it runs
**Then** it does NOT depend on the resolver seam (read-side only) and can ship in parallel after EXEC.2
**And** tags feed the existing `--include/--exclude` path unchanged.

**Dev Agent Record (EXEC.4 — status: review, 2026-06-23):**
- Backend NEW `explorer/service.py::list_all_tags` (per-test `[Tags]` + suite-level Force/Default/Test/Keyword Tags; sorted/deduped; resolver-free) + `GET /explorer/{id}/tags`.
- Frontend NEW `getRepoTags` (explorer.api); MOD `ExecutionView.vue` — fetch on repo change, `<datalist id="run-repo-tags">` bound to both tag inputs (`list=`), free-typing still allowed.
- NEW `tests/explorer/test_tag_discovery.py` (3); 111 explorer tests green; vue-tsc clean; 0 new ruff.

### Story EXEC.5: Long-name / id surfacing (EXEC-4)

As a user reviewing results,
I want each test's long name and structural id shown read-only,
So that I can identify and (later) externally reference specific tests.

**Acceptance Criteria:**

**Given** a completed run's `output.xml`
**When** I view the run/report detail
**Then** each test's long name (`Suite.Sub.Test`) and structural id (`s1-t1`) are displayed read-only
**And** parsing uses `defusedxml` and degrades gracefully if ids/long-names are absent
**And** no Jira integration is built (Phase-6); only the id surface is exposed.
**And** the exact module that parses `output.xml` for this is pinned during dev (resolves architecture Gap 2).

**Dev Agent Record (EXEC.5 — status: review, 2026-06-23):**
- Gap 2 pinned: parsing module is `backend/src/reports/parser.py`.
- MOD `reports/schemas.py` — `TestResultResponse.long_name` computed-field (derived from stored suite+test; NO migration; degrades to test name). MOD `reports/parser.py::_parse_test_deep` — surfaces RF structural `id` (e.g. `s1-s1-t1`), degrades to "" when absent.
- Frontend MOD `types/domain.types.ts` (`TestResult.long_name?`), `views/ReportDetailView.vue` (read-only long-name `:title` tooltip on test links).
- NEW `tests/reports/test_exec4_longname_id.py` (4) + 22 parser regression green; vue-tsc clean. No Jira (Phase-6) — id surface only.

### Story EXEC.6: __init__.robot suite-init editor (EXEC-5)

As a test author,
I want to author/edit a suite's `__init__.robot` in the editor,
So that I can set suite-level setup/teardown/name without leaving RoboScope.

**Acceptance Criteria:**

**Given** a suite directory
**When** I edit its `__init__.robot`
**Then** the editor supports `Suite Setup`/`Suite Teardown`/`Name`/imports on the `robotTextIO.ts` round-trip
**And** the editor enforces the init-file constraint — no `*** Test Cases ***` section
**And** the round-trip is pinned by a dedicated spec (no corruption of init-only settings).

### Story EXEC.7: PreRunModifier support (EXEC-2)

As a power user (curated) or ADMIN (custom code),
I want to apply PreRunModifiers to a run,
So that I can shape the suite model before execution.

**Acceptance Criteria:**

**Given** `executionAdvancedArgs`/curated path
**When** I select a RoboScope-provided (curated) modifier
**Then** it is applied via `--prerunmodifier` through the resolver (reusing the `quarantine_listener.py` precedent); no user code involved.

**Given** user-authored modifier code
**When** I try to use it
**Then** it requires the ADMIN-only `executionPreRunModifierUserCode` flag (default OFF) with explicit "runs arbitrary code in the execution environment" consent
**And** it is never reachable through the EXEC-1b generic args field.

**Given** any modifier run
**When** it executes
**Then** the resolved argv (incl. modifier refs) is audited per NFR4
**And** runner parity holds (the parity test covers `--prerunmodifier`).

**Dev Agent Record (EXEC.7 — status: review, 2026-06-23):**
- `resolver.py` — `ResolvedRunSpec` gains `advanced_args` + `prerun_modifiers`; `robot_flag_args` emits `--prerunmodifier <spec>` and validated freeform args (before target). Curated-modifier channel bypasses the args deny-list.
- Threaded `advanced_args` + `prerun_modifiers` through `runners/base.py`, `subprocess_runner.py`, `docker_runner.py` (execute + build), and `tasks.py` (reads `run.advanced_config`, formats modifiers to `name:arg` specs). **This also makes EXEC.3's persisted freeform args actually execute** (previously stored/gated/audited but not applied).
- Conservative gating: ALL modifiers currently require the ADMIN `executionPreRunModifierUserCode` flag (no curated allowlist shipped yet — that's the follow-up); docker in-container module availability is the same FLAKY-3 caveat as listeners.
- NEW `tests/execution/test_resolver_advanced.py` (4); 45 targeted tests green (resolver/parity/runners/audit); resolver ruff-clean.

### Story EXEC.8: DataDriver offline-vendoring sub-spike (EXEC-6 spike)

As a RoboScope maintainer,
I want a feasibility spike for DataDriver before building the feature,
So that the offline-only constraint and authoring flow are de-risked first.

**Acceptance Criteria:**

**Given** the offline-only constraint
**When** the spike completes
**Then** it confirms the DataDriver wheel (+ XLS extra) can be vendored + version-pinned like `roboscopeheal` into `wheels/`
**And** it validates the `[Template]` + data-source authoring flow in the Flow Editor
**And** it produces a go/no-go feasibility note; the EXEC.9 feature story is gated on it.

**Dev Agent Record (EXEC.8 — status: review, 2026-06-23):** Feasibility note at
`planning-artifacts/exec8-datadriver-spike.md`. **Outcome GO (CSV-first)**: DataDriver is a
library-import (Listener v3) ride-along — no runner change; offline vendoring mirrors
`roboscopeheal` (wheel in `wheels/` + offline `import DataDriver` CI gate); `[Template]`
authoring reuses the existing Flow Editor `templateRows`. XLS extra deferred.

### Story EXEC.9: DataDriver dynamic test generation (EXEC-6 feature)

As a test author,
I want to generate tests at runtime from a CSV/Excel data source against a `[Template]`,
So that I can data-drive a suite without writing each case.

**Acceptance Criteria:**

**Given** the EXEC.8 spike returned go AND `executionDataDriver` is ON
**When** I configure a data source (repo-confined path) against a `[Template]` test
**Then** DataDriver (Listener v3) generates the cases at runtime via the resolver
**And** the data source is sandboxed to the repo tree.

**Given** the offline bundle
**When** CI builds it
**Then** a gate asserts `import DataDriver` succeeds in the offline bundle (mirror `roboscopeheal` Gate 6/7).

**Dev Agent Record (EXEC.9 — status: review, 2026-06-23):**
- Added `robotframework-datadriver>=1.11,<2` to `backend/pyproject.toml` dependencies and ran `uv lock` (DataDriver 1.11.2 resolved; `uv sync --frozen` consistent). It's on PyPI, so the offline build collects its wheel from the lock like any other dep — no source-vendoring needed (simpler than roboheal).
- **Offline import gate** added to `.github/workflows/phase4-gates.yml` (Windows install gate now asserts `import DataDriver` alongside `import RoboScopeHeal`) + in-repo `tests/execution/test_datadriver_available.py` (import + flag-default-off).
- DataDriver runs as a normal **Library import** (Listener v3) inside the suite — no runner change; data source is naturally repo-confined (runs with `cwd=repo_path`). Gated behind `executionDataDriver` (default OFF, EXEC.2). CSV-first; XLS extra deferred per the spike.
- 8 tests green; ruff clean. (Network was available via the non-sandboxed path, so the dependency could be resolved + locked here — the earlier "blocked" assessment was wrong.)

### Story EXEC.10: Curated & org-extensible execution modifiers + admin code-loading levers

> Drafted 2026-06-24 as a follow-up surfaced during the EXEC code review; scope
> extended 2026-06-24 to cover **organization-deployed custom modifiers** and the
> **post-execution (`--prerebotmodifier`) hook**. The Z3 freeform deny-list is
> deliberately **absolute and role-independent** — even an ADMIN cannot pass
> `--listener`/`--pythonpath`/`--variablefile`/`--argumentfile`/`--prerunmodifier`/
> `--prerebotmodifier` through the generic advanced-args field. Today that leaves
> both end users AND deploying organizations with NO supported path to capabilities
> they legitimately need (a company that runs its own modifier to push results to a
> test-management system or emit custom reports cannot wire it up at all). This
> story delivers those capabilities **without weakening the deny-list**, via typed
> `ResolvedRunSpec` channels and a **modifier registry with three trust tiers**. It
> also closes the EXEC.7 deferred gap (no curated PreRunModifier allowlist / no UI
> producer shipped).

As an organization deploying RoboScope (and as an ADMIN / power user within it),
I want curated, org-extensible, audited channels for execution modifiers (pre- and
post-execution) plus repo-confined code-loading levers,
So that we can wire in our own vetted modifiers — e.g. to update our test-management system
or emit custom reports after a run — and use safe advanced levers, without anyone being able
to smuggle arbitrary code through the generic advanced-args field.

**Hard invariant (non-negotiable, carried from NFR1 + the 2026-06-24 review):**
`validate_advanced_args` stays absolute — every lever here is a **separate typed channel in
`ResolvedRunSpec`**, emitted through the resolver like the existing `prerun_modifiers`, NEVER
a relaxation or role-conditional branch of the Z3 deny-list. No "if ADMIN, allow anything"
path is ever introduced.

#### Modifier trust tiers (the curation model)

A single **modifier registry** is the source of truth. A registry entry is
`{key, class_path, kind: prerun|prerebot, label, args_schema, tier, i18n_key}`. The gate routes
by registry membership, never by free-typed class path:

- **Tier A — Vendor-curated:** RoboScope ships the modifier class in-repo (the
  `quarantine_listener.py` precedent — vetted, audited, offline). Selectable by **EDITOR**.
- **Tier B — Org/deployment-registered:** the **operator** registers their own modifier
  class(es) via **backend configuration, NOT the UI** — trust is established at deploy time
  (the same basis as installing a package or configuring an environment), so once registered
  they are first-class curated entries usable by **EDITOR**. Two offline-friendly mechanisms,
  both pure backend config:
  1. **Python entry-points** — the org installs a package into the backend venv exposing the
     `roboscope.modifiers` entry-point group; RoboScope discovers it at startup via
     `importlib.metadata.entry_points`. Self-registering, no central file to edit. (Offline:
     the wheel is installed into the venv like any dep — mirror the `roboscopeheal` vendoring.)
  2. **Config-file registry** — `ROBOSCOPE_MODIFIERS_CONFIG` points to a YAML/TOML listing the
     entries above (for orgs that prefer declaring class paths without packaging entry-points).
  Org modifiers are NOT repo-confined (they are operator-installed packages, deliberately
  trusted) — distinct from the `--variablefile`/`--pythonpath` repo-confinement below.
- **Tier C — Runtime user-code:** an end user names an **arbitrary** class path at run time →
  ADMIN-only `executionPreRunModifierUserCode` flag + explicit "runs arbitrary code in the
  execution environment" consent. The escape hatch, never the default.

**Acceptance Criteria:**

**Given** the EXEC.7 curated-modifier gap and the registry above
**When** EXEC.10 lands
**Then** Tier-A vendor modifiers ship and are surfaced in the run dialog's Advanced section as a
picker (gated `executionAdvancedArgs` + EDITOR) that populates `advanced_config.prerun_modifiers`
/ `advanced_config.prerebot_modifiers` by **registry key + declared args** (the user never types
a class path)
**And** a modifier reference that is NOT a registry key is treated as Tier-C user-code (ADMIN +
`executionPreRunModifierUserCode` + consent).

**Given** an organization with its own modifier class (e.g. a results→test-management sync, or a
custom report emitter)
**When** the operator registers it via the `roboscope.modifiers` entry-point OR the
`ROBOSCOPE_MODIFIERS_CONFIG` file
**Then** RoboScope loads + validates it at startup (importable, correct RF modifier base class;
a bad entry is logged and skipped, never a boot failure) and it appears as a Tier-B curated
picker entry usable by EDITOR — **no per-run user-code flag required**
**And** nothing about this path goes through the UI (org maintenance is backend config / package
install only).

**Given** a registered modifier declared `kind: prerebot`
**When** a run using it completes
**Then** the resolver emits it as `--prerebotmodifier <spec>` (runs against the **result** model
after execution, before report/log generation — the correct hook for "update our reports / push
to our TMS"); `kind: prerun` emits `--prerunmodifier` (runs against the running model before
execution). Both are typed `ResolvedRunSpec` channels that bypass the Z3 deny-list, never the
freeform field.

**Given** an ADMIN who needs a custom library search path
**When** they enable a new default-OFF `executionPythonPath` flag (registered `False`, ADMIN-only)
**Then** they can add one or more **repo-confined** paths that the resolver emits as
`--pythonpath` (reusing `_safe_resolve` path-confinement; a path escaping the repo tree is
rejected with `AdvancedArgError` → 422)
**And** the value is NEVER read from the Z3 freeform field — it is its own typed
`ResolvedRunSpec` channel.

**Given** an ADMIN who needs to load variables from a file
**When** they enable a new default-OFF `executionVariableFile` flag (registered `False`, ADMIN-only)
**Then** they can select a **repo-confined** variable file that the resolver emits as
`--variablefile`, with the same path-confinement + explicit arbitrary-code consent.

**Given** any run using one of these levers (allowed or blocked)
**When** it is processed
**Then** the resolved argv (incl. the lever values + the resolved modifier class paths / tier) is
audited per NFR4 — own `AuditLog` row + `db.commit()` before raising on the block path
**And** runner parity holds (`test_runner_parity` extended to cover the prerun/prerebot + path
channels)
**And** the new flags each resolve OFF by default (extend `test_exec_flags_default_off`).

**Given** the docker runner
**When** a code-loading lever or a modifier is requested on docker
**Then** it honours the FLAKY-3 caveat (in-container module availability — an org modifier
installed in the backend venv is NOT importable inside the container) — disable/clearly warn on
docker where the lever cannot apply, mirroring the listener-parity precedent.

**Given** new UI strings
**Then** EN/DE/FR/ES (+ ZH overlay) entries exist under `execution.advanced.*` (Gate 8 green).

**Given** these mechanisms are non-obvious and operator-facing
**When** EXEC.10 ships
**Then** a **thorough description of all of it lands in the in-app application documentation**
(`frontend/src/docs/content/{en,de,fr,es}.ts`) — not just a code README. It must cover: the
three trust tiers; the modifier registry shape; the **two org-registration mechanisms**
(`roboscope.modifiers` entry-point AND `ROBOSCOPE_MODIFIERS_CONFIG` file) with a worked example
(e.g. a results→test-management `prerebot` modifier); the pre- vs. post-execution
(`--prerunmodifier` vs `--prerebotmodifier`) distinction; the repo-confined `--pythonpath` /
`--variablefile` levers; and the explicit statement that these are curated channels, NOT a Z3
deny-list override
**And** it is added as a dedicated subsection under the `execution` doc section in all four
locales (top-level doc section ids stay consistent — Gate 8), with the `de.ts` subsection id
following that file's `execution-` prefix convention.

**Out of scope / explicitly deferred:** `--argumentfile` (arg-file indirection is strictly worse
than the typed channels and offers no capability they don't already provide); custom
`--listener` support (split into **EXEC.11**, which extends this story's registry with a
`listener` kind); relaxing the Z3 deny-list in any form.

**Dev notes (anchors):** `execution/resolver.py` (typed `prerun_modifiers` + new
`prerebot_modifiers`/`python_paths`/`variable_files` channels on `ResolvedRunSpec` +
`robot_flag_args`; deny-list untouched), NEW `execution/modifiers/` (registry + Tier-A vendor
classes + entry-point/config-file loader at startup), `governance/flags.py` (new flags incl.
`executionPythonPath`/`executionVariableFile`, all `False`), `governance/dependencies.py::
gate_advanced_execution` (route curated[A/B]→EDITOR vs user-code[C]→ADMIN by registry membership;
consent + audit), `execution/tasks.py` (thread the new channels like `prerun_modifiers`),
`components/execution/AdvancedRunConfig.vue` (registry-key pickers + consent checkboxes, flag-gated
via `useFeatureFlags`). Mandated tests: `test_resolver_advanced.py` (path-confinement reject +
prerebot emission), `test_runner_parity.py`, `test_exec_flags_default_off.py`,
`test_advanced_run_audit.py`, plus a registry-loader test (entry-point + config-file discovery,
bad-entry skip) and an offline `import` gate for any vendored org-modifier example.

### Story EXEC.11: Custom execution listeners (curated, org-extensible)

> Drafted 2026-06-24 as the fast-follow to EXEC.10. A **listener** differs from a modifier: it
> receives **live, per-event callbacks throughout execution** (RF Listener API v2/v3:
> `start_test`/`end_test`/`log_message`/`close`…) rather than transforming the model once before
> (`prerunmodifier`) or after (`prerebotmodifier`) the run. That makes it the right hook for
> **live** integrations — e.g. streaming each result to a test-management system or telemetry
> dashboard AS the run progresses, custom per-keyword artifacts, or mid-run reactions. RoboScope
> already uses listeners internally (the FLAKY-2 quarantine-skip listener + the `RoboScopeHeal`
> sidecar), and the `listeners` channel already exists on `ResolvedRunSpec` — today it is
> **system-controlled only**. EXEC.11 opens that channel to vetted org/admin listeners through
> EXEC.10's registry. **Hard dependency: EXEC.10** (registry, trust tiers, gate routing).

As an organization deploying RoboScope (and as an ADMIN within it),
I want to attach our own vetted listeners to a run through the same curated, audited registry,
So that we can react to or stream execution events live (e.g. push results to our TMS as tests
finish) without ever exposing a free-typed `--listener` code-execution vector.

**Hard invariant (carried from EXEC.10 + NFR1):** free-typed `--listener` stays denied in the Z3
freeform field — absolutely, for every role. Custom listeners are reachable ONLY through the
registry (Tier A/B) or the Tier-C runtime user-code path; never as a deny-list relaxation.

**Acceptance Criteria:**

**Given** EXEC.10's modifier registry
**When** EXEC.11 lands
**Then** the registry gains a third `kind: listener` (entry shape otherwise unchanged:
`{key, class_path, kind, label, args_schema, tier, i18n_key}`), and the same **three trust tiers**
apply — Tier A vendor-shipped, Tier B org-registered via the `roboscope.modifiers` entry-point /
`ROBOSCOPE_MODIFIERS_CONFIG` file (operator-trusted, EDITOR-usable), Tier C runtime user-code
behind a NEW default-OFF ADMIN-only `executionCustomListenerUserCode` flag + explicit
"runs arbitrary code throughout execution" consent.

**Given** a registered listener selected for a run
**When** the run executes
**Then** the resolver emits it via the existing `listeners` `ResolvedRunSpec` channel
(`--listener <spec>`) **in addition to** RoboScope's own system-injected listeners
**And** system listeners (quarantine-skip, heal sidecar) are ALWAYS injected and are never
clobbered, reordered destructively, or able to be disabled by a user listener
**And** the live WebSocket run-status streaming is unaffected (a user listener cannot break or
hijack `_broadcast_run_status`).

**Given** the RF Listener API has two versions
**When** a listener is registered
**Then** the registry entry declares (or the loader detects) API v2 vs v3, and the loader
validates the class against the declared version at startup (bad/incompatible entry logged and
skipped, never a boot failure).

**Given** any run using a custom listener (allowed or blocked)
**When** it is processed
**Then** the resolved argv (incl. listener class path + tier) is audited per NFR4 (own `AuditLog`
row + commit before raising on block)
**And** runner parity holds (`test_runner_parity` covers the listener channel)
**And** `executionCustomListenerUserCode` resolves OFF by default (extend
`test_exec_flags_default_off`)
**And** a coexistence test asserts a user listener runs alongside the quarantine/heal listeners
without dropping either.

**Given** the docker runner
**When** a custom listener is requested on docker
**Then** the FLAKY-3 caveat applies even more sharply (the listener runs throughout, and an
org listener installed in the backend venv is not importable in-container) — disable/clearly
warn on docker, mirroring the existing listener-parity handling.

**Given** new UI + docs
**Then** EN/DE/FR/ES (+ ZH overlay) strings under `execution.advanced.*` (Gate 8 green)
**And** the in-app application documentation (`frontend/src/docs/content/{en,de,fr,es}.ts`) is
extended to cover custom listeners: the **live (listener) vs. post-run (`prerebotmodifier`)**
distinction, the trust tiers (shared with EXEC.10), and a worked example (a live results→TMS
streaming listener) — in all four locales (`de.ts` keeps its `execution-` id prefix).

**Out of scope:** any free-typed `--listener` in the Z3 field; replacing or bypassing the
system quarantine/heal listeners; relaxing the Z3 deny-list in any form.

**Dev notes (anchors):** `execution/modifiers/` (extend the EXEC.10 registry + loader with the
`listener` kind + v2/v3 validation), `execution/resolver.py` (route registry listeners into the
existing `listeners` channel; deny-list untouched), `execution/tasks.py` (merge user/org
listeners with the system-injected quarantine/heal listeners — additive, system-first),
`governance/flags.py` (`executionCustomListenerUserCode`, `False`),
`governance/dependencies.py::gate_advanced_execution` (Tier routing for listeners),
`components/execution/AdvancedRunConfig.vue` (listener picker + consent). Mandated tests:
`test_runner_parity.py`, `test_exec_flags_default_off.py`, `test_advanced_run_audit.py`, a
registry-loader test (listener kind, v2/v3, bad-entry skip), and a system-listener coexistence test.

## Review Findings (code review — 2026-06-23, whole-epic EXEC.1–EXEC.9)

Adversarial review (Blind Hunter + Edge Case Hunter + Acceptance Auditor) over the full uncommitted
working tree, audited against this epic + `exec-architecture.md`. 8 patch, 4 defer, 7 dismissed as noise.

### Patch (unchecked — fixable, fix is unambiguous)

- [x] [Review][Patch] (fixed 2026-06-24) **Z3 deny-list bypassable via short flags + `--variablefile`/`--argumentfile`** [backend/src/execution/resolver.py:46,96] — `DENIED_FLAGS`/`OWNED_FLAGS` match exact long flags only. RF also accepts short aliases (`-V`=`--variablefile` → arbitrary Python execution, `-A`=`--argumentfile` → smuggles `--listener`/`--pythonpath` from a file, `-P`=`--pythonpath`, `-d/-o/-l/-r/-x/-b/-L/-C` for owned output flags) and unambiguous long-option abbreviations (`--listen`, `--prerunmod`). None are caught. **HIGH** (capped from Critical only because `executionAdvancedArgs` is default-OFF + EDITOR-gated). Fix: add `--variablefile`/`--argumentfile` + all short aliases to the deny/owned sets, and canonicalize/reject RF abbreviations of denied/owned flags. Defeats NFR1.
- [x] [Review][Patch] (fixed 2026-06-24) **Audit records raw input args, not the resolved argv / mandated payload shape** [backend/src/governance/dependencies.py:139] — `detail=f"advanced_args:{args}"` logs the raw input list; architecture mandates `{"resolved_argv":[...],"zones_used":[...],"blocked":bool}` and modifier runs aren't reflected in the audited content at all (`resolver.audit_payload` is built but never used). NFR4 content deviation. MEDIUM.
- [x] [Review][Patch] (fixed 2026-06-24) **Missing dedicated `__init__.robot` round-trip pinning spec** [frontend/src/tests/components/InitFileConstraint.spec.ts] — EXEC.6 AC mandates a spec pinning `parseRobotText`→`serializeRobotForm` of an init file with `Suite Setup`/`Suite Teardown`/`Name`/imports (no corruption of init-only settings). Only the two pure helpers are unit-tested; the round-trip contract is unpinned. MEDIUM.
- [x] [Review][Patch] (fixed 2026-06-24) **`__init__.robot` constraint is a passive warning, and `initFileHasTestCases` is dead** [frontend/src/components/editor/RobotEditor.vue:231] — AC says the editor "enforces" the no-`*** Test Cases ***` constraint; ship is a soft badge driven by `form.testCases.length` (post-parse). The exported, tested `initFileHasTestCases` (raw-text detection — catches a declared-but-empty section the parse count misses) is never imported by the editor. Recommended: keep non-blocking (hard save-block mid-edit is user-hostile; round-trip is non-destructive) but make detection authoritative by wiring the helper. LOW.
- [x] [Review][Patch] (fixed 2026-06-24) **`list_all_tags` splits suite tags on exactly 4 spaces; matches prefixes outside `*** Settings ***`** [backend/src/explorer/service.py:351] — `rest.split("    ")` drops/merges tab- or 2-/6-space-separated suite tags (RF separator is tab or 2+ spaces); prefix-match runs on every line so `[Documentation]`/comments/keyword names named like a setting yield phantom tags; also scans `.resource` files (no suite-level Force/Test tags). Picker only (free-type fallback intact). LOW–MED. Fix: `re.split(r"\t|  +", rest)` and scope to the Settings section.
- [x] [Review][Patch] (fixed 2026-06-24) **`parseArgs` whitespace-splits, shredding quoted args with spaces** [frontend/src/views/ExecutionView.vue:160] — `text.split(/\s+/)` turns `--name "My Suite"` into `['--name','"My','Suite"']`. Not a security issue (only yields more tokens, all still deny-list-validated), but silently mis-expresses any value with spaces. LOW. Fix: quote-aware tokenization.
- [x] [Review][Patch] (fixed 2026-06-24) **`get_repo_tags` unguarded on `repo.local_path` None / missing dir** [backend/src/explorer/router.py:142] — passes `repo.local_path` straight to `list_all_tags` → `Path(None)`/`rglob` on a never-synced repo can 500 the picker. LOW. Fix: return `[]` when path is unset or absent.
- [x] [Review][Patch] (fixed 2026-06-24) **Doc/code mismatch: 422 deny-check runs AFTER the 403 flag/role checks** [backend/src/governance/dependencies.py:84-130] — architecture (line 290) + the EXEC.3 dev record claim `AdvancedArgError`→422 fires BEFORE any 403; the code orders flag(403)→role(403)→modifier(403)→validate(422). The implemented flag-first order is defensible (fail-fast on authz; doesn't leak deny-list contents to unauthorized callers). LOW. Recommended: correct the architecture doc + dev record to match the safer implemented order rather than reorder the code.

### Defer (checked — real but not actionable in this pass)

- [x] [Review][Defer] **EXEC.7 curated-modifier "default path" not shipped / unreachable** [backend/src/governance/dependencies.py:101] — AC promised curated (no-code) modifiers as the default path with user-code behind the ADMIN flag; reality is ALL modifiers require the ADMIN `executionPreRunModifierUserCode` flag, no curated allowlist exists, and the frontend never sends `prerun_modifiers`. Acknowledged in the EXEC.7 dev record as follow-up. Safe (conservative gating), but the AC is not met.
- [x] [Review][Defer] **Docker runner re-joins resolved argv into a space-delimited string** [backend/src/execution/runners/docker_runner.py:268] — `_build_robot_command` returns `" ".join(...)`, undoing the resolver's list-safety (NFR2) for any value with spaces/metachars. Pre-existing runner contract, not introduced by EXEC; docker-py accepts list commands (no shell). Recommend returning the list form.
- [x] [Review][Defer] **`--prerunmodifier name:arg` built by naive `:`-join (no escaping)** [backend/src/execution/tasks.py:357] — a modifier arg containing `:` (Windows path / URL) re-splits into extra positionals. Not reachable today (no curated channel, ADMIN-gated). Tie to the EXEC.7 curated-modifier follow-up.
- [x] [Review][Defer] **`Schedule.advanced_config`/`Schedule.variables` are storage-only** [backend/src/execution/models.py] — columns persisted (D4 parity) but no scheduler reads them into a run, so they're inert. When the schedule→run path is wired, it MUST route through `gate_advanced_execution` and the resolver re-validates — execution-time trusts persisted config (`tasks.py` re-validates args via the resolver but NOT `prerun_modifiers`).

### Dismissed as noise (7)

- `Role(user.role)` ValueError→500 for an unknown role — pre-existing pattern (`require_package_op` does the same); role is a DB-constrained enum.
- Stale tag list on rapid repo switch — minor advisory-picker UX, low probability.
- `ResolvedRunSpec` mutated via `object.__setattr__` — deliberate, working post-init backfill idiom; "immutable" externally holds.
- Audit `detail` unbounded length — `detail` is an unbounded Text column.
- `tasks.py` `json.loads(run.advanced_config)` lacks try/except — mirrors the existing `json.loads(run.variables)`; only writer is the gated `start_run`; malformed only via direct DB tampering.
- `long_name` string-concat may differ from RF's true long name — auditor confirmed it degrades gracefully and is read-only display; EXEC.4 satisfied.
- e2e flag-leak if `afterAll` teardown fails — best-effort test teardown is standard; test-only.

### Verified-correct invariants (no action)
FR1/D1 single-builder (old `_build_command` deleted, both runners delegate) · NFR2 list-args/no-shell at the resolver · NFR3 all 3 flags explicitly `False` + pinned · NFR4 block-path own-row+commit-before-raise (the production-biter) pinned · NFR6 migration nullable+default-NULL, up+down, `down_revision='f1a2b3c4d5e6'` chain valid, pre-migration load pinned · EXEC.4 defusedxml deep-parse + graceful degrade · the 4 mandated pinning tests + offline `import DataDriver` gate all present and asserting what's claimed.
