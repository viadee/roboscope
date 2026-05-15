/**
 * Story HEAL-1 — per-step Self-Healing toggle in the FlowEditor detail panel.
 *
 * FlowEditor.vue depends on Vue Flow + a canvas; mounting it is out of
 * scope for this unit-level spec. Instead we mirror the two functions
 * that drive the toggle behaviour (`computeStepHealMode` and
 * `computeNextKeyword`) in the same style as
 * RobotEditorEscapeRoundTrip.spec.ts and RobotEditorSidecarPrune.spec.ts.
 *
 * Pins (in importance order):
 *  1. The toggle is hidden for keywords not in HEAL_VARIANTS (most steps).
 *  2. The toggle is visible (off) for bare heal-able keywords when the
 *     form has a Browser or RoboScopeHeal library import.
 *  3. The toggle is visible (on) for Heal* keywords.
 *  4. The toggle is hidden when the form has no Browser/RoboScopeHeal
 *     import even if the keyword name matches — avoids rewriting custom
 *     user-defined `Click` keywords.
 *  5. Enabling rewrites the keyword from bare to Heal*.
 *  6. Disabling rewrites the keyword from Heal* back to bare.
 *  7. The `assignment` step type is supported (Heal Click is valid for
 *     `${var}=    Click    selector`).
 */
import { describe, it, expect } from 'vitest'
import {
  getHealVariant,
  getBaseKeyword,
  isHealedKeyword,
  hasBrowserLibraryImport,
  hasRoboScopeHealImport,
} from '@/utils/healToggle'
import type { RobotForm } from '@/components/editor/flow/flowConverter'

// ── Type mirrors ────────────────────────────────────────────────────

type StepType = 'keyword' | 'assignment' | 'if' | 'for' | 'end' | 'comment' | 'var'

// ── Mirror of FlowEditor.vue::selectedStepHealMode ──────────────────

function computeStepHealMode(
  stepType: StepType,
  keyword: string,
  form: RobotForm,
): 'on' | 'off' | 'hidden' {
  if (stepType !== 'keyword' && stepType !== 'assignment') return 'hidden'
  const kw = keyword.trim()
  const isOn = isHealedKeyword(kw)
  const isOff = getHealVariant(kw) !== null
  if (!isOn && !isOff) return 'hidden'
  if (!hasBrowserLibraryImport(form) && !hasRoboScopeHealImport(form)) return 'hidden'
  return isOn ? 'on' : 'off'
}

// ── Mirror of FlowEditor.vue::onStepHealToggle — keyword rewrite ────

function computeNextKeyword(currentKeyword: string, checked: boolean): string | null {
  const kw = currentKeyword.trim()
  return checked ? getHealVariant(kw) : getBaseKeyword(kw)
}

// ── Factories ────────────────────────────────────────────────────────

function bareForm(libValue?: string): RobotForm {
  return {
    settings: libValue ? [{ key: 'Library', value: libValue, args: [] }] : [],
    variables: [],
    testCases: [],
    keywords: [],
    preambleLines: [],
  }
}

// ── Tests ─────────────────────────────────────────────────────────────

