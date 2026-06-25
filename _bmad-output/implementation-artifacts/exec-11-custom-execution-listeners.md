# Story EXEC.11: Custom execution listeners (curated, org-extensible)

Status: done

Epic: EXEC — RF Execution Configuration
Story Key: `exec-11-custom-execution-listeners`
Depends on: EXEC.10 (modifier registry, trust tiers, gate routing)

## Story

As an organization deploying RoboScope (and as an ADMIN within it),
I want to attach our own vetted listeners to a run through the same curated, audited registry,
so that we can react to or stream execution events live (e.g. push results to our TMS as tests
finish) without ever exposing a free-typed `--listener` code-execution vector.

## Hard invariant (carried from EXEC.10 + NFR1)

Free-typed `--listener` stays denied in the Z3 freeform field — absolutely, for every role. Custom
listeners are reachable ONLY through the registry (Tier A/B) or the Tier-C runtime user-code path;
never as a deny-list relaxation. System-injected listeners (quarantine-skip, heal sidecar) are
ALWAYS applied and are never clobbered, reordered destructively, or disabled by a user listener.

## Acceptance Criteria

1. **AC1 — Registry `listener` kind.** The EXEC.10 registry gains a third `kind: listener`
   (entry shape unchanged). At least one Tier-A vendor listener ships so the picker is non-empty.
   `get_available_modifiers("listener")` returns listener entries. Pinned by a registry test.
2. **AC2 — Trust tiers reused.** Tier A (vendor) + Tier B (org via `roboscope.modifiers`
   entry-point / `ROBOSCOPE_MODIFIERS_CONFIG`) listeners are EDITOR-usable; a non-registered class
   path is Tier-C user-code → ADMIN + new default-OFF `executionCustomListenerUserCode` flag +
   explicit "runs arbitrary code throughout execution" consent.
3. **AC3 — Resolver emission via the existing channel.** Curated/user listeners are emitted as
   `--listener <spec>` via the existing `ResolvedRunSpec.listeners` channel, IN ADDITION to the
   system-injected listeners; the deny-list is untouched.
4. **AC4 — System listeners never clobbered.** `tasks.py` merges user/org listeners with the
   system quarantine/heal listeners additively (system-first); a user listener cannot drop either
   or break the live WebSocket run-status streaming. Pinned by a coexistence test.
5. **AC5 — Kind enforcement.** A curated key whose registry kind is not `listener` submitted in the
   listeners list → 422 (reuse the EXEC.10 kind-match guard).
6. **AC6 — Audit + parity + flags-off.** Resolved listener class path + tier audited; runner parity
   covers the listener channel; `executionCustomListenerUserCode` resolves OFF by default.
7. **AC7 — Docker FLAKY-3.** Custom listeners are dropped/warned on docker (an org listener in the
   backend venv is not importable in-container), mirroring the existing listener + EXEC.10 handling.
8. **AC8 — i18n + docs.** EN/DE/FR/ES (+ ZH) strings under `execution.advanced.*`; the in-app
   `execution-modifiers` doc subsection (4 locales) is extended to cover custom listeners and the
   live (listener) vs. post-run (`prerebotmodifier`) distinction, with a worked live-TMS example.

## Tasks / Subtasks

- [x] **T1 — Registry listener kind** (AC1): `VALID_KINDS += "listener"`; ship a Tier-A vendor listener (e.g. a progress/event-log listener) in `builtin.py`; registry test
- [x] **T2 — Flag** (AC2, AC6): register `executionCustomListenerUserCode` (False) in `governance/flags.py`
- [x] **T3 — Gate routing** (AC2, AC5): `gate_advanced_execution` handles `advanced_config.listeners` — curated key (kind must be `listener`) → EDITOR; non-curated → ADMIN + `executionCustomListenerUserCode` + consent; audit incl. tier
- [x] **T4 — tasks.py merge** (AC3, AC4): resolve curated listener keys → specs and merge with the system quarantine/heal listeners (system-first, additive); thread into `runner.execute(listeners=...)`
- [x] **T5 — Frontend** (AC8): `AdvancedRunConfig.vue` listener picker (kind=listener) + user-code consent; emit; payload
- [x] **T6 — Tests** (AC1, AC4, AC5, AC6): registry-loader (listener kind), gate routing + kind-mismatch, coexistence-with-system-listeners, parity, flags-off
- [x] **T7 — Docs** (AC8): extend the `execution-modifiers` subsection (4 locales) with custom listeners + live-vs-prerebot
- [x] **T8 — bmad-code-review + fixes**, then mark story `done` + sprint-status sync

