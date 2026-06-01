/**
 * Tests for Story HEAL-1 / HEAL-2 — healToggle.ts.
 *
 * Covers the keyword-name mapping, library-import add/remove rules,
 * and `applyHealToForm` across the edge cases listed in the story
 * spec.
 */
import { describe, it, expect } from 'vitest'
import {
  HEAL_VARIANTS,
  getHealVariant,
  getBaseKeyword,
  isHealableKeyword,
  isHealedKeyword,
  ensureRoboScopeHealLibrary,
  removeRoboScopeHealLibraryIfUnused,
  countHealedSteps,
  countHealableSteps,
  applyHealToForm,
  hasBrowserLibraryImport,
  hasRoboScopeHealImport,
} from '@/utils/healToggle'
import type {
  RobotForm,
  RobotStep,
  RobotTestCase,
  RobotKeywordDef,
} from '@/components/editor/flow/flowConverter'

// ─── Factories ─────────────────────────────────────────────────────

function step(keyword: string, args: string[] = []): RobotStep {
  return {
    type: 'keyword',
    keyword,
    args,
    returnVars: [],
    condition: '',
    loopVar: '',
    loopFlavor: '',
    loopValues: [],
    exceptPattern: '',
    exceptVar: '',
    varScope: '',
    comment: '',
  }
}

function testCase(name: string, steps: RobotStep[]): RobotTestCase {
  return {
    name,
    documentation: '',
    tags: [],
    setup: '',
    teardown: '',
    timeout: '',
    template: '',
    steps,
  }
}

function userKeyword(name: string, steps: RobotStep[]): RobotKeywordDef {
  return {
    name,
    documentation: '',
    arguments: [],
    tags: [],
    setup: '',
    teardown: '',
    timeout: '',
    returnValue: '',
    steps,
  }
}

interface Opts {
  settings?: RobotForm['settings']
  variables?: RobotForm['variables']
  testCases?: RobotTestCase[]
  keywords?: RobotKeywordDef[]
  preambleLines?: string[]
}
function form(opts: Opts = {}): RobotForm {
  return {
    settings: opts.settings ?? [],
    variables: opts.variables ?? [],
    testCases: opts.testCases ?? [],
    keywords: opts.keywords ?? [],
    preambleLines: opts.preambleLines ?? [],
  }
}

// ─── HEAL_VARIANTS map ─────────────────────────────────────────────

describe('HEAL_VARIANTS map', () => {
  it('contains all 13 supported keywords from library.py', () => {
    expect(Object.keys(HEAL_VARIANTS).sort()).toEqual([
      'Check Checkbox',
      'Click',
      'Drag And Drop',
      'Fill Text',
      'Get Element Count',
      'Get Text',
      'Hover',
      'Press Keys',
      'Select Options By',
      'Type Text',
      'Uncheck Checkbox',
      'Upload File',
      'Wait For Elements State',
    ])
  })

  it('every variant is the bare name with a "Heal " prefix', () => {
    for (const [base, heal] of Object.entries(HEAL_VARIANTS)) {
      expect(heal).toBe(`Heal ${base}`)
    }
  })

  it('is frozen (Object.freeze) to prevent accidental mutation', () => {
    expect(Object.isFrozen(HEAL_VARIANTS)).toBe(true)
  })
})

// ─── getHealVariant / getBaseKeyword / classifiers ─────────────────

describe('getHealVariant', () => {
  it('returns the heal name for a bare keyword', () => {
    expect(getHealVariant('Click')).toBe('Heal Click')
    expect(getHealVariant('Drag And Drop')).toBe('Heal Drag And Drop')
  })

  it('trims surrounding whitespace before lookup', () => {
    expect(getHealVariant('  Click  ')).toBe('Heal Click')
  })

  it('returns null for an already-healed keyword', () => {
    expect(getHealVariant('Heal Click')).toBeNull()
  })

  it('returns null for an unknown keyword', () => {
    expect(getHealVariant('Go To')).toBeNull()
    expect(getHealVariant('Log')).toBeNull()
    expect(getHealVariant('')).toBeNull()
  })

  it('is case-sensitive (Robot Framework keyword matching is)', () => {
    expect(getHealVariant('click')).toBeNull()
    expect(getHealVariant('CLICK')).toBeNull()
  })
})

