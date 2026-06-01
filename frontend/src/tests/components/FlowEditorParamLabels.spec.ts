/**
 * Story EDITOR-2 — argSpecs propagation through the converter and the
 * resolveArgSpecs helper. Mirrors the FlowEditorSelectorPicker spec
 * style: pure functional tests, no Vue Flow mounting.
 */
import { describe, it, expect } from 'vitest'
import {
  resolveArgSpecs,
  robotFormToFlow,
  type RobotForm,
  type RobotStep,
  type FlowNodeData,
  type SignatureMap,
} from '@/components/editor/flow/flowConverter'

function mkStep(over: Partial<RobotStep> = {}): RobotStep {
  return {
    type: 'keyword',
    keyword: '',
    args: [],
    returnVars: [],
    condition: '',
    loopVar: '',
    loopFlavor: '',
    loopValues: [],
    exceptPattern: '',
    exceptVar: '',
    varScope: '',
    comment: '',
    ...over,
  }
}

const signatures: SignatureMap = new Map([
  ['click', ['selector: str', 'button: MouseButton = left']],
  ['press keys', ['selector: str', '*keys: str', 'press_duration: timedelta = 0:00:00']],
])

function mkForm(steps: RobotStep[]): RobotForm {
  return {
    settings: [],
    variables: [],
    preambleLines: [],
    keywords: [],
    testCases: [
      {
        name: 'TC',
        documentation: '',
        tags: [],
        setup: '',
        teardown: '',
        timeout: '',
        template: '',
        steps,
      },
    ],
  }
}

describe('resolveArgSpecs', () => {
  it('returns parsed specs for known keywords (case-insensitive lookup)', () => {
    const out = resolveArgSpecs(mkStep({ keyword: 'CLICK' }), signatures)
    expect(out).not.toBeNull()
    expect(out!).toHaveLength(2)
    expect(out![0].name).toBe('selector')
    expect(out![1].name).toBe('button')
    expect(out![1].defaultValue).toBe('left')
  })

  it('returns null for unknown keywords', () => {
    expect(resolveArgSpecs(mkStep({ keyword: 'UnknownKeyword' }), signatures)).toBeNull()
  })

  it('returns null when signatures map is null', () => {
    expect(resolveArgSpecs(mkStep({ keyword: 'Click' }), null)).toBeNull()
  })

  it('returns null for steps without a keyword', () => {
    expect(resolveArgSpecs(mkStep({ keyword: '' }), signatures)).toBeNull()
  })

  it('filters out the libdoc "/" separator for positional-only params', () => {
    // RF libdoc emits the `/` marker as its own descriptor between
    // positional-only params and the rest. Without filtering it
    // would surface in the FlowEditor detail panel as a bogus slot
    // labelled `/:`, and `addArgOptions` would treat positional-only
    // separators as filled slots. The Heal* keywords (added in
    // v0.2.2) are the first real-world consumer of this shape.
    const healSigs: SignatureMap = new Map([
      ['heal click', ['selector: str', '/', '*args: Any', '**kwargs: Any']],
      ['heal fill text', [
        'selector: str',
        '/',
        'text: str',
        '*args: Any',
        '**kwargs: Any',
      ]],
      ['heal drag and drop', [
        'source_selector: str',
        'target_selector: str',
        '/',
        '*args: Any',
        '**kwargs: Any',
      ]],
    ])
    expect(
      resolveArgSpecs(mkStep({ keyword: 'Heal Click' }), healSigs)!
        .map((a) => `${a.name}:${a.kind}`),
    ).toEqual(['selector:positional', 'args:varargs', 'kwargs:kwargs'])

    expect(
      resolveArgSpecs(mkStep({ keyword: 'Heal Fill Text' }), healSigs)!
        .map((a) => `${a.name}:${a.kind}`),
    ).toEqual([
      'selector:positional',
      'text:positional',
      'args:varargs',
      'kwargs:kwargs',
    ])

    // Two-selector variant — both selectors are positional-only and
    // the `/` follows them. Filtering still collapses the gap so the
    // detail panel labels stay aligned (slot 0 = source, slot 1 = target).
    expect(
      resolveArgSpecs(mkStep({ keyword: 'Heal Drag And Drop' }), healSigs)!
        .map((a) => a.name),
    ).toEqual(['source_selector', 'target_selector', 'args', 'kwargs'])
  })

  it('filters out the lone "*" named-only separator too', () => {
    // Pre-existing libdoc shape for `def fn(self, x, *, y)` — `*`
    // separates positional-or-keyword from keyword-only. Same
    // structural-marker reasoning as `/`; pin so a future "tidy up"
    // doesn't reintroduce a bogus slot.
    const sigs: SignatureMap = new Map([
      ['namedonly demo', ['x: str', '*', 'y: int = 1']],
    ])
    expect(
      resolveArgSpecs(mkStep({ keyword: 'NamedOnly Demo' }), sigs)!
        .map((a) => a.name),
    ).toEqual(['x', 'y'])
  })
})

describe('robotFormToFlow attaches argSpecs to keyword nodes', () => {
  it('populates argSpecs for known keywords', () => {
    const form = mkForm([
      mkStep({ keyword: 'Click', args: ['text=OK', 'right'] }),
    ])
    const { nodes } = robotFormToFlow(form, null, signatures)
    const data = nodes.find((n) => n.id === 'tc0-step-0')!.data as FlowNodeData
    expect(data.argSpecs).not.toBeNull()
    expect(data.argSpecs!.map((a) => a.name)).toEqual(['selector', 'button'])
  })

  it('leaves argSpecs null for unknown keywords', () => {
    const form = mkForm([
      mkStep({ keyword: 'Custom Project Keyword', args: ['x'] }),
    ])
    const { nodes } = robotFormToFlow(form, null, signatures)
    const data = nodes.find((n) => n.id === 'tc0-step-0')!.data as FlowNodeData
    expect(data.argSpecs).toBeNull()
  })

  it('handles varargs in a known keyword (Press Keys)', () => {
    const form = mkForm([
      mkStep({ keyword: 'Press Keys', args: ['#in', 'Enter', 'Tab'] }),
    ])
    const { nodes } = robotFormToFlow(form, null, signatures)
    const data = nodes.find((n) => n.id === 'tc0-step-0')!.data as FlowNodeData
    expect(data.argSpecs).not.toBeNull()
    expect(data.argSpecs![0].name).toBe('selector')
    expect(data.argSpecs![1].kind).toBe('varargs')
    expect(data.argSpecs![1].name).toBe('keys')
  })

  it('argSpecs is null when the converter is called without a signatures map', () => {
    const form = mkForm([mkStep({ keyword: 'Click', args: ['x'] })])
    const { nodes } = robotFormToFlow(form, null, null)
    const data = nodes.find((n) => n.id === 'tc0-step-0')!.data as FlowNodeData
    expect(data.argSpecs).toBeNull()
  })
})
