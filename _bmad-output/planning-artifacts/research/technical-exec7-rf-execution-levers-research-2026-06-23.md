---
stepsCompleted: [1]
inputDocuments:
  - _bmad-output/planning-artifacts/exec-prd.md
  - backend/src/execution/runners/subprocess_runner.py
  - backend/src/execution/runners/docker_runner.py
  - backend/src/execution/schemas.py
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'EXEC-7 — Robot Framework execution levers → prioritized UI backlog'
research_goals: 'Sharpen the scope of EXEC-1..6 with a feasibility + prioritized backlog grounded in RF docs and the current RoboScope runner'
user_name: 'Thomas'
date: '2026-06-23'
web_research_enabled: true
source_verification: true
---

# Research Report: EXEC-7 — Robot Framework Execution Levers → UI Backlog

**Date:** 2026-06-23
**Author:** Thomas (with Mary, Analyst)
**Research Type:** Technical (spike)
**Purpose:** EXEC-7 is the de-risking spike for Epic EXEC. It verifies how RF's real execution levers work against current docs, measures them against what RoboScope's runner already does, and produces a prioritized backlog that sharpens EXEC-1..6 before we commit to architecture.

---

## Research Overview & Methodology

Two-sided research: (1) **verify RF capabilities** against current Robot Framework docs (RF 7.4.x is current), and (2) **read the ground truth** of what RoboScope's execution layer already supports, so the backlog is grounded in the real gap — not a greenfield wishlist.

Sources verified via web; codebase facts read directly from `backend/src/execution/`.

---

## Ground truth — what RoboScope already does (read from code)

`subprocess_runner._build_command()` builds the `robot` invocation today:

```
python -m robot --outputdir <dir> --loglevel INFO --consolecolors off
  [--include <tag>]...        # from tags_include (comma-split)
  [--exclude <tag>]...        # from tags_exclude (comma-split)
  [--listener <spec>]...      # ALREADY WIRED (subprocess only)
  [--variable KEY:VALUE]...   # from variables dict
  <target_path>
```

`RunCreate` schema fields: `target_path`, `branch`, `tags_include`, `tags_exclude`, `variables`, `parallel`, `max_retries`, `timeout_seconds`, `runner_type`.

**Two findings that change the EXEC plan:**

1. **EXEC-1 (CLI args) and EXEC-3 (tags) already have a foothold.** Tags shipped in 0.11.0 (`5a43237`); the command builder is an explicit *allow-list*, not a freeform string. The EXEC-1 question is therefore **not** "can we pass args" but "do we expose a *curated set of safe flags* or a *freeform escape hatch* — and with what validation."
2. **A `--listener` is already wired in the subprocess runner.** This is the single most important feasibility signal for the whole epic, because:
   - **DataDriver (EXEC-6) IS a listener** (Listener API v3) — it plugs into the exact mechanism already present.
   - **PreRunModifier (EXEC-2) is a sibling CLI option** (`--prerunmodifier`) with the same "module name or Python object" calling convention as `--listener`.
   So EXEC-2 and EXEC-6 share plumbing with code that already exists.

**Parity gap (flag for architecture):** `docker_runner` builds `--include/--exclude/--variable` but **NOT `--listener`** (subprocess-only today). Any EXEC-2/EXEC-6 work that relies on listeners/modifiers must close this runner-parity gap or explicitly scope to subprocess-only.

---

## Verified RF facts per lever

### EXEC-1 — `robot` CLI argument pass-through
RF accepts a large, stable option set (`--include`, `--exclude`, `--variable`, `--variablefile`, `--name`, `--randomize`, `--rerunfailed`, `--listener`, `--prerunmodifier`, `--prerebotmodifier`, `--maxerrorlines`, …). Long-option names map cleanly to the Python `robot.run()` API (option names = long names without hyphens; repeatable options take lists). **Feasibility: trivial-to-moderate.** The runner is already structured for it. Risk is **security/footgun**, not capability — freeform args could inject `--pythonpath`, `--listener arbitrary.py`, output-path traversal, etc.

### EXEC-2 — PreRunModifier
`--prerunmodifier` takes a `SuiteVisitor` subclass (class name or path; repeatable; supports named args since RF 4.0). Modifies the in-memory suite **before** execution (e.g. inject teardowns, filter/reorder tests, tag dynamically). Same value-passing convention as the already-wired `--listener`. **Feasibility: moderate.** Plumbing exists; the open question is *where the modifier code lives* (user-authored file in repo? curated RoboScope-provided modifiers? both) and the runner-parity gap.

### EXEC-3 — Suite/test tag management
`--include`/`--exclude` with pattern/partial matching already shipped. The remaining EXEC-3 surface is *discovery* — surfacing the tags that exist in the repo's suites in Explorer/Flow editor so "run by tag" is pick-from-list, not free-text. **Feasibility: easy** (tag discovery can reuse the libdoc/keyword-introspection pattern, or parse `[Tags]`/`Force Tags`/`Default Tags`/`Test Tags`).

### EXEC-4 — Unique test ID / Long Name (Jira foundation)
RF assigns stable structural IDs in `output.xml` (`s1`, `s1-t1`, …) and each test has a **long name** (`Parent Suite.Child Suite.Test Name`). Custom suite names via the `Name` setting (RF 6.1+). Jira tools (Xray, AIO) key off either the long name or **tags carrying issue keys** (e.g. `SCRUM-TC-408`). **Feasibility: easy to surface** (read-only: show long name + id in the run/report detail). The actual Jira *integration* is explicitly Phase-6 and out of scope — EXEC-4 only exposes the ID surface.

