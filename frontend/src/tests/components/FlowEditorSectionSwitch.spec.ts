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

  it('keyword with [Documentation] gets a doc-meta side node', () => {
    const { nodes, edges } = robotKeywordsToFlow(form)
    const docNode = nodes.find((n) => n.id === 'kw0-doc')
    expect(docNode).toBeDefined()
    expect(docNode?.type).toBe('doc-meta')
    expect((docNode?.data as { text: string }).text).toContain('Open the SQLite file')
    expect((docNode?.data as { text: string }).text).toContain('users')

    const docEdge = edges.find((e) => e.id === 'kw0-doc-edge')
    expect(docEdge).toBeDefined()
    expect(docEdge?.source).toBe('kw0-doc')
    expect(docEdge?.target).toBe('kw0-start')
  })

  it('keyword without [Documentation] gets NO doc-meta node', () => {
    const { nodes } = robotKeywordsToFlow(form)
    expect(nodes.find((n) => n.id === 'kw1-doc')).toBeUndefined()
  })

  it('visible-nodes filter for Keywords/index 0 matches kw0- but not kw1- or tc-', () => {
    const { nodes } = robotKeywordsToFlow(form)
    const visible = nodes.filter((n) => n.id.startsWith('kw0-'))
    expect(visible.some((n) => n.id === 'kw0-start')).toBe(true)
    expect(visible.some((n) => n.id === 'kw0-doc')).toBe(true)
    expect(visible.some((n) => n.id.startsWith('kw1-'))).toBe(false)
    expect(visible.some((n) => n.id.startsWith('tc'))).toBe(false)
  })
})
