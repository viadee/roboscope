/**
 * Regression guard for the "detail panel closes mid-typing" bug.
 *
 * The detail panel's text/number inputs use v-model on
 * `selectedNodeData.step.args[i]`. The flow converter previously
 * built node data with a shallow `step: { ...step }` spread, leaving
 * the `args` / `returnVars` / `loopValues` arrays as SHARED
 * REFERENCES with the form. Every keystroke wrote through to
 * `props.form`, which fired the deep `watch([() => props.form, …],
 * { deep: true })` callback in FlowEditor.vue and reset
 * `selectedNode = null` — closing the panel mid-edit.
 *
 * Fix: `cloneStep()` deep-copies the array fields so the node carries
 * its own writable buffers. The form is updated only on blur via
 * `updateStepFromNode`'s `Object.assign`, which replaces the form's
 * arrays with the node's arrays in one shot.
 *
 * This test pins the no-shared-array invariant: if anyone removes the
 * deep clone (or adds a new array field to RobotStep without copying
 * it), the panel-close bug comes back.
 */
import { describe, it, expect } from 'vitest'

import { robotFormToFlow, type RobotForm, type RobotStep, type FlowNodeData } from '@/components/editor/flow/flowConverter'

function step(keyword: string, args: string[]): RobotStep {
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

describe('FlowEditor step isolation — detail panel typing must not mutate form', () => {
  it('node data carries its own `args` array (NOT shared with the form)', () => {
    const form: RobotForm = {
      settings: { documentation: '', library: [], resource: [], suite_setup: '', suite_teardown: '', test_setup: '', test_teardown: '', force_tags: [], default_tags: [], force_keyword_tags: [], default_keyword_tags: [] },
      variables: [],
      testCases: [
        { name: 'TC', documentation: '', tags: [], setup: '', teardown: '', timeout: '', template: '', steps: [step('Click', ['#login'])] },
      ],
      keywords: [],
    } as RobotForm

    const { nodes } = robotFormToFlow(form)
    const stepNode = nodes.find((n) => n.id === 'tc0-step-0')!
    const nodeData = stepNode.data as FlowNodeData

    // Reference identity check — the precise invariant the panel
    // depends on. If this fails, the deep watcher will fire on every
    // keystroke and the detail panel closes mid-edit.
    expect(nodeData.step.args).not.toBe(form.testCases[0].steps[0].args)
    expect(nodeData.step.returnVars).not.toBe(form.testCases[0].steps[0].returnVars)
    expect(nodeData.step.loopValues).not.toBe(form.testCases[0].steps[0].loopValues)

    // Content is still equal — the clone is value-preserving.
    expect(nodeData.step.args).toEqual(form.testCases[0].steps[0].args)
  })

  it('mutating the node `args` does NOT mutate the form', () => {
    const form: RobotForm = {
      settings: { documentation: '', library: [], resource: [], suite_setup: '', suite_teardown: '', test_setup: '', test_teardown: '', force_tags: [], default_tags: [], force_keyword_tags: [], default_keyword_tags: [] },
      variables: [],
      testCases: [
        { name: 'TC', documentation: '', tags: [], setup: '', teardown: '', timeout: '', template: '', steps: [step('Click', ['#login'])] },
      ],
      keywords: [],
    } as RobotForm
    const original = form.testCases[0].steps[0].args[0]

    const { nodes } = robotFormToFlow(form)
    const nodeData = nodes.find((n) => n.id === 'tc0-step-0')!.data as FlowNodeData

    // Simulate v-model writing a partial keystroke into the panel.
    nodeData.step.args[0] = `${original}-typing`

    // The form's array is unchanged — ergo the deep `props.form`
    // watcher does NOT fire mid-keystroke.
    expect(form.testCases[0].steps[0].args[0]).toBe(original)
  })
})
