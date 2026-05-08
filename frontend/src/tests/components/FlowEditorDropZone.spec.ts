/**
 * Regression guard for the drag-drop insertion-point math in the
 * FlowEditor canvas.
 *
 * Reported bug: dropping a new keyword from the palette landed at
 * what felt like fixed offsets — the visual indicator and the actual
 * insertion index didn't match where the user thought they were
 * pointing. Cause: `findInsertIndex` and `getDropIndicatorY` both
 * compared `flowY` against each node's `position.y` (TOP edge) only,
 * ignoring that nodes have variable heights (keyword nodes grow with
 * argument count, one chip per row).
 *
 * The two functions live inside FlowEditor.vue's <script setup> and
 * are not directly importable; we mirror their core math here, using
 * the SAME `estimateNodeHeight` helper they call. If the height
 * estimator drifts, both this test and the production code drift
 * together — that's the point.
 */
import { describe, it, expect } from 'vitest'

import { estimateNodeHeight, type RobotStep } from '@/components/editor/flow/flowConverter'

function step(args: string[] = []): RobotStep {
  return {
    type: 'keyword',
    keyword: 'Click',
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

interface PositionedNode {
  step: RobotStep
  positionY: number
}

/** Mirror of FlowEditor.vue::findInsertIndex. */
function findInsertIndex(stepNodes: PositionedNode[], flowY: number): number {
  if (stepNodes.length === 0) return 0
  for (let i = 0; i < stepNodes.length; i++) {
    const top = stepNodes[i].positionY
    const midpoint = top + estimateNodeHeight(stepNodes[i].step) / 2
    if (flowY < midpoint) return i
  }
  return stepNodes.length
}

describe('findInsertIndex — midpoint snap, not top-edge snap', () => {
  it('insertion in the upper half of a node maps to BEFORE that node', () => {
    // Two nodes with one arg each (taller than base): node 0 at y=0,
    // node 1 at y=100.
    const a = step(['#login'])
    const b = step(['#submit'])
    const ha = estimateNodeHeight(a)  // 44 + 4 + 22 = 70
    const nodes: PositionedNode[] = [
      { step: a, positionY: 0 },
      { step: b, positionY: 100 },
    ]
    // Drop in node 0's upper half — expect insert at index 0 (before).
    expect(findInsertIndex(nodes, 5)).toBe(0)
    expect(findInsertIndex(nodes, ha / 2 - 1)).toBe(0)
  })

  it('insertion in the lower half of a node maps to AFTER that node', () => {
    const a = step(['#login'])
    const b = step(['#submit'])
    const ha = estimateNodeHeight(a)
    const nodes: PositionedNode[] = [
      { step: a, positionY: 0 },
      { step: b, positionY: 100 },
    ]
    // Drop just past node 0's midpoint — expect insert at index 1.
    // (Pre-fix: any flowY ≥ 0 and < 100 returned 1 too — the bug was
    // not in this case directly, but the boundary was at the TOP of
    // node 1, so the entire body of node 0 felt "below" it.)
    expect(findInsertIndex(nodes, ha / 2 + 1)).toBe(1)
  })

  it('respects variable node heights — tall arg-heavy node pushes its midpoint down', () => {
    // Node 0 has 5 args → much taller than base. The midpoint sits
    // ~44 + 4 + 5*22 / 2 = 79px from top.
    const tall = step(['a', 'b', 'c', 'd', 'e'])
    const small = step([])
    const tallH = estimateNodeHeight(tall)  // 44 + 4 + 110 = 158
    const tallMid = tallH / 2
    const nodes: PositionedNode[] = [
      { step: tall, positionY: 0 },
      { step: small, positionY: 200 },
    ]
    // 50px is BELOW the small-node midpoint (~22) but ABOVE the
    // tall-node midpoint (~79). With the fix it correctly maps to
    // index 0; before the fix it would have mapped to 1 because 50
    // is below tall's TOP-only check.
    expect(findInsertIndex(nodes, 50)).toBe(0)
    // Past tall's midpoint should jump to 1.
    expect(findInsertIndex(nodes, tallMid + 1)).toBe(1)
  })

  it('flowY past every midpoint maps to "append at end"', () => {
    const a = step()
    const b = step()
    const nodes: PositionedNode[] = [
      { step: a, positionY: 0 },
      { step: b, positionY: 100 },
    ]
    expect(findInsertIndex(nodes, 1000)).toBe(2)
  })

  it('empty list returns 0', () => {
    expect(findInsertIndex([], 50)).toBe(0)
  })
})
