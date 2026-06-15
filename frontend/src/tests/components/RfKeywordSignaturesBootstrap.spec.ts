/**
 * Story FE-KWSRC — the static signature map is a STANDARD-LIBRARY-ONLY
 * bootstrap; libdoc-per-environment is the universal source and overrides it.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import {
  RF_KEYWORD_SIGNATURES,
  RF_BOOTSTRAP_SIGNATURES,
} from '@/utils/robotKeywordSignatures'
import { useExplorerStore } from '@/stores/explorer.store'
import { useKeywordSignatures } from '@/composables/useKeywordSignatures'

describe('FE-KWSRC — bootstrap map invariants', () => {
  it('the bootstrap alias is the same map', () => {
    expect(RF_BOOTSTRAP_SIGNATURES).toBe(RF_KEYWORD_SIGNATURES)
  })

  it('contains standard-library essentials', () => {
    expect(RF_KEYWORD_SIGNATURES.has('log')).toBe(true)
    expect(RF_KEYWORD_SIGNATURES.has('should be equal')).toBe(true)
  })

  it('contains NO third-party keywords (those come from libdoc) — shrink, do not grow', () => {
    // Browser / SeleniumLibrary signatures must NOT be baked into the bootstrap.
    const thirdParty = [
      'new browser', 'new page', 'fill text', // Browser
      'open browser', 'input text', 'click element', 'go to', // SeleniumLibrary
    ]
    for (const kw of thirdParty) {
      expect(RF_KEYWORD_SIGNATURES.has(kw)).toBe(false)
    }
  })
})

describe('FE-KWSRC — resolution order libdoc(env) > bootstrap', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('a libdoc/env keyword overrides the bootstrap signature for the same name', () => {
    const explorer = useExplorerStore()
    // Simulate libdoc returning a different signature for a BuiltIn name.
    explorer.keywords.push({
      name: 'Log', library: 'BuiltIn', doc: '', args: ['msg_from_libdoc'],
    })
    const { getArgs } = useKeywordSignatures()
    expect(getArgs('Log')).toEqual(['msg_from_libdoc'])
  })

  it('falls back to bootstrap when libdoc has nothing for the keyword', () => {
    const { getArgs } = useKeywordSignatures()
    expect(getArgs('Log')).not.toBeNull() // from bootstrap
  })
})
