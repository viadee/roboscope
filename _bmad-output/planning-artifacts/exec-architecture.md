---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-06-23'
inputDocuments:
  - _bmad-output/planning-artifacts/exec-prd.md
  - _bmad-output/planning-artifacts/research/technical-exec7-rf-execution-levers-research-2026-06-23.md
  - _bmad-output/planning-artifacts/presentation-feedback-epics.md
  - _bmad-output/project-context.md
  - backend/src/execution/runners/subprocess_runner.py
  - backend/src/execution/runners/docker_runner.py
  - backend/src/execution/schemas.py
workflowType: 'architecture'
project_name: 'roboscope'
user_name: 'Thomas'
date: '2026-06-23'
epic: 'EXEC — RF Execution Configuration'
---

# Architecture Decision Document — Epic EXEC (RF Execution Configuration)

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Scope sharpeners carried from EXEC-7 (architectural inputs)

1. **EXEC-1 is a security story** — `robot` CLI args via allow-list + deny-list + a GOV-gated freeform field, not a freeform string passed to `robot`.
2. **Close the subprocess↔docker `--listener` parity gap** before EXEC-2/EXEC-6 (docker runner lacks `--listener` today).
3. **EXEC-5 `__init__.robot` is an editor feature** on the `robotTextIO.ts` round-trip contract, not a runner change.
4. **EXEC-6 DataDriver needs an offline-wheel vendoring sub-spike** (bundle like `roboscopeheal`; offline-only constraint).
5. **EXEC-4 surfaces long-name / id only** — Jira integration is Phase-6, out of scope.

## Foundational principle — test basis is the running model, not the file

A `.robot` file is a **Suite**, not a test case. A test case's basis is the in-memory
**running model** (`robot.running.model` → `TestSuite`/`TestCase`); the file is one
serialization of it, and RF executes against the model. This is *why* the EXEC seam
splits the way it does:
- **EXEC-2 (PreRunModifier)** and **EXEC-6 (DataDriver)** operate on the *model* via
  `--listener`/`--prerunmodifier` — they create/mutate tests at runtime, NOT by editing
  `.robot` text.
- **EXEC-5 (`__init__.robot`)** is the deliberate exception — it IS about the text
  serialization, so it lives in the editor stack, not the runner.

## Project Context Analysis

### Requirements Overview

**Functional Requirements (from exec-prd.md + EXEC-7 research):**
- **EXEC-1b** — guarded "advanced robot args" + variables key/value UI → new `ExecutionRun`
  column + Alembic migration + injection-safe arg merge into `_build_command()`.
- **EXEC-2** — PreRunModifier support (`--prerunmodifier`); modifier resolution + security model.
- **EXEC-4** — long-name / structural id (`s1-t1`) surfacing from `output.xml` (read-only;
  Jira integration is Phase-6, out of scope).
- **EXEC-5** — `__init__.robot` suite-init authoring in the editor (`robotTextIO.ts` round-trip).
- **EXEC-6** — DataDriver dynamic test generation (Listener v3) — offline-vendoring sub-spike first.

**Non-Functional Requirements:**
- **SECURITY (dominant).** Hardened by the Red-Team pass below into a concrete model
  (three-zone flag taxonomy + single-arg-builder invariant + EXEC-2 separate consent).
- **GOVERNANCE** — advanced levers gated behind Epic GOV feature flags
  (`resolve_flag` / `require_feature`); EXEC-2 user-authored code is its own flag.
- **AUDIT** — runs carrying advanced args/modifiers serialize the resolved arg list to
  `AuditLog` on BOTH success and block (the GOV 403-not-auto-audited trap applies).
- **OFFLINE-ONLY** — EXEC-6 dependency (DataDriver + XLS extra) vendored + version-pinned
  like `roboscopeheal`; no PyPI at runtime.
- **RUNNER PARITY** — subprocess and docker build identical `robot` arg lists from one source.

**Scale & Complexity:**
- Primary domain: backend execution / subprocess orchestration; focused frontend + editor.
- Complexity level: **medium** (concentrated in the EXEC-1b/2 security model + EXEC-6 vendoring).
- Estimated architectural components: ~5 (shared arg-builder, `ExecutionRun` schema/migration,
  GOV gate wiring, `output.xml` id surfacing, editor `__init__.robot` support).

### Security model (hardened via Red Team vs Blue Team)

