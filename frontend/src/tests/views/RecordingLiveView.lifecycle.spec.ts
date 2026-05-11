/**
 * Story RECORDER-VIS-1 — phase state machine of RecordingLiveView.vue.
 *
 * The setup script's `_transitionTo`, `handleLifecycle` and
 * `handleCommand` aren't directly importable (Vue SFC `<script
 * setup>`), so we mirror their pure-data behaviour here and exercise
 * the transitions across every entry point in the contract.
 *
 * Catches regressions in:
 *   - the bare `connecting` → `browser_starting` fallback when SSE
 *     opens before the backend emits a lifecycle event,
 *   - the `command`-first fallback that flips to `browser_ready` so a
 *     queue refilling mid-restart doesn't look like a hang,
 *   - the `browser_restarting` / `browser_starting` paths clearing
 *     `readyAtMs` so the uptime counter restarts from zero,
 *   - the `browser_crashed` path stopping the uptime ticker.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

type RecorderPhase =
  | 'connecting'
  | 'browser_starting'
  | 'browser_ready'
  | 'browser_restarting'
  | 'browser_crashed'
  | 'done'
  | 'error'

interface LifecyclePayload {
  phase: 'browser_starting' | 'browser_ready' | 'browser_crashed' | 'browser_restarting'
  ts: number
  message?: string | null
}

interface StateMachine {
  phase: RecorderPhase
  readyAtMs: number | null
  crashMessage: string | null
  uptimeIntervalActive: boolean
  /** Drives `handleCommand` — bumped on every command. */
  commandCount: number
}

function createMachine(): StateMachine {
  return {
    phase: 'connecting',
    readyAtMs: null,
    crashMessage: null,
    uptimeIntervalActive: false,
    commandCount: 0,
  }
}

// Mirror of RecordingLiveView.vue::_transitionTo. Tracks the same
// invariants — only with `uptimeIntervalActive` as a boolean instead
// of a real `setInterval` handle, because we don't need real timer
// behaviour in unit tests.
function transitionTo(
  m: StateMachine,
  next: RecorderPhase,
  message: string | null = null,
): void {
  m.phase = next
  if (next === 'browser_ready') {
    m.readyAtMs = Date.now()
    m.crashMessage = null
    if (!m.uptimeIntervalActive) m.uptimeIntervalActive = true
  } else if (next === 'browser_restarting' || next === 'browser_starting') {
    m.readyAtMs = null
  } else if (next === 'browser_crashed') {
    m.crashMessage = message
    m.readyAtMs = null
    if (m.uptimeIntervalActive) m.uptimeIntervalActive = false
  }
}

function handleLifecycle(m: StateMachine, payload: LifecyclePayload): void {
  transitionTo(m, payload.phase, payload.message ?? null)
}

function handleCommand(m: StateMachine): void {
  m.commandCount += 1
  if (m.phase === 'connecting' || m.phase === 'browser_starting') {
    transitionTo(m, 'browser_ready')
  }
}

