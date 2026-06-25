---
title: 'Quiet, repo-scoped keyword loading in the Explorer/Flow Editor'
type: 'refactor'
created: '2026-06-19'
status: 'done'
baseline_commit: '25737b3'
context:
  - '{project-root}/CLAUDE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Switching files in the Explorer re-runs `RobotEditor`'s file-switch
watcher → `explorer.refreshKeywords(repoId)`, which **invalidates the backend
libdoc cache and re-fetches the whole repo keyword set on every switch**. That
both wastes work (the env's installed libraries — and the repo's project
keywords — don't change between files) and flips `keywordsLoading=true`, which
renders the prominent full-width `.keyword-loading-bar` ("Keywords aus Umgebung
werden geladen…") again and again.

**Approach:** (1) Make keyword loading **repo-scoped + idempotent**: a plain file
switch only *ensures* the repo's keywords are loaded (no-op when already cached
for that repo), instead of invalidating + refetching. Genuine invalidation
(import added/removed, manual refresh, post-install) keeps using
`refreshKeywords`. (2) Make the loading indicator **subtle** — a slim top
progress line with a small muted label instead of the full-width bar.

## Boundaries & Constraints

**Always:**
- Keyword data stays repo-scoped; the store tracks which repo `keywords` belongs
  to and skips reloading when it already matches.
- `refreshKeywords` (invalidate + refetch) still fires for: `libraries-changed`,
  manual refresh button, and post-install — these legitimately need
  re-introspection.
- Keep the i18n string available as the indicator's accessible label
  (`aria-label`/`title`) in all 5 locales.

**Ask First:**
- Any change to the *backend* keyword cache / introspection (this is a
  frontend-only change).

**Never:**
- Don't remove the ability to refresh after an import change or install.
- Don't make file switches trigger a backend cache invalidation.
- No new dependencies.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Switch files, same repo, keywords already loaded | `preloadKeywords(sameRepo)` | Immediate no-op; no fetch, no loading indicator | N/A |
| Switch files, keywords not yet loaded | `preloadKeywords(repo)` | Fetches once, sets repo anchor | falls back to rf-knowledge / empty on error (unchanged) |
| Switch to a different repo | `preloadKeywords(otherRepo)` | Repo anchor differs → loads fresh | as above |
| Add `Library X` import | `libraries-changed` | `refreshKeywords` invalidates + refetches (unchanged) | non-critical catch (unchanged) |
| Initial repo open while loading | `keywordsLoading=true` | Slim top line + small muted label shown | N/A |

</frozen-after-approval>

## Code Map

- `frontend/src/stores/explorer.store.ts` -- `preloadKeywords`/`refreshKeywords`; add a `keywordsRepoId` anchor + idempotent guard.
- `frontend/src/components/editor/RobotEditor.vue` -- file-switch watcher (~787-793) currently calls `_refreshKeywordsIfPossible()`; switch it to an ensure-loaded call. Keep `onLibrariesChanged`/install refresh paths.
- `frontend/src/views/ExplorerView.vue` -- `.keyword-loading-bar` markup (~927-930) + styles (~1789-1812): restyle to a slim, subtle indicator.
- `frontend/src/stores/explorer.store.ts` tests + a RobotEditor file-switch test -- pin the idempotency + no-refetch-on-switch behavior.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/src/stores/explorer.store.ts` -- add `keywordsRepoId` ref; `preloadKeywords(repoId)` early-returns when `keywordsLoaded && keywordsRepoId === repoId && !keywordsLoading`; set `keywordsRepoId = repoId` on successful load; reset in `clearAll`. Export `keywordsRepoId`. -- repo-scoped idempotent cache.
- [x] `frontend/src/components/editor/RobotEditor.vue` -- in the `props.filePath` watcher, replace `_refreshKeywordsIfPossible()` with an ensure-loaded call (`explorer.preloadKeywords(repoId)`); update the comment. Leave `onLibrariesChanged` + install refresh untouched. -- stop full reload on file switch.
- [x] `frontend/src/views/ExplorerView.vue` -- restyle the indicator to a slim 2px indeterminate top line + a small muted label; keep the i18n text as visible small label and `aria-label`. -- quieter indicator.
- [x] `frontend/src/tests/stores/explorer.store.spec.ts` -- test: second `preloadKeywords(sameRepo)` does not refetch; different repo does; `clearAll` resets the anchor. -- pin caching.

**Acceptance Criteria:**
- Given a repo with keywords loaded, when the user switches between files in that repo, then no keyword fetch fires and the loading indicator does not reappear.
- Given an import is added in the Flow Editor, when `libraries-changed` fires, then `refreshKeywords` still invalidates and refetches.
- Given keywords are loading on first repo open, then the indicator is a slim line + small muted label (no full-width bar), with an accessible label.

## Design Notes

The libdoc cache is **per-environment** (installed libraries), and project
keywords are **repo-wide** — neither changes when you switch files, so the
file-switch refetch was pure waste. The fix is an idempotency anchor, not new
caching infrastructure.

## Verification

**Commands:**
- `cd frontend && npm run type-check` -- expected: clean
- `cd frontend && npx vitest run src/tests/stores/explorer.store.spec.ts` -- expected: pass
- `cd frontend && npm run build` -- expected: clean (no i18n escape break)
- `cd e2e && npx playwright test explorer flow-editor-resource-ux --reporter=line` -- expected: pass (no regression in file open / palette)

## Suggested Review Order

**Repo-scoped caching (the core change)**

- The idempotency guard — a file switch no-ops when this repo is already cached.
  [`explorer.store.ts:151`](../../frontend/src/stores/explorer.store.ts#L151)
- The anchor it keys off, set only on successful load.
  [`explorer.store.ts:35`](../../frontend/src/stores/explorer.store.ts#L35)
- File-switch watcher: ensure-loaded (`preloadKeywords`) instead of invalidate+refetch.
  [`RobotEditor.vue:795`](../../frontend/src/components/editor/RobotEditor.vue#L795)

**Concurrency / correctness (from review)**

- Latest-wins re-run so a fast repo switch mid-load isn't silently dropped.
  [`explorer.store.ts:200`](../../frontend/src/stores/explorer.store.ts#L200)
- Error path clears the anchor so it never advertises an unloaded repo.
  [`explorer.store.ts:196`](../../frontend/src/stores/explorer.store.ts#L196)

**Quieter indicator**

- Slim line + small muted label, `role="status"` + reduced-motion handling.
  [`ExplorerView.vue:931`](../../frontend/src/views/ExplorerView.vue#L931)

**Tests**

- Idempotency, cross-repo reload, refresh-forces-reload, race, error-clears-anchor, clearAll.
  [`explorer.store.spec.ts:85`](../../frontend/src/tests/stores/explorer.store.spec.ts#L85)
