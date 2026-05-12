/**
 * Pin `effectiveSelector` against the Python emitter's
 * `_emit_command` selector-composition contract. The live recorder
 * view shows what THIS helper returns; the saved `.robot` is what
 * the Python emitter writes. They MUST match — drift = user
 * confusion.
 *
 * The cases mirror `backend/tests/recording/test_robot_emit.py`'s
 * `TestDefensiveDisambiguation` + `TestFrameChainEmit` so a
 * regression in one side is caught by the same scenarios on the
 * other.
 */
import { describe, it, expect } from 'vitest'
import { effectiveSelector } from '@/utils/effectiveSelector'
import type { RecordedCommand, SelectorCandidate } from '@/types/recorder.types'

function makeCmd(overrides: Partial<RecordedCommand>): RecordedCommand {
  return {
    index: 0,
    keyword: 'Click',
    args: {},
    selector_candidates: [],
    active_candidate_index: 0,
    ...overrides,
  }
}

function cand(
  value: string,
  strategy: SelectorCandidate['strategy'] = 'css',
  qs = 80,
  verified = true,
): SelectorCandidate {
  return {
    strategy,
    value,
    quality_score: qs,
    verified_unique: verified,
  }
}

describe('effectiveSelector', () => {
  describe('inner selector rendering', () => {
    it('renders xpath candidate with xpath= prefix', () => {
      const c = makeCmd({
        selector_candidates: [cand('//button[@id="x"]', 'xpath')],
      })
      expect(effectiveSelector(c)).toBe('xpath=//button[@id="x"]')
    })

    it('renders text candidate with text= prefix when not already there', () => {
      const c = makeCmd({
        selector_candidates: [cand('"Submit"', 'text')],
      })
      expect(effectiveSelector(c)).toBe('text="Submit"')
    })

    it('keeps text= prefix when already present', () => {
      const c = makeCmd({
        selector_candidates: [cand('text="Submit"', 'text')],
      })
      expect(effectiveSelector(c)).toBe('text="Submit"')
    })

    it('renders css / testid verbatim', () => {
      const c = makeCmd({
        selector_candidates: [cand('button.primary', 'css')],
      })
      expect(effectiveSelector(c)).toBe('button.primary')
    })
  })

  describe('defensive disambiguation (mirrors Python emitter)', () => {
    it('wraps unverified text candidate with >> nth=0', () => {
      const c = makeCmd({
        selector_candidates: [cand('text="Zustimmen"', 'text', 70, false)],
      })
      expect(effectiveSelector(c)).toBe('text="Zustimmen" >> nth=0')
    })

    it('does NOT wrap verified text candidate', () => {
      const c = makeCmd({
        selector_candidates: [cand('text="OnlyOne"', 'text', 70, true)],
      })
      expect(effectiveSelector(c)).toBe('text="OnlyOne"')
    })

    it('does NOT wrap unverified css with id', () => {
      const c = makeCmd({
        selector_candidates: [cand('#login-form', 'css', 85, false)],
      })
      expect(effectiveSelector(c)).toBe('#login-form')
    })

    it('does wrap unverified generic css class', () => {
      const c = makeCmd({
        selector_candidates: [cand('button.primary', 'css', 50, false)],
      })
      expect(effectiveSelector(c)).toBe('button.primary >> nth=0')
    })

    it('does NOT wrap xpath (never in the risky set)', () => {
      const c = makeCmd({
        selector_candidates: [
          cand("//button[normalize-space()='Click me']", 'xpath', 60, false),
        ],
      })
      expect(effectiveSelector(c)).toBe(
        "xpath=//button[normalize-space()='Click me']",
      )
    })

    it('does NOT double-wrap an already-disambiguated value', () => {
      const c = makeCmd({
        selector_candidates: [
          cand('text="Zustimmen" >> nth=0', 'text', 55, false),
        ],
      })
      const out = effectiveSelector(c)
      // Exactly ONE `>> nth=0` in the output.
      expect(out.match(/>> nth=0/g)?.length).toBe(1)
    })
  })

  describe('iframe wrapper composition', () => {
    it('uses frame_chain[0].selector_candidates[0] when present', () => {
      const c = makeCmd({
        selector_candidates: [cand('[data-testid="btn"]', 'testid', 95, true)],
        frame_url: 'https://cmp.example.com/consent',
        frame_chain: [
          {
            url: 'https://cmp.example.com/consent',
            selector_candidates: [
              cand('iframe#cmp-banner', 'css', 90, true),
              cand('iframe[src*="cmp.example.com"]', 'css', 65, true),
            ],
          },
        ],
      })
      expect(effectiveSelector(c)).toBe(
        'iframe#cmp-banner >>> [data-testid="btn"]',
      )
    })

    it('falls back to URL-host iframe when frame_chain is empty', () => {
      const c = makeCmd({
        selector_candidates: [cand('button.accept', 'css', 80, true)],
        frame_url: 'https://cmp.example.com/consent',
        frame_chain: [],
      })
      expect(effectiveSelector(c)).toBe(
        'iframe[src*="cmp.example.com"] >>> button.accept',
      )
    })

    it('falls back to URL-host iframe when frame_chain is undefined (legacy sidecar)', () => {
      const c = makeCmd({
        selector_candidates: [cand('button.accept', 'css', 80, true)],
        frame_url: 'https://cmp.example.com/consent',
      })
      expect(effectiveSelector(c)).toBe(
        'iframe[src*="cmp.example.com"] >>> button.accept',
      )
    })

    it('uses rung URL-host fallback when rung has no candidates', () => {
      const c = makeCmd({
        selector_candidates: [cand('button.accept', 'css', 80, true)],
        frame_url: 'https://cmp.example.com/consent',
        frame_chain: [
          {
            url: 'https://cmp.example.com/consent',
            selector_candidates: [], // detached, couldn't synth
          },
        ],
      })
      expect(effectiveSelector(c)).toBe(
        'iframe[src*="cmp.example.com"] >>> button.accept',
      )
    })

    it('composes nested iframes outer >>> inner >>> element', () => {
      const c = makeCmd({
        selector_candidates: [cand('button.accept', 'css', 80, true)],
        frame_url: 'https://inner.example.com/',
        frame_chain: [
          {
            url: 'https://outer.example.com/',
            selector_candidates: [cand('iframe#outer-host', 'css', 90, true)],
          },
          {
            url: 'https://inner.example.com/',
            selector_candidates: [cand('iframe[name=consent]', 'css', 85, true)],
          },
        ],
      })
      expect(effectiveSelector(c)).toBe(
        'iframe#outer-host >>> iframe[name=consent] >>> button.accept',
      )
    })

    it('no iframe wrapper for top-frame events (frame_url null)', () => {
      const c = makeCmd({
        selector_candidates: [cand('button.accept', 'css', 80, true)],
        frame_url: null,
      })
      expect(effectiveSelector(c)).toBe('button.accept')
    })
  })

  describe('heise.de Zustimmen integration', () => {
    it('produces the full composite line user expects', () => {
      // User's reported regression: this whole shape needs to be
      // visible in the live view, NOT just `text="Zustimmen"`.
      const c = makeCmd({
        selector_candidates: [
          cand('text="Zustimmen"', 'text', 70, false),
          cand("//button[normalize-space()='Zustimmen']", 'xpath', 65, false),
        ],
        frame_url: 'https://cmp.heise.de/index.html?hasCsp=true',
        frame_chain: [
          {
            url: 'https://cmp.heise.de/index.html?hasCsp=true',
            selector_candidates: [
              cand('iframe#sp_message_iframe_1454968', 'css', 90, true),
              cand('iframe[src*="cmp.heise.de"]', 'css', 65, true),
            ],
          },
        ],
      })
      expect(effectiveSelector(c)).toBe(
        'iframe#sp_message_iframe_1454968 >>> text="Zustimmen" >> nth=0',
      )
    })
  })

  describe('edge cases', () => {
    it('returns empty string when there are no selector candidates', () => {
      const c = makeCmd({ selector_candidates: [] })
      expect(effectiveSelector(c)).toBe('')
    })

    it('uses active_candidate_index to pick, not always slot 0', () => {
      const c = makeCmd({
        selector_candidates: [
          cand('button.primary', 'css', 50, false),
          cand('#submit', 'css', 90, true), // user picked this one
        ],
        active_candidate_index: 1,
      })
      expect(effectiveSelector(c)).toBe('#submit')
    })
  })

  /**
   * `effective_override` on a candidate is the verbatim emit-form
   * set via the SelectorPicker's ✏ Edit form (the "Effektiv" field).
   * It MUST short-circuit composition entirely so the user can drop
   * an unwanted `>> nth=0`, replace the synthesised iframe rung, or
   * write any cross-frame chain the recorder didn't produce — and
   * that string round-trips through swap, the picker display, and
   * the .robot emitter without re-decoration.
   */
  describe('effective_override', () => {
    it('returns the override verbatim, skipping renderSelector + iframe chain', () => {
      const c = makeCmd({
        selector_candidates: [
          {
            strategy: 'text',
            value: 'text=Welcome',
            quality_score: 50,
            verified_unique: false,
            // Override removes the defensive nth=0 the auto-compose
            // would have added.
            effective_override: 'iframe.consent >>> text=Welcome',
          },
        ],
        frame_chain: [
          { url: 'https://cmp.example/', selector_candidates: [
            { strategy: 'css', value: 'iframe#auto-synth', quality_score: 90, verified_unique: true },
          ] },
        ],
      })
      // Auto-compose would have produced
      //   `iframe#auto-synth >>> text=Welcome >> nth=0`
      // → the override completely supersedes it.
      expect(effectiveSelector(c)).toBe('iframe.consent >>> text=Welcome')
    })

    it('treats null and empty-string override as "no override"', () => {
      const baseCand: SelectorCandidate = {
        strategy: 'css',
        value: 'button#x',
        quality_score: 80,
        verified_unique: true,
      }
      const cmdNull = makeCmd({
        selector_candidates: [{ ...baseCand, effective_override: null }],
      })
      const cmdEmpty = makeCmd({
        selector_candidates: [{ ...baseCand, effective_override: '' }],
      })
      const cmdWhitespace = makeCmd({
        selector_candidates: [{ ...baseCand, effective_override: '   ' }],
      })
      expect(effectiveSelector(cmdNull)).toBe('button#x')
      expect(effectiveSelector(cmdEmpty)).toBe('button#x')
      expect(effectiveSelector(cmdWhitespace)).toBe('button#x')
    })
  })
})