**Three-zone flag taxonomy** (replaces a flat allow/deny):
- **Z1 — RoboScope-owned (never user-settable):** `--outputdir`, `--output`, `--log`,
  `--report`, `--loglevel`, `--consolecolors`. Server controls all output paths — denied
  even inside the freeform field. (Prevents path-traversal / report-exfiltration via
  legitimate flags.)
- **Z2 — safe-curated (exposed as discrete UI controls):** e.g. `--randomize`,
  `--rerunfailed`, `--variablefile`, `--name`, `--maxerrorlines`.
- **Z3 — freeform (GOV-gated):** an "advanced args" field behind a feature flag, with a
  **hard deny-list of code-loading flags** applied on top — `--pythonpath`, `--listener`,
  `--prerunmodifier`, `--prerebotmodifier`, `--parser` are never accepted here.

**Invariants:**
1. **Single shared arg-builder.** ALL `robot` args flow through one tested function both
   runners call; the parity test asserts identical build AND identical rejection. (Day-2
   drift — a new runner or a "convenience" bypass — is the top residual risk; this invariant
   is what holds the model together.)
2. **No shell.** Args are always passed as a list to subprocess (`cmd.extend`), never a
   shell string; pin a test asserting `shell=True` is never used. (Neutralizes
   `$()`/`;`/`&&` injection through `--variable` values etc.)
3. **EXEC-2 user-authored modifier code is a distinct GOV flag, default OFF, ADMIN-only,
   with explicit "runs arbitrary code in the execution environment" consent** — never
   reachable through EXEC-1b generic args. Curated RoboScope-provided modifiers (no user
   code) are the default path.
4. **Audit the resolved arg list** on success and on block (block path must write its own
   `AuditLog` row + commit before raising — the GOV middleware skips ≥400 responses).
5. **EXEC-6 data source is repo-confined** (reuse existing path-confinement) and the
   DataDriver wheel is version-pinned/vendored so the parser surface is known and auditable.

### Technical Constraints & Dependencies
- Extends existing seam: `backend/src/execution/runners/{subprocess,docker}_runner.py`
  `_build_command()`; `RunCreate` in `schemas.py`. Migration-free for tags/variables;
  EXEC-1b needs a new column.
- Reuses Epic GOV gating (`resolve_flag` / `require_feature` / `require_*_op`).
- Reuses editor stack (`robotTextIO.ts`) for EXEC-5; must honor the round-trip contract.
- Offline-only: EXEC-6 wheel vendored into `wheels/` like `roboscopeheal`.

### Cross-Cutting Concerns Identified
1. Injection-safe `robot` arg construction (three-zone taxonomy + single shared builder).
2. GOV feature-flag gating of advanced execution levers (incl. separate EXEC-2 code flag).
3. subprocess↔docker runner parity (incl. the `--listener` gap) — blocks EXEC-2/EXEC-6.
4. Audit logging of advanced-arg / modifier runs (success AND block).
5. Offline dependency vendoring + repo-confined data sources (EXEC-6).

### Failure Modes & Mandated Guards (operational, via FMEA)

| Component | Failure mode | Guard |
|-----------|-------------|-------|
| Shared arg-builder | New flag added to one runner only (drift); unknown control silently skipped | Builder returns typed result; **unknown control = hard error, not silent skip**; parity + per-flag contract tests |
| `ExecutionRun` migration | NULL on old rows; untested downgrade; offline-bundle DB un-upgraded | Column **nullable+default**; upgrade AND downgrade; pre-migration run-load test; verify offline boot runs `alembic upgrade head` |
| GOV gate wiring | Default-ON freeform; UI renders control while server 403s | Z3 + EXEC-2 flags **default OFF**; `useFeatureFlags()` **hides** control when off (no render-then-403); server authoritative |
| Audit logging | Block raises before commit (GOV ≥400 middleware skip); logs UI input not resolved args | Log **resolved** arg list; block path writes own `AuditLog` + `db.commit()` before raising |
| `output.xml` id surfacing | Eager parse of huge XML; XXE; assumes ids/long-names present | Use existing **`defusedxml`**; read-only + degrade gracefully if absent; bound large-file parse |
| `__init__.robot` editor | User adds illegal `*** Test Cases ***`; round-trip corrupts init-only setting | Editor **enforces init-file constraint**; reuse `robotTextIO.ts` round-trip + dedicated pinning spec |
| DataDriver vendoring | Wheel absent in offline `wheels/`; XLS extra missing; version drift vs `uv.lock` | **Sub-spike gates it**; vendor + version-pin like `roboscopeheal`; CI gate asserts `import DataDriver` in offline bundle |
| Runner selection | Advanced modifier requested on docker before `--listener` parity closed | Listener-parity is a **hard prerequisite**; until closed, disable modifier features on docker with a clear UI reason (recorder `capabilities` pattern) |

