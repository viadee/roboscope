/**
 * Story EDITOR-2 — verifies the composable that combines static
 * RF_KEYWORD_SIGNATURES with the dynamic explorer-store cache.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useExplorerStore } from '@/stores/explorer.store'
import { useKeywordSignatures } from '@/composables/useKeywordSignatures'

describe('useKeywordSignatures', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('returns args from RF_KEYWORD_SIGNATURES for built-in keywords', () => {
    const { getArgs } = useKeywordSignatures()
    // RF BuiltIn → "log" has signature ['message', 'level=INFO', ...]
    expect(getArgs('Log')).toEqual([
      'message', 'level=INFO', 'html=False', 'console=False', 'repr=False',
    ])
  })

  it('is case-insensitive', () => {
    const { getArgs } = useKeywordSignatures()
    expect(getArgs('log')).toEqual(getArgs('LOG'))
  })

  it('returns null for unknown keywords', () => {
    const { getArgs } = useKeywordSignatures()
    expect(getArgs('No Such Keyword')).toBeNull()
  })

  it('returns null for empty / falsy input', () => {
    const { getArgs } = useKeywordSignatures()
    expect(getArgs('')).toBeNull()
  })

  it('dynamic explorer.keywords entries override the static fallback', () => {
    const explorer = useExplorerStore()
    // Push a dynamic library kw shadowing the BuiltIn name
    explorer.keywords.push({
      name: 'Log',
      library: 'CustomLib',
      doc: '',
      args: ['custom_message: str', 'level: int = 5'],
    })
    const { getArgs } = useKeywordSignatures()
    expect(getArgs('Log')).toEqual(['custom_message: str', 'level: int = 5'])
  })

  it('getParsedArgs maps each raw arg through parseArgSignature', () => {
    const explorer = useExplorerStore()
    explorer.keywords.push({
      name: 'Click',
      library: 'Browser',
      doc: '',
      args: ['selector: str', 'button: MouseButton = left'],
    })
    const { getParsedArgs } = useKeywordSignatures()
    const parsed = getParsedArgs('Click')
    expect(parsed).toHaveLength(2)
    expect(parsed![0].name).toBe('selector')
    expect(parsed![1].defaultValue).toBe('left')
  })

  describe('getKeywordInfo (Story EDITOR-7)', () => {
    it('returns display + library + doc for dynamic-library keywords', () => {
      const explorer = useExplorerStore()
      explorer.keywords.push({
        name: 'Click',
        library: 'Browser',
        doc: 'Clicks the element identified by ``selector``.',
        args: ['selector: str', 'button: MouseButton = left'],
      })
      const { getKeywordInfo } = useKeywordSignatures()
      const info = getKeywordInfo('Click')
      expect(info).not.toBeNull()
      expect(info!.display).toBe('Click')
      expect(info!.library).toBe('Browser')
      expect(info!.doc).toContain('Clicks the element')
      expect(info!.args).toEqual(['selector: str', 'button: MouseButton = left'])
    })

    it('falls back to "BuiltIn" + empty doc for static-fallback keywords', () => {
      const { getKeywordInfo } = useKeywordSignatures()
      const info = getKeywordInfo('Log')
      expect(info).not.toBeNull()
      expect(info!.library).toBe('BuiltIn')
      expect(info!.doc).toBe('')
      expect(info!.args.length).toBeGreaterThan(0)
    })

    it('returns null for unknown keywords', () => {
      const { getKeywordInfo } = useKeywordSignatures()
      expect(getKeywordInfo('No Such Keyword')).toBeNull()
    })

    it('preserves the library author casing in display', () => {
      const explorer = useExplorerStore()
      explorer.keywords.push({
        name: 'Get Element By XPath',
        library: 'Browser',
        doc: '',
        args: ['xpath: str'],
      })
      const { getKeywordInfo } = useKeywordSignatures()
      const info = getKeywordInfo('GET ELEMENT BY XPATH')
      expect(info!.display).toBe('Get Element By XPath')
    })
  })
})
