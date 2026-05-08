/**
 * Pinia store for the interactive Robot Framework debug session
 * (Story DEBUG-2). One store, one active session — DEBUG-2's "one
 * concurrent session per (user, run)" rule maps cleanly to a single
 * front-end slot. If the user opens a second debug elsewhere the
 * existing one is replaced.
 *
 * The store is fed by:
 *   - REST kicks (`startFromRun`, control posts, `refreshState`)
 *   - WebSocket `debug_event` messages dispatched by `useWebSocket.ts`
 *     (state events overwrite the cached state; output events append)
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as debugApi from '@/api/debug.api'
import type {
  DebugSessionState,
  DebugScope,
  DebugCallStackFrame,
  DebugPausedAt,
  DebugSessionStartResponse,
  StartFromStepRequest,
} from '@/api/debug.api'
import { extractErrorStatus } from '@/utils/errors'

const blankPausedAt: DebugPausedAt = { file: null, line: null, keyword: null }

const blankState: DebugSessionState = {
  session_id: '',
  paused: false,
  terminated: false,
  paused_at: blankPausedAt,
  scopes: [],
  call_stack: [],
  output_lines: [],
}

export const useDebugStore = defineStore('debug', () => {
  const sessionId = ref<string | null>(null)
  const robotFile = ref<string | null>(null)
  const breakpointLine = ref<number | null>(null)
  const testName = ref<string | null>(null)
  const state = ref<DebugSessionState>({ ...blankState })
  const outputLog = ref<string[]>([])
  const loading = ref(false)
  const lastError = ref<string | null>(null)

  const isActive = computed(() => sessionId.value !== null && !state.value.terminated)
  const paused = computed(() => state.value.paused)
  const pausedAt = computed<DebugPausedAt>(() => state.value.paused_at)
  const scopes = computed<DebugScope[]>(() => state.value.scopes)
  const callStack = computed<DebugCallStackFrame[]>(() => state.value.call_stack)

  async function startFromRun(runId: number): Promise<DebugSessionStartResponse> {
    loading.value = true
    lastError.value = null
    try {
      const resp = await debugApi.startDebugSession({ run_id: runId })
      _adoptStart(resp)
      return resp
    } finally {
      loading.value = false
    }
  }

  /**
   * DEBUG-3 — start a session from a Flow Editor step click.
   *
   * Returns the response *and* a flag indicating whether the backend
   * dedup-409'd into an existing session. AC6 silent-resume: the
   * caller can show the panel without a "started new session" toast
   * when `resumed === true`.
   */
  async function startFromStep(
    payload: StartFromStepRequest,
  ): Promise<{ resp: DebugSessionStartResponse; resumed: boolean }> {
    loading.value = true
    lastError.value = null
    try {
      try {
        const resp = await debugApi.startDebugFromStep(payload)
        _adoptStart(resp)
        return { resp, resumed: false }
      } catch (e: unknown) {
        // 409 is silent-resume — the response payload carries the
        // existing session metadata under detail.
        if (extractErrorStatus(e) === 409) {
          const detail = (e as { response?: { data?: { detail?: unknown } } })
            ?.response?.data?.detail
          if (detail && typeof detail === 'object') {
            const d = detail as Record<string, unknown>
            const resp: DebugSessionStartResponse = {
              session_id: String(d.session_id ?? ''),
              robot_file: String(d.robot_file ?? payload.file),
              breakpoint_line: Number(d.breakpoint_line ?? payload.line),
              test_name: (d.test_name as string | null | undefined) ?? null,
            }
            if (resp.session_id) {
              _adoptStart(resp)
              return { resp, resumed: true }
            }
          }
        }
        throw e
      }
    } finally {
      loading.value = false
    }
  }

  /** Compare the active session against a new step click. Returns
   *  `'idle'` when no session is running, `'same'` when the click
   *  resumes (file + line both match), `'different'` when a confirm-
   *  modal is needed before swapping. */
  function classifyStepClick(
    file: string,
    line: number,
  ): 'idle' | 'same' | 'different' {
    if (!sessionId.value || state.value.terminated) return 'idle'
    if (robotFile.value === file && breakpointLine.value === line) return 'same'
    return 'different'
  }

  function _adoptStart(resp: DebugSessionStartResponse): void {
    sessionId.value = resp.session_id
    robotFile.value = resp.robot_file
    breakpointLine.value = resp.breakpoint_line
    testName.value = resp.test_name
    state.value = { ...blankState, session_id: resp.session_id }
    outputLog.value = []
  }

  async function refreshState(): Promise<void> {
    if (!sessionId.value) return
    state.value = await debugApi.getDebugState(sessionId.value)
  }

  async function control(cmd: 'continue' | 'next' | 'stepIn' | 'stepOut'): Promise<void> {
    if (!sessionId.value) return
    await debugApi.postControl(sessionId.value, cmd)
  }

  async function stop(): Promise<void> {
    if (!sessionId.value) return
    const sid = sessionId.value
    try {
      await debugApi.postControl(sid, 'disconnect')
    } finally {
      reset()
    }
  }

  function reset(): void {
    sessionId.value = null
    robotFile.value = null
    breakpointLine.value = null
    testName.value = null
    state.value = { ...blankState }
    outputLog.value = []
    lastError.value = null
  }

  /**
   * Handler for incoming WebSocket `debug_event` messages. Routed
   * from `useWebSocket.ts` so we keep all WS plumbing in one place.
   */
  function handleWsEvent(msg: { topic: string; kind: string; body: Record<string, unknown> }): void {
    if (!sessionId.value) return
    if (msg.topic !== `debug:session:${sessionId.value}`) return
    switch (msg.kind) {
      case 'state':
        // The body is a full DebugSessionState snapshot.
        state.value = msg.body as unknown as DebugSessionState
        break
      case 'output': {
        const line = String(msg.body.output ?? '').replace(/\n+$/, '')
        if (line) outputLog.value.push(line)
        // Cap the live log so the panel stays responsive on long
        // runs. Trigger at 300 so we never carry more than that.
        if (outputLog.value.length > 300) {
          outputLog.value = outputLog.value.slice(-300)
        }
        break
      }
      case 'terminated':
        state.value = { ...state.value, terminated: true, paused: false }
        break
      // 'stopped' is informational — the manager always follows up
      // with a 'state' event carrying the fresh snapshot, so we
      // don't need to act on the bare 'stopped' here.
    }
  }

  return {
    sessionId,
    robotFile,
    breakpointLine,
    testName,
    state,
    outputLog,
    loading,
    lastError,
    isActive,
    paused,
    pausedAt,
    scopes,
    callStack,
    startFromRun,
    startFromStep,
    classifyStepClick,
    refreshState,
    control,
    stop,
    reset,
    handleWsEvent,
  }
})