describe('FlowEditorHealToggle — selectedStepHealMode', () => {
  describe('hidden — non-keyword step types', () => {
    for (const stepType of ['if', 'for', 'end', 'comment', 'var'] as StepType[]) {
      it(`is hidden for step type "${stepType}" even with a heal-able keyword`, () => {
        const form = bareForm('Browser')
        expect(computeStepHealMode(stepType, 'Click', form)).toBe('hidden')
      })
    }
  })

  describe('hidden — keyword not in HEAL_VARIANTS', () => {
    it('is hidden for an unrelated keyword (Go To)', () => {
      const form = bareForm('Browser')
      expect(computeStepHealMode('keyword', 'Go To', form)).toBe('hidden')
    })

    it('is hidden for "Log"', () => {
      expect(computeStepHealMode('keyword', 'Log', bareForm('Browser'))).toBe('hidden')
    })

    it('is hidden for a Heal-prefixed name not in the map (Heal Login)', () => {
      const form = bareForm('RoboScopeHeal')
      expect(computeStepHealMode('keyword', 'Heal Login', form)).toBe('hidden')
    })
  })

  describe('hidden — no Browser / RoboScopeHeal import', () => {
    it('is hidden when the form has no library import at all', () => {
      const form = bareForm()
      expect(computeStepHealMode('keyword', 'Click', form)).toBe('hidden')
    })

    it('is hidden when only an unrelated library (SeleniumLibrary) is imported', () => {
      const form = bareForm('SeleniumLibrary')
      expect(computeStepHealMode('keyword', 'Click', form)).toBe('hidden')
    })
  })

  describe('off — bare heal-able keyword with Browser import', () => {
    it('is "off" for "Click" when Browser library is imported', () => {
      const form = bareForm('Browser')
      expect(computeStepHealMode('keyword', 'Click', form)).toBe('off')
    })

    it('is "off" for all 13 supported keywords with Browser import', () => {
      const form = bareForm('Browser')
      const supported = [
        'Click', 'Fill Text', 'Type Text', 'Hover', 'Press Keys',
        'Wait For Elements State', 'Upload File', 'Check Checkbox',
        'Uncheck Checkbox', 'Select Options By', 'Get Text',
        'Get Element Count', 'Drag And Drop',
      ]
      for (const kw of supported) {
        expect(computeStepHealMode('keyword', kw, form)).toBe('off')
      }
    })

    it('is "off" for assignment steps (${var}= Click …) with Browser import', () => {
      const form = bareForm('Browser')
      expect(computeStepHealMode('assignment', 'Click', form)).toBe('off')
    })

    it('is "off" when RoboScopeHeal (instead of Browser) is already imported', () => {
      const form = bareForm('RoboScopeHeal')
      expect(computeStepHealMode('keyword', 'Click', form)).toBe('off')
    })
  })

  describe('on — Heal* keyword', () => {
    it('is "on" for "Heal Click" when Browser library is imported', () => {
      const form = bareForm('Browser')
      expect(computeStepHealMode('keyword', 'Heal Click', form)).toBe('on')
    })

    it('is "on" for assignment steps (${var}= Heal Click …)', () => {
      const form = bareForm('RoboScopeHeal')
      expect(computeStepHealMode('assignment', 'Heal Click', form)).toBe('on')
    })

    it('trims surrounding whitespace before classification', () => {
      const form = bareForm('Browser')
      expect(computeStepHealMode('keyword', '  Heal Click  ', form)).toBe('on')
    })
  })
})

describe('FlowEditorHealToggle — keyword rewrite on toggle', () => {
  describe('enable (checked=true)', () => {
    it('rewrites "Click" to "Heal Click"', () => {
      expect(computeNextKeyword('Click', true)).toBe('Heal Click')
    })

    it('rewrites "Fill Text" to "Heal Fill Text"', () => {
      expect(computeNextKeyword('Fill Text', true)).toBe('Heal Fill Text')
    })

    it('trims whitespace before rewriting', () => {
      expect(computeNextKeyword('  Click  ', true)).toBe('Heal Click')
    })

    it('returns null for a non-heal-able keyword (no-op guard)', () => {
      expect(computeNextKeyword('Go To', true)).toBeNull()
    })

    it('returns null when already healed (no double-prefix)', () => {
      expect(computeNextKeyword('Heal Click', true)).toBeNull()
    })
  })

  describe('disable (checked=false)', () => {
    it('rewrites "Heal Click" back to "Click"', () => {
      expect(computeNextKeyword('Heal Click', false)).toBe('Click')
    })

    it('rewrites "Heal Wait For Elements State" back to bare form', () => {
      expect(computeNextKeyword('Heal Wait For Elements State', false)).toBe(
        'Wait For Elements State',
      )
    })

    it('returns null for a bare keyword (no-op guard)', () => {
      expect(computeNextKeyword('Click', false)).toBeNull()
    })

    it('returns null for a custom Heal-prefixed keyword not in the map', () => {
      expect(computeNextKeyword('Heal Login', false)).toBeNull()
    })
  })

  describe('roundtrip symmetry', () => {
    it('enable then disable restores the original keyword for all 13 variants', () => {
      const supported = [
        'Click', 'Fill Text', 'Type Text', 'Hover', 'Press Keys',
        'Wait For Elements State', 'Upload File', 'Check Checkbox',
        'Uncheck Checkbox', 'Select Options By', 'Get Text',
        'Get Element Count', 'Drag And Drop',
      ]
      for (const base of supported) {
        const healed = computeNextKeyword(base, true)!
        const restored = computeNextKeyword(healed, false)
        expect(restored).toBe(base)
      }
    })
  })
})
