/**
 * DEBUG-3 follow-up: live step-line computation.
 *
 * The "Bis hier ausführen" button used to read `step._lineNumber`
 * which the parser stamps once at file-load. After the user inserted
 * a new keyword above the selected step, every subsequent step's
 * stale `_lineNumber` pointed at the wrong .robot line — debug broke
 * one keyword too early.
 *
 * `computeStepLine(form, isResource, tcIdx, stepIdx)` mirrors the
 * serializer line-for-line, so its result tracks any structural edit
 * the user makes in the editor.
 */
import { describe, it, expect } from 'vitest'
import {
  computeStepLine,
  type RobotForm,
  type RobotStep,
  type RobotTestCase,
} from '@/components/editor/flow/flowConverter'

function step(keyword: string, args: string[] = []): RobotStep {
  return {
    type: 'keyword',
    keyword,
    args,
    returnVars: [],
    condition: '',
    loopVar: '',
    loopFlavor: '',
    loopValues: [],
    exceptPattern: '',
    exceptVar: '',
    varScope: '',
    comment: '',
  }
}

function testCase(name: string, steps: RobotStep[], extra: Partial<RobotTestCase> = {}): RobotTestCase {
  return {
    name,
    documentation: '',
    tags: [],
    setup: '',
    teardown: '',
    timeout: '',
    template: '',
    steps,
    ...extra,
  }
}

function makeForm(testCases: RobotTestCase[], extra: Partial<RobotForm> = {}): RobotForm {
  return {
    settings: [],
    variables: [],
    keywords: [],
    preambleLines: [],
    testCases,
    ...extra,
  }
}

describe('computeStepLine — minimal file', () => {
  it('returns 3 for the first step in a single-test no-metadata file', () => {
    // File:
    //   1: *** Test Cases ***
    //   2: Demo
    //   3:     Log    one
    //   4:     Log    two
    const form = makeForm([
      testCase('Demo', [step('Log', ['one']), step('Log', ['two'])]),
    ])
    expect(computeStepLine(form, false, 0, 0)).toBe(3)
    expect(computeStepLine(form, false, 0, 1)).toBe(4)
  })

  it('returns null for resource files', () => {
    const form = makeForm([testCase('Demo', [step('Log', ['x'])])])
    expect(computeStepLine(form, true, 0, 0)).toBeNull()
  })

  it('returns null for out-of-range indices', () => {
    const form = makeForm([testCase('Demo', [step('Log', ['x'])])])
    expect(computeStepLine(form, false, 5, 0)).toBeNull()
    expect(computeStepLine(form, false, 0, 5)).toBeNull()
    expect(computeStepLine(form, false, -1, 0)).toBeNull()
  })
})

describe('computeStepLine — live updates after structural edits', () => {
  it('PRIMARY REGRESSION: inserting a step above shifts subsequent step lines', () => {
    // Initial: Demo with two Logs. Step 1 ("Log two") is on line 4.
    let form = makeForm([
      testCase('Demo', [step('Log', ['one']), step('Log', ['two'])]),
    ])
    expect(computeStepLine(form, false, 0, 1)).toBe(4)

    // User inserts a new keyword between the two — same step (now
    // index 2) MUST report line 5, not the stale 4 the old
    // _lineNumber-based path would have returned.
    form = makeForm([
      testCase('Demo', [
        step('Log', ['one']),
        step('Log', ['inserted']),
        step('Log', ['two']),
      ]),
    ])
    expect(computeStepLine(form, false, 0, 2)).toBe(5)
  })

  it('removing a step shifts subsequent step lines DOWN', () => {
    let form = makeForm([
      testCase('Demo', [
        step('Log', ['one']),
        step('Log', ['removeMe']),
        step('Log', ['three']),
      ]),
    ])
    expect(computeStepLine(form, false, 0, 2)).toBe(5)

    form = makeForm([
      testCase('Demo', [step('Log', ['one']), step('Log', ['three'])]),
    ])
    expect(computeStepLine(form, false, 0, 1)).toBe(4)
  })
})

