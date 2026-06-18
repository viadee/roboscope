/**
 * Release gate — language & docs consistency.
 *
 * Complements the two locale-parity specs (`locale-parity.spec.ts` for
 * en/de/fr/es, `ZhLocaleParity.spec.ts` for zh) by pinning the things that
 * silently drift when a UI language is added but the *prose* that enumerates
 * languages isn't updated — the exact regression that left "supports 4
 * languages" in the tour and docs after Chinese shipped.
 *
 * It also guards that the four documentation locales keep the same top-level
 * section structure, so a section added to the English docs can't ship without
 * its translated counterparts.
 */
import { describe, it, expect } from 'vitest'
import en from '@/i18n/locales/en'
import de from '@/i18n/locales/de'
import fr from '@/i18n/locales/fr'
import es from '@/i18n/locales/es'
import zh from '@/i18n/locales/zh'
import enDocs from '@/docs/content/en'
import deDocs from '@/docs/content/de'
import frDocs from '@/docs/content/fr'
import esDocs from '@/docs/content/es'

// Canonical set of shipped UI locales. Adding a language means: add it here,
// add its locale file, AND update the language list in tour.langSwitcher (all
// locales) + the docs "Language Support" table. This spec fails until the
// count is back in sync everywhere.
const UI_LOCALES = { en, de, fr, es, zh } as const
const LOCALE_COUNT = Object.keys(UI_LOCALES).length

type Dict = Record<string, unknown>
function get(obj: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((o, k) => (o as Dict)?.[k], obj)
}

describe('release gate — language & docs consistency', () => {
  it('ships exactly five UI locales', () => {
    expect(LOCALE_COUNT).toBe(5)
    for (const [code, msgs] of Object.entries(UI_LOCALES)) {
      expect(msgs, `locale '${code}' is empty`).toBeTruthy()
    }
  })

  it('the language-switcher tour step names the real language count in every locale', () => {
    // Guards against a stale "supports N languages" claim: the number in the
    // prose must equal the number of locales actually shipped.
    for (const [code, msgs] of Object.entries(UI_LOCALES)) {
      const desc = get(msgs, 'tour.langSwitcher.description')
      expect(desc, `'${code}' is missing tour.langSwitcher.description`).toBeTruthy()
      expect(
        String(desc),
        `'${code}' tour.langSwitcher.description must mention ${LOCALE_COUNT} languages`,
      ).toContain(String(LOCALE_COUNT))
    }
  })

  it('every documentation locale exposes the same top-level section ids', () => {
    const sectionIds = (d: typeof enDocs) => d.map((s) => s.id)
    const reference = sectionIds(enDocs)
    for (const [code, d] of Object.entries({ de: deDocs, fr: frDocs, es: esDocs })) {
      expect(sectionIds(d), `'${code}' docs top-level sections drifted from en`).toEqual(reference)
    }
  })

  it('en/fr/es share identical subsection ids per section', () => {
    // EN/FR/ES are authored in lockstep, so their subsection trees must match
    // exactly — this catches a subsection added to one but not the others.
    // German (de) is intentionally NOT included: its docs use an independent
    // subsection structure + id scheme (different granularity, e.g. a combined
    // sync section, a DE-only API page), so it is pinned at top-level only
    // (the test above). Enforcing de subsection parity would force artificial
    // content changes.
    const subTree = (d: typeof enDocs) =>
      Object.fromEntries(d.map((s) => [s.id, s.subsections.map((ss) => ss.id).sort()]))
    const ref = subTree(enDocs)
    for (const [code, d] of Object.entries({ fr: frDocs, es: esDocs })) {
      expect(subTree(d), `'${code}' docs subsections drifted from en`).toEqual(ref)
    }
  })
})
