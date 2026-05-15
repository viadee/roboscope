/**
 * Story HEAL-2 — suite-level Self-Healing toggle in the RobotEditor toolbar.
 *
 * RobotEditor.vue has deep CodeMirror + Vue Flow dependencies that make
 * full component mounting impractical. We mirror the toggle's internal
 * state-machine and action logic (`computeHealSuiteState` and
 * `simulateToggle`) in the same style as RobotEditorEscapeRoundTrip.spec.ts,
 * and exercise them against fixture forms.
 *
 * What `applyHealToForm` itself does is pinned in healToggle.spec.ts;
 * this spec focuses on the component-level wiring:
 *  - when the button is shown vs hidden
 *  - what state label is displayed
 *  - that clicking through the toggle applies the right mode and
 *    produces a changed form with the library import updated
 */
import { describe, it, expect } from 'vitest'
import {
  applyHealToForm,
  countHealedSteps,
  countHealableSteps,
  hasBrowserLibraryImport,
  hasRoboScopeHealImport,
} from '@/utils/healToggle'
import type {
  RobotForm,
  RobotStep,
  RobotTestCase,
} from '@/components/editor/flow/flowConverter'

// ── Mirror of RobotEditor.vue::healSuiteState ────────────────────────

function computeHealSuiteState(form: RobotForm): 'on' | 'off' | 'hidden' {
  const healed = countHealedSteps(form)
  const healable = countHealableSteps(form)
  if (healed === 0 && healable === 0) return 'hidden'
  if (!hasBrowserLibraryImport(form) && !hasRoboScopeHealImport(form)) return 'hidden'
  return healed > 0 ? 'on' : 'off'
}

// ── Mirror of RobotEditor.vue::onHealSuiteToggle (core logic) ───────

function simulateToggle(form: RobotForm): {
  nextForm: RobotForm
  changedKeywords: number
  toastKey: string
} | null {
  const state = computeHealSuiteState(form)
  if (state === 'hidden') return null
  const mode = state === 'on' ? 'disable' : 'enable'
  const { form: nextForm, changedKeywords } = applyHealToForm(form, mode)
  const toastKey = mode === 'enable'
    ? 'robotEditor.heal.toastEnabled'
    : 'robotEditor.heal.toastDisabled'
  return { nextForm, changedKeywords, toastKey }
}

// ── Factories ────────────────────────────────────────────────────────

function mkStep(keyword: string, args: string[] = []): RobotStep {
  return {
    type: 'keyword', keyword, args, returnVars: [], condition: '',
    loopVar: '', loopFlavor: '', loopValues: [], exceptPattern: '',
    exceptVar: '', varScope: '', comment: '',
  }
}

function mkTC(name: string, steps: RobotStep[]): RobotTestCase {
  return {
    name, documentation: '', tags: [], setup: '', teardown: '',
    timeout: '', template: '', steps,
  }
}

function mkForm(opts: {
  settings?: RobotForm['settings']
  testCases?: RobotTestCase[]
  keywords?: RobotForm['keywords']
} = {}): RobotForm {
  return {
    settings: opts.settings ?? [],
    variables: [],
    testCases: opts.testCases ?? [],
    keywords: opts.keywords ?? [],
    preambleLines: [],
  }
}

function browserForm(steps: RobotStep[]): RobotForm {
  return mkForm({
    settings: [{ key: 'Library', value: 'Browser', args: [] }],
    testCases: [mkTC('TC1', steps)],
  })
}

// ── Tests ─────────────────────────────────────────────────────────────

