# EXEC.8 — DataDriver Offline-Vendoring Sub-Spike (feasibility note)

**Date:** 2026-06-23 · **Epic:** EXEC · **Gates:** EXEC.9 (feature)
**Outcome: GO** (with the offline-vendoring + CI-gate conditions below).

## Question

Can `robotframework-datadriver` (Listener v3 dynamic test generation) be shipped
under RoboScope's **offline-only** constraint, and does the `[Template]` authoring
flow fit the existing editor/runner? This spike de-risks EXEC.9 before committing.

## Findings

### 1. Mechanism fit — GO
- DataDriver is a **Listener v3** library (verified, EXEC-7 research). RoboScope's
  runner already emits `--listener` (EXEC.1), and EXEC.7 added the
  `--prerunmodifier`/curated-channel plumbing. DataDriver is activated as a
  **library import** in the suite (`Library  DataDriver  file=data.csv`) plus a
  `[Template]` test — NOT a CLI listener — so no runner change is required to
  *run* it; it rides the normal robot invocation. The resolver/runner seam is
  unaffected.
- The data source is repo-relative → reuse the existing `_safe_resolve`
  path-confinement (no new sandbox needed).

### 2. Offline vendoring — GO, mirrors `roboscopeheal`
- Pattern already proven in `backend/pyproject.toml` for
  `robotframework-roboscopeheal`: declare the dep, vendor the wheel, and the
  offline build script drops it into the bundle's `wheels/` for
  `pip install --no-index --find-links wheels/`.
- **Conditions for EXEC.9:**
  1. Add `robotframework-datadriver` (pin a version, e.g. `>=1.11,<2`) to
     `dependencies`. The **XLS extra** (`robotframework-datadriver[XLS]`) is
     required for `.xlsx`; decide whether to vendor it (adds `openpyxl`/`xlrd`).
     Recommend **CSV-first** (no extra) for EXEC.9, XLS as a follow-up.
  2. Vendor the wheel(s) into `wheels/` via the offline build scripts (mac/linux
     `.sh` + windows `.ps1`), exactly like the roboheal wheel.
  3. **CI gate** (mirror roboheal Gate 6/7): assert `import DataDriver` succeeds
     in the built offline bundle. Without this gate the absence only surfaces on
     an air-gapped customer install — the worst place (FMEA "production-biter").

### 3. Authoring flow — GO with editor follow-up
- A DataDriver suite = `Library  DataDriver  <source>` import + a single
  `[Template]` test + an external CSV/Excel. The `[Template]` data-row authoring
  already exists in the Flow Editor (`RobotTestCase.templateRows`, per CLAUDE.md).
  The new editor surface is: the **Library import + data-source path**, which is
  ordinary settings/imports editing. No round-trip contract change.

## Risks / non-goals
- **XLS parser surface**: pin the version; CSV-first keeps the dependency tree
  minimal for the first cut.
- **Governance**: gated behind `executionDataDriver` (already registered,
  default-OFF, EXEC.2).
- Generating tests *from Jira* (raw feedback note) is explicitly out of scope —
  Phase-6.

## Recommendation for EXEC.9
GO, **CSV-first**, behind `executionDataDriver`, with the vendored wheel + the
offline `import DataDriver` CI gate as hard acceptance criteria. EXEC.9 cannot be
verified-complete until the wheel is vendored (a network/artifact step), so its
implementation is: (a) dependency + vendoring + CI gate, (b) editor import/data
-source surface, (c) e2e behind the flag.