describe('getBaseKeyword', () => {
  it('returns the bare name for a heal-prefixed keyword', () => {
    expect(getBaseKeyword('Heal Click')).toBe('Click')
    expect(getBaseKeyword('Heal Wait For Elements State')).toBe(
      'Wait For Elements State',
    )
  })

  it('returns null for a bare keyword', () => {
    expect(getBaseKeyword('Click')).toBeNull()
  })

  it('returns null for an arbitrary "Heal Foo" not in the map', () => {
    // A user could write `Heal Login` referencing their own custom
    // heal-prefixed user keyword. We must NOT convert that to `Login`.
    expect(getBaseKeyword('Heal Foo')).toBeNull()
    expect(getBaseKeyword('Heal Login')).toBeNull()
  })

  it('trims whitespace', () => {
    expect(getBaseKeyword('  Heal Click  ')).toBe('Click')
  })
})

describe('isHealableKeyword', () => {
  it('is true for the bare form of supported keywords', () => {
    expect(isHealableKeyword('Click')).toBe(true)
    expect(isHealableKeyword('Hover')).toBe(true)
  })
  it('is true for the Heal form of supported keywords', () => {
    expect(isHealableKeyword('Heal Click')).toBe(true)
    expect(isHealableKeyword('Heal Hover')).toBe(true)
  })
  it('is false for unrelated keywords', () => {
    expect(isHealableKeyword('Log')).toBe(false)
    expect(isHealableKeyword('Go To')).toBe(false)
    expect(isHealableKeyword('Heal Foo')).toBe(false)
  })
})

describe('isHealedKeyword', () => {
  it('is true only for Heal* of supported keywords', () => {
    expect(isHealedKeyword('Heal Click')).toBe(true)
    expect(isHealedKeyword('Click')).toBe(false)
    expect(isHealedKeyword('Heal Foo')).toBe(false)
  })
})

// ─── Library-import add / remove ───────────────────────────────────

describe('ensureRoboScopeHealLibrary', () => {
  it('appends a bare row when no RoboScopeHeal library is present', () => {
    const before = [{ key: 'Library', value: 'Browser', args: [] }]
    const after = ensureRoboScopeHealLibrary(before)
    expect(after).toHaveLength(2)
    expect(after[1]).toEqual({ key: 'Library', value: 'RoboScopeHeal', args: [] })
  })

  it('is idempotent when a bare RoboScopeHeal row already exists', () => {
    const before = [
      { key: 'Library', value: 'Browser', args: [] },
      { key: 'Library', value: 'RoboScopeHeal', args: [] },
    ]
    expect(ensureRoboScopeHealLibrary(before)).toBe(before)
  })

  it('preserves a user-configured RoboScopeHeal row (no second row added)', () => {
    const before = [
      { key: 'Library', value: 'Browser', args: [] },
      { key: 'Library', value: 'RoboScopeHeal', args: ['budget=5'] },
    ]
    const after = ensureRoboScopeHealLibrary(before)
    expect(after).toBe(before)
    expect(after.filter(r => r.value === 'RoboScopeHeal')).toHaveLength(1)
  })

  it('returns the original array reference when no change is needed', () => {
    const before = [{ key: 'Library', value: 'RoboScopeHeal', args: [] }]
    expect(ensureRoboScopeHealLibrary(before)).toBe(before)
  })
})

describe('removeRoboScopeHealLibraryIfUnused', () => {
  it('removes the bare row when no Heal* keyword remains', () => {
    const before = [
      { key: 'Library', value: 'Browser', args: [] },
      { key: 'Library', value: 'RoboScopeHeal', args: [] },
    ]
    const after = removeRoboScopeHealLibraryIfUnused(before, false)
    expect(after).toEqual([{ key: 'Library', value: 'Browser', args: [] }])
  })

  it('preserves the row when stillUsed is true', () => {
    const before = [
      { key: 'Library', value: 'Browser', args: [] },
      { key: 'Library', value: 'RoboScopeHeal', args: [] },
    ]
    expect(removeRoboScopeHealLibraryIfUnused(before, true)).toBe(before)
  })

  it('preserves a user-configured row even when stillUsed is false', () => {
    const before = [
      { key: 'Library', value: 'RoboScopeHeal', args: ['budget=3'] },
    ]
    expect(removeRoboScopeHealLibraryIfUnused(before, false)).toBe(before)
  })

  it('is a no-op when no RoboScopeHeal row is present', () => {
    const before = [{ key: 'Library', value: 'Browser', args: [] }]
    expect(removeRoboScopeHealLibraryIfUnused(before, false)).toBe(before)
  })
})

