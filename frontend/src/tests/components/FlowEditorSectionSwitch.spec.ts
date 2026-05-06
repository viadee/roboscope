/**
 * Regression guard for the "switching to Keywords still shows test case
 * content" bug reported during 0.9.0 doc-meta polish.
 *
 * The pure-converter contract is the foundation: when a file has both
 * test cases AND keywords, asking for the keywords graph must produce
 * `kw{i}-…` prefixed nodes only, with the keyword name on the start
 * node and (when applicable) a `doc-meta` side note.
 *
 * The visible-prefix filter inside FlowEditor depends on this naming
 * contract. If converter output ever leaks `tc{i}-…` ids into the
 * keywords path (or vice versa), the filter would still match and the
 * canvas would silently render the wrong section.
 */
import { describe, it, expect } from 'vitest'

import {
  robotFormToFlow,
  robotKeywordsToFlow,
  type RobotForm,
} from '@/components/editor/flow/flowConverter'

function emptySettings() {
  return {
    documentation: '', library: [], resource: [], suite_setup: '',
    suite_teardown: '', test_setup: '', test_teardown: '',
    force_tags: [], default_tags: [], force_keyword_tags: [], default_keyword_tags: [],
  }
}

describe('FlowEditor section switch — converter outputs are prefix-disjoint', () => {
  const form: RobotForm = {
    settings: emptySettings(),
    variables: [],
    testCases: [
      {
        name: 'Insert And Read Back A Row',
        documentation: '',
        tags: [], setup: '', teardown: '', timeout: '', template: '',
        steps: [
          { type: 'keyword', keyword: 'Execute SQL String', args: ['SELECT 1'], returnVars: [], condition: '', loopVar: '', loopFlavor: '', loopValues: [], exceptPattern: '', exceptVar: '', varScope: '', comment: '' },
        ],
      },
    ],
    keywords: [
      {
        name: 'Connect And Create Schema',
        documentation: 'Open the SQLite file (created on first connect)\nand define a fresh `users` table for each run.',
        arguments: [], tags: [], setup: '', teardown: '', timeout: '', returnValue: '',
        steps: [
          { type: 'keyword', keyword: 'Connect To Database', args: ['sqlite3'], returnVars: [], condition: '', loopVar: '', loopFlavor: '', loopValues: [], exceptPattern: '', exceptVar: '', varScope: '', comment: '' },
        ],
      },
      {
        name: 'Disconnect And Cleanup',
        documentation: '',
        arguments: [], tags: [], setup: '', teardown: '', timeout: '', returnValue: '',
        steps: [
          { type: 'keyword', keyword: 'Disconnect From Database', args: [], returnVars: [], condition: '', loopVar: '', loopFlavor: '', loopValues: [], exceptPattern: '', exceptVar: '', varScope: '', comment: '' },
        ],
      },
    ],
  } as RobotForm

  it('robotFormToFlow yields tc{i}- prefixed nodes only', () => {
    const { nodes } = robotFormToFlow(form)
    expect(nodes.length).toBeGreaterThan(0)
    for (const n of nodes) {
      expect(n.id).toMatch(/^tc\d+-/)
    }
    const startTc0 = nodes.find((n) => n.id === 'tc0-start')
    expect(startTc0?.data?.label).toBe('Insert And Read Back A Row')
  })

  it('robotKeywordsToFlow yields kw{i}- prefixed nodes only — never tc-', () => {
    const { nodes } = robotKeywordsToFlow(form)
    expect(nodes.length).toBeGreaterThan(0)
    for (const n of nodes) {
      expect(n.id).toMatch(/^kw\d+-/)
    }
    expect(nodes.some((n) => n.id.startsWith('tc'))).toBe(false)
    const kw0Start = nodes.find((n) => n.id === 'kw0-start')
    expect(kw0Start?.data?.label).toBe('Connect And Create Schema')
  })

  it('keyword with [Documentation] gets a setting-meta side node', () => {
    const { nodes, edges } = robotKeywordsToFlow(form)
    const docNode = nodes.find((n) => n.id === 'kw0-documentation')
    expect(docNode).toBeDefined()
    expect(docNode?.type).toBe('setting-meta')
    expect((docNode?.data as { kind: string }).kind).toBe('documentation')
    expect((docNode?.data as { text: string }).text).toContain('Open the SQLite file')
    expect((docNode?.data as { text: string }).text).toContain('users')

    const docEdge = edges.find((e) => e.id === 'kw0-documentation-edge')
    expect(docEdge).toBeDefined()
    expect(docEdge?.source).toBe('kw0-documentation')
    expect(docEdge?.target).toBe('kw0-start')
  })

  it('keyword without [Documentation] gets NO documentation side node', () => {
    const { nodes } = robotKeywordsToFlow(form)
    expect(nodes.find((n) => n.id === 'kw1-documentation')).toBeUndefined()
  })

  it('visible-nodes filter for Keywords/index 0 matches kw0- but not kw1- or tc-', () => {
    const { nodes } = robotKeywordsToFlow(form)
    const visible = nodes.filter((n) => n.id.startsWith('kw0-'))
    expect(visible.some((n) => n.id === 'kw0-start')).toBe(true)
    expect(visible.some((n) => n.id === 'kw0-documentation')).toBe(true)
    expect(visible.some((n) => n.id.startsWith('kw1-'))).toBe(false)
    expect(visible.some((n) => n.id.startsWith('tc'))).toBe(false)
  })

  it('keyword with [Tags] gets a tags side node stacked below documentation', () => {
    const formWithTags: RobotForm = {
      ...form,
      keywords: [
        { ...form.keywords[0], tags: ['smoke', 'db'] },
        form.keywords[1],
      ],
    } as RobotForm
    const { nodes, edges } = robotKeywordsToFlow(formWithTags)
    const docNode = nodes.find((n) => n.id === 'kw0-documentation')
    const tagsNode = nodes.find((n) => n.id === 'kw0-tags')
    expect(docNode).toBeDefined()
    expect(tagsNode).toBeDefined()
    expect(tagsNode?.type).toBe('setting-meta')
    expect((tagsNode?.data as { kind: string }).kind).toBe('tags')
    expect((tagsNode?.data as { text: string }).text).toBe('smoke, db')
    // Stacked: tags sits one META_PITCH (96px) below documentation —
    // wider than step pitch (80px) so the side-note CSS max-height
    // can't push the next note into the previous one.
    expect((tagsNode!.position.y - docNode!.position.y)).toBe(96)
    // Edge wires up to the same start node.
    expect(edges.find((e) => e.id === 'kw0-tags-edge')?.target).toBe('kw0-start')
  })

  it('keyword without [Tags] gets NO tags side node', () => {
    const { nodes } = robotKeywordsToFlow(form)
    expect(nodes.find((n) => n.id === 'kw0-tags')).toBeUndefined()
  })

  it('test case with empty-string [Tags] entry still renders a side node', () => {
    // The "+ [Tags]" affordance seeds `tags = ['']` so the side note
    // appears even before the user types — presence is gated on
    // length > 0, NOT on the joined string being non-blank.
    const seeded: RobotForm = {
      ...form,
      testCases: [{ ...form.testCases[0], tags: [''] }],
    } as RobotForm
    const { nodes } = robotFormToFlow(seeded)
    expect(nodes.find((n) => n.id === 'tc0-tags')).toBeDefined()
  })

  it('test case with seeded space [Documentation] still renders a side node', () => {
    // The "+ [Documentation]" affordance seeds with a single space
    // so the user lands in a focused panel; the side note must not
    // be filtered out by a value-trim check.
    const seeded: RobotForm = {
      ...form,
      testCases: [{ ...form.testCases[0], documentation: ' ' }],
    } as RobotForm
    const { nodes } = robotFormToFlow(seeded)
    expect(nodes.find((n) => n.id === 'tc0-documentation')).toBeDefined()
  })

  it('test case with truly empty [Tags] (length 0) does NOT render a side node', () => {
    // Counter-test for the regression: the empty default must still
    // suppress the side note, otherwise plain test cases would gain
    // unwanted decorative side notes.
    const { nodes } = robotFormToFlow(form)
    expect(nodes.find((n) => n.id === 'tc0-tags')).toBeUndefined()
  })

  it('test case with [Setup] [Teardown] [Timeout] [Template] all get side nodes', () => {
    const tcForm: RobotForm = {
      ...form,
      testCases: [
        {
          ...form.testCases[0],
          setup: 'Login User',
          teardown: 'Cleanup',
          timeout: '30s',
          template: 'Run Scenario',
        },
      ],
    } as RobotForm
    const { nodes } = robotFormToFlow(tcForm)
    const ids = nodes.map((n) => n.id)
    expect(ids).toContain('tc0-setup')
    expect(ids).toContain('tc0-teardown')
    expect(ids).toContain('tc0-template')
    expect(ids).toContain('tc0-timeout')
    expect((nodes.find((n) => n.id === 'tc0-setup')?.data as { text: string }).text).toBe('Login User')
    expect((nodes.find((n) => n.id === 'tc0-timeout')?.data as { text: string }).text).toBe('30s')
  })
})
