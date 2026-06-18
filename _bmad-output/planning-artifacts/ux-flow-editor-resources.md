---
workflowType: 'ux-design'
status: 'ready'
scope: 'flow-editor-keyword-palette-and-resources'
project_name: 'roboscope'
author: 'Sally (UX) + Thomas'
date: '2026-06-18'
relatedArtifacts:
  - res-prd.md
  - res-architecture.md
note: 'Scoped spec — does NOT supersede ux-design-specification.md (Phase 4).'
---

# UX Design — Flow Editor Keyword Palette & Custom Resources

## The story we're fixing

> Thomas keeps his team's shared keywords in `resources/common.resource`. In the
> Flow Editor he opens `tests/login.robot`, finds **Open Login Page** in the
> palette, clicks **+**. The node drops onto the canvas — and three things happen
> in silence: "Libraries (0)" ticks to "(1)", a `Resource` import is written into
> Settings, and the detail panel opens with an **empty** "+ add argument" even
> though the keyword takes `${url}`. It *works*. But Thomas can't *see* that it
> wired the import, his own keyword is buried as one of 18 look-alike categories,
> the long name is clipped with no tooltip, and he's re-typing an argument the
> tool already knows. The magic isn't trustworthy, and his own code doesn't feel
> first-class.

The goal: make **using your own repository keywords feel direct, legible, and
trustworthy** — the import visible, the signature respected, the palette yours
to shape.

## Current-state findings (observed live, 2026-06-18)

| # | Finding | Evidence |
|---|---------|----------|
| F1 | **Silent auto-import** — inserting a `.resource` keyword writes the `Resource` import with no acknowledgement; the only signal is the "Libraries" counter. | `FlowEditor.addLibrary` emits `libraries-changed` but no toast/inline confirmation. |
| F2 | **Resource conflated with Library** — `.resource` imports live in the panel labelled "Libraries"; RF distinguishes `Library` vs `Resource`. | `form.settings` Library+Resource share the "Bibliotheken" panel. |
| F3 | **Arguments not pre-filled** — the inserted resource-keyword node shows empty "+ add argument" despite a known `[Arguments] ${url}` signature; Library keywords *do* get arg slots. | Palette shows "Open Login Page (1)"; detail panel shows no `${url}` slot. |
| F4 | **Project keywords aren't first-class** — `PROJECT: COMMON.RESOURCE` (shouty, basename only, no path, no file/resource icon) sits as one of ~18 categories. | Palette category list. |
| F5 | **Long names break down** — `.palette-item-name` is `ellipsis/nowrap` in a 220px rail with **no `title` tooltip**; descriptive resource names get clipped unrecoverably. | `.palette-item-name` CSS; 220px `.keyword-palette`. |
| F6 | **No sort control** — categories are usage-then-fallback ordered; the user can't choose (e.g. alphabetical, project-first). | `libCats.sort(...usage...)` hardcoded. |
| F7 | **No "what's shown" filter** — non-installed libraries are always offered as "examples"; the user can't hide them to see only what's imported / their own. | `_ALWAYS_VISIBLE_LIBS` + `isExamples` always rendered. |

## Design directions

### D1 — Resources are first-class & distinct (F2, F4)

Split the palette's project/resource grouping out of the generic library list and
give it its own, top-pinned section with a file glyph and the **relative path**
as a subtitle. Separate the imports panel into **Resources** and **Libraries**.

```
┌─ Keywords ───────────────────[⇅][▼ filter]─┐
│ [ search… ]                                 │
│                                             │
│ ▾  YOUR RESOURCES                           │   ← own section, pinned, not SHOUTY
│   📄 common.resource    · resources/        │   ← path subtitle, file glyph
│       Open Login Page                 (1)   │
│       Submit Credentials                    │
│   📄 keywords.resource  · resources/shared/ │
│       …                                     │
│ ──────────────────────────────────────────  │
│ ▸  BuiltIn                            537   │
│ ▸  Browser              [+ lib]       144   │
│ …                                           │
└─────────────────────────────────────────────┘

Settings panel (was "Libraries (1)"):
   Resources (1)  ▸  resources/common.resource          [↗ open] [×]
   Libraries (0)  ▸  —
```

