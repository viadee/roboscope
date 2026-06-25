# Presentation Feedback (2026-06-17) — Epics + Stories

**Status**: Planning
**Date**: 2026-06-18
**Owner**: RoboScope core team
**Analyst**: Mary
**Source**: Field notes from the 2026-06-17 presentation (Provinzial, Daniel, team Q&A)

## Headline

Five raw feedback items from real users group cleanly into **four epics**:

1. **GOV — Deployment Governance & Feature Lockdown** — let operators disable feature areas (first: package management) per deployment, so end users on a managed/remote install can't (de)install packages.
2. **RES — Repository Resource Files** — make local/repo `.resource` keywords first-class (discover, autocomplete, execute).
3. **EXEC — Robot Framework Execution Configuration** — surface RF's real execution levers (CLI args, PreRunModifiers, tagging, `__init__.robot`, dynamic data) in the UI.
4. **AIX — AI Provider & Output Enhancements** — LiteLLM gateway + analysis verbosity control.

## Traceability — raw note → epic/story

| Raw note | Maps to |
|---|---|
| Disabling einzelner Komponenten (z.B. "Python Pakete verwalten" bei Provinzial); remote-managed, Endnutzer dürfen nicht (de)installieren | GOV-1, GOV-2, GOV-3, GOV-4 |
| Verbosity der KI-Analyse begrenzen | AIX-2 |
| (Daniel) Lokale/Repository Resources einlad- und nutzbar machen | RES-1..RES-4 |
| PreRunModifiers + Suite-Tagging | EXEC-2, EXEC-3 |
| robot.exe-Parameter übergebbar/verwaltbar | EXEC-1 |
| Eindeutige ID / "Long Name" → Jira-Assoziation | EXEC-4 |
| Inhalte in `__init__.robot` | EXEC-5 |
| DataDriver / dynamisch (z.B. aus Jira) Testfälle erzeugen | EXEC-6 |
| RF-"Magic" / Best-Practices aus der Doku in die UI (RF Certified Professional) | EXEC-7 |
| LiteLLM-Anbindung | AIX-1 |

---

## Epic GOV — Deployment Governance & Feature Lockdown

### Why this, why now
At Provinzial, Python environment installation is owned by a central administration team — and on a shared/remote RoboScope install, an end user clicking "uninstall package" mutates the **server's** environment for everyone. Today every authenticated user with the right role can install/uninstall/upgrade packages and trigger Docker builds (`environments/router.py`). Operators need a hard, deployment-level switch to take these affordances away, independent of user roles. This is a concrete deployment blocker for a named enterprise prospect.

### Stories

**GOV-1 — Feature-flag foundation**
As an operator, I want a server-side configuration that turns whole feature areas on/off, so I can tailor an install to my organization's governance.
- Flags resolved server-side from `app_settings` (admin-editable) with an **env-var override** that wins (for locked-down/remote installs the admin team controls); precedence documented.
- `GET /config/features` returns the resolved flag set; a frontend `useFeatureFlags()` composable gates UI.
- Unknown flags default to **enabled** (no silent feature loss on upgrade). Flag changes are audit-logged.

**GOV-2 — Lock package management**
As an operator, I want to disable package install/uninstall/upgrade and Docker build, so end users can't mutate managed environments.
- Behind a `packageManagement` flag: UI hides the install/uninstall/upgrade/build/retry/rfbrowser-init actions; the matching `environments` endpoints return **403** when off (defense in depth — UI hiding is not enough).
- Read paths (list packages, keyword cache) stay available so the rest of the app still works.
- Blocked attempts are audit-logged with user/IP.

**GOV-3 — Read-only Environments mode**
As an operator, I want a "view-only" environments mode, so users can see what's installed without changing it.
- Sub-mode of GOV-2: packages + versions + Docker image visible; all mutating controls disabled with a clear "managed by your administrator" hint (i18n EN/DE/FR/ES).

**GOV-4 — Configurable role floor for package ops**
As an operator who still allows package ops, I want to set the **minimum role** that may perform them, so only ADMINs (or a chosen role) can.
- Per-operation min-role setting (install / uninstall / upgrade / docker-build); enforced in the same dependency the endpoints already use.
- Defaults preserve today's behavior (no breaking change for existing installs).