describe('computeStepLine — metadata lines push step bodies down', () => {
  it('counts [Documentation] (single-line) +1', () => {
    // 1: *** Test Cases ***
    // 2: Demo
    // 3:     [Documentation]    a doc
    // 4:     Log    x
    const form = makeForm([
      testCase('Demo', [step('Log', ['x'])], { documentation: 'a doc' }),
    ])
    expect(computeStepLine(form, false, 0, 0)).toBe(4)
  })

  it('counts multi-line [Documentation] continuations', () => {
    // 1: *** Test Cases ***
    // 2: Demo
    // 3:     [Documentation]    line 1
    // 4:     ...    line 2
    // 5:     ...    line 3
    // 6:     Log    x
    const form = makeForm([
      testCase('Demo', [step('Log', ['x'])], {
        documentation: 'line 1\nline 2\nline 3',
      }),
    ])
    expect(computeStepLine(form, false, 0, 0)).toBe(6)
  })

  it('counts every metadata setting that is set', () => {
    // 1: *** Test Cases ***
    // 2: Demo
    // 3:     [Documentation]    doc
    // 4:     [Tags]    a    b
    // 5:     [Setup]    Some Kw
    // 6:     [Teardown]    Some Kw
    // 7:     [Timeout]    1m
    // 8:     [Template]    Run Test
    // 9:     Log    x
    const form = makeForm([
      testCase('Demo', [step('Log', ['x'])], {
        documentation: 'doc',
        tags: ['a', 'b'],
        setup: 'Some Kw',
        teardown: 'Some Kw',
        timeout: '1m',
        template: 'Run Test',
      }),
    ])
    expect(computeStepLine(form, false, 0, 0)).toBe(9)
  })
})

describe('computeStepLine — multi-test-case files', () => {
  it('stacks test cases with a trailing blank between them', () => {
    // 1: *** Test Cases ***
    // 2: Alpha
    // 3:     Log    a
    // 4: (blank)
    // 5: Beta
    // 6:     Log    b
    const form = makeForm([
      testCase('Alpha', [step('Log', ['a'])]),
      testCase('Beta', [step('Log', ['b'])]),
    ])
    expect(computeStepLine(form, false, 0, 0)).toBe(3)
    expect(computeStepLine(form, false, 1, 0)).toBe(6)
  })

  it('handles middle-test-case after a documented one', () => {
    // 1: *** Test Cases ***
    // 2: Alpha
    // 3:     [Documentation]    a
    // 4:     Log    a
    // 5: (blank)
    // 6: Beta
    // 7:     Log    b
    const form = makeForm([
      testCase('Alpha', [step('Log', ['a'])], { documentation: 'a' }),
      testCase('Beta', [step('Log', ['b'])]),
    ])
    expect(computeStepLine(form, false, 1, 0)).toBe(7)
  })
})

describe('computeStepLine — sections above test cases shift everything', () => {
  it('Settings section pushes the test cases down', () => {
    // 1: *** Settings ***
    // 2: Library    Browser
    // 3: (blank)
    // 4: *** Test Cases ***
    // 5: Demo
    // 6:     Log    x
    const form = makeForm([testCase('Demo', [step('Log', ['x'])])], {
      settings: [{ key: 'Library', value: 'Browser', args: [] }],
    })
    expect(computeStepLine(form, false, 0, 0)).toBe(6)
  })

  it('Variables section between Settings and Test Cases', () => {
    // 1: *** Settings ***
    // 2: Library    Browser
    // 3: (blank)
    // 4: *** Variables ***
    // 5: ${X}    1
    // 6: (blank)
    // 7: *** Test Cases ***
    // 8: Demo
    // 9:     Log    x
    const form = makeForm([testCase('Demo', [step('Log', ['x'])])], {
      settings: [{ key: 'Library', value: 'Browser', args: [] }],
      variables: [{ name: '${X}', value: '1' }],
    })
    expect(computeStepLine(form, false, 0, 0)).toBe(9)
  })

  it('preambleLines (a leading comment) push everything by their length', () => {
    // 1: # leading comment
    // 2: (blank)
    // 3: *** Test Cases ***
    // 4: Demo
    // 5:     Log    x
    const form = makeForm([testCase('Demo', [step('Log', ['x'])])], {
      preambleLines: ['# leading comment'],
    })
    expect(computeStepLine(form, false, 0, 0)).toBe(5)
  })
})