// ─── countHealedSteps / countHealableSteps ────────────────────────

describe('countHealedSteps', () => {
  it('counts Heal* steps across test cases and user keywords', () => {
    const f = form({
      testCases: [
        testCase('TC1', [step('Heal Click', ['#a']), step('Click', ['#b'])]),
      ],
      keywords: [userKeyword('KW', [step('Heal Fill Text', ['#x', 'v'])])],
    })
    expect(countHealedSteps(f)).toBe(2)
  })

  it('returns 0 for an empty form', () => {
    expect(countHealedSteps(form())).toBe(0)
  })
})

describe('countHealableSteps', () => {
  it('counts bare heal-able steps only (Heal* form is excluded)', () => {
    const f = form({
      testCases: [
        testCase('TC1', [step('Heal Click', ['#a']), step('Click', ['#b'])]),
      ],
    })
    expect(countHealableSteps(f)).toBe(1)
  })

  it('ignores unrelated keywords', () => {
    const f = form({
      testCases: [
        testCase('TC1', [step('Log', ['hello']), step('Go To', ['url'])]),
      ],
    })
    expect(countHealableSteps(f)).toBe(0)
  })
})

// ─── Library-import detection (HEAL-2 toggle gate) ─────────────────

describe('hasBrowserLibraryImport', () => {
  it('matches the canonical "Browser" library name', () => {
    const f = form({
      settings: [{ key: 'Library', value: 'Browser', args: [] }],
    })
    expect(hasBrowserLibraryImport(f)).toBe(true)
  })

  it('matches Library with extra args (auto_closing_level=...)', () => {
    const f = form({
      settings: [
        { key: 'Library', value: 'Browser', args: ['auto_closing_level=KEEP'] },
      ],
    })
    expect(hasBrowserLibraryImport(f)).toBe(true)
  })

  it('matches the pip-name variants', () => {
    for (const name of [
      'robotframework-browser',
      'robotframework_browser',
      'robotframework-browser-batteries',
      'robotframework_browser_batteries',
    ]) {
      const f = form({
        settings: [{ key: 'Library', value: name, args: [] }],
      })
      expect(hasBrowserLibraryImport(f)).toBe(true)
    }
  })

  it('is case-insensitive on the library name', () => {
    const f = form({
      settings: [{ key: 'Library', value: 'BROWSER', args: [] }],
    })
    expect(hasBrowserLibraryImport(f)).toBe(true)
  })

  it('ignores whitespace around the value', () => {
    const f = form({
      settings: [{ key: 'Library', value: '  Browser  ', args: [] }],
    })
    expect(hasBrowserLibraryImport(f)).toBe(true)
  })

  it('returns false when no Library row matches', () => {
    const f = form({
      settings: [
        { key: 'Library', value: 'SeleniumLibrary', args: [] },
        { key: 'Library', value: 'RequestsLibrary', args: [] },
      ],
    })
    expect(hasBrowserLibraryImport(f)).toBe(false)
  })

  it('does not match a non-Library row even if value is "Browser"', () => {
    const f = form({
      settings: [{ key: 'Documentation', value: 'Browser tests', args: [] }],
    })
    expect(hasBrowserLibraryImport(f)).toBe(false)
  })

  it('returns false for an empty settings list', () => {
    expect(hasBrowserLibraryImport(form())).toBe(false)
  })
})

