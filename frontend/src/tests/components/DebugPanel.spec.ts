/**
 * DEBUG-6: DebugPanel button-wiring component tests.
 *
 * The 5 toolbar buttons (Continue / Step Over / Step Into / Step Out
 * / Stop) each have to:
 *
 *   1. Be ENABLED only when the session is paused & not terminated.
 *   2. Fire the correct ``debug.store`` action when clicked.
 *   3. Emit a ``closed`` event from Stop after disconnect resolves.
 *   4. Re-render correctly when WebSocket-driven state events arrive.
 *
 * The user-reported "I can't cleanly step / abort / continue via the
 * UI" turned out to be the missing ``robot/sync`` ack at the DAP
 * layer (DEBUG-5). With that fix the buttons now work, and these
 * tests pin the UI contract so a future refactor doesn't reopen the
 * silent-failure mode.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'

import DebugPanel from '@/components/debug/DebugPanel.vue'
import { useDebugStore } from '@/stores/debug.store'
import en from '@/i18n/locales/en'

vi.mock('@/api/debug.api', () => ({
  startDebugSession: vi.fn(),
  startDebugFromStep: vi.fn(),
  postControl: vi.fn(),
  getDebugState: vi.fn(),
  disconnectViaBeacon: vi.fn(),
  installPrerequisites: vi.fn(),
}))

import * as debugApi from '@/api/debug.api'

function createTestI18n() {
  return createI18n({
    legacy: false,
    locale: 'en',
    fallbackLocale: 'en',
    messages: { en },
  })
}

function mountPanel() {
  return mount(DebugPanel, {
    global: {
      plugins: [createTestI18n()],
      stubs: {
        BaseButton: {
          template:
            '<button :disabled="disabled" :data-variant="variant" :data-loading="loading" @click="$emit(\'click\', $event)"><slot /></button>',
          props: ['disabled', 'variant', 'loading', 'size'],
          emits: ['click'],
        },
      },
    },
  })
}

/** Set the store into "paused at line N" — the standard precondition
 *  for every control-button test. Mirrors what a `state` WebSocket
 *  event from the backend would do. */
function pauseStore(file = 'tests/login.robot', line = 5, keyword = 'Log') {
  const store = useDebugStore()
  store.sessionId = 'sess-1'
  store.robotFile = file
  store.breakpointLine = line
  store.testName = 'Login'
  store.state = {
    session_id: 'sess-1',
    paused: true,
    terminated: false,
    paused_at: { file, line, keyword },
    scopes: [],
    call_stack: [{ name: keyword, file, line }],
    output_lines: [],
  }
  return store
}

