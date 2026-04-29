/**
 * Regression guard for the FlowEditor reorder UX:
 *
 *   1. After `moveStepUp` / `moveStepDown` we want the *moved step*
 *      to remain selected so the user can press Up repeatedly to walk
 *      a step to the top of the list. Selection survival relies on
 *      one specific contract: `stepsToFlow` MUST emit node IDs of the
 *      shape `${prefix}-step-${i}` so the editor can compute the
 *      moved step's new id (`stepNodeIdAt(idx-1)`) before rebuilding.
 *      If the id format ever changes, the moveStepUp fix breaks
 *      silently — this test pins it.
 *
 *   2. The drag-arm delay constant is shared between KeywordNode and
 *      ControlNode. Pin its value so neither component drifts.
 */
import { describe, it, expect } from 'vitest'

import { stepsToFlow, type RobotStep } from '@/components/editor/flow/flowConverter'
import { DRAG_ARM_DELAY_MS } from '@/components/editor/flow/reorderDrag'

function plainStep(keyword: string): RobotStep {
  return {
    type: 'keyword',
    keyword,
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
  }
}

describe('FlowEditor reorder — node id format contract', () => {
  it('emits position-based node ids `${prefix}-step-${i}` for each non-end step', () => {
    const steps: RobotStep[] = [plainStep('A'), plainStep('B'), plainStep('C')]
    const { nodes } = stepsToFlow(steps, 'My TC', 'tc0', 'testcase', 0)

    const stepNodes = nodes.filter((n) => /-step-\d+$/.test(n.id))
    expect(stepNodes.map((n) => n.id)).toEqual([
      'tc0-step-0',
      'tc0-step-1',
      'tc0-step-2',
    ])
  })

  it('reuses position-based ids after a swap — selection-persistence works only if FlowEditor.moveStepUp pins to the NEW slot id', () => {
    // Simulate moveStepUp on idx=2: swap [2] and [1].
    const steps: RobotStep[] = [plainStep('A'), plainStep('B'), plainStep('C')]
    const tmp = steps[2]
    steps[2] = steps[1]
    steps[1] = tmp

    const { nodes } = stepsToFlow(steps, 'My TC', 'tc0', 'testcase', 0)

    // The id `tc0-step-1` now points to the step that USED TO be at
    // index 2 — i.e. the moved step. moveStepUp must therefore look
    // up `tc0-step-1` (the new slot), NOT `tc0-step-2` (the old slot,
    // which now points to the swapped neighbour). This assertion
    // documents that contract — if the id format ever decouples from
    // the array index, FlowEditor.stepNodeIdAt MUST be updated in
    // lockstep or the selection silently jumps to the wrong step.
    const movedNode = nodes.find((n) => n.id === 'tc0-step-1')
    expect(movedNode).toBeDefined()
    expect((movedNode!.data as { step: RobotStep }).step.keyword).toBe('C')

    const swappedNode = nodes.find((n) => n.id === 'tc0-step-2')
    expect((swappedNode!.data as { step: RobotStep }).step.keyword).toBe('B')
  })
})

describe('FlowEditor reorder — drag-arm delay', () => {
  it('keeps the hold-then-arm constant in a usable range', () => {
    // 200 ms is comfortably above accidental-click duration (~60–120 ms)
    // and below the threshold where deliberate hold-and-drag starts to
    // feel laggy. If anyone changes this, the test is a forcing
    // function to consider both sides.
    expect(DRAG_ARM_DELAY_MS).toBeGreaterThanOrEqual(150)
    expect(DRAG_ARM_DELAY_MS).toBeLessThanOrEqual(400)
  })
})
