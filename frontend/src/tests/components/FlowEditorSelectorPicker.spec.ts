/**
 * Story EDITOR-1 — integration test for the SelectorPicker wiring inside
 * the visual flow editor.
 *
 * We don't mount the full FlowEditor (it depends on Vue Flow + a canvas);
 * instead we exercise the converter + matcher contract that decides
 * whether the picker is rendered, and the swap handler that persists
 * the index back into the sidecar.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/explorer.api', () => ({
  getFile: vi.fn(),
  saveFile: vi.fn(),
}))

import { saveFile } from '@/api/explorer.api'
import { saveSidecar } from '@/composables/useRecordingSidecar'
import {
  applySelectorSwap,
  isCustomSelectorValue,
  matchStepToCommand,
  recordedIndex,
  isRecordedStep,
  robotFormToFlow,
  type RobotForm,
  type RobotStep,
  type FlowNodeData,
} from '@/components/editor/flow/flowConverter'
import type { RecordedCommand, RecordedFlow } from '@/types/recorder.types'

const mockedSave = saveFile as unknown as ReturnType<typeof vi.fn>

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

const sidecar: RecordedFlow = {
  schema_version: 1,
  transport: 'web_playwright',
  session_id: '17',
  name: null,
  commands: [
    {
      index: 0,
      keyword: 'Scroll To Element',
      args: {},
      selector_candidates: [
        { strategy: 'text', value: 'text=Welcome', quality_score: 50, verified_unique: false },
        { strategy: 'css', value: 'div.intro', quality_score: 45, verified_unique: false },
      ],
      active_candidate_index: 0,
    },
    {
      index: 1,
      keyword: 'Click',
      args: {},
      selector_candidates: [
        { strategy: 'aria', value: 'role=button[name="OK"]', quality_score: 80, verified_unique: false },
        { strategy: 'text', value: 'text=OK', quality_score: 60, verified_unique: false },
      ],
      active_candidate_index: 0,
    },
  ],
}

describe('isRecordedStep', () => {
  it('matches keyword + assignment, skips control-flow', () => {
    expect(isRecordedStep(mkStep({ type: 'keyword' }))).toBe(true)
    expect(isRecordedStep(mkStep({ type: 'assignment' }))).toBe(true)
    expect(isRecordedStep(mkStep({ type: 'if' }))).toBe(false)
    expect(isRecordedStep(mkStep({ type: 'for' }))).toBe(false)
    expect(isRecordedStep(mkStep({ type: 'end' }))).toBe(false)
    expect(isRecordedStep(mkStep({ type: 'comment' }))).toBe(false)
    expect(isRecordedStep(mkStep({ type: 'var' }))).toBe(false)
  })
})

describe('recordedIndex', () => {
  it('counts only recorded-eligible steps before the target', () => {
    const steps = [
      mkStep({ type: 'keyword', keyword: 'A' }),  // 0
      mkStep({ type: 'if' }),                      // skipped
      mkStep({ type: 'keyword', keyword: 'B' }),  // 1
      mkStep({ type: 'end' }),                     // skipped
      mkStep({ type: 'keyword', keyword: 'C' }),  // 2
    ]
    expect(recordedIndex(steps, 0)).toBe(0)
    expect(recordedIndex(steps, 2)).toBe(1)
    expect(recordedIndex(steps, 4)).toBe(2)
    expect(recordedIndex(steps, 1)).toBe(-1) // 'if' is not recorded
    expect(recordedIndex(steps, 3)).toBe(-1) // 'end' is not recorded
  })

  it('returns -1 for out-of-range indices', () => {
    expect(recordedIndex([], 0)).toBe(-1)
    expect(recordedIndex([mkStep()], -1)).toBe(-1)
    expect(recordedIndex([mkStep()], 5)).toBe(-1)
  })
})

describe('matchStepToCommand', () => {
  const steps = [
    mkStep({ type: 'keyword', keyword: 'Scroll To Element' }),
    mkStep({ type: 'if', condition: '${x}' }),
    mkStep({ type: 'keyword', keyword: 'Click' }),
    mkStep({ type: 'end' }),
  ]

  it('matches the n-th recorded step to the n-th command', () => {
    expect(matchStepToCommand(steps, sidecar, 0)?.keyword).toBe('Scroll To Element')
    expect(matchStepToCommand(steps, sidecar, 2)?.keyword).toBe('Click')
  })

  it('returns null for control-flow steps', () => {
    expect(matchStepToCommand(steps, sidecar, 1)).toBeNull()
    expect(matchStepToCommand(steps, sidecar, 3)).toBeNull()
  })

  it('returns null when sidecar is null', () => {
    expect(matchStepToCommand(steps, null, 0)).toBeNull()
  })

  it('returns null when there is no command at the matching position', () => {
    const longerSteps = [...steps, mkStep({ type: 'keyword', keyword: 'Press Keys' })]
    // longerSteps[4] would be the third recorded step → idx 2 → no command
    expect(matchStepToCommand(longerSteps, sidecar, 4)).toBeNull()
  })
})

describe('robotFormToFlow with sidecar', () => {
  function mkForm(steps: RobotStep[]): RobotForm {
    return {
      settings: [],
      variables: [],
      preambleLines: [],
      keywords: [],
      testCases: [
        {
          name: 'Recording 17',
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

  it('attaches recording to matched keyword nodes, leaves others null', () => {
    const form = mkForm([
      mkStep({ type: 'keyword', keyword: 'Scroll To Element', args: ['text=Welcome'] }),
      mkStep({ type: 'keyword', keyword: 'Click', args: ['role=button[name="OK"]'] }),
    ])
    const { nodes } = robotFormToFlow(form, sidecar)
    const stepNodes = nodes.filter((n) => n.id.startsWith('tc0-step-'))
    expect(stepNodes).toHaveLength(2)
    const data0 = stepNodes[0].data as FlowNodeData
    const data1 = stepNodes[1].data as FlowNodeData
    expect(data0.recording?.keyword).toBe('Scroll To Element')
    expect(data1.recording?.keyword).toBe('Click')
  })

  it('attaches null when sidecar is null', () => {
    const form = mkForm([mkStep({ type: 'keyword', keyword: 'Click', args: ['x'] })])
    const { nodes } = robotFormToFlow(form, null)
    const data = nodes.find((n) => n.id === 'tc0-step-0')!.data as FlowNodeData
    expect(data.recording).toBeNull()
  })

  it('only matches the first test case (Recorder v2 emits one per session)', () => {
    const form: RobotForm = {
      settings: [],
      variables: [],
      preambleLines: [],
      keywords: [],
      testCases: [
        {
          name: 'TC1', documentation: '', tags: [], setup: '', teardown: '',
          timeout: '', template: '',
          steps: [mkStep({ type: 'keyword', keyword: 'Click', args: ['x'] })],
        },
        {
          name: 'TC2', documentation: '', tags: [], setup: '', teardown: '',
          timeout: '', template: '',
          steps: [mkStep({ type: 'keyword', keyword: 'Click', args: ['y'] })],
        },
      ],
    }
    const { nodes } = robotFormToFlow(form, sidecar)
    const tc1Step = nodes.find((n) => n.id === 'tc1-step-0')!.data as FlowNodeData
    expect(tc1Step.recording).toBeNull()
  })
})

describe('saveSidecar (smoke test for swap persistence)', () => {
  beforeEach(() => mockedSave.mockReset())

  it('persists a mutated sidecar', async () => {
    mockedSave.mockResolvedValue({})
    const mutated = JSON.parse(JSON.stringify(sidecar)) as RecordedFlow
    mutated.commands[0].active_candidate_index = 1
    await saveSidecar(5, 'flows/recording.robot', mutated)
    expect(mockedSave).toHaveBeenCalledTimes(1)
    const writtenContent = mockedSave.mock.calls[0][2] as string
    const reparsed = JSON.parse(writtenContent) as RecordedFlow
    expect(reparsed.commands[0].active_candidate_index).toBe(1)
  })
})

describe('applySelectorSwap', () => {
  function clone(): { step: RobotStep; cmd: RecordedCommand } {
    return {
      step: mkStep({ keyword: 'Click', args: ['text=Welcome'] }),
      cmd: JSON.parse(JSON.stringify(sidecar.commands[0])),
    }
  }

  it('updates args[0] and active_candidate_index for a valid index', () => {
    const { step, cmd } = clone()
    expect(applySelectorSwap(step, cmd, 1)).toBe(true)
    expect(step.args[0]).toBe('div.intro')
    expect(cmd.active_candidate_index).toBe(1)
  })

  it('does nothing for an out-of-range index', () => {
    const { step, cmd } = clone()
    expect(applySelectorSwap(step, cmd, 99)).toBe(false)
    expect(step.args[0]).toBe('text=Welcome')
    expect(cmd.active_candidate_index).toBe(0)
  })

  it('appends to args when args is empty', () => {
    const step = mkStep({ keyword: 'Click', args: [] })
    const cmd = JSON.parse(JSON.stringify(sidecar.commands[0]))
    expect(applySelectorSwap(step, cmd, 0)).toBe(true)
    expect(step.args).toEqual(['text=Welcome'])
  })
})

describe('isCustomSelectorValue', () => {
  it('returns true when args[0] is not in the recorded candidates', () => {
    const step = mkStep({ args: ['#manual-id'] })
    expect(isCustomSelectorValue(step, sidecar.commands[0])).toBe(true)
  })

  it('returns false when args[0] matches a recorded candidate', () => {
    const step = mkStep({ args: ['div.intro'] })
    expect(isCustomSelectorValue(step, sidecar.commands[0])).toBe(false)
  })

  it('returns false for an empty args list', () => {
    const step = mkStep({ args: [] })
    expect(isCustomSelectorValue(step, sidecar.commands[0])).toBe(false)
  })

  it('returns false when the command has no candidates', () => {
    const step = mkStep({ args: ['anything'] })
    const cmd: RecordedCommand = { ...sidecar.commands[0], selector_candidates: [] }
    expect(isCustomSelectorValue(step, cmd)).toBe(false)
  })
})
