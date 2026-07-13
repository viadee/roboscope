# Retrospective — 0.11.0 Epic: Flow Editor Resources & Keyword UX

- **Date:** 2026-06-23
- **Release:** v0.11.0 (Latest on GitHub, commit `e1ac267`)
- **Facilitator:** Amelia (Developer) · **Project Lead:** Thomas
- **Participants:** Amelia (Developer), Sally (UX Designer), Winston (Architect), Dana (QA)
- **Scope note:** This work shipped via quick-dev + direct epics, not the formal `sprint-status.yaml` plan (which predates it, last updated 2026-05-08). Material was drawn from git history (`v0.10.0..v0.11.0`) and the planning/implementation specs.

---

## Epic Summary — what shipped

Headline epic — **make repository `.resource` keywords first-class in the Flow Editor**:

| Item | Commit / PR | Notes |
|------|-------------|-------|
| RES — repo `.resource` keywords usable, auto-`Resource` import on insert | `1086ebb` | mirrors Library auto-import; execution honors the import |
| D1–D6 UX wave | `9100039` | pinned "Your resources" section, import-confirmation toast, required-arg prefill, sort/filter/dedup controls |
| Palette double-display fix | `c1443e0` / #53 | root cause: `rf_knowledge.py` stem attribution; fixed with `resourceFileStems` dedup + pinning test |
| Quiet, repo-scoped keyword loading | `e91a576` / #55 | slim 2px indicator; no full-state reload on file switch; per-repo cache anchor |
| Security sweep | `0360c3f`, `25737b3` | all 12 Dependabot alerts cleared + dompurify GHSA-cmwh-pvxp-8882 |

Shipped in parallel in the same release: **GOV** (deployment feature lockdown, `790e327`), **AIX** (LiteLLM provider type + analysis verbosity, `8eea70d`), **EXEC-1/EXEC-3** (tag selection in run dialog, `5a43237`).

### Quality signals
- **9/9 CI gates green** on every PR (#52–#56)
- 851/854 frontend unit tests, 2161 backend tests, prod build verified, real-UI e2e for the resource UX
- **Zero production incidents** — clean release
- Release published with all 5 distribution assets attached

---

## What went well

- **The UX arc (RES → D1–D6)** — *Thomas's named win.* We moved the resource experience from "technically works" to "feels right": repo keywords got their own pinned home instead of being buried among library suggestions; the previously-silent auto-import became a visible toast; required args are pre-filled so an inserted node isn't born broken (no more silent runtime "No keyword found").
- **Clean, broad release** — RES + GOV + AIX + EXEC + a full security sweep all landed together without destabilizing; every PR went in on green gates.
- **Fast, precise root-causing** — both the palette-duplicate (#53) and the keyword-reload churn were traced to exact source lines (`rf_knowledge.py` stem attribution; `RobotEditor` file-switch watcher) and fixed with pinning tests.
- **Architecture discipline held** — D1–D6 touched `flowConverter.ts` / `paletteView.ts` but kept `robotTextIO.ts` as the single parse/serialize source of truth; no round-trip corruption regressions.

## Challenges & growth areas

- **UI-visible behavior escaped unit tests** — *Thomas's named carry-forward lesson.* The palette double-display (#53) reached a release candidate because the dedup logic was implicit and unit tests didn't assert the rendered palette. Bugs that change the screen need a real-UI assertion.
- **Minimal fixtures hide reset-and-rebuild bugs** — a recurring class (also seen in the prior flow-editor epic and again with keyword loading): single-item / single-file fixtures don't surface the "reset to index 0 / full-state reload" failure modes. These only appear with ≥2 items and a real auth token.
- **Year-old dual-type-debt persists** — two parallel `RobotForm`/`RobotStep` declarations (`robotTextIO.ts` and `flow/flowConverter.ts`). The `kind` discriminator added this epic had to be applied to both. Adding any new field still means touching both or vue-tsc breaks.
- **Release-asset tooling friction** — `gh run download` and large asset uploads stalled/failed under the rtk wrapper (and `gh run download` is all-or-nothing on timeout). Cost real time during publish; now captured as a memory note (use `gh api .../artifacts/<id>/zip` per artifact; plain `gh` for uploads).

---

## Next epic preview — EXEC (RF Execution Configuration)

PRD exists (`planning-artifacts/exec-prd.md`); no architecture/stories yet. Surfaces RF's real execution levers: `robot` CLI args (EXEC-1, partially shipped), PreRunModifiers (EXEC-2), tag management (EXEC-3, partially shipped), unique ID/Long Name for Jira (EXEC-4), `__init__.robot` (EXEC-5), DataDriver/dynamic generation (EXEC-6 spike), best-practices research (EXEC-7 spike).

**Decision (Thomas):** **Start EXEC with the EXEC-7 research spike** — it sharpens the scope of EXEC-1..6 before committing to implementation, then proceed to architecture.

**Dependencies / readiness:** EXEC-1 and EXEC-3 already have a foothold from 0.11.0 (`5a43237`), so the run-dialog surface exists to build on. No blocking dependencies from the resources epic.

---

## Action items

| # | Action | Category | Owner | Success criteria |
|---|--------|----------|-------|------------------|
| 1 | Make ≥2-item / ≥2-file fixtures the default for flow-editor & explorer e2e | Process / Testing | Dev | New e2e fixtures seed ≥2 items; reset-and-rebuild bugs caught in CI not UI |
| 2 | Gate UI-visible behavior (dedup, visibility, ordering) with real-UI e2e assertions, not just unit tests | Testing | Dev/QA | Any palette/visibility change ships with an e2e that asserts the rendered result |
| 3 | Unify the dual `RobotForm`/`RobotStep` type decls before EXEC adds new fields | Tech Debt | Dev/Architect | Single shared type module; CLAUDE.md tech-debt note removed |
| 4 | Keep the release-asset playbook current (gh-api artifact download + plain-gh upload) | Documentation | Dev | Memory note + release-publish skill reflect the working path |

## Critical path before EXEC kickoff
- None blocking. EXEC can start with the EXEC-7 spike. Action item #3 (type unification) is **recommended-before** EXEC implementation but not a hard blocker for the spike.

## Readiness assessment
- **Testing & quality:** Green across all gates; gap is fixture richness (action items #1/#2).
- **Deployment:** v0.11.0 published, Latest, all assets attached. ✅
- **Stakeholder acceptance:** Thomas (Project Lead) drove and accepted the work hands-on. ✅
- **Technical health:** Stable; one known debt item (dual type decls) tracked.
- **Unresolved blockers:** None.

---

## Key takeaways
1. The win that mattered was the **experience arc** — burying users' own keywords and failing silently was the real problem; a pinned home + visible import + arg prefill fixed the *feeling*, not just the function.
2. **If it changes the screen, an e2e must assert it** — unit tests passed while the palette showed duplicates.
3. **Fixtures must be ≥2 items** to expose reset-and-rebuild bugs; this class keeps recurring.
4. Start EXEC lean with the **EXEC-7 spike** before committing implementation scope.
