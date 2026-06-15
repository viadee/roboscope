/**
 * Story: Chinese (zh) locale support. Pins structural completeness — every key
 * present in the English base must resolve under zh (translated or English
 * fallback via deep-merge) — plus a few spot-checks that real translations
 * landed and placeholders survived.
 */
import { describe, it, expect } from 'vitest'
import en from '@/i18n/locales/en'
import zh from '@/i18n/locales/zh'

type Dict = { [k: string]: unknown }

function leafKeys(obj: Dict, prefix = ''): string[] {
  const out: string[] = []
  for (const k of Object.keys(obj)) {
    const v = obj[k]
    const path = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object') out.push(...leafKeys(v as Dict, path))
    else out.push(path)
  }
  return out
}

function get(obj: Dict, path: string): unknown {
  return path.split('.').reduce<unknown>((o, k) => (o as Dict)?.[k], obj)
}

describe('zh locale — completeness + spot translations', () => {
  it('resolves every English key under zh (no missing keys)', () => {
    const enKeys = leafKeys(en as unknown as Dict)
    const missing = enKeys.filter((k) => get(zh as unknown as Dict, k) === undefined)
    expect(missing).toEqual([])
    expect(enKeys.length).toBeGreaterThan(200) // sanity: the base is large
  })

  it('translated the high-traffic strings to Chinese', () => {
    const z = zh as unknown as Dict
    expect(get(z, 'common.save')).toBe('保存')
    expect(get(z, 'common.cancel')).toBe('取消')
    expect(get(z, 'nav.dashboard')).toBe('仪表盘')
    expect(get(z, 'flowEditor.variables')).toBe('变量')
  })

  it('preserves interpolation placeholders in translated strings', () => {
    expect(get(zh as unknown as Dict, 'common.pageOf')).toContain('{current}')
    expect(get(zh as unknown as Dict, 'common.pageOf')).toContain('{total}')
    expect(get(zh as unknown as Dict, 'auth.ssoError.contactAdmin')).toContain('{email}')
  })
})
