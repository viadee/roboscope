# Story EDITOR-11: RobotCode-style RF syntax highlighting (Weg A — extend CodeMirror)

Status: done

Epic: EDITOR — Visual Flow Editor usability for non-developers
Story Key: `editor-11-rf-syntax-highlighting`

## Background

Reference: [robotcodedev/robotcode IntelliJ plugin](https://github.com/robotcodedev/robotcode/tree/main/intellij-client/src/main/kotlin/dev/robotcode/robotcode4ij/highlighting). RobotCode reads a TextMate grammar at runtime (`TextMateLexerCore`) and maps scope names to IntelliJ colours; the actual highlight quality comes from the upstream `robotframework.tmLanguage.json` grammar shared with the VS Code extension.

Two paths to bring that visual quality to RoboScope:

- **Weg A (this story).** Extend our hand-written CodeMirror `StreamLanguage` to emit a richer set of standard tokens (function call vs. definition, library namespace, inner `${…}` braces, escape sequences, atoms, named-arg + operator split). Add a brand-coloured `HighlightStyle` that maps those tokens to RoboScope-coded colours.
- **Weg B (deferred — see EDITOR-12).** Re-platform the code editor to Monaco so we can drop in the verbatim RobotCode TextMate grammar + later a Robot Framework Language Server.

Decision per the user: do A now, B later. Weg A buys ~80% of the visible win at <1% of the cost.

## Change

`frontend/src/utils/robotLanguage.ts` — rewritten tokenizer plus a new exported `robotHighlightStyle`:

| Surface | Old token | New token |
|---|---|---|
| Section header `*** Settings ***` | `heading` | `heading` (unchanged) |
| Test case / keyword definition name | `definition` (whole line) | `definition` (whole cell, unchanged) |
| Keyword call (indented verb) | `function` | `function` (now applies to project / custom kws too, not only builtins) |
| Library namespace in `Browser.Click` | (none — was part of the kw match) | `tagName` for `Browser`, `punctuation` for `.`, `function` for `Click` |
| Variable `${USER}` | one `variableName` token | `bracket` + `variableName` + `bracket` |
| Variable index `[0]` after `}` | folded into the cell value | distinct `bracket` + `bracket` |
| Continuation `...` | (often missed) | `meta` — same colour as `[Setup]` etc. |
| Escape sequences `\n`, `\t`, `\\` | (folded into argument) | `string-2` (special-string tag) |
| Named arg `name=value` | one `attributeName` token (incl. `=`) | `attributeName` + `operator` (split) |
| Atoms `True` / `False` / `None` / `EMPTY` | (none — plain text) | `atom` |
| BDD prefix `Given/When/Then/And/But` | `keyword` | `keyword` (unchanged, but now requires word-boundary + keyword-call position) |
| Variables-section value (`admin` after `${USER}`) | mis-tagged as `function` | un-tagged value (no colour, fall-through) |

`robotHighlightStyle` is a `HighlightStyle.define([...])` that maps every Lezer tag the new tokenizer touches to a RoboScope brand colour:

- Headings + definitions: `--color-navy` `#1A2D50`, bold.
- Keyword calls + variable braces + namespace + named-arg names: `--color-primary` `#3B7DD8`, accent purple `#7B61FF`.
- Control flow + escape sequences + operators: `--color-accent` `#D4883E`.
- Strings + meta (`[Setup]`, `...`): green `#2C9846`.
- Numbers + atoms: red `#C0392B`.
- Comments + cell separators: muted greys.

`RobotEditor.vue` adds the new style with `syntaxHighlighting(robotHighlightStyle, { fallback: true })` BEFORE the existing `defaultHighlightStyle` so unknown tags still degrade cleanly.

## Acceptance Criteria

- [x] Section headers render with the heading style.
- [x] Keyword definitions render distinct from keyword calls.
- [x] `Library.Keyword` splits into namespace + dot + function.
- [x] `${var}` shows visible braces + name.
- [x] `\n` / `\t` escape sequences render distinctly inside arguments.
- [x] Named args split into name (italic purple) + `=` (orange).
- [x] Atoms (True/False/None) coloured.
- [x] Continuation `...` coloured as meta.
- [x] Variables-section values are not mis-coloured as keyword calls.
- [x] No new TS errors. Full Vitest suite still green (352/352, +12 new cases).
- [x] No bundle-size impact (only modifies an existing module + adds a small `HighlightStyle.define` block).

## Out of scope

- Embedded variables in keyword definitions (`User ${name} Logs In`).
- `Run Keyword`-style nested keyword calls (`Run Keyword If    cond    Set Variable    foo` doesn't re-tokenize the inner kw).
- Markdown-style emphasis inside `Documentation` strings.
- Theming the rest of the editor chrome (line numbers, gutter) — outside scope.

All of the above are reachable later via Weg B (Monaco + RobotCode TextMate grammar) — see EDITOR-12.

## Verification

- `npx vitest run` → 352/352 pass (12 new robotLanguage cases).
- `npx vue-tsc --noEmit` total error count unchanged at 31 (all pre-existing).
- Manual smoke: open `recording.robot` in code tab, see distinct colours for `Click`, `Browser` namespace, `${var}`, `text=Alle ablehnen`, `\n` escapes.
