/**
 * Edge-case-hunter follow-up — round-trip data-loss fixes.
 * (Story: Flow Editor — Verification & Hardening, hardening pass.)
 */
import { describe, it, expect } from 'vitest'
import { parseRobotText, serializeRobotForm } from '@/components/editor/robotTextIO'

const rt = (s: string) => serializeRobotForm(parseRobotText(s))

describe('ECH — control-line inline comment is preserved', () => {
  it('keeps a trailing comment on an IF line', () => {
    const src = '*** Test Cases ***\nT\n    IF    ${x}    # decide\n        Log    a\n    END\n'
    const out = rt(src)
    expect(out).toContain('# decide')
    // re-parse keeps it on the IF step
    const ifStep = parseRobotText(out).testCases[0].steps.find((s) => s.type === 'if')
    expect(ifStep?.trailingComment).toBe('# decide')
  })

  it('keeps a trailing comment on a FOR line', () => {
    const src = '*** Test Cases ***\nT\n    FOR    ${i}    IN    1    2    # loop\n        Log    ${i}\n    END\n'
    expect(rt(src)).toContain('# loop')
  })
})

describe('ECH — template data cells survive special content', () => {
  it("a cell starting with '#' is escaped and round-trips as data, not a comment", () => {
    const src = '*** Test Cases ***\nT\n    [Template]    Click Should Work\n    #login-form    ok\n'
    const out = rt(src)
    expect(out).toContain('\\#login-form')   // escaped in output
    const tc = parseRobotText(out).testCases[0]
    expect(tc.templateRows).toEqual([['#login-form', 'ok']])
  })

  it('a cell with an internal double space survives round-trip', () => {
    // Build the form directly (a user typing a 2-space cell in the table UI).
    const form = parseRobotText('*** Test Cases ***\nT\n    [Template]    Check\n    a    b\n')
    form.testCases[0].templateRows = [['hello  world', 'x']]
    const out = serializeRobotForm(form)
    const tc = parseRobotText(out).testCases[0]
    expect(tc.templateRows).toEqual([['hello  world', 'x']])
  })
})

describe('ECH — [Template] declared AFTER data rows', () => {
  it('still routes the rows to templateRows, not keyword steps', () => {
    const src = '*** Test Cases ***\nT\n    1    2    3\n    [Template]    Add Should Be\n    5    7    12\n'
    const tc = parseRobotText(src).testCases[0]
    expect(tc.template).toBe('Add Should Be')
    expect(tc.steps).toHaveLength(0)
    expect(tc.templateRows).toEqual([['1', '2', '3'], ['5', '7', '12']])
  })
})
