import { describe, it, expect } from 'vitest'
import {
  RECORDER_SCHEMA_VERSION,
  validateSchemaVersion,
  activeSelector,
  type RecordedCommand,
  type RecordedFlow,
} from '@/types/recorder.types'

describe('RECORDER_SCHEMA_VERSION', () => {
  it('is 1 for v2 MVP', () => {
    expect(RECORDER_SCHEMA_VERSION).toBe(1)
  })
})

describe('validateSchemaVersion', () => {
  it('accepts the current version', () => {
    expect(() => validateSchemaVersion({ schema_version: 1 })).not.toThrow()
  })

  it('throws when missing', () => {
    expect(() => validateSchemaVersion({})).toThrow(/missing schema_version/)
  })

  it('throws when non-integer', () => {
    expect(() => validateSchemaVersion({ schema_version: '1' })).toThrow(/integer/)
    expect(() => validateSchemaVersion({ schema_version: 1.5 })).toThrow(/integer/)
  })

  it('throws when newer than supported', () => {
    expect(() => validateSchemaVersion({ schema_version: 99 })).toThrow(/newer than supported/)
  })

  it('throws when below 1', () => {
    expect(() => validateSchemaVersion({ schema_version: 0 })).toThrow(/>= 1/)
  })
})

describe('activeSelector', () => {
  it('returns null for a no-target command', () => {
    const cmd: RecordedCommand = {
      index: 0,
      keyword: 'Go To',
      args: { url: 'https://example.com' },
      selector_candidates: [],
      active_candidate_index: 0,
    }
    expect(activeSelector(cmd)).toBeNull()
  })

  it('returns the active candidate by index', () => {
    const cmd: RecordedCommand = {
      index: 0,
      keyword: 'Click',
      args: {},
      selector_candidates: [
        { strategy: 'testid', value: 'a', quality_score: 95, verified_unique: true },
        { strategy: 'css', value: '.a', quality_score: 50, verified_unique: false },
      ],
      active_candidate_index: 1,
    }
    expect(activeSelector(cmd)?.strategy).toBe('css')
  })
})

describe('RecordedFlow shape stability', () => {
  it('round-trips through JSON', () => {
    const original: RecordedFlow = {
      schema_version: 1,
      transport: 'web_playwright',
      session_id: 's-1',
      name: 'Login',
      commands: [
        {
          index: 0,
          keyword: 'Click',
          args: {},
          selector_candidates: [
            { strategy: 'testid', value: 'btn', quality_score: 95, verified_unique: true },
          ],
          active_candidate_index: 0,
        },
      ],
    }
    const roundTripped = JSON.parse(JSON.stringify(original)) as RecordedFlow
    expect(roundTripped).toEqual(original)
  })
})