describe('DebugPanel — toolbar button wiring', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(debugApi.postControl).mockResolvedValue()
  })

  describe('button enablement', () => {
    it('all step/continue buttons are DISABLED when not paused', () => {
      // Default store state: no session, paused=false.
      const w = mountPanel()
      const buttons = w.findAll('button')
      // continue, stepOver, stepIn, stepOut, stop — Stop is always
      // enabled, the other four are gated on paused.
      expect(buttons.length).toBeGreaterThanOrEqual(5)
      const [cont, stepOver, stepIn, stepOut, stop] = buttons
      expect(cont.attributes('disabled')).toBeDefined()
      expect(stepOver.attributes('disabled')).toBeDefined()
      expect(stepIn.attributes('disabled')).toBeDefined()
      expect(stepOut.attributes('disabled')).toBeDefined()
      // Stop has NO disabled gate — the user must always be able to
      // abort, even from a half-broken state.
      expect(stop.attributes('disabled')).toBeUndefined()
    })

    it('all step/continue buttons are ENABLED when paused', async () => {
      pauseStore()
      const w = mountPanel()
      await w.vm.$nextTick()
      const buttons = w.findAll('button')
      const [cont, stepOver, stepIn, stepOut, _stop] = buttons
      expect(cont.attributes('disabled')).toBeUndefined()
      expect(stepOver.attributes('disabled')).toBeUndefined()
      expect(stepIn.attributes('disabled')).toBeUndefined()
      expect(stepOut.attributes('disabled')).toBeUndefined()
    })

    it('step/continue buttons re-DISABLE on terminated state', async () => {
      const store = pauseStore()
      const w = mountPanel()
      await w.vm.$nextTick()

      // Mimic a `terminated` WebSocket event arriving.
      store.handleWsEvent({
        topic: 'debug:session:sess-1',
        kind: 'terminated',
        body: {},
      })
      await w.vm.$nextTick()

      const buttons = w.findAll('button')
      const [cont, stepOver, stepIn, stepOut] = buttons
      expect(cont.attributes('disabled')).toBeDefined()
      expect(stepOver.attributes('disabled')).toBeDefined()
      expect(stepIn.attributes('disabled')).toBeDefined()
      expect(stepOut.attributes('disabled')).toBeDefined()
    })
  })

  describe('button click → store action → API', () => {
    it('Continue calls debug.control("continue") → postControl(sid, "continue")', async () => {
      pauseStore()
      const w = mountPanel()
      await w.vm.$nextTick()
      const [cont] = w.findAll('button')
      await cont.trigger('click')
      expect(debugApi.postControl).toHaveBeenCalledWith('sess-1', 'continue')
    })

    it('Step Over calls debug.control("next")', async () => {
      pauseStore()
      const w = mountPanel()
      await w.vm.$nextTick()
      const [, stepOver] = w.findAll('button')
      await stepOver.trigger('click')
      expect(debugApi.postControl).toHaveBeenCalledWith('sess-1', 'next')
    })

    it('Step Into calls debug.control("stepIn")', async () => {
      pauseStore()
      const w = mountPanel()
      await w.vm.$nextTick()
      const [, , stepIn] = w.findAll('button')
      await stepIn.trigger('click')
      expect(debugApi.postControl).toHaveBeenCalledWith('sess-1', 'stepIn')
    })

    it('Step Out calls debug.control("stepOut")', async () => {
      pauseStore()
      const w = mountPanel()
      await w.vm.$nextTick()
      const [, , , stepOut] = w.findAll('button')
      await stepOut.trigger('click')
      expect(debugApi.postControl).toHaveBeenCalledWith('sess-1', 'stepOut')
    })

    it('Stop calls debug.stop() → postControl(sid, "disconnect") and emits closed', async () => {
      pauseStore()
      const w = mountPanel()
      await w.vm.$nextTick()
      const [, , , , stop] = w.findAll('button')
      await stop.trigger('click')
      // Wait for the awaited stop() to resolve.
      await new Promise(resolve => setTimeout(resolve, 0))
      expect(debugApi.postControl).toHaveBeenCalledWith('sess-1', 'disconnect')
      // After stop, panel emits closed so the parent can remove it.
      expect(w.emitted('closed')).toBeTruthy()
    })

    it('Stop resets the store even when disconnect throws', async () => {
      pauseStore()
      vi.mocked(debugApi.postControl).mockRejectedValueOnce(
        new Error('connection refused'),
      )
      const w = mountPanel()
      await w.vm.$nextTick()
      const [, , , , stop] = w.findAll('button')
      await stop.trigger('click')
      await new Promise(resolve => setTimeout(resolve, 0))
      const store = useDebugStore()
      // The user clicked Stop — the panel MUST close even if the
      // backend is unreachable.
      expect(store.sessionId).toBeNull()
      expect(w.emitted('closed')).toBeTruthy()
    })
  })

  describe('error surface', () => {
    it('shows an error message when a control command fails', async () => {
      pauseStore()
      vi.mocked(debugApi.postControl).mockRejectedValueOnce(
        Object.assign(new Error('boom'), {
          response: { data: { detail: 'Pause failed: race condition' } },
        }),
      )
      const w = mountPanel()
      await w.vm.$nextTick()
      const [cont] = w.findAll('button')
      await cont.trigger('click')
      await new Promise(resolve => setTimeout(resolve, 0))
      expect(w.text()).toContain('Pause failed')
    })

    it('clears the error message on the next successful action', async () => {
      pauseStore()
      vi.mocked(debugApi.postControl).mockRejectedValueOnce(
        Object.assign(new Error('first fail'), {
          response: { data: { detail: 'first failure' } },
        }),
      )
      const w = mountPanel()
      await w.vm.$nextTick()
      const [cont] = w.findAll('button')
      await cont.trigger('click')
      await new Promise(resolve => setTimeout(resolve, 0))
      expect(w.text()).toContain('first failure')

      // Second click succeeds — error must clear.
      vi.mocked(debugApi.postControl).mockResolvedValueOnce()
      await cont.trigger('click')
      await new Promise(resolve => setTimeout(resolve, 0))
      expect(w.text()).not.toContain('first failure')
    })
  })

  describe('state-event reactivity (the user-reported "doesn\'t feel clean" path)', () => {
    it('updates paused_at line when a fresh state event arrives after step', async () => {
      const store = pauseStore('demo.robot', 5, 'Log')
      const w = mountPanel()
      await w.vm.$nextTick()
      expect(w.text()).toContain('demo.robot:5')

      // Simulate the backend's `state` WS event after stepping over.
      store.handleWsEvent({
        topic: 'debug:session:sess-1',
        kind: 'state',
        body: {
          session_id: 'sess-1',
          paused: true,
          terminated: false,
          paused_at: { file: 'demo.robot', line: 6, keyword: 'Log' },
          scopes: [],
          call_stack: [{ name: 'Log', file: 'demo.robot', line: 6 }],
          output_lines: [],
        },
      })
      await w.vm.$nextTick()
      expect(w.text()).toContain('demo.robot:6')
    })

    it('shows the Terminated badge when a terminated event arrives', async () => {
      const store = pauseStore()
      const w = mountPanel()
      await w.vm.$nextTick()
      expect(w.text()).toContain('Paused')

      store.handleWsEvent({
        topic: 'debug:session:sess-1',
        kind: 'terminated',
        body: {},
      })
      await w.vm.$nextTick()
      expect(w.text()).toContain('Terminated')
    })

    it('appends output lines from output events', async () => {
      const store = pauseStore()
      const w = mountPanel()
      await w.vm.$nextTick()

      store.handleWsEvent({
        topic: 'debug:session:sess-1',
        kind: 'output',
        body: { output: 'KEYWORD: Log    one\n' },
      })
      await w.vm.$nextTick()
      expect(store.outputLog.length).toBe(1)
      expect(store.outputLog[0]).toBe('KEYWORD: Log    one')
    })

    it('ignores events for OTHER session ids', async () => {
      const store = pauseStore()
      const w = mountPanel()
      await w.vm.$nextTick()
      expect(w.text()).toContain('Paused')

      store.handleWsEvent({
        topic: 'debug:session:OTHER-SESSION',
        kind: 'terminated',
        body: {},
      })
      await w.vm.$nextTick()
      // Still showing Paused — the other session's terminate didn't
      // affect us.
      expect(w.text()).toContain('Paused')
      expect(w.text()).not.toContain('Terminated')
    })
  })
})
