# Story EDITOR-12: Decision — defer Monaco re-platform for code-tab editor

Status: deferred

Epic: EDITOR — Visual Flow Editor usability for non-developers
Story Key: `editor-12-monaco-replatform-decision`

## Context

The user asked whether we should swap the code-tab editor from CodeMirror to Monaco (the editor behind VS Code) so we can use the upstream RobotCode TextMate grammar verbatim and unlock LSP-driven goodies (parameter hints, hover, jump-to-definition, inline diagnostics).

## Decision

**Defer.** Implement Story EDITOR-11 (extend the existing CodeMirror grammar) as the short-term win. Re-evaluate Monaco when **at least one** of these signals appears:

- The code tab becomes a primary user surface (not the current "power-user fallback to the visual flow editor").
- A Robot Framework Language Server (e.g. RobotCode-LSP) is available + we have an integration story for it.
- The "270 KB docs eagerly bundled" issue from CLAUDE.md is solved AND the team accepts a further +3–5 MB to the offline bundle.

## Trade-offs captured

| Aspect | CodeMirror (current) | Monaco (deferred target) |
|---|---|---|
| Bundle size | ~250 KB | ~3–5 MB minified, all offline-bundleable |
| Highlight quality | Hand-tuned StreamLanguage (EDITOR-11 brings it close to TextMate) | Pixel-equivalent to VS Code RobotCode (TextMate grammar imported as JSON) |
| Hover / parameter hints | Custom integration needed | Built-in |
| LSP-readiness | Requires bespoke wiring | First-class via `monaco-languageclient` |
| Mobile | Solid | Weaker |
| Existing integrations | 3 surfaces (`RobotEditor.vue` code tab, `SpecEditor.vue`, generic editor in `ExplorerView.vue`) | All three need re-wiring |
| Estimated migration effort | — | ~1 week focused (spike, parity, theming, tests) |

## Why "TextMate alone" is not enough justification

TextMate is a grammar format, not an editor. The only realistic browser-side TextMate runtime is `vscode-textmate` + `onigasm` WASM, which works but couples poorly with `@codemirror/language`. The natural editor that ships TextMate as its native grammar engine is Monaco. So "switch to TextMate" effectively means "switch to Monaco." If the goal is just better highlighting, EDITOR-11 captures most of the visible win without re-platforming.

## What re-evaluating later should look like

1. Spike: confirm Monaco can be bundled offline-friendly via Vite + `vite-plugin-monaco-editor` (it can; document the actual gz-payload).
2. Spike: integrate RobotCode-LSP via `monaco-languageclient`, run against an existing `.robot` file, evaluate completion/hover/diagnostic UX.
3. Decision gate: if (a) bundle hit is ≤ 5 MB after compression AND (b) LSP UX is materially better than what EDITOR-2/3/4/7 deliver, schedule the migration as its own epic.

## Out of scope for this story

Implementation. This is a decision document only — see EDITOR-11 for the actual highlighting work.
