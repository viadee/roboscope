/**
 * Control-structure nesting round-trip (Story: Flow Editor — Verification &
 * Hardening, AC-D). Parse→serialize→parse must conserve nested FOR/IF/WHILE/
 * TRY blocks and their matching END markers at depth.
 */
import { describe, it, expect } from 'vitest'
import { parseRobotText, serializeRobotForm, type RobotStep } from '@/components/editor/robotTextIO'

function steps(src: string): RobotStep[] {
  const form = parseRobotText(src)
  return form.testCases[0]?.steps ?? form.keywords[0]?.steps ?? []
}

function roundTripTypes(src: string): string[] {
  const out = serializeRobotForm(parseRobotText(src))
  return steps(out).map((s) => s.type)
}

describe('FlowEditor control structures — nesting round-trip', () => {
  it('nested FOR inside IF preserves blocks + both ENDs', () => {
    const src = [
      '*** Test Cases ***', 'T',
      '    IF    ${cond}',
      '        FOR    ${i}    IN RANGE    3',
      '            Log    ${i}',
      '        END',
      '    ELSE',
      '        Log    nope',
      '    END', '',
    ].join('\n')
    const types = roundTripTypes(src)
    expect(types.filter((t) => t === 'if')).toHaveLength(1)
    expect(types.filter((t) => t === 'for')).toHaveLength(1)
    expect(types.filter((t) => t === 'else')).toHaveLength(1)
    expect(types.filter((t) => t === 'end')).toHaveLength(2)
  })

  it('TRY / EXCEPT AS / FINALLY round-trips with the exception var', () => {
    const src = [
      '*** Test Cases ***', 'T',
      '    TRY',
      '        Do Thing',
      '    EXCEPT    Some Error    AS    ${err}',
      '        Log    ${err}',
      '    FINALLY',
      '        Cleanup',
      '    END', '',
    ].join('\n')
    const out = serializeRobotForm(parseRobotText(src))
    const ss = steps(out)
    expect(ss.map((s) => s.type)).toEqual(
      ['try', 'keyword', 'except', 'keyword', 'finally', 'keyword', 'end'],
    )
    const except = ss.find((s) => s.type === 'except')!
    expect(except.exceptPattern).toBe('Some Error')
    expect(except.exceptVar).toBe('${err}')
    expect(out).toContain('EXCEPT    Some Error    AS    ${err}')
  })

  it('WHILE with a limit= argument survives', () => {
    const src = [
      '*** Test Cases ***', 'T',
      '    WHILE    $x < 5    limit=10',
      '        Log    loop',
      '    END', '',
    ].join('\n')
    const out = serializeRobotForm(parseRobotText(src))
    expect(out).toContain('WHILE    $x < 5    limit=10')
    expect(steps(out).filter((s) => s.type === 'end')).toHaveLength(1)
  })

  it('END matching is conserved at depth 3 (FOR>IF>FOR)', () => {
    const src = [
      '*** Test Cases ***', 'T',
      '    FOR    ${a}    IN    @{xs}',
      '        IF    ${a}',
      '            FOR    ${b}    IN    @{ys}',
      '                Log    ${b}',
      '            END',
      '        END',
      '    END', '',
    ].join('\n')
    const types = roundTripTypes(src)
    expect(types.filter((t) => t === 'for')).toHaveLength(2)
    expect(types.filter((t) => t === 'if')).toHaveLength(1)
    expect(types.filter((t) => t === 'end')).toHaveLength(3)
    // double round-trip is byte-stable
    const a = serializeRobotForm(parseRobotText(src))
    const b = serializeRobotForm(parseRobotText(a))
    expect(b).toBe(a)
  })

  it('BREAK / CONTINUE inside a loop are preserved', () => {
    const src = [
      '*** Test Cases ***', 'T',
      '    FOR    ${i}    IN RANGE    10',
      '        IF    ${i} == 5',
      '            BREAK',
      '        END',
      '        CONTINUE',
      '    END', '',
    ].join('\n')
    const types = roundTripTypes(src)
    expect(types).toContain('break')
    expect(types).toContain('continue')
    expect(types.filter((t) => t === 'end')).toHaveLength(2)
  })
})
