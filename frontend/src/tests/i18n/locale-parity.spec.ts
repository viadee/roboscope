/**
 * i18n locale parity guard.
 *
 * RoboScope ships in EN/DE/FR/ES. The CLAUDE.md convention is that
 * every user-facing string must have all four locale entries. The
 * regression that triggers most often: a developer adds a new key
 * to `en.ts` and forgets to mirror it. Vue-i18n then falls back to
 * the EN string at runtime — fine in dev, but the leaked English
 * shows up in screenshots from non-English users.
 *
 * This spec recursively flattens each locale into a list of dotted
 * key-paths and asserts the sets are identical. It runs in a fraction
 * of a second so it's cheap to keep on every test run.
 */

import { describe, it, expect } from 'vitest'
import en from '@/i18n/locales/en'
import de from '@/i18n/locales/de'
import fr from '@/i18n/locales/fr'
import es from '@/i18n/locales/es'

type LocaleTree = Record<string, unknown>

function flatten(obj: LocaleTree, prefix = ''): string[] {
  const out: string[] = []
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k
    if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
      out.push(...flatten(v as LocaleTree, path))
    } else {
      out.push(path)
    }
  }
  return out
}

describe('i18n locale parity', () => {
  const locales = {
    en: flatten(en as LocaleTree).sort(),
    de: flatten(de as LocaleTree).sort(),
    fr: flatten(fr as LocaleTree).sort(),
    es: flatten(es as LocaleTree).sort(),
  } as const

  it('en, de, fr, es expose the same key-paths', () => {
    // Use EN as the reference and report diffs for each other locale
    // — gives a single test failure that names every missing key
    // grouped by locale, not 1500 individual passes per language.
    const enSet = new Set(locales.en)
    const diffs: Record<string, { missing: string[]; extra: string[] }> = {}
    for (const lang of ['de', 'fr', 'es'] as const) {
      const langSet = new Set(locales[lang])
      const missing = locales.en.filter(k => !langSet.has(k))
      const extra = locales[lang].filter(k => !enSet.has(k))
      if (missing.length || extra.length) {
        diffs[lang] = { missing, extra }
      }
    }
    expect(diffs).toEqual({})
  })

  it('every locale defines at least 1000 key-paths (sanity floor)', () => {
    for (const [lang, keys] of Object.entries(locales)) {
      expect(keys.length, `${lang} has too few keys`).toBeGreaterThan(1000)
    }
  })
})
