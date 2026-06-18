/**
 * UX D5 / D6 (ux-flow-editor-resources.md) — pure view-state helpers for the
 * Flow Editor keyword palette: the "what's shown" filter (incl. its adaptive
 * default) and the sort control. Kept framework-free so the heuristic and the
 * ordering are unit-testable without mounting the component.
 */

/** The four toggle-able category buckets in the D6 filter. */
export interface PaletteFilter {
  /** Project `.robot` / `.resource` keyword files ("Your resources"). */
  resources: boolean
  /** Real/installed libraries (libdoc-backed), BuiltIn excluded. */
  importedLibs: boolean
  /** Curated example libraries that aren't installed in the env. */
  exampleLibs: boolean
  /** The always-available BuiltIn library. */
  builtin: boolean
}

export type PaletteSort = 'mostUsed' | 'alpha' | 'importedFirst'

/** localStorage keys for the persisted manual overrides. */
export const PALETTE_FILTER_LS_KEY = 'roboscope.flowPalette.filter'
export const PALETTE_SORT_LS_KEY = 'roboscope.flowPalette.sort'

/**
 * D6 "sophisticated file" thresholds. A file counts as a real/sophisticated
 * test (vs a fresh "mini" file still being explored) when it already imports
 * at least one Library/Resource OR has a non-trivial number of steps. Kept in
 * one place so they're tunable and pinned by a unit test.
 */
export const SOPHISTICATED_MIN_IMPORTS = 1
export const SOPHISTICATED_MIN_STEPS = 5

export interface FileShape {
  /** Count of `Library` + `Resource` imports in the open file. */
  importCount: number
  /** Total steps across the open file's test cases + keywords. */
  stepCount: number
}

/** True when the open file looks like a real test rather than a fresh stub. */
export function isSophisticatedFile(f: FileShape): boolean {
  return f.importCount >= SOPHISTICATED_MIN_IMPORTS || f.stepCount >= SOPHISTICATED_MIN_STEPS
}

const ALL_VISIBLE: PaletteFilter = {
  resources: true,
  importedLibs: true,
  exampleLibs: true,
  builtin: true,
}

const IMPORTED_ONLY: PaletteFilter = {
  resources: true,
  importedLibs: true,
  exampleLibs: false, // hide the not-installed example noise
  builtin: true,
}

/**
 * D6 adaptive default (decided 2026-06-18). For a repo that already has an
 * environment AND a sophisticated open file, default to imported-only (hide
 * example libs). Env-less repos and fresh/mini files default to showing
 * everything so beginners can discover the example-library catalogue.
 */
export function adaptiveDefaultFilter(opts: {
  hasEnvData: boolean
  file: FileShape
}): PaletteFilter {
  if (opts.hasEnvData && isSophisticatedFile(opts.file)) return { ...IMPORTED_ONLY }
  return { ...ALL_VISIBLE }
}

/** Parse a persisted filter override, tolerating malformed/legacy values. */
export function parseStoredFilter(raw: string | null): PaletteFilter | null {
  if (!raw) return null
  try {
    const o = JSON.parse(raw) as Partial<PaletteFilter>
    if (
      typeof o?.resources === 'boolean' &&
      typeof o?.importedLibs === 'boolean' &&
      typeof o?.exampleLibs === 'boolean' &&
      typeof o?.builtin === 'boolean'
    ) {
      return { resources: o.resources, importedLibs: o.importedLibs, exampleLibs: o.exampleLibs, builtin: o.builtin }
    }
  } catch {
    /* fall through */
  }
  return null
}

export function parseStoredSort(raw: string | null): PaletteSort | null {
  return raw === 'mostUsed' || raw === 'alpha' || raw === 'importedFirst' ? raw : null
}

/**
 * Lower-cased stems (basename minus final extension) of the repo's project
 * keyword files. The rf-knowledge search path attributes a repo keyword to a
 * "library" equal to its source file stem (`backend/.../rf_knowledge.py`:
 * `library = f.stem`), so `login.resource` keywords come back under a library
 * group named `login`. The palette already renders those same keywords in the
 * pinned "Your resources" section (grouped by `login.resource`), so the library
 * group is a duplicate — this set lets the palette drop it. No-op on the
 * env-libdoc path (which never introspects resource files).
 */
export function resourceFileStems(filePaths: string[]): Set<string> {
  const stems = new Set<string>()
  for (const p of filePaths) {
    const base = (p.split('/').pop() || p).trim()
    const stem = base.replace(/\.[^.]+$/, '')
    if (stem) stems.add(stem.toLowerCase())
  }
  return stems
}

/** The minimal category shape these helpers reason about. */
export interface CatLike {
  name: string
  kind: 'resource' | 'library' | 'control'
  isExamples?: boolean
  isCurrentFile?: boolean
  /** Whether the owning library is imported in the open file (for sort/filter). */
  imported?: boolean
}

/** Which filter bucket a category belongs to (null = never filtered, e.g. Control). */
export function bucketOf(cat: CatLike): keyof PaletteFilter | null {
  if (cat.kind === 'resource') return 'resources'
  if (cat.kind === 'control') return null
  if (cat.name === 'BuiltIn') return 'builtin'
  if (cat.isExamples) return 'exampleLibs'
  return 'importedLibs'
}

/** Apply the filter; Control is always kept. */
export function applyFilter<T extends CatLike>(cats: T[], filter: PaletteFilter): T[] {
  return cats.filter((c) => {
    const b = bucketOf(c)
    return b === null ? true : filter[b]
  })
}

/**
 * Count how many categories the filter is currently hiding (for the
 * "{count} hidden · show all" affordance). Control never counts.
 */
export function hiddenCount(cats: CatLike[], filter: PaletteFilter): number {
  return cats.reduce((n, c) => {
    const b = bucketOf(c)
    return b !== null && !filter[b] ? n + 1 : n
  }, 0)
}

/**
 * Order LIBRARY categories per the sort mode. Resources and Control are sorted
 * by the caller into their own pinned positions — this only governs the
 * library block. `usage` maps library name → usage count (most-used sort).
 */
export function sortLibraries<T extends CatLike>(
  libs: T[],
  mode: PaletteSort,
  usage: Map<string, number>,
): T[] {
  const out = [...libs]
  if (mode === 'alpha') {
    out.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
  } else if (mode === 'importedFirst') {
    // Imported (in-file) / real libs first, examples last; ties by usage desc.
    out.sort((a, b) => {
      const ai = a.isExamples ? 1 : 0
      const bi = b.isExamples ? 1 : 0
      if (ai !== bi) return ai - bi
      return (usage.get(b.name) ?? 0) - (usage.get(a.name) ?? 0)
    })
  } else {
    // mostUsed (default) — stable usage-desc; preserves natural order on ties.
    out.sort((a, b) => (usage.get(b.name) ?? 0) - (usage.get(a.name) ?? 0))
  }
  return out
}
