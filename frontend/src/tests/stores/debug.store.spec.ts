/**
 * DEBUG-2: debug store unit tests.
 *
 * Covers the WebSocket-driven state replacement, output buffering,
 * topic-routing (events for other sessions are ignored), and the
 * REST kick + reset flows.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDebugStore } from '@/stores/debug.store'

vi.mock('@/api/debug.api', () => ({
  startDebugSession: vi.fn(),
  startDebugFromStep: vi.fn(),
  postControl: vi.fn(),
  getDebugState: vi.fn(),
  disconnectViaBeacon: vi.fn(),
}))

import * as debugApi from '@/api/debug.api'

describe('debug.store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('startFromRun', () => {
    it('adopts the start response and clears prior state', async () => {
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 'abc123',
        robot_file: 'tests/login.robot',
        breakpoint_line: 42,
        test_name: 'Login Works',
      })
      const store = useDebugStore()
      await store.startFromRun(7)

      expect(store.sessionId).toBe('abc123')
      expect(store.robotFile).toBe('tests/login.robot')
      expect(store.breakpointLine).toBe(42)
      expect(store.testName).toBe('Login Works')
      expect(store.isActive).toBe(true)
      expect(store.outputLog).toEqual([])
    })
  })

  describe('handleWsEvent', () => {
    it('replaces state on a "state" event for the active session', async () => {
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 'abc123',
        robot_file: 'tests.robot',
        breakpoint_line: 1,
        test_name: null,
      })
      const store = useDebugStore()
      await store.startFromRun(1)

      store.handleWsEvent({
        topic: 'debug:session:abc123',
        kind: 'state',
        body: {
          session_id: 'abc123',
          paused: true,
          terminated: false,
          paused_at: { file: '/x.robot', line: 7, keyword: 'Click' },
          scopes: [{ name: 'Local', variables: [{ name: '${x}', value: '1', type: 'int' }] }],
          call_stack: [{ name: 'Sample', file: '/x.robot', line: 7 }],
          output_lines: [],
        },
      })
      expect(store.paused).toBe(true)
      expect(store.pausedAt.line).toBe(7)
      expect(store.scopes[0].variables[0].name).toBe('${x}')
    })

    it('ignores events for other sessions', async () => {
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 'mine',
        robot_file: 'tests.robot',
        breakpoint_line: 1,
        test_name: null,
      })
      const store = useDebugStore()
      await store.startFromRun(1)

      store.handleWsEvent({
        topic: 'debug:session:not-mine',
        kind: 'terminated',
        body: {},
      })
      // State stays as the post-start blank.
      expect(store.state.terminated).toBe(false)
    })

    it('appends output lines and caps the buffer', async () => {
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 'abc',
        robot_file: 'tests.robot',
        breakpoint_line: 1,
        test_name: null,
      })
      const store = useDebugStore()
      await store.startFromRun(1)

      // Push 600 lines — the cap kicks in past 500.
      for (let i = 0; i < 600; i++) {
        store.handleWsEvent({
          topic: 'debug:session:abc',
          kind: 'output',
          body: { output: `line ${i}\n` },
        })
      }
      expect(store.outputLog.length).toBeLessThanOrEqual(300)
      expect(store.outputLog[store.outputLog.length - 1]).toBe('line 599')
    })

    it('marks the session terminated', async () => {
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 'abc',
        robot_file: 'tests.robot',
        breakpoint_line: 1,
        test_name: null,
      })
      const store = useDebugStore()
      await store.startFromRun(1)
      expect(store.isActive).toBe(true)

      store.handleWsEvent({
        topic: 'debug:session:abc',
        kind: 'terminated',
        body: {},
      })
      expect(store.state.terminated).toBe(true)
      expect(store.isActive).toBe(false)
    })
  })

  describe('control', () => {
    it('forwards the command to the API with the active session id', async () => {
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 'sess-7',
        robot_file: 'tests.robot',
        breakpoint_line: 1,
        test_name: null,
      })
      const store = useDebugStore()
      await store.startFromRun(1)
      await store.control('continue')
      expect(debugApi.postControl).toHaveBeenCalledWith('sess-7', 'continue')
    })

    it('does nothing without an active session', async () => {
      const store = useDebugStore()
      await store.control('continue')
      expect(debugApi.postControl).not.toHaveBeenCalled()
    })
  })

  describe('stop', () => {
    it('disconnects and resets the store', async () => {
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 'sess-X',
        robot_file: 'tests.robot',
        breakpoint_line: 1,
        test_name: null,
      })
      const store = useDebugStore()
      await store.startFromRun(1)
      await store.stop()
      expect(debugApi.postControl).toHaveBeenCalledWith('sess-X', 'disconnect')
      expect(store.sessionId).toBeNull()
      expect(store.isActive).toBe(false)
    })
  })

  // -------------------------------------------------------------------------
  // DEBUG-3 — Flow Editor "run up to here" + classifyStepClick
  // -------------------------------------------------------------------------

  describe('startFromStep', () => {
    it('adopts the start response from a step click', async () => {
      vi.mocked(debugApi.startDebugFromStep).mockResolvedValueOnce({
        session_id: 'sess-step-1',
        robot_file: 'tests/login.robot',
        breakpoint_line: 12,
        test_name: 'Login Works',
      })
      const store = useDebugStore()
      const { resp, resumed } = await store.startFromStep({
        file: 'tests/login.robot',
        test_name: 'Login Works',
        line: 12,
        repo_id: 4,
      })
      expect(resumed).toBe(false)
      expect(resp.session_id).toBe('sess-step-1')
      expect(store.sessionId).toBe('sess-step-1')
      expect(store.robotFile).toBe('tests/login.robot')
      expect(store.breakpointLine).toBe(12)
    })

    it('treats a 409 dedup as silent resume', async () => {
      // Build an axios-style error so extractErrorStatus reads 409.
      const err = Object.assign(new Error('conflict'), {
        response: {
          status: 409,
          data: {
            detail: {
              session_id: 'existing-sid',
              robot_file: 'tests.robot',
              breakpoint_line: 5,
              test_name: 'Sample',
            },
          },
        },
      })
      vi.mocked(debugApi.startDebugFromStep).mockRejectedValueOnce(err)

      const store = useDebugStore()
      const { resumed, resp } = await store.startFromStep({
        file: 'tests.robot',
        test_name: 'Sample',
        line: 5,
        repo_id: 1,
      })
      expect(resumed).toBe(true)
      expect(resp.session_id).toBe('existing-sid')
      expect(store.sessionId).toBe('existing-sid')
    })

    it('rethrows non-409 errors', async () => {
      vi.mocked(debugApi.startDebugFromStep).mockRejectedValueOnce(
        Object.assign(new Error('boom'), { response: { status: 500 } }),
      )
      const store = useDebugStore()
      await expect(
        store.startFromStep({
          file: 'tests.robot',
          test_name: 'Sample',
          line: 5,
          repo_id: 1,
        }),
      ).rejects.toThrow()
    })
  })

  describe('classifyStepClick', () => {
    it('returns idle when no session is active', () => {
      const store = useDebugStore()
      expect(store.classifyStepClick('any.robot', 1)).toBe('idle')
    })

    it('returns same for an exact file+line match', async () => {
      vi.mocked(debugApi.startDebugFromStep).mockResolvedValueOnce({
        session_id: 's1',
        robot_file: 'tests.robot',
        breakpoint_line: 7,
        test_name: 'X',
      })
      const store = useDebugStore()
      await store.startFromStep({
        file: 'tests.robot', test_name: 'X', line: 7, repo_id: 1,
      })
      expect(store.classifyStepClick('tests.robot', 7)).toBe('same')
    })

    it('returns different when the line differs', async () => {
      vi.mocked(debugApi.startDebugFromStep).mockResolvedValueOnce({
        session_id: 's1',
        robot_file: 'tests.robot',
        breakpoint_line: 7,
        test_name: 'X',
      })
      const store = useDebugStore()
      await store.startFromStep({
        file: 'tests.robot', test_name: 'X', line: 7, repo_id: 1,
      })
      expect(store.classifyStepClick('tests.robot', 9)).toBe('different')
    })

    it('returns idle once the session is terminated', async () => {
      vi.mocked(debugApi.startDebugFromStep).mockResolvedValueOnce({
        session_id: 's1',
        robot_file: 'tests.robot',
        breakpoint_line: 7,
        test_name: 'X',
      })
      const store = useDebugStore()
      await store.startFromStep({
        file: 'tests.robot', test_name: 'X', line: 7, repo_id: 1,
      })
      // Simulate a terminated event landing on the WS channel.
      store.handleWsEvent({
        topic: 's1' === store.sessionId ? `debug:session:${store.sessionId}` : '',
        kind: 'terminated',
        body: {},
      })
      // `classifyStepClick` checks state.terminated, which the WS
      // handler flipped to true.
      expect(store.classifyStepClick('tests.robot', 7)).toBe('idle')
    })
  })

  // -------------------------------------------------------------------------
  // DEBUG-3 — parser line annotation contract (not a store test, but
  // pinned next to the other DEBUG-3 unit coverage so the related
  // pieces are visible together).
  // -------------------------------------------------------------------------

  describe('cloneStep carries _lineNumber (DEBUG-3 contract)', () => {
    it('preserves _lineNumber across the FlowConverter clone path', async () => {
      const { robotFormToFlow } = await import('@/components/editor/flow/flowConverter')
      const form = {
        settings: [],
        variables: [],
        testCases: [{
          name: 'T',
          documentation: '', tags: [],
          setup: '', teardown: '', timeout: '', template: '',
          steps: [
            {
              type: 'keyword' as const,
              keyword: 'Log', args: ['hi'], returnVars: [],
              condition: '', loopVar: '', loopFlavor: '', loopValues: [],
              exceptPattern: '', exceptVar: '', varScope: '', comment: '',
              _lineNumber: 42,
            },
          ],
        }],
        keywords: [],
        preambleLines: [],
      }
      const { nodes } = robotFormToFlow(form, null, new Map())
      const stepNode = nodes.find(n => n.type === 'keyword')
      expect(stepNode).toBeDefined()
      // The clone in flowConverter.ts must carry _lineNumber
      // through. If it doesn't, the Run-up-to-here button can't
      // resolve the breakpoint line.
      expect(
        (stepNode!.data as { step: { _lineNumber?: number } }).step._lineNumber,
      ).toBe(42)
    })
  })
})