describe('RecordingLiveView phase state machine — RECORDER-VIS-1', () => {
  let m: StateMachine

  beforeEach(() => {
    m = createMachine()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-11T10:00:00Z'))
  })

  describe('lifecycle event routing', () => {
    it('starts in connecting with no ready timestamp', () => {
      expect(m.phase).toBe('connecting')
      expect(m.readyAtMs).toBeNull()
      expect(m.uptimeIntervalActive).toBe(false)
    })

    it('connecting → browser_starting on the backend signal', () => {
      handleLifecycle(m, { phase: 'browser_starting', ts: Date.now() / 1000 })
      expect(m.phase).toBe('browser_starting')
      expect(m.readyAtMs).toBeNull()
    })

    it('browser_starting → browser_ready captures ts and starts ticker', () => {
      handleLifecycle(m, { phase: 'browser_starting', ts: 0 })
      handleLifecycle(m, { phase: 'browser_ready', ts: 0 })
      expect(m.phase).toBe('browser_ready')
      expect(m.readyAtMs).not.toBeNull()
      expect(m.uptimeIntervalActive).toBe(true)
    })

    it('browser_crashed surfaces the error message and stops the ticker', () => {
      handleLifecycle(m, { phase: 'browser_ready', ts: 0 })
      expect(m.uptimeIntervalActive).toBe(true)
      handleLifecycle(m, {
        phase: 'browser_crashed',
        ts: 0,
        message: 'X server not found',
      })
      expect(m.phase).toBe('browser_crashed')
      expect(m.crashMessage).toBe('X server not found')
      expect(m.readyAtMs).toBeNull()
      expect(m.uptimeIntervalActive).toBe(false)
    })

    it('browser_crashed without a message stores null', () => {
      handleLifecycle(m, { phase: 'browser_crashed', ts: 0 })
      expect(m.crashMessage).toBeNull()
    })

    it('browser_restarting clears readyAtMs but keeps ticker until ready arrives again', () => {
      handleLifecycle(m, { phase: 'browser_ready', ts: 0 })
      expect(m.readyAtMs).not.toBeNull()
      handleLifecycle(m, { phase: 'browser_restarting', ts: 0 })
      expect(m.phase).toBe('browser_restarting')
      // readyAtMs is cleared so the uptime label hides during the
      // restart transient.
      expect(m.readyAtMs).toBeNull()
    })

    it('full restart cycle restores ready state with a fresh timestamp', () => {
      handleLifecycle(m, { phase: 'browser_ready', ts: 0 })
      const firstReady = m.readyAtMs!
      vi.advanceTimersByTime(2000)
      handleLifecycle(m, { phase: 'browser_restarting', ts: 0 })
      vi.advanceTimersByTime(1000)
      handleLifecycle(m, { phase: 'browser_starting', ts: 0 })
      vi.advanceTimersByTime(500)
      handleLifecycle(m, { phase: 'browser_ready', ts: 0 })
      // Second ready arrived strictly after the first.
      expect(m.readyAtMs).toBeGreaterThan(firstReady)
      expect(m.phase).toBe('browser_ready')
      expect(m.crashMessage).toBeNull()
    })

    it('crash after ready clears the existing message slot', () => {
      handleLifecycle(m, {
        phase: 'browser_crashed', ts: 0, message: 'first crash',
      })
      expect(m.crashMessage).toBe('first crash')
      handleLifecycle(m, { phase: 'browser_ready', ts: 0 })
      expect(m.crashMessage).toBeNull()
    })
  })

  describe('command-first fallback', () => {
    it('flips connecting → browser_ready when commands arrive before any lifecycle event', () => {
      // Backend that crashed lifecycle emission, or a stale-attach
      // case where the queue already has commands when the consumer
      // subscribes.
      handleCommand(m)
      expect(m.phase).toBe('browser_ready')
      expect(m.commandCount).toBe(1)
    })

    it('flips browser_starting → browser_ready when commands arrive early', () => {
      handleLifecycle(m, { phase: 'browser_starting', ts: 0 })
      handleCommand(m)
      expect(m.phase).toBe('browser_ready')
    })

    it('does NOT regress an already-ready phase', () => {
      handleLifecycle(m, { phase: 'browser_ready', ts: 0 })
      handleCommand(m)
      expect(m.phase).toBe('browser_ready')
    })

    it('does NOT promote crashed → ready (a stray late command is harmless)', () => {
      handleLifecycle(m, {
        phase: 'browser_crashed', ts: 0, message: 'gone',
      })
      handleCommand(m)
      // Phase stays — only `connecting` / `browser_starting` are
      // upgraded by a command. A crashed browser by definition can't
      // send commands; if one slips through (race between the
      // disconnect listener and a buffered binding callback) we
      // record it but don't lie about the phase.
      expect(m.phase).toBe('browser_crashed')
      expect(m.commandCount).toBe(1)
    })

    it('does NOT regress restarting → ready on command (restart-in-flight)', () => {
      handleLifecycle(m, { phase: 'browser_restarting', ts: 0 })
      handleCommand(m)
      expect(m.phase).toBe('browser_restarting')
    })
  })

  describe('uptime label computation', () => {
    function formatUptime(readyAtMs: number | null, now: number): string | null {
      if (readyAtMs === null) return null
      const elapsed = Math.max(0, Math.floor((now - readyAtMs) / 1000))
      const mm = String(Math.floor(elapsed / 60)).padStart(2, '0')
      const ss = String(elapsed % 60).padStart(2, '0')
      return `${mm}:${ss}`
    }

    it('returns null before ready', () => {
      expect(formatUptime(null, Date.now())).toBeNull()
    })

    it('renders mm:ss padded for small uptime', () => {
      const ready = Date.now()
      expect(formatUptime(ready, ready + 5000)).toBe('00:05')
    })

    it('renders multi-minute uptime', () => {
      const ready = Date.now()
      expect(formatUptime(ready, ready + (65 * 1000))).toBe('01:05')
    })

    it('clamps negative deltas to 00:00 (clock skew safety)', () => {
      const ready = Date.now()
      expect(formatUptime(ready, ready - 1000)).toBe('00:00')
    })
  })
})
