/**
 * Story HEAL-1 / HEAL-2 — Self-Healing opt-in helpers.
 *
 * Pure mapping + form-rewrite utilities for switching Browser-library
 * keyword calls between their bare form (`Click`, `Fill Text`, …) and
 * their RoboScopeHeal variant (`Heal Click`, `Heal Fill Text`, …).
 *
 * The 13 supported keywords are derived from
 * `backend/src/recording/heal/library.py`. Adding a new `@keyword` there
 * means adding one entry here.
 *
 * Design invariants (per CLAUDE.md "Auto-fixing test code requires the
 * SH-2 opt-in contract"):
 *   1. Per-keyword opt-in only — no monkey-patching the Browser library.
 *   2. Never mutate `.robot` at runtime — all changes go through the
 *      form path so they show up as standard unsaved-changes edits the
 *      user reviews and saves explicitly.
 *   3. Custom-configured `Library    RoboScopeHeal    <args>` rows are
 *      preserved across both directions.
 */
import type { RobotForm, RobotStep } from '@/components/editor/flow/flowConverter'

/**
 * Browser-library keyword → its RoboScopeHeal variant. Source of
 * truth is `library.py`'s `@keyword(...)` decorators.
 */
export const HEAL_VARIANTS: Readonly<Record<string, string>> = Object.freeze({
  'Click': 'Heal Click',
  'Fill Text': 'Heal Fill Text',
  'Type Text': 'Heal Type Text',
  'Hover': 'Heal Hover',
  'Press Keys': 'Heal Press Keys',
  'Wait For Elements State': 'Heal Wait For Elements State',
  'Upload File': 'Heal Upload File',
  'Check Checkbox': 'Heal Check Checkbox',
  'Uncheck Checkbox': 'Heal Uncheck Checkbox',
  'Select Options By': 'Heal Select Options By',
  'Get Text': 'Heal Get Text',
  'Get Element Count': 'Heal Get Element Count',
  'Drag And Drop': 'Heal Drag And Drop',
})

/** Reverse map of HEAL_VARIANTS, built once. */
const BASE_BY_HEAL: Readonly<Record<string, string>> = Object.freeze(
  Object.fromEntries(
    Object.entries(HEAL_VARIANTS).map(([base, heal]) => [heal, base]),
  ),
)

/**
 * Trims whitespace and looks up the Heal variant for a bare keyword.
 * Returns `null` for keywords that are already heal'd, unknown, or
 * non-heal-able. (Robot Framework is case-sensitive for keyword
 * names, so the lookup is too.)
 */
export function getHealVariant(keyword: string): string | null {
  const k = keyword.trim()
  return HEAL_VARIANTS[k] ?? null
}

/**
 * Reverse of `getHealVariant`: given `Heal Click`, returns `Click`.
 * Returns `null` for inputs that are not in the heal-variant set.
 */
export function getBaseKeyword(keyword: string): string | null {
  const k = keyword.trim()
  return BASE_BY_HEAL[k] ?? null
}

/** `true` when the keyword name (bare or Heal*) is one of the 13 supported. */
export function isHealableKeyword(keyword: string): boolean {
  const k = keyword.trim()
  return k in HEAL_VARIANTS || k in BASE_BY_HEAL
}

/** `true` only for Heal* form of one of the 13 supported keywords. */
export function isHealedKeyword(keyword: string): boolean {
  return getBaseKeyword(keyword) !== null
}

type Settings = RobotForm['settings']
type SettingRow = Settings[number]

/**
 * Returns the index of the bare `Library    RoboScopeHeal` row (no
 * args). A row with extra args (e.g., budget config) is considered
 * a "user-configured" row and is NOT the auto-added one, so the
 * lookup ignores it. Returns -1 when no bare row is present.
 */
function findBareRoboScopeHealRow(settings: Settings): number {
  return settings.findIndex(
    s =>
      s.key === 'Library' &&
      s.value === 'RoboScopeHeal' &&
      s.args.length === 0,
  )
}

/**
 * Returns `true` when ANY Library row (bare or configured) references
 * `RoboScopeHeal`. Used to suppress duplicate adds when the user
 * already configured the lib manually.
 */
function hasAnyRoboScopeHealRow(settings: Settings): boolean {
  return settings.some(s => s.key === 'Library' && s.value === 'RoboScopeHeal')
}

/**
 * Ensures `Library    RoboScopeHeal` is present in the form's settings.
 * Idempotent: returns the same array reference when no change is
 * needed (existing row, bare or configured). Otherwise returns a new
 * array with the bare row appended.
 */
export function ensureRoboScopeHealLibrary(settings: Settings): Settings {
  if (hasAnyRoboScopeHealRow(settings)) return settings
  const newRow: SettingRow = { key: 'Library', value: 'RoboScopeHeal', args: [] }
  return [...settings, newRow]
}

/**
 * Removes the bare `Library    RoboScopeHeal` row when no Heal*
 * keyword is left in the file. Preserves the row if:
 *   - `stillUsed` is true (some Heal* keyword still references it), OR
 *   - the row carries args (`Library RoboScopeHeal budget=3 …`) — that
 *     user-configured form is never auto-removed.
 *
 * Idempotent: returns the input reference when no change is needed.
 */
