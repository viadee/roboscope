/**
 * UX D5 / D6 (ux-flow-editor-resources.md) — pure view-state helpers for the
 * Flow Editor keyword palette: the adaptive "what's shown" filter default, the
 * sophisticated-file heuristic, filtering, hidden-count, and library sort.
 */
import { describe, it, expect } from 'vitest'
import {
  adaptiveDefaultFilter,
  isSophisticatedFile,
  applyFilter,
  hiddenCount,
  sortLibraries,
  bucketOf,
  parseStoredFilter,
  parseStoredSort,
  SOPHISTICATED_MIN_STEPS,
  type CatLike,
  type PaletteFilter,
} from '@/components/editor/flow/paletteView'

const RESOURCE: CatLike = { name: 'common.resource', kind: 'resource' }
const BUILTIN: CatLike = { name: 'BuiltIn', kind: 'library' }
const REAL_LIB: CatLike = { name: 'Browser', kind: 'library', imported: true }
const EXAMPLE_LIB: CatLike = { name: 'SeleniumLibrary', kind: 'library', isExamples: true }
const CONTROL: CatLike = { name: 'Control', kind: 'control' }

describe('isSophisticatedFile (D6 heuristic)', () => {
  it('is sophisticated when the file already imports something', () => {
    expect(isSophisticatedFile({ importCount: 1, stepCount: 0 })).toBe(true)
  })
  it('is sophisticated at the step threshold', () => {
    expect(isSophisticatedFile({ importCount: 0, stepCount: SOPHISTICATED_MIN_STEPS })).toBe(true)
  })
  it('is a mini/fresh file with no imports and few steps', () => {
    expect(isSophisticatedFile({ importCount: 0, stepCount: 2 })).toBe(false)
  })
})

describe('adaptiveDefaultFilter (D6 decided 2026-06-18)', () => {
  it('hides example libs for a sophisticated file in an env-backed repo', () => {
    const f = adaptiveDefaultFilter({ hasEnvData: true, file: { importCount: 3, stepCount: 12 } })
    expect(f).toEqual({ resources: true, importedLibs: true, exampleLibs: false, builtin: true })
  })
  it('shows everything for an env-less repo (pure discovery)', () => {
    const f = adaptiveDefaultFilter({ hasEnvData: false, file: { importCount: 3, stepCount: 12 } })
    expect(f.exampleLibs).toBe(true)
  })
  it('shows everything for a fresh/mini file even with an env', () => {
    const f = adaptiveDefaultFilter({ hasEnvData: true, file: { importCount: 0, stepCount: 1 } })
    expect(f.exampleLibs).toBe(true)
  })
})

describe('bucketOf', () => {
  it('maps categories to their filter buckets, Control to none', () => {
    expect(bucketOf(RESOURCE)).toBe('resources')
    expect(bucketOf(BUILTIN)).toBe('builtin')
    expect(bucketOf(REAL_LIB)).toBe('importedLibs')
    expect(bucketOf(EXAMPLE_LIB)).toBe('exampleLibs')
    expect(bucketOf(CONTROL)).toBeNull()
  })
})

describe('applyFilter + hiddenCount (D6)', () => {
  const cats = [RESOURCE, BUILTIN, REAL_LIB, EXAMPLE_LIB, CONTROL]
  it('keeps Control regardless of the filter', () => {
    const none: PaletteFilter = { resources: false, importedLibs: false, exampleLibs: false, builtin: false }
    expect(applyFilter(cats, none)).toEqual([CONTROL])
  })
  it('hides only the example libs under the imported-only default', () => {
    const f: PaletteFilter = { resources: true, importedLibs: true, exampleLibs: false, builtin: true }
    const out = applyFilter(cats, f)
    expect(out).not.toContain(EXAMPLE_LIB)
    expect(out).toContain(REAL_LIB)
    expect(hiddenCount(cats, f)).toBe(1)
  })
  it('reports zero hidden when everything is shown', () => {
    const all: PaletteFilter = { resources: true, importedLibs: true, exampleLibs: true, builtin: true }
    expect(hiddenCount(cats, all)).toBe(0)
  })
})

describe('sortLibraries (D5)', () => {
  const libs: CatLike[] = [
    { name: 'Browser', kind: 'library', isExamples: false },
    { name: 'AppiumLibrary', kind: 'library', isExamples: true },
    { name: 'Collections', kind: 'library', isExamples: false },
  ]
  const usage = new Map<string, number>([['Collections', 5], ['Browser', 2]])

  it('mostUsed orders by usage desc', () => {
    expect(sortLibraries(libs, 'mostUsed', usage).map((l) => l.name)).toEqual([
      'Collections', 'Browser', 'AppiumLibrary',
    ])
  })
  it('alpha orders case-insensitively A–Z', () => {
    expect(sortLibraries(libs, 'alpha', usage).map((l) => l.name)).toEqual([
      'AppiumLibrary', 'Browser', 'Collections',
    ])
  })
  it('importedFirst puts non-example libs ahead of examples', () => {
    const out = sortLibraries(libs, 'importedFirst', usage).map((l) => l.name)
    expect(out.indexOf('AppiumLibrary')).toBe(out.length - 1) // the only example → last
    expect(out.slice(0, 2).sort()).toEqual(['Browser', 'Collections'])
  })
})

describe('parseStoredFilter / parseStoredSort (persistence)', () => {
  it('round-trips a valid filter', () => {
    const f: PaletteFilter = { resources: true, importedLibs: false, exampleLibs: true, builtin: false }
    expect(parseStoredFilter(JSON.stringify(f))).toEqual(f)
  })
  it('rejects malformed / partial / null filter blobs', () => {
    expect(parseStoredFilter(null)).toBeNull()
    expect(parseStoredFilter('not json')).toBeNull()
    expect(parseStoredFilter('{"resources":true}')).toBeNull()
  })
  it('accepts only known sort modes', () => {
    expect(parseStoredSort('alpha')).toBe('alpha')
    expect(parseStoredSort('importedFirst')).toBe('importedFirst')
    expect(parseStoredSort('bogus')).toBeNull()
    expect(parseStoredSort(null)).toBeNull()
  })
})