describe('hasRoboScopeHealImport', () => {
  it('matches the bare Library row', () => {
    const f = form({
      settings: [{ key: 'Library', value: 'RoboScopeHeal', args: [] }],
    })
    expect(hasRoboScopeHealImport(f)).toBe(true)
  })

  it('matches a user-configured row with args', () => {
    const f = form({
      settings: [
        { key: 'Library', value: 'RoboScopeHeal', args: ['budget=10'] },
      ],
    })
    expect(hasRoboScopeHealImport(f)).toBe(true)
  })

  it('returns false when only Browser is imported (no heal yet)', () => {
    const f = form({
      settings: [{ key: 'Library', value: 'Browser', args: [] }],
    })
    expect(hasRoboScopeHealImport(f)).toBe(false)
  })
})

// ─── applyHealToForm ───────────────────────────────────────────────

describe('applyHealToForm — enable', () => {
  it('rewrites all bare heal-able keywords and adds the library import', () => {
    const f = form({
      settings: [{ key: 'Library', value: 'Browser', args: [] }],
      testCases: [testCase('TC1', [step('Click', ['#a']), step('Hover', ['#b'])])],
    })
    const out = applyHealToForm(f, 'enable')

    expect(out.changedKeywords).toBe(2)
    expect(out.form.testCases[0].steps[0].keyword).toBe('Heal Click')
    expect(out.form.testCases[0].steps[1].keyword).toBe('Heal Hover')
    expect(out.form.settings).toEqual([
      { key: 'Library', value: 'Browser', args: [] },
      { key: 'Library', value: 'RoboScopeHeal', args: [] },
    ])
  })

  it('promotes only heal-able keywords, leaves others untouched', () => {
    const f = form({
      testCases: [
        testCase('TC1', [
          step('Log', ['hello']),
          step('Click', ['#a']),
          step('Go To', ['url']),
        ]),
      ],
    })
    const out = applyHealToForm(f, 'enable')
    expect(out.changedKeywords).toBe(1)
    expect(out.form.testCases[0].steps.map(s => s.keyword)).toEqual([
      'Log',
      'Heal Click',
      'Go To',
    ])
  })

  it('promotes heal-able steps inside user keywords too', () => {
    const f = form({
      testCases: [],
      keywords: [
        userKeyword('Login Helper', [
          step('Fill Text', ['#user', 'admin']),
          step('Click', ['#submit']),
        ]),
      ],
    })
    const out = applyHealToForm(f, 'enable')
    expect(out.changedKeywords).toBe(2)
    expect(out.form.keywords[0].steps.map(s => s.keyword)).toEqual([
      'Heal Fill Text',
      'Heal Click',
    ])
    expect(out.form.settings).toEqual([
      { key: 'Library', value: 'RoboScopeHeal', args: [] },
    ])
  })

  it('is a no-op when every step is already Heal* (idempotent enable)', () => {
    const f = form({
      settings: [{ key: 'Library', value: 'RoboScopeHeal', args: [] }],
      testCases: [testCase('TC1', [step('Heal Click', ['#a'])])],
    })
    const out = applyHealToForm(f, 'enable')
    expect(out.changedKeywords).toBe(0)
    expect(out.form.testCases[0].steps[0].keyword).toBe('Heal Click')
    expect(out.form.settings).toBe(f.settings)
  })

  it('does NOT add the library when the file has zero heal-able steps', () => {
    const f = form({
      testCases: [testCase('TC1', [step('Log', ['hello'])])],
    })
    const out = applyHealToForm(f, 'enable')
    expect(out.changedKeywords).toBe(0)
    expect(out.form.settings).toEqual([])
  })

  it('preserves a user-configured library row instead of adding a second', () => {
    const f = form({
      settings: [
        { key: 'Library', value: 'RoboScopeHeal', args: ['budget=10'] },
      ],
      testCases: [testCase('TC1', [step('Click', ['#a'])])],
    })
    const out = applyHealToForm(f, 'enable')
    expect(out.form.settings).toHaveLength(1)
    expect(out.form.settings[0]).toEqual({
      key: 'Library', value: 'RoboScopeHeal', args: ['budget=10'],
    })
  })

  it('does NOT rewrite a Click name when it appears as an argument (Run Keyword Click ...)', () => {
    // `step.keyword === 'Run Keyword'`, `step.args === ['Click', '#a']`.
    // The args are NEVER traversed by applyHealToForm — pinned here so
    // a future refactor doesn't accidentally walk them.
    const f = form({
      testCases: [
        testCase('TC1', [step('Run Keyword', ['Click', '#a'])]),
      ],
    })
    const out = applyHealToForm(f, 'enable')
    expect(out.changedKeywords).toBe(0)
    expect(out.form.testCases[0].steps[0].keyword).toBe('Run Keyword')
    expect(out.form.testCases[0].steps[0].args).toEqual(['Click', '#a'])
  })
})

