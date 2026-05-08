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
})