**Four pinning tests / CI gates the architecture mandates up front:**
1. **Runner-parity test** — subprocess & docker build identical arg lists *and* reject identically.
2. **Blocked-advanced-run audit test** — a denied advanced run produces an `AuditLog` row.
3. **Pre-migration run-load test** — a run row created before the EXEC-1b column loads without error.
4. **Offline `import DataDriver` gate** — mirror the `roboscopeheal` Gate 6/7 offline-import assertion.

**Highest-severity / lowest-visibility (production-biters):** silent arg-drop in the builder · block-path audit gap · offline DataDriver wheel absence.

## Architecture Decision: the arg-builder seam (Tree of Thoughts)

**Decision:** **Resolved value-object at the service layer (Path C), with a small declarative flag registry (Path D) inside the resolver.**

### Options evaluated

| Path | Drift safety | Simplicity | Testability | Refactor cost |
|------|:---:|:---:|:---:|:---:|
| A — shared free function `build_robot_args(config)` | ⚠️ by discipline | ★★★ | ★★★ | low |
| B — `RobotArgsBuilder` class with zone methods | ⚠️ by discipline | ★★ | ★★★ | low |
| **C — `ResolvedRunSpec` value-object, runners consume only that** | ✅ **structural** | ★★ | ★★★ | med |
| D — `FLAG_REGISTRY` policy table | ⚠️ by discipline | ★ | ★★ | med |

### Rationale

The dominant risk — confirmed by Red Team (day-2 bypass) **and** FMEA (silent arg-drop / runner
divergence) — is **drift**. Only Path C answers it *structurally* rather than by convention:
runners lose the ability to construct args at all, so they physically cannot bypass validation.
The "all args flow through one tested function" invariant becomes a **type-level guarantee**.

### Shape

- **Service layer:** `RunConfig` → `resolve_run_spec()` → **`ResolvedRunSpec`** (immutable;
  validated `robot` token list + chosen runner + audit payload). **GOV gate + `AuditLog`
  happen here, once** (success and block).
- **Runners:** `subprocess` / `docker` accept a `ResolvedRunSpec` and do **only** host-vs-container
  **path mapping** + process spawn — **no flag logic, no access to raw `RunConfig`**.
- **Registry:** a small `FLAG_REGISTRY` (`name`, `zone` Z1/Z2/Z3, `validator`, `runner_compat`)
  drives the resolver; adding a Z2 control is a declarative data change. Kept small and in one
  place, so we don't pay full registry-indirection cost.
- **Parity test** asserts: both runners, given the same `ResolvedRunSpec`, spawn identical arg
  lists modulo path mapping — and reject identically.