### Epic acceptance gates
1. With the flag OFF, there is **no path** (UI, direct API, API token) to mutate an environment — pinned by a backend test that calls each endpoint and asserts 403.
2. Flags are discoverable and documented (CLAUDE.md gotcha + in-app docs + GitHub Pages); default-on so 0.10.x → next is non-breaking.
3. The "disabled" UX is consistent and localized across every affected surface.

### Non-goals
- Per-project (vs. per-deployment) feature flags — start global; revisit if a customer needs it.
- A full policy engine — this is a small, explicit flag set, not OPA.

---

## Epic RES — Repository Resource Files (.resource)

### Why this, why now
Mature RF teams keep shared keywords in `.resource` files imported via `Resource    ../common.resource`. RoboScope's keyword discovery today is libdoc-per-environment + partial project-keyword detection (`useKeywordSignatures.ts` order: project keywords > libdoc(env) > bootstrap). Daniel's ask: make **repo resource files** properly loadable and usable — discovery, autocomplete, and reliable execution.

### Stories

**RES-1 — Index repository `.resource` files**
As a test author, I want keywords defined in my repo's `.resource` files to be discovered, so I can use them like any other keyword.
- Parse `.resource` (and `.robot` keyword sections) in the project tree into a keyword index with names + signatures + source path.
- Refresh on file change / sync; cache keyed per repo.

**RES-2 — Resolve `Resource` imports for autocomplete**
As a test author, I want the editor + flow palette to suggest keywords from `Resource`-imported files, so I don't have to remember signatures.
- Follow the `Resource` import graph (transitively, with cycle guard) from the open file; surface those keywords in the palette under a "Project Resources" category.
- Signature resolution order stays RF-faithful: **project keywords > resources > libdoc(env) > bootstrap**.

**RES-3 — Resource keyword detail (signatures + docs)**
As a test author, I want argument hints and `[Documentation]` for resource keywords, so the detail panel and doc modal work for them too.

**RES-4 — Execution honors resource imports (verify + pin)**
As a test author, I want a run to resolve `Resource` imports identically across subprocess and Docker runners, so what autocompletes also runs.
- Verify current behavior; add a pinned e2e (a test that calls a resource keyword) for both runner types.

### Non-goals
- Authoring new `.resource` files via a dedicated wizard — out of scope; the existing file-create + editor suffices for v1.

---

## Epic EXEC — Robot Framework Execution Configuration

### Why this, why now
The biggest cluster of feedback is "let me drive RF the way I actually run it." Today the run dialog exposes target path, timeout, environment. Power users need the real `robot` levers: argument pass-through, PreRunModifiers, tagging, suite-init, and dynamic data generation. Several of these also unlock the Phase-6 Jira plugin (unique IDs / Long Name). EXEC-7 (research) should run **first** — it sharpens the scope of EXEC-1..6.

### Stories

**EXEC-1 — Manage `robot` CLI arguments per run / schedule**
As a power user, I want to pass and save `robot` arguments, so I can control selection and variables without leaving RoboScope.
- Curated, validated arg surface: `--include/--exclude` (tags), `--variable`, `--variablefile`, `--name`, `--settag`, `--rerunfailed`, plus a guarded free-text "advanced args" field with an allowlist + injection-safe construction.
- Args persist on the run config and on Schedules; echoed into the run record for reproducibility.

**EXEC-2 — PreRunModifier support**
As a power user, I want to apply `--prerunmodifier`s, so I can transform the suite before execution (tag injection, filtering, dynamic test creation).
- Configure one or more prerun modifiers (built-in helpers + project-provided module path); resolved in the run's environment.
- Documented security note: modifiers run arbitrary code in the env (same trust boundary as the tests themselves).

**EXEC-3 — Suite/test tag management in the UI**
As a test author, I want to view and edit tags and run "by tag", so I can organize and select tests.
- Surface tags in Explorer/Flow editor; "Run by tag" wired to EXEC-1's `--include/--exclude`.

**EXEC-4 — Unique test ID / Long Name surfacing (Jira foundation)**
As a QA lead, I want each test's stable Long Name / unique ID exposed, so I can associate it with a Jira issue.
- Compute + display the RF **Long Name** (`Suite.Sub.Test`); allow a stable external-ID mapping (tag convention or metadata). Lays groundwork for the Phase-6 Jira plugin — no Jira API in this story.

