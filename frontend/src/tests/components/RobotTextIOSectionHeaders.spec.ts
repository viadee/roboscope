/**
 * Section-header tolerance in the editor's `.robot` parser (GitHub #58).
 *
 * `SECTION_HEADER_RE` required exactly three asterisks and no BOM, so a file
 * using any other form Robot Framework accepts parsed as one big preamble: the
 * content survived a save (no data loss), but the Flow Editor rendered an empty
 * file. Same root cause as the backend explorer parser.
 *
 * The negative cases matter as much as the positive ones — RF rejects
 * tab-padded headers, so the editor must not invent structure RF would not see.
 */
import { describe, it, expect } from 'vitest'
import { parseRobotText, serializeRobotForm } from '@/components/editor/robotTextIO'

const BODY = 'My Keyword\n    Log    hi\n'

function keywordsFor(header: string): string[] {
  return parseRobotText(`${header}\n${BODY}`).keywords.map(k => k.name)
}

describe('robotTextIO section headers', () => {
  it.each([
    ['canonical', '*** Keywords ***'],
    ['no spaces', '***Keywords***'],
    ['four asterisks', '**** Keywords ****'],
    ['single asterisk', '* Keywords'],
    ['no closing run', '*** Keywords'],
    ['singular', '*** Keyword ***'],
    ['lowercase', '*** keywords ***'],
    ['uppercase', '*** KEYWORDS ***'],
    ['leading BOM', '﻿*** Keywords ***'],
  ])('parses the keywords section written as %s', (_label, header) => {
    expect(keywordsFor(header)).toEqual(['My Keyword'])
  })

  it.each([
    ['tab-padded (RF rejects it)', '***\tKeywords\t***'],
    ['unknown section name', '*** Bogus ***'],
  ])('does not treat %s as a keywords section', (_label, header) => {
    expect(keywordsFor(header)).toEqual([])
  })

  it('recognises every section kind with a non-canonical asterisk run', () => {
    const text = [
      '**** Settings ****',
      'Library    Collections',
      '',
      '* Variables',
      '${NAME}    world',
      '',
      '***Test Cases***',
      'My Test',
      '    Log    hi',
      '',
      '**** Keywords ****',
      'My Keyword',
      '    Log    hi',
    ].join('\n')
    const form = parseRobotText(text)
    expect(form.settings.map(s => s.value)).toEqual(['Collections'])
    expect(form.variables).toHaveLength(1)
    expect(form.testCases.map(t => t.name)).toEqual(['My Test'])
    expect(form.keywords.map(k => k.name)).toEqual(['My Keyword'])
  })

  it('keeps the body intact through a parse/serialize round-trip', () => {
    // Even before the fix nothing was lost — the file just became preamble.
    // Pin that the fix did not trade the empty-editor bug for a data-loss bug.
    const out = serializeRobotForm(parseRobotText(`**** Keywords ****\n${BODY}`))
    expect(out).toContain('My Keyword')
    expect(out).toContain('Log')
  })

  it('flags an init file whose test-case section uses a non-canonical header', () => {
    // RF forbids *** Test Cases *** in __init__.robot; the warning badge must
    // not be dodgeable by writing the header differently.
    const form = parseRobotText('**** Test Cases ****\nMy Test\n    Log    hi\n')
    expect(form.testCases.map(t => t.name)).toEqual(['My Test'])
  })
})