export function removeRoboScopeHealLibraryIfUnused(
  settings: Settings,
  stillUsed: boolean,
): Settings {
  if (stillUsed) return settings
  const idx = findBareRoboScopeHealRow(settings)
  if (idx === -1) return settings
  return [...settings.slice(0, idx), ...settings.slice(idx + 1)]
}

/**
 * Walks every step in test cases + user keywords and returns the
 * count that currently use a Heal* keyword. Used by the UI to render
 * "toggle is On" vs "Off" and by the disable path to decide whether
 * to remove the Library row.
 */
export function countHealedSteps(form: RobotForm): number {
  let n = 0
  for (const tc of form.testCases) {
    for (const s of tc.steps) if (isHealedKeyword(s.keyword)) n += 1
  }
  for (const kw of form.keywords) {
    for (const s of kw.steps) if (isHealedKeyword(s.keyword)) n += 1
  }
  return n
}

/**
 * `true` when the file imports the Browser library (any of the
 * common names: bare `Browser`, the pip-name variants
 * `robotframework-browser` / `robotframework_browser` and the
 * batteries fork). The toggle uses this to avoid offering "Heal"
 * for files where a step keyword happens to be called `Click`
 * but is actually a custom user keyword — rewriting it to
 * `Heal Click` would break the test rather than heal it.
 */
export function hasBrowserLibraryImport(form: RobotForm): boolean {
  return form.settings.some(s => {
    if (s.key !== 'Library') return false
    const v = s.value.trim()
    return /^(?:Browser|robotframework[-_]browser(?:[-_]batteries)?)$/i.test(v)
  })
}

/**
 * `true` when the file already imports `Library    RoboScopeHeal`
 * (any args). Once present, the user has explicitly opted into the
 * heal contract, so the toggle stays visible even without an
 * explicit Browser library import.
 */
export function hasRoboScopeHealImport(form: RobotForm): boolean {
  return form.settings.some(
    s => s.key === 'Library' && s.value.trim() === 'RoboScopeHeal',
  )
}

/**
 * Walks every step in test cases + user keywords and returns the count
 * that use a bare heal-able keyword (i.e., would be promoted by
 * `enable`). Used by the UI to decide whether the suite-level toggle
 * is shown at all (`0` heal-able + `0` heal'd → hide).
 */
export function countHealableSteps(form: RobotForm): number {
  let n = 0
  for (const tc of form.testCases) {
    for (const s of tc.steps) if (getHealVariant(s.keyword) !== null) n += 1
  }
  for (const kw of form.keywords) {
    for (const s of kw.steps) if (getHealVariant(s.keyword) !== null) n += 1
  }
  return n
}

/**
 * Rewrites a single step's keyword name to its Heal variant (mode
 * 'enable') or its bare form (mode 'disable'). Returns a new step
 * object on change, or the same reference when nothing applies.
 * Non-keyword fields (args, condition, return vars, comment, …) are
 * preserved by spread.
 */
function rewriteStep(step: RobotStep, mode: 'enable' | 'disable'): RobotStep {
  if (mode === 'enable') {
    const variant = getHealVariant(step.keyword)
    if (variant !== null) return { ...step, keyword: variant }
  } else {
    const base = getBaseKeyword(step.keyword)
    if (base !== null) return { ...step, keyword: base }
  }
  return step
}

export interface ApplyHealResult {
  /** New form with all rewrites + library-import updates applied. */
  form: RobotForm
  /** Count of keyword-name rewrites performed. Zero when no-op. */
  changedKeywords: number
}

/**
 * Story HEAL-2: rewrite every heal-able step across all test cases
 * and user keywords, plus add or remove the bare
 * `Library    RoboScopeHeal` row based on whether any Heal*
 * keyword remains.
 *
 * Pure — does not mutate the input form. The returned form
 * preserves array identity for unchanged subtrees so Vue's reactivity
 * only sees the parts that actually changed.
 */
export function applyHealToForm(
  form: RobotForm,
  mode: 'enable' | 'disable',
): ApplyHealResult {
  let changes = 0

  const newTestCases = form.testCases.map(tc => {
    let touched = false
    const steps = tc.steps.map(s => {
      const r = rewriteStep(s, mode)
      if (r !== s) {
        touched = true
        changes += 1
      }
      return r
    })
    return touched ? { ...tc, steps } : tc
  })

  const newKeywords = form.keywords.map(kw => {
    let touched = false
    const steps = kw.steps.map(s => {
      const r = rewriteStep(s, mode)
      if (r !== s) {
        touched = true
        changes += 1
      }
      return r
    })
    return touched ? { ...kw, steps } : kw
  })

  const anyHealLeft =
    newTestCases.some(tc => tc.steps.some(s => isHealedKeyword(s.keyword))) ||
    newKeywords.some(kw => kw.steps.some(s => isHealedKeyword(s.keyword)))

  let newSettings = form.settings
  if (mode === 'enable' && anyHealLeft) {
    newSettings = ensureRoboScopeHealLibrary(newSettings)
  } else if (mode === 'disable') {
    newSettings = removeRoboScopeHealLibraryIfUnused(newSettings, anyHealLeft)
  }

  return {
    form: {
      ...form,
      settings: newSettings,
      testCases: newTestCases,
      keywords: newKeywords,
    },
    changedKeywords: changes,
  }
}
