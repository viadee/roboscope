/**
 * Story FE-TPL — [Template] data-driven rows.
 */
import { describe, it, expect } from 'vitest'
import { parseRobotText, serializeRobotForm } from '@/components/editor/robotTextIO'
import { robotFormToFlow, type RobotForm } from '@/components/editor/flow/flowConverter'

const TEMPLATED = [
  '*** Test Cases ***',
  'Addition',
  '    [Template]    Add Should Be',
  '    1    2    3',
  '    5    7    12',
  '', '',
].join('\n')

describe('FE-TPL — parser routes body rows to templateRows', () => {
  it('parses data rows as templateRows, not keyword steps', () => {
    const tc = parseRobotText(TEMPLATED).testCases[0]
    expect(tc.template).toBe('Add Should Be')
    expect(tc.steps).toHaveLength(0)
    expect(tc.templateRows).toEqual([['1', '2', '3'], ['5', '7', '12']])
  })

  it('round-trips data rows (RF-equivalent)', () => {
    const out = serializeRobotForm(parseRobotText(TEMPLATED))
    expect(out).toContain('[Template]    Add Should Be')
    expect(out).toContain('1    2    3')
    expect(out).toContain('5    7    12')
    // idempotent second pass
    expect(serializeRobotForm(parseRobotText(out))).toBe(out)
  })

  it('leaves a NON-templated test as keyword steps (unaffected)', () => {
    const src = '*** Test Cases ***\nPlain\n    Log    hi\n    Click    btn\n'
    const tc = parseRobotText(src).testCases[0]
    expect(tc.templateRows).toBeUndefined()
    expect(tc.steps.map((s) => s.keyword)).toEqual(['Log', 'Click'])
  })

  it('a `...` continuation extends the previous data row', () => {
    const src = [
      '*** Test Cases ***', 'T',
      '    [Template]    Check',
      '    a    b',
      '    ...    c    d', '',
    ].join('\n')
    const tc = parseRobotText(src).testCases[0]
    expect(tc.templateRows).toEqual([['a', 'b', 'c', 'd']])
  })

  it('a control structure inside a templated test stays a step', () => {
    const src = [
      '*** Test Cases ***', 'T',
      '    [Template]    Check',
      '    FOR    ${x}    IN    1    2',
      '        ${x}    ${x}',
      '    END', '',
    ].join('\n')
    const tc = parseRobotText(src).testCases[0]
    expect(tc.steps.some((s) => s.type === 'for')).toBe(true)
    expect(tc.steps.some((s) => s.type === 'end')).toBe(true)
  })
})

describe('FE-TPL — converter emits a template-table node', () => {
  function templatedForm(): RobotForm {
    const f = parseRobotText(TEMPLATED) as unknown as RobotForm
    return f
  }
  it('produces a template-table node carrying the rows + keyword', () => {
    const { nodes } = robotFormToFlow(templatedForm())
    const table = nodes.find((n) => n.type === 'template-table')
    expect(table).toBeTruthy()
    expect(table!.data.templateKeyword).toBe('Add Should Be')
    expect(table!.data.templateRows).toEqual([['1', '2', '3'], ['5', '7', '12']])
  })
})