## Out of scope

Any free-typed `--listener` in the Z3 field; replacing/bypassing the system quarantine/heal
listeners; relaxing the Z3 deny-list.

## Dev notes (anchors)

`execution/modifiers/registry.py` (+ `builtin.py` vendor listener), `governance/flags.py`,
`governance/dependencies.py::gate_advanced_execution` (listener routing), `execution/tasks.py`
(merge with system listeners), `components/execution/AdvancedRunConfig.vue` (listener picker).

## Dev Agent Record

### Completion Notes

- Built on the EXEC.10 registry: `VALID_KINDS += "listener"`, a Tier-A vendor `LiveProgressListener`
  (RF Listener API v2), and the `executionCustomListenerUserCode` flag (default OFF, ADMIN).
- Gate routes `advanced_config.listeners` like modifiers: curated key (kind must be `listener`) →
  EDITOR; non-curated class path → user-code (ADMIN + flag + consent). `tasks.py::_merge_listeners`
  appends user/org listeners AFTER the system quarantine listener (system-first, additive,
  de-duplicated). Audit records resolved class path + tier.
- Code-review (3 adversarial reviewers): hard invariant intact (free-typed `--listener` stays
  denied; system listeners never clobbered — pinned). 4 fixes applied:
  - **v2/v3 validation** (`_validate_listener_class`): a class registered as `kind: listener` must
    declare a valid `ROBOT_LISTENER_API_VERSION` (2/3) or it's skipped — makes the AC2 loader
    claim real; pinned by `test_listener_kind_requires_valid_api_version`.
  - **`_merge_listeners` de-dup** — a user listener equal to a system spec can't double its
    callbacks; pinned by `test_merge_dedups_a_user_listener_equal_to_a_system_one`.
  - Robust vendor `LiveProgressListener` format string (handles non-standard/absent status).
  - Comment accuracy (system listener built in that block is the quarantine-skip listener).
  - Dismissed: docker drops listeners (pre-existing FLAKY-3, AC7-intended), user-code-listener
    UI is API-only (consistent with user-code modifiers), execution-time kind enforcement
    (the gate is the authoritative writer — same trust model as EXEC.10).

## File List

- backend/src/execution/modifiers/registry.py (MOD — listener kind, vendor listener, v2/v3 validation)
- backend/src/execution/modifiers/builtin.py (MOD — LiveProgressListener)
- backend/src/governance/flags.py (MOD — executionCustomListenerUserCode)
- backend/src/governance/dependencies.py (MOD — listener routing + audit)
- backend/src/execution/tasks.py (MOD — _merge_listeners + user-listener formatting/merge)
- backend/tests/execution/test_exec11_listeners.py (NEW)
- backend/tests/execution/{test_modifier_registry,test_advanced_run_audit,test_exec_flags_default_off}.py (MOD)
- frontend/src/components/execution/AdvancedRunConfig.vue (MOD — listener picker group)
- frontend/src/views/ExecutionView.vue (MOD — listeners payload)
- frontend/src/i18n/locales/{en,de,fr,es,zh}.ts (MOD — modifiers.listener)
- frontend/src/docs/content/{en,de,fr,es}.ts (MOD — Live listeners doc)

## Change Log

- 2026-06-24: EXEC.11 implemented (listener kind on the EXEC.10 registry, system-first merge,
  user-code listener gating). Code-review: hard invariant intact, 4 fixes applied (v2/v3
  validation, merge de-dup, format-string robustness, comment). Backend + frontend tests green.