### EXEC-5 — `__init__.robot` (suite initialization)
A directory suite uses `__init__.robot` for `Suite Setup`/`Suite Teardown`/`Name`/imports that apply to the whole directory. Same syntax as a test file minus the test cases section; not all settings supported. **Feasibility: moderate** — this is mostly an *editor* feature (let users author/edit `__init__.robot` for a suite directory), reusing the existing `.robot` parse/serialize stack (`robotTextIO.ts`), not a runner change. Watch for the "no test cases section" constraint in the editor.

### EXEC-6 — DataDriver / dynamic test generation
`robotframework-datadriver` (Snooz82, active) creates N test cases at runtime from a CSV/Excel data source against a `[Template]` keyword, via **Listener v3**. Excel needs the `XLS` extra. **Feasibility: moderate-to-high effort but low *mechanism* risk** — it's a listener (plumbing exists) plus a third-party dependency to vendor (offline-only constraint!) and a data-source UI. **Recommend a sub-spike before committing**: confirm offline wheel vendoring + the `[Template]` authoring flow in the Flow Editor.

---

## Prioritized EXEC backlog (the EXEC-7 deliverable)

Scored by **value × (1/effort) × unblocks-others**, grounded in the runner reality above.

| Rank | Story | Why first | Effort | Notes / scope sharpener |
|------|-------|-----------|--------|-------------------------|
| **1** | **EXEC-3 tag discovery** | Tags already execute; discovery turns free-text into pick-from-list — high UX value, low effort, reuses introspection pattern | **S** | Parse `[Tags]`/`Test Tags`/`Force Tags`/`Default Tags`; surface in Explorer + run dialog |
| **2** | **EXEC-1 curated safe-flags + freeform escape hatch** | Biggest demand; runner already an allow-list. Ship a *curated* set (`--randomize`, `--rerunfailed`, `--variablefile`, `--name`, `--maxerrorlines`) with a gated freeform field | **M** | **Security is the work, not capability.** Deny-list dangerous flags (`--pythonpath`, `--listener`, output-path escapes); governance-flag the freeform field (Epic GOV pattern) |
| **3** | **EXEC-4 long-name / id surfacing (read-only)** | Cheap, unblocks the Phase-6 Jira story, no runner change | **S** | Show long name + `s1-t1` id in run/report detail; document the tag=issue-key convention |
| **4** | **Runner `--listener` parity (subprocess↔docker)** | Foundational: EXEC-2 and EXEC-6 both need it; docker runner lacks it today | **S/M** | Pure plumbing; pin with a parity test asserting both runners build identical arg lists |
| **5** | **EXEC-5 `__init__.robot` editor support** | Editor feature, reuses `robotTextIO.ts`; independent of runner | **M** | Enforce "no test cases section"; surface `Suite Setup`/`Teardown`/`Name` |
| **6** | **EXEC-2 PreRunModifier** | Real power-user lever; needs #4 first + a decision on where modifier code lives | **M** | Curated RoboScope-provided modifiers first; user-authored path later |
| **7** | **EXEC-6 DataDriver** *(sub-spike → feature)* | Highest effort + offline-vendoring + dependency risk; do the sub-spike before committing | **L** | Confirm offline wheel vendoring (offline-only constraint!) + `[Template]` Flow-Editor authoring |

### Scope sharpeners for architecture (CA)
1. **EXEC-1 is a security story.** Frame the architecture around an allow-list + deny-list + a GOV-gated freeform field, not "pass a string to robot."
2. **Close the listener-parity gap (#4) before EXEC-2/EXEC-6.** Make it an explicit prerequisite story.
3. **EXEC-5 lives in the editor stack, not the runner.** Keep it on the `robotTextIO.ts` round-trip contract.
4. **EXEC-6 needs an offline-vendoring sub-spike.** The DataDriver wheel (and its XLS extra) must be bundled like `roboscopeheal` — don't assume PyPI at runtime.
5. **EXEC-4 ≠ Jira integration.** Only the ID surface; integration is Phase-6.

---

## Recommendation

EXEC is **well-scoped and low-mechanism-risk** — the runner's existing allow-list + wired `--listener` de-risk most of it. Sequence the epic as **#1→#4** above (discovery, curated args, id surfacing, listener parity) as a coherent first wave, then tackle #5/#6/#7 with EXEC-6 gated behind its own sub-spike.

**Next BMAD step:** `[CA] bmad-create-architecture` for EXEC, carrying the five scope sharpeners above as architectural inputs.

---

## Sources
- [RF User Guide — Configuring Execution](https://github.com/robotframework/robotframework/blob/master/doc/userguide/src/ExecutingTestCases/ConfiguringExecution.rst)
- [RF API docs (7.4.x) — robot package / SuiteVisitor](https://robot-framework.readthedocs.io/en/stable/autodoc/robot.html)
- [RF — Creating test suites / `__init__.robot`](https://github.com/robotframework/robotframework/blob/master/doc/userguide/src/CreatingTestData/CreatingTestSuites.rst)
- [RFCP Syllabus — Initialization files](https://robotframework.org/robotframework-RFCP-syllabus/docs/chapter-04/init_files)
- [robotframework-datadriver (Snooz82)](https://github.com/Snooz82/robotframework-datadriver) · [PyPI](https://pypi.org/project/robotframework-datadriver/)
- [DataDriven tests — docs.robotframework.org](https://docs.robotframework.org/docs/testcase_styles/datadriven)
- [Xray — Taking advantage of Robot XML reports (long name / id / tags)](https://confluence.xpand-it.com/display/XRAY21/Taking+advantage+of+Robot+XML+reports)
- [RF issue #3255 — access to include/exclude tags from ListenerV3/PreRunModifier](https://github.com/robotframework/robotframework/issues/3255)
