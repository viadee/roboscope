/**
 * RECORDER-IDMAP Phase 2 — id-based mapping between Robot steps and
 * sidecar selector groups.
 *
 * User report: "wenn mehrere selektoren aufgenommen wurden passen
 * diese nicht zu den korrekten befehlen in der aufnahme. … dies ist
 * das einzig echte mapping, welches unabhängig von der position des
 * eintrags im recording oder später auch im testfall gemacht werden
 * kann."
 *
 * Phase 1 (backend, commit prior) added `RecordedCommand.id` and an
 * emit-time trailing `# rbs:<id>` comment. Phase 2 (this test file)
 * pins the FE matcher contract: prefer id, fall back to position
 * for legacy recordings, return null when an id is set but the
 * sidecar lacks the matching command (drift detection).
 */
import { describe, it, expect } from 'vitest'

import {
  matchStepToCommand,
  type RobotStep,
  type RecordedFlow,
  type RecordedCommand,
} from '@/components/editor/flow/flowConverter'

function _step(keyword: string, rbs_id?: string): RobotStep {
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
    ...(rbs_id ? { rbs_id } : {}),
  }
}

function _cmd(id: string, keyword: string): RecordedCommand {
  return {
    id,
    index: 0,
    keyword,
    args: {},
    selector_candidates: [],
    active_candidate_index: 0,
  }
}

function _flow(commands: RecordedCommand[]): RecordedFlow {
  return {
    schema_version: 1,
    transport: 'web_playwright',
    session_id: 's1',
    name: null,
    commands,
  }
}

describe('matchStepToCommand — RECORDER-IDMAP', () => {
  it('matches by id when both step and sidecar carry it', () => {
    const steps = [_step('Click', 'abc123')]
    const sidecar = _flow([_cmd('abc123', 'Click')])
    const cmd = matchStepToCommand(steps, sidecar, 0)
    expect(cmd?.id).toBe('abc123')
  })

  it('id-match survives reorder — the user-reported regression', () => {
    // Steps in their AS-RECORDED order would have matched commands
    // at indexes 0/1/2. Reorder reverses them; positional lookup
    // would now show the wrong selector group on each row, but
    // id-lookup finds the right one regardless of position.
    const steps = [
      _step('Click', 'id-c'),  // was last in recording, now first
      _step('Type Text', 'id-b'),
      _step('Go To', 'id-a'),  // was first in recording, now last
    ]
    const sidecar = _flow([
      _cmd('id-a', 'Go To'),
      _cmd('id-b', 'Type Text'),
      _cmd('id-c', 'Click'),
    ])
    expect(matchStepToCommand(steps, sidecar, 0)?.id).toBe('id-c')
    expect(matchStepToCommand(steps, sidecar, 1)?.id).toBe('id-b')
    expect(matchStepToCommand(steps, sidecar, 2)?.id).toBe('id-a')
  })

  it('id-match survives row insertion in the middle', () => {
    // Insert a hand-written step (no rbs_id) BETWEEN two recorded
    // ones. Positional lookup would shift cmd[1] down to step 2,
    // but id-lookup still pairs the right command to the right step.
    const steps = [
      _step('Click', 'rec-1'),
      _step('Log', undefined),  // hand-inserted, no id
      _step('Click', 'rec-2'),
    ]
    const sidecar = _flow([
      _cmd('rec-1', 'Click'),
      _cmd('rec-2', 'Click'),
    ])
    expect(matchStepToCommand(steps, sidecar, 0)?.id).toBe('rec-1')
    expect(matchStepToCommand(steps, sidecar, 1)).toBeNull()  // no id, no positional twin
    expect(matchStepToCommand(steps, sidecar, 2)?.id).toBe('rec-2')
  })

  it('falls back to positional match when neither side has ids (legacy recording)', () => {
    // Pre-IDMAP recording — step has no rbs_id, command has no id
    // (or fresh id from the default factory that the .robot doesn't
    // know about). Positional fallback is the de-facto contract.
    const steps = [_step('Click'), _step('Type Text')]
    const sidecar = _flow([_cmd('legacy-1', 'Click'), _cmd('legacy-2', 'Type Text')])
    // Sidecar's ids exist but step has none → fall back to position.
    expect(matchStepToCommand(steps, sidecar, 0)?.id).toBe('legacy-1')
    expect(matchStepToCommand(steps, sidecar, 1)?.id).toBe('legacy-2')
  })

  it('returns null when step has an id with no matching sidecar command (drift)', () => {
    // Step references an id the sidecar doesn't know about — typical
    // when the user re-recorded part of a flow and the sidecar got
    // truncated. Returning null is more honest than silently
    // back-filling with positional match (which would show an
    // unrelated row's selectors).
    const steps = [_step('Click', 'orphan-id')]
    const sidecar = _flow([_cmd('present-id', 'Click')])
    expect(matchStepToCommand(steps, sidecar, 0)).toBeNull()
  })

  it('returns null when no sidecar at all', () => {
    const steps = [_step('Click', 'abc')]
    expect(matchStepToCommand(steps, null, 0)).toBeNull()
  })

  it('returns null for non-recorded step types (FOR/IF/comment etc.)', () => {
    const stepFor: RobotStep = { ..._step('FOR'), type: 'for' }
    const sidecar = _flow([_cmd('a', 'Click')])
    expect(matchStepToCommand([stepFor], sidecar, 0)).toBeNull()
  })

  it('returns null for out-of-range indices', () => {
    const steps = [_step('Click', 'a')]
    const sidecar = _flow([_cmd('a', 'Click')])
    expect(matchStepToCommand(steps, sidecar, -1)).toBeNull()
    expect(matchStepToCommand(steps, sidecar, 99)).toBeNull()
  })
})
