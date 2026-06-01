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
  installPrerequisites: vi.fn(),
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
      const result = await store.startFromStep({
        file: 'tests.robot',
        test_name: 'Sample',
        line: 5,
        repo_id: 1,
      })
      expect(result).not.toBeNull()
      expect(result!.resumed).toBe(true)
      expect(result!.resp.session_id).toBe('existing-sid')
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

  describe('DEBUG-4 prereq install dialog flow', () => {
    function fakeAxios424(detail: Record<string, unknown>) {
      return Object.assign(new Error('failed dependency'), {
        response: { status: 424, data: { detail } },
      })
    }

    it('startFromRun returns null on 424 and stashes prereq state', async () => {
      vi.mocked(debugApi.startDebugSession).mockRejectedValueOnce(
        fakeAxios424({
          code: 'robotcode_not_installed',
          repo_id: 17,
          env_id: 5,
          package: 'robotcode',
          message: 'RobotCode is not installed',
        }),
      )
      const store = useDebugStore()
      const resp = await store.startFromRun(99)

      expect(resp).toBeNull()
      expect(store.isActive).toBe(false)
      expect(store.prereqMissing).toEqual({
        repoId: 17,
        envId: 5,
        packageName: 'robotcode',
        message: 'RobotCode is not installed',
      })
    })

    it('startFromStep returns null on 424 and stashes step retry payload', async () => {
      vi.mocked(debugApi.startDebugFromStep).mockRejectedValueOnce(
        fakeAxios424({
          code: 'robotcode_not_installed',
          repo_id: 3,
          env_id: 1,
          package: 'robotcode',
          message: '',
        }),
      )
      const store = useDebugStore()
      const result = await store.startFromStep({
        file: 'tests/login.robot',
        test_name: 'Login',
        line: 4,
        repo_id: 3,
      })
      expect(result).toBeNull()
      expect(store.prereqMissing?.repoId).toBe(3)
    })

    it('installPrereqAndRetry installs then re-fires the original start', async () => {
      // First call (initial start) fails with 424.
      vi.mocked(debugApi.startDebugSession).mockRejectedValueOnce(
        fakeAxios424({
          code: 'robotcode_not_installed',
          repo_id: 1,
          env_id: 2,
          package: 'robotcode',
          message: '',
        }),
      )
      // Install endpoint succeeds.
      vi.mocked(debugApi.installPrerequisites).mockResolvedValueOnce({
        already_installed: false,
        log_tail: 'Installed robotcode 1.2.3',
      })
      // Retry call resolves successfully.
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 's-after-install',
        robot_file: 'tests.robot',
        breakpoint_line: 7,
        test_name: 'Sample',
      })

      const store = useDebugStore()
      await store.startFromRun(42)
      expect(store.prereqMissing).not.toBeNull()

      const ok = await store.installPrereqAndRetry()
      expect(ok).toBe(true)
      expect(store.sessionId).toBe('s-after-install')
      expect(store.isActive).toBe(true)
      expect(store.prereqMissing).toBeNull()
      expect(debugApi.installPrerequisites).toHaveBeenCalledWith(1)
    })

    it('installPrereqAndRetry surfaces install failure and keeps dialog open', async () => {
      vi.mocked(debugApi.startDebugSession).mockRejectedValueOnce(
        fakeAxios424({
          code: 'robotcode_not_installed',
          repo_id: 1,
          env_id: 2,
          package: 'robotcode',
          message: '',
        }),
      )
      vi.mocked(debugApi.installPrerequisites).mockRejectedValueOnce(
        Object.assign(new Error('boom'), {
          response: { status: 500, data: { detail: { message: 'pip failed' } } },
        }),
      )

      const store = useDebugStore()
      await store.startFromRun(42)

      const ok = await store.installPrereqAndRetry()
      expect(ok).toBe(false)
      expect(store.installError).toBeTruthy()
      expect(store.prereqMissing).not.toBeNull()
      expect(store.isActive).toBe(false)
    })

    it('cancelPrereq clears all prereq state', async () => {
      vi.mocked(debugApi.startDebugSession).mockRejectedValueOnce(
        fakeAxios424({
          code: 'robotcode_not_installed',
          repo_id: 1,
          env_id: 2,
          package: 'robotcode',
          message: '',
        }),
      )

      const store = useDebugStore()
      await store.startFromRun(42)
      expect(store.prereqMissing).not.toBeNull()

      store.cancelPrereq()
      expect(store.prereqMissing).toBeNull()
      expect(store.installing).toBe(false)
      expect(store.installError).toBeNull()
    })
  })

  // -------------------------------------------------------------------------
  // DEBUG-7 — race conditions and complex sequences
  // -------------------------------------------------------------------------

  describe('event-stream edge cases', () => {
    async function withActiveSession() {
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 'sid-1',
        robot_file: 'tests.robot',
        breakpoint_line: 3,
        test_name: null,
      })
      const store = useDebugStore()
      await store.startFromRun(7)
      return store
    }

    it('terminated event arriving DURING a pending control resolves cleanly', async () => {
      const store = await withActiveSession()
      // The user has clicked a step button — postControl is in flight.
      // While we await, the test terminates and the WS sends terminated.
      let resolveControl: () => void = () => {}
      vi.mocked(debugApi.postControl).mockImplementationOnce(
        () => new Promise<void>((r) => { resolveControl = r }),
      )
      const stepPromise = store.control('next')

      // Terminated arrives BEFORE the step response.
      store.handleWsEvent({
        topic: 'debug:session:sid-1',
        kind: 'terminated',
        body: {},
      })
      // Step response finally lands.
      resolveControl()
      await stepPromise

      // Both signals are honored: terminated wins for state.
      expect(store.state.terminated).toBe(true)
      expect(store.state.paused).toBe(false)
      expect(store.isActive).toBe(false)
    })

    it('multiple state events update to the LAST one (last-write-wins)', async () => {
      const store = await withActiveSession()

      const stateA = {
        session_id: 'sid-1',
        paused: true,
        terminated: false,
        paused_at: { file: 'tests.robot', line: 3, keyword: 'Log' },
        scopes: [], call_stack: [], output_lines: [],
      }
      const stateB = { ...stateA, paused_at: { file: 'tests.robot', line: 5, keyword: 'Log' } }
      const stateC = { ...stateA, paused_at: { file: 'tests.robot', line: 7, keyword: 'Log' } }

      // Simulate three rapid state events (e.g. user clicked Step
      // three times very quickly).
      store.handleWsEvent({ topic: 'debug:session:sid-1', kind: 'state', body: stateA })
      store.handleWsEvent({ topic: 'debug:session:sid-1', kind: 'state', body: stateB })
      store.handleWsEvent({ topic: 'debug:session:sid-1', kind: 'state', body: stateC })

      expect(store.state.paused_at.line).toBe(7)
    })

    it('output buffer is capped at 300 lines on overflow', async () => {
      const store = await withActiveSession()
      // Pump 350 outputs in. Cap is 300.
      for (let i = 0; i < 350; i++) {
        store.handleWsEvent({
          topic: 'debug:session:sid-1',
          kind: 'output',
          body: { output: `line-${i}\n` },
        })
      }
      expect(store.outputLog.length).toBe(300)
      // Last line is the most recent — first line was dropped.
      expect(store.outputLog[299]).toBe('line-349')
      expect(store.outputLog[0]).toBe('line-50')
    })

    it('events for a different session_id are silently ignored', async () => {
      const store = await withActiveSession()
      const before = { ...store.state }
      store.handleWsEvent({
        topic: 'debug:session:OTHER-SESSION',
        kind: 'state',
        body: {
          session_id: 'OTHER-SESSION',
          paused: true,
          terminated: false,
          paused_at: { file: 'other.robot', line: 99, keyword: 'X' },
          scopes: [], call_stack: [], output_lines: [],
        },
      })
      // No state change.
      expect(store.state.paused_at.line).toBe(before.paused_at.line)
    })

    it('events arriving after store reset are ignored', async () => {
      const store = await withActiveSession()
      store.reset()
      // Simulate a stale event after the panel was closed.
      store.handleWsEvent({
        topic: 'debug:session:sid-1',
        kind: 'state',
        body: {
          session_id: 'sid-1',
          paused: true,
          terminated: false,
          paused_at: { file: 'tests.robot', line: 3, keyword: 'Log' },
          scopes: [], call_stack: [], output_lines: [],
        },
      })
      expect(store.sessionId).toBeNull()
      expect(store.state.paused).toBe(false)
    })
  })

  describe('rapid control commands', () => {
    it('rapid sequential control calls all dispatch (no implicit dedup)', async () => {
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 'sid-r1',
        robot_file: 'tests.robot',
        breakpoint_line: 1,
        test_name: null,
      })
      const store = useDebugStore()
      await store.startFromRun(99)

      // Three quick step clicks (UI normally disables the button
      // between, but verify the store doesn't ALSO dedup — letting
      // the disabled-state contract own that responsibility).
      await Promise.all([
        store.control('next'),
        store.control('next'),
        store.control('next'),
      ])

      expect(debugApi.postControl).toHaveBeenCalledTimes(3)
      expect(debugApi.postControl).toHaveBeenNthCalledWith(1, 'sid-r1', 'next')
      expect(debugApi.postControl).toHaveBeenNthCalledWith(2, 'sid-r1', 'next')
      expect(debugApi.postControl).toHaveBeenNthCalledWith(3, 'sid-r1', 'next')
    })

    it('control call without an active session is a silent no-op', async () => {
      const store = useDebugStore()
      await store.control('continue')
      await store.control('next')
      await store.control('stepIn')
      await store.control('stepOut')
      expect(debugApi.postControl).not.toHaveBeenCalled()
    })

    it('stop after a session reset is a no-op (no double-disconnect)', async () => {
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 'sid-s1',
        robot_file: 'tests.robot',
        breakpoint_line: 1,
        test_name: null,
      })
      const store = useDebugStore()
      await store.startFromRun(1)
      await store.stop()
      // postControl was called once for the disconnect.
      expect(debugApi.postControl).toHaveBeenCalledTimes(1)

      // Click Stop again — the store's session is already null, so
      // nothing fires.
      await store.stop()
      expect(debugApi.postControl).toHaveBeenCalledTimes(1)
    })
  })

  describe('session lifecycle transitions', () => {
    it('sessionId is null until startFromRun, set during life, null after stop', async () => {
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 'lifecycle-sid',
        robot_file: 'tests.robot',
        breakpoint_line: 5,
        test_name: 'X',
      })
      const store = useDebugStore()
      expect(store.sessionId).toBeNull()
      expect(store.isActive).toBe(false)

      await store.startFromRun(1)
      expect(store.sessionId).toBe('lifecycle-sid')
      expect(store.isActive).toBe(true)

      await store.stop()
      expect(store.sessionId).toBeNull()
      expect(store.isActive).toBe(false)
    })

    it('terminated state correctly flips isActive false', async () => {
      vi.mocked(debugApi.startDebugSession).mockResolvedValueOnce({
        session_id: 'term-sid',
        robot_file: 'tests.robot',
        breakpoint_line: 5,
        test_name: null,
      })
      const store = useDebugStore()
      await store.startFromRun(1)
      expect(store.isActive).toBe(true)

      store.handleWsEvent({
        topic: 'debug:session:term-sid',
        kind: 'terminated',
        body: {},
      })
      // isActive = sessionId !== null && !terminated → false now.
      expect(store.isActive).toBe(false)
      // sessionId still set so the user can see the terminated badge.
      expect(store.sessionId).toBe('term-sid')
    })
  })
})
