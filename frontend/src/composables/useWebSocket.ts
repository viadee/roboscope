import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useExecutionStore } from '@/stores/execution.store'
import { useUiStore } from '@/stores/ui.store'

export function useWebSocket() {
  const connected = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  // Capture composables during setup (must not be called inside callbacks)
  const { t } = useI18n()
  const execution = useExecutionStore()
  const ui = useUiStore()

  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    ws = new WebSocket(`${protocol}//${host}/ws/notifications`)

    ws.onopen = () => {
      connected.value = true
      startPing()
    }

    ws.onmessage = (event) => {
      if (typeof event.data !== 'string' || event.data === 'pong') return
      let data: any
      try {
        data = JSON.parse(event.data)
      } catch {
        return // ignore non-JSON messages
      }
      handleMessage(data)
    }

    ws.onclose = () => {
      connected.value = false
      reconnectTimer = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (pingTimer) clearInterval(pingTimer)
    ws?.close()
    ws = null
    connected.value = false
  }

  let pingTimer: ReturnType<typeof setInterval> | null = null

  function startPing() {
    if (pingTimer) clearInterval(pingTimer)
    pingTimer = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 30000)
  }

  function handleMessage(data: any) {
    switch (data.type) {
      case 'run_status_changed':
        execution.updateRunFromWs(data.run_id, data.status)
        if (data.status === 'passed') {
          ui.success(t('websocket.runPassed'), t('websocket.runPassedMsg', { id: data.run_id }))
        } else if (data.status === 'failed') {
          ui.warning(t('websocket.runFailed'), t('websocket.runFailedMsg', { id: data.run_id }))
        } else if (data.status === 'error') {
          ui.error(t('websocket.runError'), t('websocket.runErrorMsg', { id: data.run_id }))
        }
        break

      case 'notification':
        ui.addToast(data.title, data.message, data.level || 'info')
        break
    }
  }

  return { connected, connect, disconnect }
}

export function useRunWebSocket(runId: number) {
  const outputLines = ref<string[]>([])
  const connected = ref(false)
  let ws: WebSocket | null = null

  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    ws = new WebSocket(`${protocol}//${host}/ws/runs/${runId}`)

    ws.onopen = () => {
      connected.value = true
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'run_output') {
          outputLines.value.push(data.line)
        }
      } catch {
        // ignore
      }
    }

    ws.onclose = () => {
      connected.value = false
    }
  }

  function disconnect() {
    ws?.close()
    ws = null
    connected.value = false
  }

  return { outputLines, connected, connect, disconnect }
}