describe('applyHealToForm — disable', () => {
  it('rewrites all Heal* back to bare and removes the library import', () => {
    const f = form({
      settings: [
        { key: 'Library', value: 'Browser', args: [] },
        { key: 'Library', value: 'RoboScopeHeal', args: [] },
      ],
      testCases: [testCase('TC1', [step('Heal Click', ['#a'])])],
    })
    const out = applyHealToForm(f, 'disable')

    expect(out.changedKeywords).toBe(1)
    expect(out.form.testCases[0].steps[0].keyword).toBe('Click')
    expect(out.form.settings).toEqual([
      { key: 'Library', value: 'Browser', args: [] },
    ])
  })

  it('preserves the library import when some Heal* keyword still remains', () => {
    // User configured budget args; user-toggled disable but a different
    // test case still has Heal* (e.g., user manually wrote one).
    const f = form({
      settings: [
        { key: 'Library', value: 'RoboScopeHeal', args: ['budget=3'] },
      ],
      testCases: [
        testCase('TC1', [step('Click', ['#a'])]),
        testCase('TC2', [step('Heal Foo', ['#b'])]),
      ],
    })
    const out = applyHealToForm(f, 'disable')
    // Heal Foo is NOT in HEAL_VARIANTS so disable doesn't touch it.
    expect(out.changedKeywords).toBe(0)
    expect(out.form.settings).toBe(f.settings)
  })

  it('does NOT touch unknown Heal-prefixed user keywords', () => {
    const f = form({
      testCases: [
        testCase('TC1', [step('Heal Login', ['admin'])]),
      ],
    })
    const out = applyHealToForm(f, 'disable')
    expect(out.changedKeywords).toBe(0)
    expect(out.form.testCases[0].steps[0].keyword).toBe('Heal Login')
  })

  it('preserves a user-configured library row even after disabling all heals', () => {
    const f = form({
      settings: [
        { key: 'Library', value: 'RoboScopeHeal', args: ['budget=3'] },
      ],
      testCases: [testCase('TC1', [step('Heal Click', ['#a'])])],
    })
    const out = applyHealToForm(f, 'disable')
    expect(out.changedKeywords).toBe(1)
    expect(out.form.settings).toEqual([
      { key: 'Library', value: 'RoboScopeHeal', args: ['budget=3'] },
    ])
  })

  it('is a no-op when no Heal* keyword exists (idempotent disable)', () => {
    const f = form({
      testCases: [testCase('TC1', [step('Click', ['#a'])])],
    })
    const out = applyHealToForm(f, 'disable')
    expect(out.changedKeywords).toBe(0)
    expect(out.form).toEqual(f)
  })
})

describe('applyHealToForm — immutability', () => {
  it('does not mutate the input form', () => {
    const f = form({
      settings: [{ key: 'Library', value: 'Browser', args: [] }],
      testCases: [testCase('TC1', [step('Click', ['#a'])])],
    })
    const snapshot = JSON.parse(JSON.stringify(f))
    applyHealToForm(f, 'enable')
    expect(f).toEqual(snapshot)
  })

  it('preserves array identity for unchanged sub-trees (Vue reactivity)', () => {
    const f = form({
      testCases: [
        testCase('TC1', [step('Log', ['hi'])]),       // no heal-able → untouched
        testCase('TC2', [step('Click', ['#a'])]),     // heal-able → changes
      ],
    })
    const out = applyHealToForm(f, 'enable')
    // TC1 has no rewrite — should be the same object identity.
    expect(out.form.testCases[0]).toBe(f.testCases[0])
    // TC2 got rewritten — different identity.
    expect(out.form.testCases[1]).not.toBe(f.testCases[1])
  })
})
