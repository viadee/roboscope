# Epic GOV — Deployment Governance & Feature Lockdown — PRD

**Status**: Planning → ready for architecture
**Date**: 2026-06-18
**Owner / PM**: John
**Parent**: [presentation-feedback-epics.md](./presentation-feedback-epics.md) · connects into [prd.md](./prd.md)
**Epic**: GOV

## 1. Problem & evidence

On a shared or remote RoboScope install, **any** authenticated user with a sufficient role can mutate the *server's* Python environments — install/uninstall/upgrade packages, trigger Docker builds, run `rfbrowser init`. At Provinzial, environment provisioning is owned by a central administration team; end users mutating a managed environment is a governance violation and a concrete deployment blocker (raised directly at the 2026-06-17 presentation).

Role gating alone doesn't solve it: the customer wants the capability **gone** for the whole deployment, not merely restricted to higher roles — and they want it enforced server-side, not just hidden in the UI.

## 2. Users & Jobs-to-be-Done

- **Operator / Administrator** (installs & governs RoboScope): *"When I deploy RoboScope for a team whose environments I manage centrally, I want to switch off package management entirely, so no end user can change a managed environment."*
- **End user (RUNNER/EDITOR)** on a locked-down install: *"When a capability is governed away, I want a clear, non-broken UI that explains it's managed by my admin — not a button that 500s."*

## 3. Goals / Non-goals

**Goals**
- A deployment-level switch to disable feature areas, starting with **package management**.
- Enforcement **server-side** (API returns 403), not just UI hiding.
- A read-only environments mode (see, don't touch).
- Configurable minimum role for package operations where they remain enabled.
- Non-breaking: existing installs behave exactly as today unless an operator opts in.

**Non-goals (v1)**
- Per-project (vs. per-deployment) flags — global only for v1.
- A general policy engine / OPA — a small explicit flag set.
- Disabling arbitrary features beyond the defined set (extensible, but v1 ships the package-management area only).

## 4. Product decisions (open questions resolved)

1. **Scope = global per-deployment.** Flags apply install-wide. (Per-project deferred until a customer needs it.)
2. **Source of truth & precedence:** `ENV var > app_settings(DB) > built-in default`. The env var is the operator's hard lock (wins over any in-app admin toggle) — critical for managed/remote installs where the admin team owns the host, not the app.
3. **Default = enabled.** Unknown/unset flags resolve to ON, so upgrades never silently remove features.
4. **Lockdown is absolute when off:** even an ADMIN cannot install when the `packageManagement` flag is OFF (it's a deployment policy, not a permission). The *role floor* (decision 5) only applies when the area is ON.
5. **Role floor** for package ops is a separate, optional setting (default = today's behavior) for installs that keep package management ON but want to restrict who uses it.

## 5. Functional requirements

- **FR-1** A resolved feature-flag set is exposed read-only to the frontend (`GET /config/features`) and consumed by a `useFeatureFlags()` composable that gates UI affordances.
- **FR-2** Flags resolve with precedence env > DB(`app_settings`, category `features`) > default(ON). Admins can edit DB flags in Settings; the env override is visible-but-locked in the UI when set.
- **FR-3** With `packageManagement` OFF: the install/uninstall/upgrade/retry endpoints, `docker-build`, and `rfbrowser-init` return **403**; read endpoints (list packages, keyword cache, dockerfile preview) stay 200.
- **FR-4** With `packageManagement` OFF (or read-only mode ON): the Environments UI hides/disables all mutating controls and shows a localized "managed by your administrator" notice (EN/DE/FR/ES).
- **FR-5** A configurable **role floor** per mutating op (install/uninstall/upgrade/docker-build); enforced in the existing `require_role` path; default preserves current minimum roles.
- **FR-6** Every blocked attempt (403 by flag or role floor) is written to the audit log with user/IP/op.

## 6. Non-functional requirements

- **NFR-1 Security:** server-side enforcement is authoritative; UI hiding is convenience only. No flag may be bypassed via direct API or API-token calls.
- **NFR-2 Non-breaking:** default-on; a 0.10.x install upgrading sees identical behavior until an operator sets a flag.
- **NFR-3 Discoverability:** flags + precedence documented in in-app docs (EN/DE/FR/ES), GitHub Pages, and a CLAUDE.md gotcha; new audit codes documented.
- **NFR-4 Offline:** no external calls introduced (RoboScope offline-only invariant).

## 7. Stories (this epic) — see parent epics doc for full text

- **GOV-1** Feature-flag foundation (resolver + `GET /config/features` + `useFeatureFlags()`).
- **GOV-2** Lock package management (UI hide + endpoint 403 behind the flag).
- **GOV-3** Read-only Environments mode.
- **GOV-4** Configurable role floor for package ops.

Build order: GOV-1 → GOV-2 → GOV-3 → GOV-4 (each independently shippable).

## 8. Success metrics

- An operator can fully lock package management via a single env var, verified by an automated test that asserts 403 on every mutating env endpoint.
- Zero regressions for default (flag-unset) installs (existing env e2e + unit suites stay green).
- Provinzial-style acceptance: a RUNNER/EDITOR on a locked install sees a coherent read-only Environments page with no dead buttons.

## 9. Acceptance (epic-level)

1. With `packageManagement` OFF there is **no** mutation path (UI, REST, API token) — pinned by backend test hitting each endpoint → 403.
2. `GET /config/features` reflects env-over-DB-over-default precedence — pinned by unit test.
3. Locked UI is coherent + localized on every affected surface — pinned by a real-UI Playwright e2e (Environments page in locked mode).
4. Default install unchanged — full existing suites green.
5. Docs (in-app 4-lang + Pages) + CLAUDE.md gotcha + audit codes updated (Gate 8 stays green).

## 10. Handoff

→ **Architecture (Winston):** flag resolver design (env/DB/default precedence, caching, where it lives), the `/config/features` contract, how `require_role` composes with the flag check, and the frontend gating composable. Then → implementation (Amelia) story-by-story → code review → full UI E2E.