### Consequence for stories
- An early **"resolver + ResolvedRunSpec refactor"** story precedes EXEC-1b/2/6 (it is the seam
  they all build on) and folds in the `--listener` parity fix (backlog #4).

## Starter Template Evaluation

**Not applicable — brownfield epic.** EXEC extends the existing RoboScope execution
layer; there is no project to scaffold. The foundation is the established, locked stack:
FastAPI + SQLAlchemy + Alembic + uv (backend), Vue 3 + TS + Pinia + vue-i18n (frontend),
offline-only. EXEC builds directly on `backend/src/execution/runners/*` and `schemas.py`
(`RunCreate`), reusing Epic GOV gating, the `robotTextIO.ts` editor round-trip, `defusedxml`,
the audit middleware, and the `roboscopeheal` offline-vendoring pattern.

**First implementation story is NOT a scaffold** — it is the resolver/`ResolvedRunSpec`
refactor (see the arg-builder seam decision) that the EXEC stories build on.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical (block implementation):**
- D1 — `ResolvedRunSpec` resolver seam (already decided: Path C + small flag registry).
- D2 — `advanced_config` storage shape + migration.
- D3 — GOV flag registration (default OFF, explicit) — the registry fallback gotcha.

**Important (shape the architecture):**
- D4 — Schedule parity. D5 — role floor. D6 — per-lever flag granularity.

**Deferred (own future cycle):** EXEC-6 DataDriver feature (gated behind its sub-spike).

### Data Architecture (D2, D4 — decided with Thomas 2026-06-23)

- **One nullable JSON `advanced_config` `Text` column on `ExecutionRun`** holding
  `{ args: [...], prerun_modifiers: [...] }` (extensible). **Mirrors the existing
  `variables` Text/JSON column** — one Alembic migration, no new column per lever.
  - Migration: **nullable + default NULL**; upgrade AND downgrade; pre-migration
    run-load test (FMEA guard).
- **Schedule parity: add `advanced_config` to the `Schedule` model too, now** — recurring
  runs honor the same levers. This also closes the pre-existing gap that `Schedule` carries
  tags but **not** `variables` → add `variables` to `Schedule` in the same migration.
- `variables` stays as-is (already modeled/applied); EXEC-1b only adds the UI for it.

### Authentication & Security (D3, D5, D6 — decided with Thomas)

- **Per-lever GOV flags, all explicitly registered with `False` default:**
  `executionAdvancedArgs`, `executionPreRunModifierUserCode`, `executionDataDriver`.
  - **GOTCHA (determined, not optional):** `resolve_flag` falls back to
    `FEATURE_FLAGS.get(key, True)` — unregistered keys default **ON**. These three MUST be
    added to the `FEATURE_FLAGS` registry with `False`, or they silently enable. Pin with a
    test asserting each resolves OFF by default. This is the explicit **exception** to GOV's
    "default-ON so upgrades don't silently disable" convention, justified by security.
- **Role floor: EDITOR** for the Z3 freeform args / variables UI (reuse the
  `resolve_package_op_role` pattern, default EDITOR, admin-configurable). `execution
  PreRunModifierUserCode` is **ADMIN-only** regardless (arbitrary code).
- Three-zone taxonomy + single-arg-builder invariant + audit-on-block as already recorded.

### API & Communication Patterns

- `RunCreate` (and the schedule create schema) gain an optional `advanced_config` object;
  the **service layer** validates it into `ResolvedRunSpec` (GOV gate + audit here, once).
- Runners consume `ResolvedRunSpec` only (no raw `RunConfig`); the `--listener` parity fix
  lands in the resolver-refactor story.
- Error handling: invalid/denied args → **422 (validation) for malformed**, **403 (GOV)
  for disabled feature / insufficient role** — the 403 path writes its own `AuditLog`.

### Frontend Architecture

- Run dialog + schedule dialog gain a **feature-flag-gated** "Advanced" section: a variables
  key/value editor (Z2-ish) and a Z3 freeform args field. `useFeatureFlags()` **hides** each
  control when its per-lever flag is off (no render-then-403).
- i18n EN/DE/FR/ES (+ ZH overlay) for all new strings (Gate 8).

### Infrastructure & Deployment

- EXEC-6 DataDriver wheel vendored + version-pinned into `wheels/` like `roboscopeheal`;
  CI gate asserts `import DataDriver` in the offline bundle. Gated behind the sub-spike.

### Decision Impact Analysis

**Implementation sequence:** resolver/`ResolvedRunSpec` refactor + `--listener` parity (D1)
→ `advanced_config` migration on ExecutionRun + Schedule + Schedule.variables (D2/D4)
→ per-lever GOV flags registered OFF (D3/D6) → EXEC-1b UI (args + variables, EDITOR-gated, D5)
→ EXEC-4 id surfacing → EXEC-5 `__init__.robot` editor → EXEC-2 PreRunModifier (curated → ADMIN user-code)
→ EXEC-6 sub-spike → EXEC-6 feature.

**Cross-component dependencies:** D1 is the spine all run-time levers build on; D2 blocks
EXEC-1b/2; D3 blocks any UI exposure; Schedule parity (D4) rides D2's migration.

## Implementation Patterns & Consistency Rules

Scope: EXEC-specific conventions only. Repo-wide conventions (snake_case DB, REST plural
routes, Vue 3 + Pinia, vue-i18n 5-locale, `parseBackendDate`, `defusedxml`, audit
middleware) are inherited from CLAUDE.md / project-context.md and are NOT restated here.

### Naming (EXEC seam)
- Resolver: `resolve_run_spec(config, db, user) -> ResolvedRunSpec` in
  `backend/src/execution/resolver.py` (NEW module — single home for arg logic).
- Value object: `ResolvedRunSpec` (immutable dataclass): `argv: list[str]`,
  `runner_type`, `audit_payload: dict`. Runners accept ONLY this.
- Flag registry: `FLAG_REGISTRY` rows in `backend/src/execution/flags.py` (or extend the
  governance registry) — keys camelCase to match GOV: `executionAdvancedArgs`,
  `executionPreRunModifierUserCode`, `executionDataDriver`.
- Runner entry: both runners expose `run(spec: ResolvedRunSpec)`; the old `_build_command`
  is deleted, not duplicated.

### `advanced_config` canonical shape (the ONE format both ends use)
- Stored JSON (Text column): `{"args": ["--randomize", "all"], "prerun_modifiers":
  [{"name": "...", "args": [...]}]}`. Empty/absent → NULL, never `{}`.
- snake_case JSON keys (matches the existing `variables` convention). `args` is a flat
  token list already split (NOT a shell string).

### Three-zone enforcement (where each lever is decided)
- Z1 owned flags: hard-coded in the resolver, never read from config.
- Z2 curated: each is a registry row with a `validator`; resolver maps value → exact tokens.
- Z3 freeform: deny-list (`--pythonpath|--listener|--prerunmodifier|--prerebotmodifier|
  --parser|--variablefile|--argumentfile` + output-path flags, INCLUDING their RF short
  aliases `-P/-V/-A/-d/-o/-l/-r/-x/-b/-L/-C` and unambiguous long-option abbreviations)
  enforced in the resolver and raised as a typed `AdvancedArgError` (→ 422).
  **Gate order (as implemented, code-review 2026-06-24):** the `executionAdvancedArgs`
  feature flag and the EDITOR role floor are checked FIRST (→ 403), then the deny-list
  (→ 422). Fail-fast on authorization is the safer order — it neither processes nor
  leaks deny-list outcomes to a caller who lacks the feature/role. (An earlier draft
  said 422-before-403; the code does flag→role→deny and the doc now matches it.)

### Audit payload shape (success AND block)
- `AuditLog.detail` carries `{"resolved_argv": [...], "zones_used": ["z2","z3"],
  "blocked": false}`. Block path: `blocked: true, reason: "<deny|flag_off|role>"`, write +
  `db.commit()` BEFORE raising (GOV ≥400 middleware-skip rule).

### Parity-test contract (mandated)
- `test_runner_parity`: for a fixed `ResolvedRunSpec`, subprocess and docker produce
  identical `argv` modulo path mapping, and both raise identically on a denied spec.

### Frontend gating
- Each advanced control wrapped in `v-if="featureFlags.<lever>"` via `useFeatureFlags()`
  (token-guarded singleton) — hide-when-off, never render-then-403.
- i18n keys under `execution.advanced.*` in EN/DE/FR/ES (+ ZH overlay).

### Enforcement — All agents MUST
- Route every robot arg through `resolve_run_spec`; never construct argv in a runner/router.
- Add new levers as registry rows (zone + validator), not ad-hoc branches.
- Register every new GOV flag explicitly (default `False` for EXEC levers) — the
  `resolve_flag` fallback is `True` for unknown keys.
- Add EN/DE/FR/ES i18n for any user-facing string (Gate 8).

### Anti-patterns (forbidden)
- A second place that builds robot args (reopens drift).
- Passing args as a shell string / `shell=True`.
- Storing `advanced_config` as separate columns (decided against — one JSON column).
- A lever UI rendered without its feature-flag guard.

## Project Structure & Boundaries

Brownfield epic — structure is expressed as NEW vs MODIFIED files against the existing
`backend/src/execution/` and frontend tree, mapped to stories.

### Backend
```
backend/src/execution/
├── resolver.py              # NEW — resolve_run_spec() + ResolvedRunSpec + AdvancedArgError (D1; the spine)
├── flags.py                 # NEW — FLAG_REGISTRY (executionAdvancedArgs / PreRunModifierUserCode / DataDriver), all False
├── schemas.py               # MOD — RunCreate/ScheduleCreate gain optional advanced_config; RunResponse echoes it
├── models.py                # MOD — ExecutionRun.advanced_config (JSON Text, nullable); Schedule.advanced_config + Schedule.variables
├── service.py               # MOD — call resolve_run_spec(); GOV gate + AuditLog (success & block) here
├── router.py                # MOD — accept advanced_config; 422 on AdvancedArgError, 403 on flag/role
└── runners/
    ├── base.py              # MOD — run(spec: ResolvedRunSpec) signature
    ├── subprocess_runner.py # MOD — consume ResolvedRunSpec; delete _build_command
    ├── docker_runner.py     # MOD — consume ResolvedRunSpec; ADD --listener parity; path mapping only
    └── quarantine_listener.py  # (existing listener precedent — reuse pattern for EXEC-2 curated modifiers)
backend/src/governance/flags.py  # MOD (alt) — if registering EXEC flags in the GOV registry instead of execution/flags.py
backend/alembic/versions/xxxx_exec_advanced_config.py  # NEW — add columns; upgrade+downgrade; nullable+default NULL
```

### Backend tests (`backend/tests/execution/`)
```
├── test_resolver.py             # NEW — three-zone resolution, deny-list, AdvancedArgError
├── test_runner_parity.py        # NEW — subprocess≡docker argv (mandated parity contract)
├── test_exec_flags_default_off.py  # NEW — each EXEC flag resolves OFF (the resolve_flag fallback gotcha)
├── test_advanced_run_audit.py   # NEW — blocked advanced run writes an AuditLog row
└── test_premigration_run_load.py # NEW — pre-column run row loads without error
```

### Frontend
```
frontend/src/views/ExecutionView.vue   # MOD — feature-flag-gated "Advanced" section
frontend/src/components/execution/AdvancedRunConfig.vue  # NEW — advanced controls (v-if per-lever flag)
frontend/src/composables/useFeatureFlags.ts  # MOD — expose the 3 new lever flags
frontend/src/i18n/locales/{en,de,fr,es,zh}.ts  # MOD — execution.advanced.* keys
e2e/tests/run-advanced-config.spec.ts  # NEW — flag-on shows controls; create-run carries advanced_config
```

### Boundaries
- **API:** router validates shape → service resolves+gates+audits → runner executes.
  Runners NEVER see raw `RunConfig`; only `ResolvedRunSpec` (structural drift prevention).
- **Data:** `advanced_config` is opaque JSON at the DB layer; only the resolver interprets
  it. `output.xml` (EXEC-4) parsed read-only via `defusedxml`.
- **Feature:** GOV flags gate exposure (frontend hide + backend 403); EXEC-6 also gated
  behind the offline-vendoring CI assertion.

### Requirements → structure mapping
- **D1 resolver / parity** → `resolver.py`, `runners/*`, `test_resolver.py`, `test_runner_parity.py`
- **EXEC-1b args+vars** → schemas/models/service + `AdvancedRunConfig.vue` + migration
- **EXEC-2 PreRunModifier** → resolver (curated) + `quarantine_listener.py` pattern; user-code ADMIN flag
- **EXEC-4 id surfacing** → reports module, read-only via `defusedxml` (separate from runner)
- **EXEC-5 `__init__.robot`** → frontend editor (`robotTextIO.ts`) — NOT in `execution/`
- **EXEC-6 DataDriver** → `wheels/` vendoring + CI gate + `executionDataDriver` flag

## Architecture Validation Results

### Coherence ✅
`ResolvedRunSpec` seam (D1) is consistent with the three-zone taxonomy, per-lever flags,
and the parity contract — no contradictions. `advanced_config` JSON shape mirrors the
existing `variables` column. Flag defaults-OFF (D3) is the explicit, documented exception
to GOV's default-ON convention.

### Requirements Coverage ✅ (2 gaps resolved-by-recommendation)
- EXEC-1b / EXEC-2 / EXEC-5 / EXEC-6 + D1 foundation: fully covered by decisions+structure.
- **GAP 1 — EXEC-3 tag discovery** (read-side; parse `[Tags]`/`Test Tags`/`Force Tags`/
  `Default Tags`) not in the sequence. RESOLUTION: add as an early, independent,
  resolver-free story.
- **GAP 2 — EXEC-4 exact module under-specified** (read-only `output.xml`/longname/id
  surfacing). RESOLUTION: pin the precise module during epics/stories; low risk.

### Implementation Readiness ✅
- 4 mandated pinning tests named (parity, flags-off, blocked-audit, pre-migration load).
- Single seam + explicit MUST rules + anti-patterns → low divergence risk.

### Completeness Checklist
- [x] Context analyzed, scale/complexity assessed, constraints + cross-cutting concerns mapped
- [x] Critical decisions documented (D1–D6) with rationale
- [x] Implementation patterns + consistency rules established
- [x] Complete NEW/MODIFIED file map with requirements→structure mapping

### Readiness Assessment
Overall: **READY FOR EPICS/STORIES.** Confidence: **HIGH.**
Strengths: drift prevented structurally (type-level); security model stress-tested
(Red Team + FMEA); grounded in real code.
Future enhancement: the EXEC-6 sub-spike must complete before its feature story.

### Implementation Handoff
First priority: the resolver / `ResolvedRunSpec` refactor + `--listener` parity (D1) — the
spine all run-time levers build on. Then migration (D2/D4) → flags-off (D3) → EXEC-1b UI.
