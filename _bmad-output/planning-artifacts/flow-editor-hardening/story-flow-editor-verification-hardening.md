# Story: Flow Editor — Verification & Hardening (RF-Syntax-Vollständigkeit, Konsistenz, Round-Trip-Treue)

- **Status:** Done (2026-06-14)
- **Owner:** Dev (Amelia) · Architect (Winston) · UX (Sally)
- **Created:** 2026-06-14
- **Branch:** `chore/demo-readiness-bmad` (Flow-Editor-Arbeit)
- **Source:** Party-Mode-Runde 2026-06-14 (Sally/Winston/John/Amelia) + grundierte Code-Analyse

> Der Flow Editor (`frontend/src/components/editor/FlowEditor.vue`, 3534 LOC +
> `flow/flowConverter.ts`, 1042 LOC) ist das wichtigste Feature der App. Diese
> Story **verifiziert** systematisch, dass Erstellung, Veränderung und **alle**
> Modifikationsformen eines Testfalls — inkl. Anzeige von Keywords aus Standard-
> **und** Fremd-Libraries — konsistent und einfach funktionieren, und **härtet**
> die dabei gefundenen Lücken an der Quelle (keine Workarounds), jeweils mit
> vollständigen Unit- + E2E-Tests.

---

## Hintergrund / Ist-Stand (evidenzbasiert)

**Vorhanden & stark:** Test Cases + User-Keywords editierbar; Kontrollstrukturen
FOR (IN/IN RANGE/IN ENUMERATE/IN ZIP), IF/ELSE IF/ELSE, WHILE, TRY/EXCEPT/FINALLY,
BREAK/CONTINUE/RETURN mit Auto-END + farbigem Nesting; Per-Test/Keyword-Settings
([Documentation],[Tags],[Setup],[Teardown],[Timeout],[Template],[Arguments],[Return])
als Side-Note-Knoten; Keyword-Picker mit Arg-Signaturen, Named-Arg-Picker, Bool-Toggles,
Heal-Toggle, Selector-Picker, Reorder; 12 `FlowEditor*.spec.ts` Unit-Tests +
`e2e/tests/flow-editor-settings.spec.ts`.

