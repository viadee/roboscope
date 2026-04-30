/**
 * RECORDER-FRAMES round-trip — iframe-wrapped selectors land in the
 * .robot as a single token with internal single spaces around the
 * `>>>` cross-frame piercer, e.g.
 *
 *     Click    iframe[src*="x"] >>> button#foo    # rbs:abc12345
 *
 * The FlowEditor's `parseStepLine` splits on 2+ spaces / tabs, which
 * MUST keep the iframe wrap as one token. If a future "let me make
 * the splitter more flexible" tweak ever started splitting on single
 * spaces, every iframe-recorded step would shatter into garbage args.
 *
 * The escape symmetry test (RobotEditorEscapeRoundTrip.spec.ts)
 * mirrors helpers verbatim from RobotEditor.vue's <script setup> —
 * same approach here, focused on the splitter regex and the rbs
 * cell extraction.
 */
import { describe, it, expect } from 'vitest'

const RBS_ID_CELL = /^# rbs:([a-f0-9]{8,32})$/

interface ParsedLine {
  keyword: string
  args: string[]
  rbsId: string | null
}

// Mirror of `RobotEditor.vue::parseStepLine` for the keyword path.
// Restricted to what this test exercises: keyword + args + optional
// trailing `# rbs:<id>` cell. Escape handling is covered by its
// own spec; we deliberately don't unescape here.
function parseStepLine(raw: string): ParsedLine | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  const cells = trimmed.split(/  +|\t+/).filter(c => c !== '')
  if (cells.length === 0) return null
  let rbsId: string | null = null
  if (cells.length >= 1) {
    const last = cells[cells.length - 1]
    const m = RBS_ID_CELL.exec(last)
    if (m) {
      rbsId = m[1]
      cells.pop()
    }
  }
  if (cells.length === 0) return null
  return {
    keyword: cells[0],
    args: cells.slice(1),
    rbsId,
  }
}

// Mirror of `RobotEditor.vue::serializeStep` for the keyword path
// (no escape logic — we test bare iframe selectors which never
// start with `#`, so escapeRfToken is a no-op for them).
const SEP = '    ' // four-space separator
function serializeStep(p: ParsedLine): string {
  const parts = [p.keyword, ...p.args]
  let line = parts.join(SEP)
  if (p.rbsId) line += `${SEP}# rbs:${p.rbsId}`
  return line
}

describe('parseStepLine — iframe-wrapped selectors are one token', () => {
  it('keeps `iframe[...] >>> #inner` together when separated by 2+ spaces', () => {
    const raw = '    Click    iframe[src*="x.example"] >>> #inner    # rbs:abc12345'
    const parsed = parseStepLine(raw)
    expect(parsed).not.toBeNull()
    expect(parsed!.keyword).toBe('Click')
    expect(parsed!.args).toEqual(['iframe[src*="x.example"] >>> #inner'])
    expect(parsed!.rbsId).toBe('abc12345')
  })

  it('keeps chained iframe wraps together (`iframe >>> iframe >>> sel`)', () => {
    const inner = 'iframe[src*="outer.example"] >>> iframe[src*="inner.example"] >>> button.go'
    const raw = `    Click    ${inner}    # rbs:1d3ad4ee5fab`
    const parsed = parseStepLine(raw)
    expect(parsed!.args).toEqual([inner])
    expect(parsed!.rbsId).toBe('1d3ad4ee5fab')
  })

  it('preserves the iframe selector through a parse → serialize round-trip', () => {
    const original = 'Click    iframe[src*="message-eu.sp-prod.net"] >>> text="Accept all"    # rbs:c00cb1ab1e01'
    const parsed = parseStepLine(original)
    expect(parsed!.args).toEqual([
      'iframe[src*="message-eu.sp-prod.net"] >>> text="Accept all"',
    ])
    const serialized = serializeStep(parsed!)
    expect(serialized).toBe(original)
  })

  it('does NOT split on the single space inside `iframe[src*="x y"]` if the value contains a literal space', () => {
    // Defensive — a frame URL with a space (rare, but technically
    // legal in the JS substring CSS attribute selector if the host
    // contains a space, which DNS forbids but CSS doesn't). The
    // splitter is still 2+ spaces, so a single space inside the
    // value mustn't break the token.
    const inner = 'iframe[src*="x y"] >>> button.target'
    const raw = `    Click    ${inner}    # rbs:5ace1b057ab1`
    const parsed = parseStepLine(raw)
    expect(parsed!.args).toEqual([inner])
  })

  it('round-trip survives a non-iframe selector that happens to look similar', () => {
    // `iframe-wrapper` is a class name with a hyphen, NOT the wrap
    // dialect (it has no `[...]` after `iframe`). Must round-trip
    // verbatim with no special handling.
    const raw = 'Click    css=div.iframe-wrapper button    # rbs:1107a14a1000'
    const parsed = parseStepLine(raw)
    expect(parsed!.args).toEqual(['css=div.iframe-wrapper button'])
    expect(serializeStep(parsed!)).toBe(raw)
  })
})

describe('serializeStep + parseStepLine — full IDMAP / iframe contract', () => {
  it('every recorded line shape round-trips losslessly', () => {
    const cases: string[] = [
      'Click    id=submit    # rbs:51fe11d1d1d1',
      'Type Text    id=user    Alice    # rbs:abcdef012345',
      // Iframe wrap, single inner.
      'Click    iframe[src*="x.example"] >>> #foo    # rbs:1d4f01abcdef',
      // Iframe wrap with text=.
      'Click    iframe[src*="sp-prod.net"] >>> text="Zustimmen"    # rbs:c0c0bea11abc',
      // Chained iframes.
      'Click    iframe[src*="a"] >>> iframe[src*="b"] >>> #x    # rbs:c4a1de4d4eef',
      // No rbs id (legacy line).
      'Click    id=submit',
      // No rbs id, iframe-wrapped (legacy).
      'Click    iframe[src*="x.example"] >>> #foo',
    ]
    for (const raw of cases) {
      const parsed = parseStepLine(raw)
      expect(parsed, `failed to parse: ${raw}`).not.toBeNull()
      const back = serializeStep(parsed!)
      expect(back, `round-trip drift on: ${raw}`).toBe(raw)
    }
  })
})
