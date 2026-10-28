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
 * Exercises the real `parseStepLine` / `serializeStep` from robotTextIO.ts,
 * focused on the splitter regex and the rbs cell extraction.
 */
import { describe, it, expect } from 'vitest'

import { parseStepLine, serializeStep } from '@/components/editor/robotTextIO'

describe('parseStepLine — iframe-wrapped selectors are one token', () => {
  it('keeps `iframe[...] >>> #inner` together when separated by 2+ spaces', () => {
    const raw = '    Click    iframe[src*="x.example"] >>> #inner    # rbs:abc12345'
    const parsed = parseStepLine(raw)
    expect(parsed.keyword).toBe('Click')
    expect(parsed.args).toEqual(['iframe[src*="x.example"] >>> #inner'])
    expect(parsed.rbs_id).toBe('abc12345')
  })

  it('keeps chained iframe wraps together (`iframe >>> iframe >>> sel`)', () => {
    const inner = 'iframe[src*="outer.example"] >>> iframe[src*="inner.example"] >>> button.go'
    const raw = `    Click    ${inner}    # rbs:1d3ad4ee5fab`
    const parsed = parseStepLine(raw)
    expect(parsed.args).toEqual([inner])
    expect(parsed.rbs_id).toBe('1d3ad4ee5fab')
  })

  it('preserves the iframe selector through a parse → serialize round-trip', () => {
    const original = 'Click    iframe[src*="message-eu.sp-prod.net"] >>> text="Accept all"    # rbs:c00cb1ab1e01'
    const parsed = parseStepLine(original)
    expect(parsed.args).toEqual([
      'iframe[src*="message-eu.sp-prod.net"] >>> text="Accept all"',
    ])
    const serialized = serializeStep(parsed)
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
    expect(parsed.args).toEqual([inner])
  })

  it('round-trip survives a non-iframe selector that happens to look similar', () => {
    // `iframe-wrapper` is a class name with a hyphen, NOT the wrap
    // dialect (it has no `[...]` after `iframe`). Must round-trip
    // verbatim with no special handling.
    const raw = 'Click    css=div.iframe-wrapper button    # rbs:1107a14a1000'
    const parsed = parseStepLine(raw)
    expect(parsed.args).toEqual(['css=div.iframe-wrapper button'])
    expect(serializeStep(parsed)).toBe(raw)
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
      const back = serializeStep(parsed)
      expect(back, `round-trip drift on: ${raw}`).toBe(raw)
    }
  })
})