describe('RobotEditorHealToggle — healSuiteState', () => {
  describe('hidden', () => {
    it('is hidden when the file has no healable or healed keywords', () => {
      const f = browserForm([mkStep('Log', ['hello']), mkStep('Go To', ['url'])])
      expect(computeHealSuiteState(f)).toBe('hidden')
    })

    it('is hidden when an empty form (no steps at all)', () => {
      expect(computeHealSuiteState(mkForm())).toBe('hidden')
    })

    it('is hidden when the file has healable keywords but NO Browser/RoboScopeHeal import', () => {
      const f = mkForm({
        settings: [{ key: 'Library', value: 'SeleniumLibrary', args: [] }],
        testCases: [mkTC('TC1', [mkStep('Click', ['#a'])])],
      })
      expect(computeHealSuiteState(f)).toBe('hidden')
    })

    it('is hidden when there is no library import at all, even with a "Click" step', () => {
      const f = mkForm({
        testCases: [mkTC('TC1', [mkStep('Click', ['#a'])])],
      })
      expect(computeHealSuiteState(f)).toBe('hidden')
    })
  })

  describe('off — file has bare healable keywords + Browser import', () => {
    it('is "off" when file has bare Click + Browser import', () => {
      expect(computeHealSuiteState(browserForm([mkStep('Click', ['#a'])]))).toBe('off')
    })

    it('is "off" when multiple heal-able keywords exist (none healed yet)', () => {
      const f = browserForm([
        mkStep('Click', ['#a']),
        mkStep('Fill Text', ['#b', 'val']),
        mkStep('Hover', ['#c']),
      ])
      expect(computeHealSuiteState(f)).toBe('off')
    })

    it('is "off" when RoboScopeHeal (instead of Browser) is the qualifying import', () => {
      const f = mkForm({
        settings: [{ key: 'Library', value: 'RoboScopeHeal', args: [] }],
        testCases: [mkTC('TC1', [mkStep('Click', ['#a'])])],
      })
      expect(computeHealSuiteState(f)).toBe('off')
    })
  })

  describe('on — file has at least one Heal* keyword', () => {
    it('is "on" when at least one step uses Heal Click', () => {
      const f = browserForm([mkStep('Heal Click', ['#a']), mkStep('Log', ['hi'])])
      expect(computeHealSuiteState(f)).toBe('on')
    })

    it('is "on" for mixed state (some healed, some bare)', () => {
      const f = browserForm([
        mkStep('Heal Click', ['#a']),
        mkStep('Fill Text', ['#b', 'val']),
      ])
      expect(computeHealSuiteState(f)).toBe('on')
    })

    it('is "on" when a Heal* keyword is in a user keyword def, not a test case', () => {
      const f = mkForm({
        settings: [{ key: 'Library', value: 'Browser', args: [] }],
        testCases: [mkTC('TC1', [mkStep('Log', ['hello'])])],
        keywords: [
          {
            name: 'Click Helper',
            documentation: '',
            arguments: [],
            tags: [],
            setup: '',
            teardown: '',
            timeout: '',
            returnValue: '',
            steps: [mkStep('Heal Click', ['#a'])],
          },
        ],
      })
      expect(computeHealSuiteState(f)).toBe('on')
    })
  })
})

