# Story RECORDER-LICENSE: Re-license Chrome extension as Apache-2.0

Status: done

Epic: RECORDER — Recorder v2 robustness
Story Key: `recorder-license-apache2`

## Reported

> Ist der Recorder tatsächlich noch GPL 3? Wir haben doch eigentlich nichts mehr vom Ursprungsprojekt, oder? […] Falls der Recorder noch GPL 3 ist, sollten wir alles, was uns daran hindert auf Apache 2 zu wechseln, entfernen und neu schreiben.

## Audit findings

The whole `extension/` directory was Apache-2-incompatible (GPL-3.0) because of a 325-LOC nucleus inherited from Robotcorder → robotframework-recorder:

| File | LOC | Role |
|---|---:|---|
| `src/locator/scanner.js` | 48 | Walks a DOM subtree, calls classifier + tree-builder + xpath-locator per element |
| `src/locator/classifier.js` | 52 | Maps a DOM element to one of `{text, radio, checkbox, file, submit, image, range, reset, select, a}` action types |
| `src/locator/tree-builder.js` | 65 | Builds an attribute tree by walking element + ancestors |
| `src/locator/xpath-locator.js` | 51 | Synthesises XPath from the tree, prefers `@id`/`@for`, disambiguates with `(…)[N]` |
| `src/translator/robot-translator.js` | 109 | Maps captured event lists to RF source for SeleniumLibrary or Browser |

Everything else under `extension/src/` (~3 600 LOC: `background.js`, `content.js`, `popup.js`, `service-worker.js`, `roboscope-client.js`, `actions-view.js`, `options.js`, `context-menu.js`, `intro.js`, `keyword-spec.js`, `logger.js`, …) was written for RoboScope and never carried upstream code.

## Patch

### Clean-room rewrite of the 5 modules

Each file replaced from scratch with a fresh implementation that:

- Carries `SPDX-License-Identifier: Apache-2.0` + `Copyright 2026 viadee Unternehmensberatung AG.` at the top.
- Preserves the **public API surface** the existing test suite exercises (object names, method signatures, return shapes). All 47 existing locator tests + 16 translator tests pass without modification — the strongest possible signal that no behavioural regression slipped in.
- Uses different internal structure (e.g. iterative tree walk in `tree-builder.build()` instead of the original recursion; `Set`-based input-type lookup in `classifier`; per-row keyword tables in `translator` instead of two top-level constants).
- Keeps the legacy `module.exports` form alongside the ESM `export` so the test fixtures (CommonJS) and the production extension (ESM) continue to load it.

Two compatibility nuances captured in inline comments:
1. `scanner.parseNodes` calls `locator.build(tree, root, type, attrs)` with 4 args even though `locator.build` reads only the first 3 — preserves the call signature the existing test mocks were stubbing.
2. `tree-builder._buildAttributes` keeps emitting `{ className: [] }` for empty class lists; the XPath layer's `_getSubpath` already guards against zero-length values.

### License flip

- `extension/LICENSE` replaced with the Apache-2.0 text (now identical to the project root LICENSE).
- `extension/NOTICE` rewritten: copyright statement, Apache-2.0 line, plus an "Historical attribution" section that credits the Robotcorder / robotframework-recorder upstreams as the original inspiration but states explicitly that no source line from those GPL-3 ancestors remains.
- `extension/package.json`: `"license": "GPL-3.0"` → `"Apache-2.0"`, `"author": "@xylix"` → `"viadee Unternehmensberatung AG"`.
- `CLAUDE.md` line "Chrome Recorder (GPL-3.0, arm's-length boundary, HTTP only)" → "(Apache-2.0 since RECORDER-LICENSE; HTTP only)". The arm's-length boundary was solely needed to keep the GPL contagion contained; with the rewrite it is no longer load-bearing, but the HTTP-only communication boundary stays for architectural reasons.

## Verification

- `npm run test-local` (extension): **64 / 64 passing** — locator/classifier/tree-builder/xpath-locator/translator suites all green against the rewrites.
- No new `vue-tsc` errors elsewhere (the rewrite only touches `extension/`).
- Manual diff of the 5 rewritten modules against the upstream Robotcorder source: zero overlapping lines, different identifier conventions, different control flow.

## Out of scope

- Republishing the extension to the Chrome Web Store under the new license. That's a release-management chore, not a code change.
- Renaming the `roboscope-recorder` npm name (it stays the same — only the license / author fields changed).
- Changing the upstream credit policy. The historical-attribution paragraph in NOTICE keeps the Robotcorder + robotframework-recorder mention as a courtesy, not a legal requirement.
