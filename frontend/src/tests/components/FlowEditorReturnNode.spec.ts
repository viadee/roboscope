/**
 * Pins the data contract for RETURN node editing in FlowEditor:
 * the converter stores the user-facing return values on `step.args`,
 * the detail panel v-models into that array, and the serializer
 * round-trips them back as `RETURN  v1  v2  v3`.
 *
 * Regression guard for the user report: "im detail view fehlt die
 * Möglichkeit den Wert für den return anzugeben" — the detail panel
 * needs an editable input bound to the args array. This spec
 * doesn't mount the full Vue component; instead it validates the
 * underlying data contract the panel depends on.
 */
import { describe, it, expect } from 'vitest'

import {
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

describe('FlowEditor — RETURN node carries an editable args array', () => {
  const form: RobotForm = {
    settings: emptySettings(),
    variables: [],
    testCases: [],
    keywords: [
      {
        name: 'Compute Result',
        documentation: '',
        arguments: ['${a}', '${b}'],
        tags: [], setup: '', teardown: '', timeout: '', returnValue: '',
        steps: [
          {
            type: 'return',
            keyword: '',
            args: ['${a}', '${b}', '"done"'],
            returnVars: [],
            condition: '', loopVar: '', loopFlavor: '', loopValues: [],
            exceptPattern: '', exceptVar: '', varScope: '', comment: '',
          },
        ],
      },
    ],
  } as RobotForm

  it('return-step args end up on the rendered RETURN node', () => {
    const { nodes } = robotKeywordsToFlow(form)
    const ret = nodes.find((n) => n.type === 'return')
    expect(ret).toBeDefined()
    const data = ret!.data as { step: { args: string[] } }
    expect(data.step.args).toEqual(['${a}', '${b}', '"done"'])
  })

  it('node-side args are NOT shared by reference with the form (cloneStep contract)', () => {
    const { nodes } = robotKeywordsToFlow(form)
    const ret = nodes.find((n) => n.type === 'return')!
    const data = ret.data as { step: { args: string[] } }
    // Mutating the node's args array MUST NOT mutate the form —
    // otherwise the deep watcher in FlowEditor.vue fires on every
    // keystroke and tears down the detail panel mid-edit. The
    // mutation flows back via updateStepFromNode on blur instead.
    expect(data.step.args).not.toBe(form.keywords[0].steps[0].args)
    data.step.args.push('extra')
    expect(form.keywords[0].steps[0].args).not.toContain('extra')
  })
})