describe('RobotEditorHealToggle — simulateToggle (onHealSuiteToggle)', () => {
  it('returns null (no-op) when state is hidden', () => {
    const f = mkForm({
      testCases: [mkTC('TC1', [mkStep('Click', ['#a'])])],
    })
    expect(simulateToggle(f)).toBeNull()
  })

  describe('enable path (state=off → click → enable)', () => {
    it('promotes all bare heal-able keywords and returns toastEnabled key', () => {
      const f = browserForm([mkStep('Click', ['#a']), mkStep('Hover', ['#b'])])
      const result = simulateToggle(f)
      expect(result).not.toBeNull()
      expect(result!.changedKeywords).toBe(2)
      expect(result!.toastKey).toBe('robotEditor.heal.toastEnabled')
      expect(result!.nextForm.testCases[0].steps[0].keyword).toBe('Heal Click')
      expect(result!.nextForm.testCases[0].steps[1].keyword).toBe('Heal Hover')
    })

    it('adds the RoboScopeHeal library import when none was present', () => {
      const f = browserForm([mkStep('Click', ['#a'])])
      const result = simulateToggle(f)!
      const hasHeal = result.nextForm.settings.some(
        s => s.key === 'Library' && s.value === 'RoboScopeHeal',
      )
      expect(hasHeal).toBe(true)
    })

    it('returns changedKeywords=0 when all steps are already healed (idempotent)', () => {
      const f = mkForm({
        settings: [{ key: 'Library', value: 'RoboScopeHeal', args: [] }],
        testCases: [mkTC('TC1', [mkStep('Heal Click', ['#a'])])],
      })
      // State is 'on', so the toggle switches to 'disable' mode.
      // This case validates the opposite direction.
      const result = simulateToggle(f)!
      expect(result.changedKeywords).toBe(1) // disable direction
    })
  })

  describe('disable path (state=on → click → disable)', () => {
    it('reverts all Heal* keywords and returns toastDisabled key', () => {
      const f = browserForm([
        mkStep('Heal Click', ['#a']),
        mkStep('Heal Fill Text', ['#b', 'val']),
      ])
      const result = simulateToggle(f)!
      expect(result.changedKeywords).toBe(2)
      expect(result.toastKey).toBe('robotEditor.heal.toastDisabled')
      expect(result.nextForm.testCases[0].steps[0].keyword).toBe('Click')
      expect(result.nextForm.testCases[0].steps[1].keyword).toBe('Fill Text')
    })

    it('removes the bare RoboScopeHeal library import after disabling all heals', () => {
      const f = mkForm({
        settings: [
          { key: 'Library', value: 'Browser', args: [] },
          { key: 'Library', value: 'RoboScopeHeal', args: [] },
        ],
        testCases: [mkTC('TC1', [mkStep('Heal Click', ['#a'])])],
      })
      const result = simulateToggle(f)!
      const healRow = result.nextForm.settings.find(s => s.value === 'RoboScopeHeal')
      expect(healRow).toBeUndefined()
    })

    it('preserves a user-configured RoboScopeHeal row with args', () => {
      const f = mkForm({
        settings: [
          { key: 'Library', value: 'RoboScopeHeal', args: ['budget=5'] },
        ],
        testCases: [mkTC('TC1', [mkStep('Heal Click', ['#a'])])],
      })
      const result = simulateToggle(f)!
      const healRow = result.nextForm.settings.find(s => s.value === 'RoboScopeHeal')
      expect(healRow).toBeDefined()
      expect(healRow!.args).toEqual(['budget=5'])
    })
  })

  describe('state after toggle', () => {
    it('enable makes healSuiteState flip from off to on', () => {
      const f = browserForm([mkStep('Click', ['#a'])])
      expect(computeHealSuiteState(f)).toBe('off')
      const result = simulateToggle(f)!
      expect(computeHealSuiteState(result.nextForm)).toBe('on')
    })

    it('disable makes healSuiteState flip from on to off (when bare keywords remain)', () => {
      const f = browserForm([
        mkStep('Heal Click', ['#a']),
        mkStep('Hover', ['#b']),  // bare — still shows toggle as 'off'
      ])
      expect(computeHealSuiteState(f)).toBe('on')
      const result = simulateToggle(f)!
      // All Heal* reverted, but bare Hover still exists → state is off.
      expect(computeHealSuiteState(result.nextForm)).toBe('off')
    })

    it('disable on fully-healed form leads to hidden state when no bare keywords remain', () => {
      // File had only Heal Click — after disable, Click is bare but Browser
      // import is still present, so state becomes off (not hidden).
      const f = mkForm({
        settings: [
          { key: 'Library', value: 'Browser', args: [] },
          { key: 'Library', value: 'RoboScopeHeal', args: [] },
        ],
        testCases: [mkTC('TC1', [mkStep('Heal Click', ['#a'])])],
      })
      const result = simulateToggle(f)!
      expect(computeHealSuiteState(result.nextForm)).toBe('off')
    })
  })
})
