/**
 * Round-trip fidelity for the RobotEditor parse↔serialize path
 * (Story: Flow Editor — Verification & Hardening, AC-A).
 *
 * The contract is NOT byte-identity on the first pass — cell separators are
 * normalised to four spaces and blank body lines are dropped (documented,
 * RF-safe normalisation). The contract is:
 *   1. IDEMPOTENCY — a second round-trip is byte-identical to the first
 *      (serialize stabilises; no progressive drift).
 *   2. NO SILENT CORRUPTION — inline trailing comments, column-0 leading
 *      comments, escapes, `${}`/`@{}`/`&{}`/`%{}` variables, and nested
 *      control structures survive parse→serialize→parse unchanged.
 *   3. The serialized output re-parses to a structurally equal form.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import {
  parseRobotText,
  serializeRobotForm,
  type RobotForm,
} from '@/components/editor/robotTextIO'

const FIXTURE_DIR = join(__dirname, 'fixtures', 'roundtrip')
const robotFixtures = readdirSync(FIXTURE_DIR).filter((f) => f.endsWith('.robot'))

function rt(content: string, isResource = false): string {
  return serializeRobotForm(parseRobotText(content), { isResource })
}

describe('robotTextIO — round-trip fidelity', () => {
  describe('AC-A1/AC-A: idempotency over a real golden corpus', () => {
    it('has at least the seeded example fixtures', () => {
      expect(robotFixtures.length).toBeGreaterThanOrEqual(4)
    })

    for (const file of robotFixtures) {
      it(`is idempotent: ${file}`, () => {
        const content = readFileSync(join(FIXTURE_DIR, file), 'utf-8')
        const pass1 = rt(content)
        const pass2 = rt(pass1)
        // A second round-trip must not change anything the first produced.
        expect(pass2).toBe(pass1)
      })

      it(`re-parses to a structurally stable form: ${file}`, () => {
        const content = readFileSync(join(FIXTURE_DIR, file), 'utf-8')
        const form1 = parseRobotText(content)
        const form2 = parseRobotText(serializeRobotForm(form1))
        expect(stripLineNumbers(form2)).toEqual(stripLineNumbers(form1))
      })
    }
  })

  describe('AC-A2: inline trailing comments survive (no longer swallowed as \\# arg)', () => {
    it('keeps an inline comment after a keyword step', () => {
      const src = '*** Test Cases ***\nT\n    Click    ${sel}    # wait for it\n'
      const form = parseRobotText(src)
      const step = form.testCases[0].steps[0]
      expect(step.type).toBe('keyword')
      expect(step.keyword).toBe('Click')
      expect(step.args).toEqual(['${sel}'])
      expect(step.trailingComment).toBe('# wait for it')
      // and it round-trips, NOT as an escaped arg
      const out = serializeRobotForm(form)
      expect(out).toContain('Click    ${sel}    # wait for it')
      expect(out).not.toContain('\\#')
    })

    it('keeps an inline comment after an assignment step', () => {
      const src = '*** Test Cases ***\nT\n    ${x}=    Get Value    # note\n'
      const out = rt(src)
      expect(out).toContain('${x}=    Get Value    # note')
    })

    it('does NOT treat a real escaped #-selector arg as a comment', () => {
      const src = '*** Test Cases ***\nT\n    Click    \\#login-form\n'
      const form = parseRobotText(src)
      const step = form.testCases[0].steps[0]
      expect(step.args).toEqual(['#login-form']) // unescaped in-memory
      expect(step.trailingComment).toBeUndefined()
      expect(serializeRobotForm(form)).toContain('Click    \\#login-form')
    })
  })

  describe('AC-A: column-0 comments are not turned into test cases', () => {
    it('preserves a comment above a test case as a leading comment', () => {
      const src = '*** Test Cases ***\n# section note\nReal Test\n    Log    hi\n'
      const form = parseRobotText(src)
      expect(form.testCases).toHaveLength(1)
      expect(form.testCases[0].name).toBe('Real Test')
      expect(form.testCases[0].leadingComments).toEqual(['# section note'])
      const out = serializeRobotForm(form)
      expect(out).toContain('# section note')
      expect(out).toContain('Real Test')
    })
  })

  describe('AC-A2: continuation lines fold and round-trip', () => {
    it('folds [Documentation] continuation', () => {
      const src = '*** Test Cases ***\nT\n    [Documentation]    line one\n    ...    line two\n    Log    x\n'
      const form = parseRobotText(src)
      expect(form.testCases[0].documentation).toBe('line one\nline two')
      const out = rt(src)
      expect(out).toContain('[Documentation]    line one')
      expect(out).toContain('...    line two')
    })

    it('folds keyword-arg continuation into a single call', () => {
      const src = '*** Test Cases ***\nT\n    Log Many    a    b\n    ...    c    d\n'
      const form = parseRobotText(src)
      expect(form.testCases[0].steps[0].args).toEqual(['a', 'b', 'c', 'd'])
    })
  })

  describe('AC-C5: variable references survive as arg values', () => {
    it('keeps ${}, @{}, &{}, %{} verbatim', () => {
      const src =
        '*** Test Cases ***\nT\n' +
        '    Log    ${SCALAR}\n' +
        '    Log Many    @{LIST}\n' +
        '    Set To Dictionary    &{DICT}\n' +
        '    Log    %{ENV_VAR}\n'
      const out = rt(src)
      expect(out).toContain('Log    ${SCALAR}')
      expect(out).toContain('Log Many    @{LIST}')
      expect(out).toContain('Set To Dictionary    &{DICT}')
      expect(out).toContain('Log    %{ENV_VAR}')
    })
  })

  describe('AC-D2: nested control structures round-trip', () => {
    it('preserves FOR-in-IF with matching END at depth', () => {
      const form = parseRobotText(
        readFileSync(join(FIXTURE_DIR, 'kitchen_sink.robot'), 'utf-8'),
      )
      const out = serializeRobotForm(form)
      // Re-parse and count structure markers — they must be conserved.
      const reparsed = parseRobotText(out)
      const flat = reparsed.testCases.flatMap((tc) => tc.steps.map((s) => s.type))
      expect(flat.filter((t) => t === 'if')).toHaveLength(1)
      expect(flat.filter((t) => t === 'for')).toHaveLength(1)
      expect(flat.filter((t) => t === 'else')).toHaveLength(1)
      expect(flat.filter((t) => t === 'end')).toHaveLength(2)
    })

    it('preserves RETURN inside a keyword', () => {
      const form = parseRobotText(
        readFileSync(join(FIXTURE_DIR, 'kitchen_sink.robot'), 'utf-8'),
      )
      const kw = form.keywords.find((k) => k.name === 'Open Site')
      expect(kw).toBeTruthy()
      expect(kw!.steps.some((s) => s.type === 'return')).toBe(true)
    })
  })
})

// Helper: strip the metadata-only _lineNumber so structural equality holds
// (line numbers legitimately shift after the first normalisation pass).
function stripLineNumbers(form: RobotForm): RobotForm {
  const clone: RobotForm = JSON.parse(JSON.stringify(form))
  for (const tc of clone.testCases) for (const s of tc.steps) delete s._lineNumber
  for (const kw of clone.keywords) for (const s of kw.steps) delete s._lineNumber
  return clone
}
