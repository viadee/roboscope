/**
 * Story FE-BDD — Gherkin/BDD prefix awareness.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { splitBddPrefix } from '@/utils/robotKeywordSignatures'
import { robotFormToFlow, type RobotForm } from '@/components/editor/flow/flowConverter'
import { useExplorerStore } from '@/stores/explorer.store'
import { useKeywordSignatures } from '@/composables/useKeywordSignatures'

describe('splitBddPrefix', () => {
  it('splits each prefix case-insensitively, canonicalising to Title-case', () => {
    expect(splitBddPrefix('Given user logs in')).toEqual({ prefix: 'Given', rest: 'user logs in' })
    expect(splitBddPrefix('WHEN Login')).toEqual({ prefix: 'When', rest: 'Login' })
    expect(splitBddPrefix('then result is shown')).toEqual({ prefix: 'Then', rest: 'result is shown' })
    expect(splitBddPrefix('And another step')).toEqual({ prefix: 'And', rest: 'another step' })
    expect(splitBddPrefix('But not this')).toEqual({ prefix: 'But', rest: 'not this' })
  })

  it('returns null without a prefix or without a trailing word', () => {
    expect(splitBddPrefix('Click')).toBeNull()
    expect(splitBddPrefix('Given')).toBeNull()        // no following word
    expect(splitBddPrefix('Givenish thing')).toBeNull() // not a real prefix token
    expect(splitBddPrefix('')).toBeNull()
  })
})

describe('FE-BDD — converter flags BDD keyword nodes', () => {
  function formWith(keyword: string): RobotForm {
    return {
      settings: [], variables: [], testCases: [{
        name: 'T', documentation: '', tags: [], setup: '', teardown: '',
        timeout: '', template: '', steps: [{
          type: 'keyword', keyword, args: [], returnVars: [], condition: '',
          loopVar: '', loopFlavor: 'IN', loopValues: [], exceptPattern: '',
          exceptVar: '', varScope: '', comment: '',
        }],
      }], keywords: [], preambleLines: [],
    } as unknown as RobotForm
  }

  it('sets bdd on a Given step and leaves a plain step null', () => {
    const bddNode = robotFormToFlow(formWith('Given user logs in')).nodes
      .find((n) => n.type === 'keyword')
    expect(bddNode?.data.bdd).toEqual({ prefix: 'Given', rest: 'user logs in' })

    const plainNode = robotFormToFlow(formWith('Click')).nodes
      .find((n) => n.type === 'keyword')
    expect(plainNode?.data.bdd).toBeNull()
  })
})

describe('FE-BDD — signature falls back to the stripped name', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('resolves "When Log" against Log\'s BuiltIn signature', () => {
    const { getArgs } = useKeywordSignatures()
    const stripped = getArgs('When Log')
    expect(stripped).toEqual(getArgs('Log'))
    expect(stripped).not.toBeNull()
  })

  it('prefers a verbatim keyword that literally includes the prefix', () => {
    const explorer = useExplorerStore()
    explorer.keywords.push({
      name: 'Given User Logs In', library: 'proj', doc: '', args: ['role'],
    })
    const { getArgs } = useKeywordSignatures()
    expect(getArgs('Given User Logs In')).toEqual(['role'])
  })
})