**AC-D1**
- Project/resource keywords render in a dedicated, top-pinned "Your resources"
  group, grouped by file, each file showing its repo-relative directory as a
  subtitle and a file glyph (resource vs `.robot`).
- The Settings/imports panel shows **Resources** and **Libraries** as separate
  labelled lists; a `.resource` import never appears under "Libraries".
- No SHOUTY all-caps for the user's own files.

### D2 — Visible import acknowledgement (F1)

When inserting a keyword auto-adds a `Resource` (or `Library`) import, surface it.

```
        ┌─────────────────────────────────────────────┐
        │ ✓ Imported  resources/common.resource        │
        │   so "Open Login Page" resolves at runtime.   │
        └─────────────────────────────────────────────┘   (toast, 4s, undo-able)
```

Plus an inline one-time pulse on the new **Resources (1)** badge.

**AC-D2** *(decided: plain toast, no Undo)*
- Adding an import via keyword insert shows a localized toast naming the file
  (EN/DE/FR/ES/ZH) — *only* when an import was actually added (not on dedupe).
- No Undo affordance (kept deliberately simple — the import is visible in the
  Resources panel and removable there).
- No toast for BuiltIn / same-file / already-imported inserts.

### D3 — Respect the known signature (F3)

A project/resource keyword carries `[Arguments]` (the parser already extracts
them). Pre-fill the node's argument slots exactly like a Library keyword.

```
KEYWORD  Open Login Page
ARGUMENTS
   url   [ ${BASE_URL}              ]        ← pre-seeded slot from [Arguments] ${url}
   [+ add argument]
```

**AC-D3**
- Inserting a project/resource keyword pre-creates one argument slot per declared
  `[Arguments]` entry, labelled with the arg name, defaults shown where present.
- Round-trips to `.robot` correctly (positional/named).

### D4 — Long names stay legible (F5)

```
│   Open Login Page And Wait For …   (2) │   ← clip + ALWAYS a title= tooltip
│   └ hover ─► "Open Login Page And Wait For Dashboard"
```

**AC-D4**
- Every palette item carries a `title` (full keyword name) so a clipped name is
  recoverable on hover.
- The arg-count / "+ lib" badges never wrap or overlap the name; name flexes,
  badges stay pinned right.
- Consider a 2-line clamp for the user's own resource keywords (they trend long).

### D5 — Sort control (F6)

A compact ⇅ control in the palette header: **Most used** (default) · **A–Z** ·
**Project first**. Persisted per user (localStorage).

**AC-D5**: selecting a sort reorders categories live; choice persists across reloads;
"Your resources" stays pinned above libraries regardless (or honors "A–Z" if chosen).

### D6 — "What's shown" filter (F7) — *adaptive default*

A ▼ filter button: checkboxes for **Your resources**, **Imported libraries**,
**Example libraries (not installed)**, **BuiltIn**. A subtle count shows when a
filter is hiding things.

```
[▼ Filter]
  ☑ Your resources
  ☑ Imported libraries
  ☐ Example libraries (not installed)   ← Thomas's case: hide the noise
  ☑ BuiltIn
        "Hiding 12 example libraries · clear"
```

