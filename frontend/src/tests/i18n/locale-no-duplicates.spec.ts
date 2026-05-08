/**
 * I18N-1 regression guard: no duplicate top-level keys in locale files.
 *
 * The original I18N-1 bug shipped because two `recorder: { … }`
 * blocks coexisted at the top of each locale file; JavaScript
 * object-literal semantics made the second silently overwrite the
 * first, dropping 14 keys (including 4 live in production
 * `useWebSocket.ts` toast handlers — users saw the literal string
 * `"recorder.completed"` instead of "Recording Complete" for every
 * finished recording session).
 *
 * Vite emitted a warning at build time but the parity-spec
 * (`locale-parity.spec.ts`) couldn't catch it: all four locales
 * had the same corrupted shape, so the cross-locale comparison
 * passed.
 *
 * This spec parses the raw text of each locale's source file and
 * detects top-level keys (indent depth 2 == top of `export default
 * { … }`) that appear more than once. Catching them at the test
 * step rather than only at the build warning means a CI tied to
 * `npm run test:unit` will fail-loud on regressions.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const LOCALES = ['en', 'de', 'fr', 'es'] as const

const HERE = dirname(fileURLToPath(import.meta.url))

function localePath(locale: string): string {
  return resolve(HERE, '..', '..', 'i18n', 'locales', `${locale}.ts`)
}

function findDuplicateTopLevelKeys(source: string): string[] {
  // Top-level keys are `^  KEY:` (indent 2 — `export default {` opens
  // at column 0, keys live at indent 2). Block-opening pattern is
  // `^  KEY: {`. Plain string keys (`^  key: 'value'`) at indent 2
  // are also top-level.
  // We deliberately don't try to handle the general nested case;
  // the bug class is "two top-level KEYs of the same name."
  const counts = new Map<string, number>()
  for (const line of source.split('\n')) {
    const m = /^  ([a-zA-Z_$][\w$]*):/.exec(line)
    if (!m) continue
    const key = m[1]
    counts.set(key, (counts.get(key) || 0) + 1)
  }
  return Array.from(counts.entries())
    .filter(([, n]) => n > 1)
    .map(([k, n]) => `${k} (×${n})`)
}

describe('i18n locale duplicate-key guard', () => {
  it.each(LOCALES)('%s.ts has no duplicate top-level keys', (locale) => {
    const source = readFileSync(localePath(locale), 'utf-8')
    const dupes = findDuplicateTopLevelKeys(source)
    expect(
      dupes,
      `Duplicate top-level keys in ${locale}.ts: ${dupes.join(', ')}. ` +
        `JavaScript silently lets the second declaration overwrite the ` +
        `first — see I18N-1 for the recorder.* bug this catches.`,
    ).toEqual([])
  })
})
