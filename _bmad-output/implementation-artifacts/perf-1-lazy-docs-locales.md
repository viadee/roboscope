# Story PERF-1: Lazy-load docs content by locale

Status: done

## Build measurements

Before:
- `DocsView-*.js`: **413.26 kB / 124.28 kB gzipped** (all 4 locales bundled)

After:
- `DocsView-*.js`: **4.11 kB / 1.83 kB gzipped** (just the view shell)
- `en-*.js`: 101 kB / 32 kB gzipped (loaded only when viewing EN docs)
- `de-*.js`: 93 kB / 30 kB
- `fr-*.js`: 110 kB / 32 kB
- `es-*.js`: 106 kB / 31 kB

Net effect: the initial DocsView chunk is now ~100× smaller. Only
the active locale's content streams in on first visit; the other
three never load unless the user actually switches.

Epic: POLISH — backlog from CLAUDE.md "Known open issues"
Story Key: `perf-1-lazy-docs-locales`

## Reported

CLAUDE.md "Known open issues" calls out:

> 270KB docs eagerly bundled (→ dynamic import)

`frontend/src/docs/index.ts` does static `import en from './content/en'`
for all four locales (`en/de/fr/es`). Each locale file is ~2300 lines
of long HTML strings. The bundler cannot split them because the
exported `getDocsContent(locale)` reaches every key of the static map
unconditionally — Rollup conservatively ships all four. That's
~270KB extra in the DocsView chunk (per the latest production
build, the chunk weighs 413KB / 124KB gzipped).

## The fix, in one sentence

Replace the four eager `import` statements with per-locale dynamic
`import()` calls inside an async `getDocsContent(locale)`; let Rollup
do the chunk-split. Only the active locale ships on initial load.

## Acceptance Criteria

1. **AC1 — Async lookup.** `getDocsContent(locale: string)` becomes
   `Promise<DocsContent>`. Internally a `Record<string, () => Promise<...>>`
   maps locale → dynamic-import factory.

2. **AC2 — Cache once loaded.** On first await for a given locale,
   cache the resolved module so subsequent calls (locale-switch
   round-trips, search, etc.) are synchronous Promise.resolve().

3. **AC3 — Fallback to EN.** If the requested locale isn't in the
   map, fall back to `en` — same as the current sync impl.

4. **AC4 — DocsView awaits.** `DocsView.vue` switches `docs` from a
   `computed` over a sync source to a `ref<DocSection[] | null>`
   populated on mount and on `watch(locale, …)`. Render a spinner
   placeholder while it's null.

5. **AC5 — Bundle split confirmed.** After `npx vite build`, four
   separate chunks named `en-*.js / de-*.js / fr-*.js / es-*.js`
   (or similar) are emitted, and the DocsView chunk shrinks
   measurably. We expect roughly a 200KB reduction in the eager
   payload (uncompressed); record the before/after sizes in the
   commit message.

6. **AC6 — Locale switch still works**. Manually verified with
   `make dev` — switching language in the docs view repaints the
   content, no console errors.

7. **AC7 — Existing Vitest still green.** No test currently relies
   on `getDocsContent` being sync; the surface change is local to
   DocsView. 358/358 must remain.

## Out of scope (V1)

- **Per-section lazy loading**. The `en.ts` content is one huge
  string array — splitting at the section level would need a
  separate file per section, much heavier refactor. Locale-level
  split is the 80/20.
- **Translating docs at build time** (e.g. via Vue i18n's lazy
  message loader). The docs content already lives outside i18n;
  bringing it into i18n would re-bundle. Defer.
- **Service-worker prefetch of other locales** (so the next switch
  is instant). Cute, but adds a service-worker. Way out of scope.

## Risk notes

- **Promise rejection on a chunk-load failure** (network blip in a
  PWA scenario). The DocsView placeholder must clear and surface a
  retry, not hang on `null`. We add a simple `error` ref + retry
  affordance.
- **Stale `docs` ref after rapid locale switches**. Watch the
  promise: if a newer-locale request lands while an older one is
  still resolving, ignore the stale resolution. Implement with a
  per-call sequence number.