**The default is adaptive** (Thomas's call, 2026-06-18): the palette guesses
whether the user is in *discovery mode* or *building a real test* and chooses the
starting filter accordingly, so a beginner sees the rich example-library catalogue
while someone working a real suite isn't drowned in not-installed noise.

| Situation | Default filter | Rationale |
|-----------|----------------|-----------|
| Repo has **no environment** yet | **Everything** (incl. example libs) | Pure discovery — the example libs are the menu of "what's possible". |
| Repo has an env **and** the open file is a *mini / fresh* file | **Everything** | Still exploring; don't prematurely hide options. |
| Repo has an env **and** the open file is *sophisticated* | **Imported-only** (Your resources + Imported libraries + BuiltIn; example libs hidden) | The user knows their stack; surface what actually resolves at runtime. |

**"Sophisticated" heuristic** (cheap, client-side, no backend call): the open file
counts as sophisticated when it **already imports ≥1 Library/Resource** OR has
**≥ ~5 steps** across its test cases/keywords. Otherwise it's "mini/fresh". (The
two thresholds live in one place so they're tunable; pin them in a unit test.)

**AC-D6**
- Initial filter state is derived from the table above on first open of a file
  (env presence + the sophisticated heuristic); no flicker (decide before first
  paint of the category list).
- A **manual override persists** (localStorage) and wins over the adaptive default
  for that user thereafter — the heuristic only seeds the *first* experience.
- Toggles filter the visible categories live; an always-visible hint
  ("Hiding N example libraries · clear") whenever categories are hidden, so
  nothing feels "missing" by accident.
- Example libraries are never *removed* from discoverability — hiding is reversible
  in one click and announced.

## Priority

| Wave | Items | Why |
|------|-------|-----|
| **1 — Quick wins** | D2 (import toast), D3 (arg pre-fill), D4 (title tooltip) | Small, high-trust; D3 removes real re-typing; all low-risk. |
| **2 — Structure** | D1 (resources first-class + split panel), D6 (filter) | Medium; reshapes the palette mental model. |
| **3 — Polish** | D5 (sort), D1 path/preview | Nice-to-have refinements. |

## Decisions (locked 2026-06-18, with Thomas)

These resolve the former open questions; the ACs above already reflect them.

1. **D1 — separate pinned section.** Resources get their own top-pinned "Your
   resources" group (file glyph + relative-path subtitle), and the Settings panel
   splits into distinct **Resources** and **Libraries** lists. *Not* a mere
   relabel of "Libraries → Imports".
2. **D2 — plain toast, no Undo.** A localized confirmation toast only when an
   import was actually added; no Undo affordance (removal lives in the Resources
   panel).
3. **D6 — adaptive imported-only default.** For repos *with* an environment, a
   *sophisticated* open file defaults to imported-only (example libs hidden);
   fresh/mini files and env-less repos default to showing everything for
   discovery. A manual override persists and wins thereafter. (Heuristic:
   ≥1 import OR ≥~5 steps ⇒ sophisticated.)

## Implementation status (all waves shipped 2026-06-18)

All six directions are implemented, unit-tested, type-checked, prod-built, and
covered by real-UI E2E.

| Item | What landed | Where |
|------|-------------|-------|
| **D1** | Pinned "Your resources" palette section (file glyph + relative-path subtitle, no SHOUTY) via a `kind` discriminator; imports panel split into labelled **Resources** / **Libraries** lists. | `KeywordPalette.vue`, `FlowEditor.vue` (`resourceImportEntries`/`libraryImportEntries`), i18n `resourcesSectionLabel`/`resourcePanelLabel`/`librariesPanelLabel` |
| **D2** | `addLibrary` returns the kind it added (or `false`); insert + drag paths fire a localized import toast only when an import was actually added. No Undo. | `FlowEditor.vue` (`notifyImportAdded`), i18n `importAdded.*` |
| **D3** | Inserting a keyword pre-seeds one empty slot per **required** positional arg from its signature. | `FlowEditor.vue` (`prefillRequiredArgs`), `FlowEditorPrefillArgs.spec.ts` |
| **D4** | Every palette item carries a `title` (full name); name flexes, badges/argcount pinned right. | `KeywordPalette.vue` |
| **D5** | Header sort control (Most used / A–Z / Imported first), persisted in localStorage; resources stay in their pinned section. | `paletteView.ts::sortLibraries`, i18n `sort.*` |
| **D6** | Filter dropdown (resources / imported libs / example libs / BuiltIn) with the **adaptive default** (env + sophisticated heuristic ≥1 import OR ≥5 steps) and a persisted manual override + "{n} hidden · show all" affordance. | `paletteView.ts` (`adaptiveDefaultFilter`, `isSophisticatedFile`, `applyFilter`, `hiddenCount`), i18n `filter.*` |

**Tests** — `PaletteView.spec.ts` (heuristic/filter/sort/persistence), `FlowEditorPrefillArgs.spec.ts` (D3), `e2e/tests/flow-editor-resource-ux.spec.ts` (D1/D2/D3/D5/D6 real UI). Full vitest suite 851 green; prod build clean (no i18n escaping break); adjacent flow-editor E2E (12) + RES autoimport green.