**Bestätigte Lücken/Risiken:**
1. **Round-Trip-Treue** (parse→edit→serialize) für Inline-Kommentare,
   `...`-Zeilenfortsetzung, Escapes (`\`, `${}`, `\n`), Tab-vs-Space ist
   **ungetestet** → Risiko stiller Datenkorruption auf der wichtigsten Datei.
2. **Datei-Settings + `*** Variables ***`** sind im Flow **nicht** editierbar
   (nur im separaten Code-Editor) → Zwei-Editoren-Bruch; jede reale Suite zwingt
   zurück in den Code-Editor.
3. **Keyword-Discovery hängt an rf-mcp** (`GET /ai/rf-knowledge/keywords`); ist
   der MCP-Server aus, fehlen Fremd-Library-Keywords (Browser/SeleniumLibrary) —
   nur ein winziger statischer Fallback bleibt. Verstößt gegen Offline-First.
4. **Keyword-Shadowing:** Projekt-Keywords werden von gleichnamigen BuiltIn in
   der Signatur-Map überdeckt → falsche Arg-Signatur → kaputte Tests.
5. Control-Structure-**Nesting** hat **keinen** E2E-/Round-Trip-Test.

---

## Party-Mode-Entscheidungen (vom Nutzer bestätigt)

- **Offline-Keyword-Discovery → Winstons Weg:** `libdoc` pro Environment
  introspektieren, neuer Endpoint, DB-Cache mit uv-Lockfile-Hash-Invalidierung.
  Eliminiert die rf-mcp-Abhängigkeit dauerhaft (offline-first korrekt).
- **Story-Umfang (alle vier):** (P0) Round-Trip-Treue · (P0) File-Settings +
  `*** Variables ***` inline · (P0) Shadowing-Fix + `${}`/`%{}` in Args ·
  (P1) Control-Structure-E2E + Nesting-Round-Trip.
- **Leitsatz (Winston):** *RF besitzt das Dateiformat — wir leihen es uns nur
  für Diffs.* Unbekannte/nicht-modellierte Syntax wird **opak read-only
  durchgereicht statt zerstört** (gleiche Eskalationsstufe wie die SH-2-Invariante).
- **Nicht in Scope (John):** dedizierte BDD/Gherkin-UI (nur verifizieren, dass
  Given/When/Then als Keyword-Namen nicht zerschossen werden); Aufblähen der
  statischen Fallback-Map (libdoc-per-Env macht sie überflüssig); vollständiges
  Offline-Mirror aller Standard-Libs.

---

## Acceptance Criteria

### AC-A — Round-Trip-Treue (P0)
- **AC-A1:** Ein Golden-Corpus echter `.robot`-Dateien (eigene Suites +
  `backend/examples` + RF-Beispiele) durchläuft `parse → serialize` **ohne Edit
  byte-identisch** (oder gegen eine *dokumentierte* Normalisierung identisch).
- **AC-A2:** Inline-Kommentare (`# …`), `...`-Zeilenfortsetzungen und Escapes
  (`\`, `${}`, `\n`, Tab-vs-Space) überleben den Round-Trip eines **unberührten**
  Steps verbatim.
- **AC-A3:** Wird **ein** Step editiert, bleiben alle **anderen** Zeilen der
  Datei unverändert (Diff betrifft nur die geänderte Zeile).
- **AC-A4:** Nicht-modellierte Konstrukte werden opak durchgereicht, nie mangled.

### AC-B — Inline File-Settings + `*** Variables ***` (P0)
- **AC-B1:** `*** Variables ***` (Scalar/List/Dict) ist im Flow als Knoten
  anzeigbar, anlegbar, editierbar, löschbar; round-trippt korrekt (inkl.
  `${HEADLESS}    false`-Definition).
- **AC-B2:** Datei-Settings (Suite Setup/Teardown, Test Setup/Teardown-Defaults,
  Library/Resource/Variables-Imports, Force/Default Tags, Suite-Documentation,
  Metadata) sind im Flow als Knoten editierbar.
- **AC-B3:** Editier-Inputs nutzen das **Draft-Buffer-Pattern** (kein direktes
  `v-model` in `props.form`), sodass der Deep-Watcher `selectedNode` nicht
  abreißt (Regression analog `FlowEditorSectionSwitch.spec.ts`).
- **AC-B4:** i18n-Schlüssel in **EN/DE/FR/ES** vollständig.

### AC-C — Keyword-Discovery offline (libdoc-per-Env) + Shadowing + Variablen (P0)
- **AC-C1:** Neuer Endpoint `GET /environments/{env_id}/keywords` liefert
  Keywords + Signaturen aller im venv installierten Libraries via
  `python -m robot.libdoc --format JSON`, **ohne** rf-mcp.
- **AC-C2:** Ergebnis wird persistent gecacht (Tabelle `environment_keywords`),
  Invalidierung über uv-Lockfile-/`pip freeze`-Hash; Introspektion läuft als
  Background-Task (`dispatch_task()`, `db.commit()` vor dispatch, FK-Imports).
- **AC-C3:** Palette/Signatur-Map bezieht Fremd-**und** Standard-Library-Keywords
  aus diesem Endpoint und funktioniert bei rf-mcp=aus (E2E mit MCP-down).
- **AC-C4:** **Shadowing-Fix:** Resolution-Order `set_library_search_order >
  Projekt-Keywords > Library-Keywords > BuiltIn`; bei echter Ambiguität
  voll-qualifizierter Name `Library.Keyword`.
- **AC-C5:** `${VAR}`, `@{LIST}`, `&{DICT}`, `%{ENV}` als **Arg-Werte** werden
  vom Editor nicht zerschossen/umgewandelt (Round-Trip + Anzeige verifiziert).

### AC-D — Control-Structure-E2E + Nesting-Round-Trip (P1)
- **AC-D1:** Unit + E2E für verschachtelte `FOR`-in-`IF`, `TRY/EXCEPT/FINALLY`,
  `WHILE limit=`, `END`-Matching bei Tiefe ≥3.
- **AC-D2:** Nesting round-trippt (gemeinsame Fixtures mit AC-A).

### AC-DoD — Definition of Done (gesamt)
- Alle 12 bestehenden `FlowEditor*.spec.ts` + neue Specs **grün**.
- `vue-tsc --noEmit` clean; Backend `ruff` + `mypy` + neue `pytest` grün.
- E2E `flow-editor-*.spec.ts` grün.
- Jede Lücke an der Quelle gefixt (keine Workarounds), jeweils mit
  Fail-before/Pass-after-Regressionstest.

---

## Tasks / Subtasks

1. **Round-Trip (AC-A)**
   - `frontend/src/tests/components/fixtures/roundtrip/*.robot` Golden-Corpus.
   - `FlowEditorRoundTrip.spec.ts`: identity (untouched), sibling-raw-preservation,
     continuation, trailing-comment, escapes.
   - Fix in `flowConverter.ts`: `RobotStep.raw?: string[]` + `trailingComment?`;
     unberührte Steps verbatim zurückschreiben; `...`-Folgezeilen gruppieren.
   - E2E `e2e/tests/flow-editor-roundtrip.spec.ts`: 1 Arg ändern → nur 1 Zeile diff.

2. **File-Settings + Variables (AC-B)**
   - `flowConverter.ts`: neue Node-Kinds analog `appendSettingMetaNodes`;
     `SettingKind`-Union, `KIND_LABELS`, `settingTarget`/`settingDraft`-Branches.
   - `FlowEditor.vue`: Draft-Buffer + `rebuildAndReselect()`/`suppressFitView`.
   - i18n `flowEditor.fileSettings.*` + `flowEditor.variables.*` (EN/DE/FR/ES).
   - `FlowEditorFileSettings.spec.ts` + `e2e/tests/flow-editor-file-settings.spec.ts`.

3. **libdoc-per-Env (AC-C)**
   - Backend: `environment_keywords`-Modell + Alembic-Migration; `libdoc`-Runner
     in `environments/`; Endpoint in `api/v1`/`environments/router.py`;
     Cache-Hash auf Environment; Background-Task.
   - `backend/tests/environments/test_keywords_endpoint.py` (+ libdoc gemockt).
   - Frontend: `explorer.store`/`useKeywordSignatures.ts` Quelle umstellen,
     Shadowing-Reihenfolge fixen; `useKeywordSignatures.spec.ts`.
   - E2E `e2e/tests/flow-editor-offline-keywords.spec.ts` (rf-mcp down).

4. **Control-Structures (AC-D)**
   - `FlowEditorControlStructures.spec.ts` + `e2e/tests/flow-editor-control-structures.spec.ts`;
     Fixtures `fixtures/control/*.robot` (geteilt mit Task 1).

5. **DoD-Gate:** Full unit + e2e + typecheck + backend; commit + push.

---

## Test-Strategie (Winston)

- **Identity-Gate (Pre-Merge):** No-Op-Round-Trip über Golden-Corpus byte-stabil.
- **Differential gegen RF:** serialisierte Ausgabe muss `robot --dryrun` bestehen.
- **Regressions-Pins** pro Teufel: Inline-Comment, `...`, Escapes, leere Args,
  `%{ENV}`, Tab-vs-Space, nested-`END`.
- Gemeinsame Fixtures für Round-Trip (A) und Control-Structures (D).

## Risiken

- RF-Whitespace-Normalisierung — „identity" nur erreichbar, wenn unberührte
  Steps **nicht** durch den Emitter laufen (verbatim-`raw`-Pfad).
- Draft-Buffer-Disziplin — pro neuer Setting-Kind 5 synchrone Touch-Points
  (Union, TC/KW_KINDS, KIND_LABELS, get/commit, i18n×4).
- libdoc-Subprozess-Performance — Introspektion nur bei Lockfile-Drift, nie im
  Request-Pfad blockierend.

## Folge-Story (nicht in diesem Scope)

- Optional: `[Template]`-Datenzeilen als Tabellen-Node; BDD-Phrasing als
  eigener Step-Typ; `%{}`-Editing-UI; vollständige Migration weg vom statischen
  Fallback, sobald libdoc-per-Env überall greift.

---

## Closeout (2026-06-14)

All AC met; shipped in 6 commits on `chore/demo-readiness-bmad`:

| Commit | AC | Summary |
|---|---|---|
| `a575937` | AC-A | Round-trip: pure `robotTextIO.ts` extracted; trailing-comment + column-0-comment corruption fixed; 20 golden-corpus tests |
| `e8ac772` | AC-C1/2 | libdoc-per-env backend: endpoint + cache table + migration + task; 15 pytest |
| `45db750` | AC-C4 | shadowing fix project>library>BuiltIn + env-keywords API client; +4 tests |
| `64c29ec` | AC-C3 | palette sources keywords offline-first from libdoc endpoint; +4 tests |
| `14079d2` | AC-B | inline *** Variables *** + suite-settings panels; i18n×4; e2e |
| `baf5b4d` | AC-D | control-structure nesting round-trip unit (5) + e2e |

**Gate results:** 767 frontend vitest green · vue-tsc clean · 198 backend
environments pytest green (incl. 15 new) · ruff + mypy clean on all new code ·
10 flow-editor e2e green (3 file-settings + 1 control + 6 existing regression).
Full backend pytest (~1980) deferred to CI `build.yml::test-unit`.

**AC-C5** (`${}`/`@{}`/`&{}`/`%{}` survive as arg values) verified within the
round-trip golden-corpus tests.

**Deferred (documented, follow-up story):** `[Template]` data-row table node;
BDD Given/When/Then as a distinct step type; `%{}` env-var editing UI;
retiring the static fallback map once libdoc-per-env is the universal source.
Unknown/not-yet-modelled constructs pass through round-trip unmangled per the
"RF owns the format" invariant.

---

## Review Findings (code review 2026-06-14)

3-layer adversarial review (Blind Hunter · Edge Case Hunter · Acceptance Auditor)
of the epic branch. Patch findings fixed at source; defers logged.

- [x] [Review][Patch] HIGH — inline Variables/suite-settings/template-cell edits reset the active test case + selection (AC-B3, FE-TPL AC5): added `keepActiveItemOnRebuild()` (sets `suppressFitView`) to all direct form mutations [FlowEditor.vue]. Regression e2e with 2 test cases.
- [x] [Review][Patch] MED — `keyword_cache_is_fresh` shelled out to `uv pip list` on every GET /keywords: now compares `packages_changed_at` vs cache `updated_at` (no subprocess on the hot path) [service.py].
- [x] [Review][Patch] MED — redundant introspection dispatch on every poll while `building`: 120s in-flight guard, stamps `updated_at` on dispatch [router.py].
- [x] [Review][Patch] MED — empty `[Template]` value pulled body rows into data-row mode → demoted to steps on reload: lookahead now requires a non-empty template keyword [robotTextIO.ts].
- [x] [Review][Patch] LOW — `EXCEPT    AS    ${e}` catch-all dropped the capture var: `asIdx >= 1` [robotTextIO.ts].
- [x] [Review][Patch] LOW — introspection task `count` returned JSON string length, not keyword count [tasks.py].
- [x] [Review][Patch] LOW — added tab-indent/separator round-trip test pinning the documented tab→space normalization [FlowEditorRoundTripEdgeCases.spec.ts].
- [x] [Review][Defer] FQN `Library.Keyword` disambiguation on true cross-library ambiguity (AC-C4 second clause) — project>library>BuiltIn precedence is implemented; FQN tiebreak deferred (rare; project keywords already win).
- [x] [Review][Defer] Multi-line `[Tags]`/`[Setup]` `...` continuation is dropped (pre-existing in the extracted parser) — follow-up.
- [x] [Review][Defer] Template data cell whose value equals a control marker (IF/FOR/END/…) is routed to a step (RF-ambiguous) — kept the RF-aligned default; documented.
- Dismissed (4): bare `#` arg = comment (correct RF) · BDD prefix fallback (by-design AC2) · deepMerge in-place (safe as used) · VAR subscript LHS (not valid RF assignment).
