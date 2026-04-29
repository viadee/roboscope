# Story I18N-1: Locale parity guard + duplicate `recorder` key fix

Status: done

Epic: POLISH — backlog from CLAUDE.md "Known open issues"
Story Key: `i18n-1-locale-parity-and-recorder-dupe`

## Reported

While auditing i18n key counts for parity, vite surfaced:

```
warning: Duplicate key "recorder" in object literal
```

— in **all four** locale files (`en.ts`, `de.ts`, `fr.ts`, `es.ts`).

JS object-literal semantics: when a key is repeated, the last
declaration wins. The first `recorder: { … }` block (at line 973)
defined 14 simple recording-toast / lifecycle keys; the second
`recorder: { … }` block (at line 1637) defined the newer recorder
sub-tree (`recorder.live.*`, `recorder.launcher.*`,
`recorder.selector.*`). The second silently overwrote the first.

Of the 14 lost keys, 4 were live in production:

```
useWebSocket.ts:116    ui.success(t('recorder.completed'),    t('recorder.completedMsg'))
useWebSocket.ts:118    ui.error(  t('recorder.failed'),       t('recorder.failedMsg'))
```

When a recording finishes (or fails) via WebSocket, the toast was
showing the literal key string — not the localised text — to every
user, in every locale. Bug had been latent since the second
recorder block was added.

## Fix

A small Python script (`_bmad-output/...`) merged the first block's
key/value pairs into the start of the second block, then deleted
the first. Same operation across all four locales so the de / fr /
es files don't drift from en. Vite's build no longer warns; all
four `t('recorder.completed')` etc. now resolve to their localised
strings.

## Permanent regression guard

New `frontend/src/tests/i18n/locale-parity.spec.ts` — flattens each
locale's nested object into dotted key-paths and asserts the four
sets are identical. Failure surfaces as a single test with a
per-locale `{ missing, extra }` report so the developer who broke
parity sees exactly which keys to add (or stray ones to remove).

The duplicate-key bug specifically would not have been caught by
the parity test (the four locales agreed on the corrupted final
shape), but the parity test catches the more common
"added a key in EN, forgot DE/FR/ES" pattern that this codebase has
shipped multiple times historically. Coverage is cumulative.

## Verification

- `grep -c "^  recorder:" frontend/src/i18n/locales/*.ts` — was 2
  per file, now 1.
- `npx vite build` — clean, no "Duplicate key" warnings.
- `npx vitest run` — 360/360 (was 358; +2 from the new parity spec).
- Manual smoke: `t('recorder.completedMsg')` now resolves to
  "Robot Framework test file has been generated." (EN); the
  per-locale strings round-trip too.

## Out of scope

- **Removing the dead recorder keys** that aren't used anywhere
  (`recorder.title`, `.record`, `.startRecording`, `.stop`,
  `.events`, `.generating`, `.newRecording`, `.tryAgain`,
  `.cancelled`, `.waitingForEvents`, `.generatedFile`). They're
  cheap; leaving them in case some future view picks them up.
- **Eslint plugin to fail the build on duplicate object keys**
  in `.ts` files — would catch this class of bug on commit
  rather than at the test step. Adding the rule is a separate
  story.
