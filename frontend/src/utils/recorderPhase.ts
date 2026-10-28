/**
 * Story RECORDER-VIS-1 — pure phase state machine of RecordingLiveView.vue.
 * `connecting` is the only transport-level state; everything else mirrors a
 * `LifecyclePhase` from the backend's `v2_command_queue.py`. The view owns the
 * refs and the real `setInterval`; this module owns the transitions.
 */
export type RecorderPhase =
  | 'connecting'
  | 'browser_starting'
  | 'browser_ready'
  | 'browser_restarting'
  | 'browser_crashed'
  | 'done'
  | 'error'

export interface RecorderPhaseState {
  phase: RecorderPhase
  /** `browser_ready` timestamp driving the uptime counter; null while not ready. */
  readyAtMs: number | null
  crashMessage: string | null
  /** Whether the uptime ticker should be running. */
  tickerActive: boolean
}

export function initialPhaseState(): RecorderPhaseState {
  return { phase: 'connecting', readyAtMs: null, crashMessage: null, tickerActive: false }
}

export function applyPhase(
  s: RecorderPhaseState,
  next: RecorderPhase,
  message: string | null = null,
): RecorderPhaseState {
  const out = { ...s, phase: next }
  if (next === 'browser_ready') {
    out.readyAtMs = Date.now()
    out.crashMessage = null
    out.tickerActive = true
  } else if (next === 'browser_restarting' || next === 'browser_starting') {
    // Clear so the uptime label hides during the transient; the ticker keeps
    // running until the next `browser_ready` resets the counter.
    out.readyAtMs = null
  } else if (next === 'browser_crashed') {
    out.crashMessage = message
    out.readyAtMs = null
    out.tickerActive = false
  }
  return out
}

/**
 * A command arriving before any lifecycle event is still proof the browser is
 * live (lifecycle events dropped, stale attach). Only `connecting` /
 * `browser_starting` are upgraded — a crashed or restarting browser is not.
 */
export function phaseAfterCommand(phase: RecorderPhase): RecorderPhase | null {
  return phase === 'connecting' || phase === 'browser_starting' ? 'browser_ready' : null
}
