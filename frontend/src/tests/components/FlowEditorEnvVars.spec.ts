/**
 * Story FE-ENV — %{ENV} environment-variable awareness.
 */
import { describe, it, expect } from 'vitest'
import { extractEnvVarRefs, collectEnvVarRefs } from '@/utils/robotEnvVars'
import { parseRobotText, serializeRobotForm } from '@/components/editor/robotTextIO'
import { robotFormToFlow, type RobotForm } from '@/components/editor/flow/flowConverter'

describe('extractEnvVarRefs', () => {
  it('finds none in plain text', () => {
    expect(extractEnvVarRefs('Log    hello ${x}')).toEqual([])
  })
  it('finds a bare ref', () => {
    expect(extractEnvVarRefs('%{HOME}')).toEqual([{ name: 'HOME', default: null }])
  })
  it('captures an inline default', () => {
    expect(extractEnvVarRefs('%{PORT=8080}')).toEqual([{ name: 'PORT', default: '8080' }])
  })
  it('finds multiple, mixed with ${} (which is ignored)', () => {
    expect(extractEnvVarRefs('%{A} and ${B} and %{C=1}')).toEqual([
      { name: 'A', default: null },
      { name: 'C', default: '1' },
    ])
  })
})

describe('collectEnvVarRefs — de-dupe, default wins', () => {
  it('dedupes by name and keeps the default from any occurrence', () => {
    expect(collectEnvVarRefs(['%{HOME}', '%{HOME=/root}', '%{X}'])).toEqual([
      { name: 'HOME', default: '/root' },
      { name: 'X', default: null },
    ])
  })
})

describe('FE-ENV — converter flags steps with env refs', () => {
  function formWithArg(arg: string): RobotForm {
    return {
      settings: [], variables: [], testCases: [{
        name: 'T', documentation: '', tags: [], setup: '', teardown: '',
        timeout: '', template: '', steps: [{
          type: 'keyword', keyword: 'Log', args: [arg], returnVars: [], condition: '',
          loopVar: '', loopFlavor: 'IN', loopValues: [], exceptPattern: '',
          exceptVar: '', varScope: '', comment: '',
        }],
      }], keywords: [], preambleLines: [],
    } as unknown as RobotForm
  }

  it('sets envRefs for a %{}-using step, empty otherwise', () => {
    const withEnv = robotFormToFlow(formWithArg('%{HOME=/tmp}')).nodes.find((n) => n.type === 'keyword')
    expect(withEnv?.data.envRefs).toEqual([{ name: 'HOME', default: '/tmp' }])
    const without = robotFormToFlow(formWithArg('plain')).nodes.find((n) => n.type === 'keyword')
    expect(without?.data.envRefs).toEqual([])
  })
})

describe('FE-ENV — %{} survives round-trip (AC4)', () => {
  it('keeps %{NAME} and %{NAME=default} verbatim', () => {
    const src = '*** Test Cases ***\nT\n    Log    %{HOME}\n    Log    %{PORT=8080}\n'
    const out = serializeRobotForm(parseRobotText(src))
    expect(out).toContain('%{HOME}')
    expect(out).toContain('%{PORT=8080}')
  })
})
