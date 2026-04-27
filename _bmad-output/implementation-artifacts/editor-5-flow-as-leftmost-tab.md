# Story EDITOR-5: Flow tab is the leftmost / default editor tab

Status: done

Epic: EDITOR — Visual Flow Editor usability for non-developers
Story Key: `editor-5-flow-as-leftmost-tab`

## Reasoning

The visual flow editor is the primary view for non-developer Editor users (the same audience driving stories EDITOR-1 / EDITOR-2 / EDITOR-3). Burying it behind the "Visual Editor" tab means the first thing every user sees on opening a `.robot` file is the linear form editor, which is the dev-oriented view. Making **Flow** the leftmost and default tab puts the right view in front of the right user.

## Change

`frontend/src/components/editor/RobotEditor.vue`:

1. Tab default: `activeTab = ref('flow')` (was `'visual'`).
2. Tab order in the bar: `Flow | Visual | Code` (was `Visual | Flow | Code`).

No i18n change (button labels unchanged), no schema change, no API change.

## Out of scope

- Renaming the "Visual Editor" tab. Its label is still useful for the dev-style outline view.
- Removing the visual tab. It still has a use for users who prefer the form view.

## Verification

- 284-case Vitest suite still green (no test asserted tab order).
- Existing Playwright `take-demo-video` spec finds tabs by accessible name, not position — not affected.
- Manual: open any `.robot` file → Flow tab is selected and renders by default.
