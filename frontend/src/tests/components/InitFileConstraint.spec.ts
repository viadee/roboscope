/** EXEC.6 — __init__.robot init-file constraint helpers. */
import { describe, it, expect } from 'vitest'
import {
  isInitFile,
  initFileHasTestCases,
  parseRobotText,
  serializeRobotForm,
} from '@/components/editor/robotTextIO'

describe('isInitFile', () => {
  it('matches __init__.robot in any directory', () => {
    expect(isInitFile('__init__.robot')).toBe(true)
    expect(isInitFile('tests/suite/__init__.robot')).toBe(true)
    expect(isInitFile('tests\\suite\\__init__.robot')).toBe(true)
  })
  it('does not match regular robot files', () => {
    expect(isInitFile('tests/login.robot')).toBe(false)
    expect(isInitFile('tests/my__init__.robot')).toBe(false)
    expect(isInitFile(null)).toBe(false)
    expect(isInitFile(undefined)).toBe(false)
  })
})

describe('initFileHasTestCases', () => {
  it('detects a Test Cases section', () => {
    expect(initFileHasTestCases('*** Settings ***\n*** Test Cases ***\nFoo\n    Log    hi')).toBe(true)
  })
  it('detects a Tasks section', () => {
    expect(initFileHasTestCases('*** Tasks ***\nDo')).toBe(true)
  })
  it('is false for a valid init file (settings/keywords only)', () => {
    expect(initFileHasTestCases('*** Settings ***\nSuite Setup    Log    start\n\n*** Keywords ***\nHelper\n    No Operation')).toBe(false)
  })
})

// EXEC.6 AC: the parse→serialize round-trip must NOT corrupt init-only suite
// settings (Name / Suite Setup / Suite Teardown / imports). Pinned here.
describe('__init__.robot round-trip fidelity', () => {
  const INIT = [
    '*** Settings ***',
    'Name              Acceptance Suite',
    'Documentation     Suite-level init for the acceptance tree.',
    'Library           Collections',
    'Resource          ../resources/common.resource',
    'Suite Setup       Log    starting suite',
    'Suite Teardown    Log    finished suite',
    '',
    '*** Keywords ***',
    'Helper',
    '    No Operation',
    '',
  ].join('\n')

  function settingsMap(content: string): Record<string, string> {
    const form = parseRobotText(content)
    const out: Record<string, string> = {}
    for (const s of form.settings) {
      out[s.key] = [s.value, ...s.args].filter(Boolean).join('    ')
    }
    return out
  }

  it('preserves all init-only settings across parse→serialize→parse', () => {
    const form = parseRobotText(INIT)
    const serialized = serializeRobotForm(form, { isResource: false })
    const before = settingsMap(INIT)
    const after = settingsMap(serialized)

    expect(after).toEqual(before)
    expect(after['Name']).toBe('Acceptance Suite')
    expect(after['Suite Setup']).toBe('Log    starting suite')
    expect(after['Suite Teardown']).toBe('Log    finished suite')
    expect(after['Library']).toBe('Collections')
    expect(after['Resource']).toBe('../resources/common.resource')
  })

  it('round-trips an init file without inventing a Test Cases section', () => {
    const serialized = serializeRobotForm(parseRobotText(INIT), { isResource: false })
    expect(initFileHasTestCases(serialized)).toBe(false)
    expect(parseRobotText(serialized).testCases).toHaveLength(0)
  })
})
