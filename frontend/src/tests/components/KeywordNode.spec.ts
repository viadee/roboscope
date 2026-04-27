/**
 * Story EDITOR-1 — render assertions for the KeywordNode candidate badge.
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import KeywordNode from '@/components/editor/flow/KeywordNode.vue'
import type { FlowNodeData } from '@/components/editor/flow/flowConverter'
import type { RecordedCommand } from '@/types/recorder.types'

function mkData(over: Partial<FlowNodeData> = {}): FlowNodeData {
  return {
    label: 'Click',
    stepType: 'keyword',
    step: {
      type: 'keyword',
      keyword: 'Click',
      args: ['text=Hello'],
      returnVars: [],
      condition: '', loopVar: '', loopFlavor: '', loopValues: [],
      exceptPattern: '', exceptVar: '', varScope: '', comment: '',
    },
    section: 'testcase',
    sectionIndex: 0,
    stepIndex: 0,
    recording: null,
    argSpecs: null,
    ...over,
  }
}

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      flowEditor: {
        selector: {
          tooltipHasCandidates: '{count} recorded candidates — click to switch',
          customValueHint: '(custom value, not from recording)',
          candidatesBadge: '× {count}',
        },
        argLabels: {
          fallback: 'arg {n}',
          extraPositional: 'extra positional',
          extraNamed: 'extra named',
          defaultPlaceholder: 'default: {default}',
        },
      },
    },
  },
})

function mountNode(data: FlowNodeData) {
  return mount(KeywordNode, {
    props: { data },
    global: {
      plugins: [i18n],
      stubs: { Handle: true },
    },
  })
}

const recording: RecordedCommand = {
  index: 0,
  keyword: 'Click',
  args: {},
  selector_candidates: [
    { strategy: 'aria', value: 'role=button[name="OK"]', quality_score: 80, verified_unique: false },
    { strategy: 'text', value: 'text=OK', quality_score: 60, verified_unique: false },
    { strategy: 'css', value: 'button.ok', quality_score: 45, verified_unique: false },
  ],
  active_candidate_index: 0,
}

describe('KeywordNode candidate badge', () => {
  it('does not render the badge when there is no recording', () => {
    const w = mountNode(mkData({ recording: null }))
    expect(w.find('[data-testid="selector-candidate-count"]').exists()).toBe(false)
    expect(w.find('.flow-arg-dot').exists()).toBe(false)
  })

  it('does not render the badge when the recording has zero candidates', () => {
    const w = mountNode(mkData({ recording: { ...recording, selector_candidates: [] } }))
    expect(w.find('[data-testid="selector-candidate-count"]').exists()).toBe(false)
  })

  it('renders the dot + count badge for the first arg when candidates exist', () => {
    const w = mountNode(mkData({ recording }))
    // i18n template `× {count}` renders with a normal space
    expect(w.find('[data-testid="selector-candidate-count"]').text()).toBe('× 3')
    expect(w.find('.flow-arg-dot').exists()).toBe(true)
  })

  it('uses the green dot for high-quality active candidates (>= 80)', () => {
    const w = mountNode(mkData({ recording }))
    expect(w.find('.flow-arg-dot').classes()).toContain('flow-arg-dot--good')
  })

  it('uses the amber dot for mid-quality active candidates (50..79)', () => {
    const r: RecordedCommand = { ...recording, active_candidate_index: 1 }
    const w = mountNode(mkData({ recording: r }))
    expect(w.find('.flow-arg-dot').classes()).toContain('flow-arg-dot--ok')
  })

  it('uses the red dot for low-quality active candidates (< 50)', () => {
    const r: RecordedCommand = { ...recording, active_candidate_index: 2 }
    const w = mountNode(mkData({ recording: r }))
    expect(w.find('.flow-arg-dot').classes()).toContain('flow-arg-dot--poor')
  })
})

describe('KeywordNode parameter-name chips (Story EDITOR-2)', () => {
  it('does not render a name prefix when argSpecs is null (hand-written / unknown keyword)', () => {
    const w = mountNode(mkData({ argSpecs: null }))
    expect(w.find('[data-testid="arg-name-prefix"]').exists()).toBe(false)
  })

  it('renders the parameter name prefix when argSpecs is known', () => {
    const w = mountNode(mkData({
      argSpecs: [
        { name: 'selector', type: 'str', defaultValue: null, kind: 'positional' },
      ],
    }))
    const prefix = w.find('[data-testid="arg-name-prefix"]')
    expect(prefix.exists()).toBe(true)
    expect(prefix.text()).toContain('selector')
  })

  it('does not render the generic "arg N" fallback as a prefix (it would be noise)', () => {
    const w = mountNode(mkData({
      step: {
        type: 'keyword', keyword: 'X', args: ['a', 'b', 'c'], returnVars: [],
        condition: '', loopVar: '', loopFlavor: '', loopValues: [],
        exceptPattern: '', exceptVar: '', varScope: '', comment: '',
      },
      argSpecs: [
        { name: 'selector', type: 'str', defaultValue: null, kind: 'positional' },
      ],
    }))
    // arg 0 has a real name → prefix shown; args 1+2 fall back → no prefix.
    const prefixes = w.findAll('[data-testid="arg-name-prefix"]')
    expect(prefixes).toHaveLength(1)
    expect(prefixes[0].text()).toContain('selector')
  })

  it('renders "extra positional" prefix for *args entries and beyond', () => {
    const w = mountNode(mkData({
      step: {
        type: 'keyword', keyword: 'Press Keys', args: ['#in', 'Enter', 'Tab'], returnVars: [],
        condition: '', loopVar: '', loopFlavor: '', loopValues: [],
        exceptPattern: '', exceptVar: '', varScope: '', comment: '',
      },
      argSpecs: [
        { name: 'selector', type: 'str', defaultValue: null, kind: 'positional' },
        { name: 'keys', type: 'str', defaultValue: null, kind: 'varargs' },
      ],
    }))
    const prefixes = w.findAll('[data-testid="arg-name-prefix"]')
    expect(prefixes).toHaveLength(3)
    expect(prefixes[0].text()).toContain('selector')
    expect(prefixes[1].text()).toContain('extra positional')
    expect(prefixes[2].text()).toContain('extra positional')
  })
})

describe('KeywordNode friendly type icon prefix (Story EDITOR-3)', () => {
  it('renders the icon prefix when the arg has a recognised type', () => {
    const w = mountNode(mkData({
      argSpecs: [
        { name: 'selector', type: 'str', defaultValue: null, kind: 'positional' },
      ],
    }))
    const icons = w.findAll('[data-testid="arg-type-icon"]')
    expect(icons).toHaveLength(1)
    expect(icons[0].text()).toBe('Aa')
  })

  it('omits the icon prefix for the unknown type bucket (no noise)', () => {
    const w = mountNode(mkData({
      argSpecs: [
        { name: 'opaque', type: 'JsonReply', defaultValue: null, kind: 'positional' },
      ],
    }))
    expect(w.find('[data-testid="arg-type-icon"]').exists()).toBe(false)
  })

  it('omits the icon prefix when there is no signature at all', () => {
    const w = mountNode(mkData({ argSpecs: null }))
    expect(w.find('[data-testid="arg-type-icon"]').exists()).toBe(false)
  })
})