**EXEC-5 — `__init__.robot` (suite initialization) support**
As a test author, I want to edit folder-level suite setup/teardown/metadata, so suite-init behaves correctly in the UI.
- Explorer recognizes `__init__.robot`; Flow/Visual editor edits Suite Setup/Teardown/Metadata/Documentation at the directory level; round-trips faithfully.

**EXEC-6 — DataDriver / dynamic test generation (SPIKE → feature)**
As an advanced user, I want data-driven tests generated at runtime (e.g. from a data file or Jira), so I don't hand-write repetitive cases.
- **Spike first**: evaluate `robotframework-datadriver` + the PreRunModifier path (EXEC-2) as the generation mechanism; produce a feasibility note before committing the feature.

**EXEC-7 — RF best-practices research → UI backlog (SPIKE)**
As the product team, I want RF's documented best practices and "magic" (filename rules, `__init__`, tagging, selection, the RF Certified Professional syllabus) distilled into concrete UI surfacings, so we guide users toward correct usage.
- Output: a prioritized backlog of small UI improvements (warnings, hints, defaults) feeding EXEC-1..6 and beyond. **Do this first in the epic.**

### Non-goals
- A full RF CLI passthrough (every flag) — curate to what's safe + meaningful; advanced free-text is the escape hatch.
- Building a Jira integration in EXEC-4 — that's the Phase-6 plugin; EXEC-4 only exposes the ID surface.

---

## Epic AIX — AI Provider & Output Enhancements

### Why this, why now
Two small, high-leverage AI asks. The provider layer (`ai/llm_client.py`) already speaks OpenAI-compatible for openai/openrouter/ollama, so LiteLLM (an OpenAI-compatible gateway) is a thin addition. Verbosity control rides the prompt/`max_tokens` plumbing the just-shipped localized analysis already touches.

### Stories

**AIX-1 — LiteLLM provider type**
As an admin, I want to point RoboScope at a LiteLLM gateway, so I can use any model my org proxies (and centralize keys/spend).
- New `litellm` provider type reusing `_call_openai_compatible` with a configurable `base_url` + model passthrough; key handling matches existing providers (Fernet-encrypted). i18n + provider-form entry; one happy-path test against a mocked endpoint.

**AIX-2 — AI analysis verbosity control**
As a user, I want to choose how detailed the failure analysis is, so I get a tight summary or a deep dive on demand.
- Verbosity setting (e.g. `concise` / `standard` / `detailed`) mapped to prompt guidance + `max_tokens`; selectable per analysis with a default in settings. Composes with the existing language directive.

### Non-goals
- Streaming AI output — separate concern.
- Per-provider model auto-discovery — out of scope for AIX-1.

---

## Sequencing recommendation

| Wave | Stories | Rationale |
|---|---|---|
| **1 — Quick wins / unblockers** | GOV-1, GOV-2, GOV-3 · AIX-2 · EXEC-7 (spike) | GOV unblocks a named prospect; AIX-2 is cheap; EXEC-7 sharpens the whole EXEC epic before we build it. |
| **2 — Core enablers** | GOV-4 · RES-1, RES-2 · AIX-1 · EXEC-1 | Resource discovery + CLI args are broadly useful; LiteLLM is small. |
| **3 — Depth** | RES-3, RES-4 · EXEC-2, EXEC-3, EXEC-5 | Build on wave-2 foundations. |
| **4 — Bigger bets** | EXEC-4 (→ Phase-6 Jira) · EXEC-6 (DataDriver) | Larger / dependent on spikes + Jira plugin. |

## Open questions for the team
1. **GOV scope**: global (per-deployment) flags only for v1, or do any customers need per-project disabling?
2. **EXEC-1 arg surface**: which exact `robot` flags are in-scope for the curated UI vs. the advanced free-text field?
3. **Jira (EXEC-4)**: is the unique-ID convention a tag (`jira:PROJ-123`) or RF metadata — and does this wait for the Phase-6 Jira plugin or lead it?
4. **DataDriver (EXEC-6)**: which real customer workflow drives this (the "generate from Jira tickets" case)? That defines the spike's success criteria.
