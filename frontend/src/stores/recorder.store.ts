import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { RecordingSession, RecordingStatus, RecordingEvent } from '@/types/domain.types'
import type { RecordingCreateRequest } from '@/types/api.types'
import * as recorderApi from '@/api/recorder.api'

export const useRecorderStore = defineStore('recorder', () => {
  // State
  const activeSession = ref<RecordingSession | null>(null)
  const liveEvents = ref<RecordingEvent[]>([])
  const generatedRobot = ref<string | null>(null)
  const loading = ref(false)
  const panelOpen = ref(false)

  // Computed
  const isRecording = computed(() => activeSession.value?.status === 'recording')
  const isProcessing = computed(() => activeSession.value?.status === 'processing')
  const isCompleted = computed(() => activeSession.value?.status === 'completed')
  const hasSession = computed(() => activeSession.value !== null)

  // Actions
  async function createSession(data: RecordingCreateRequest) {
    loading.value = true
    try {
      activeSession.value = await recorderApi.createRecording(data)
      liveEvents.value = []
      generatedRobot.value = null
      panelOpen.value = true
    } finally {
      loading.value = false
    }
  }

  async function startSession() {
    if (!activeSession.value) return
    loading.value = true
    try {
      activeSession.value = await recorderApi.startRecording(activeSession.value.id)
    } finally {
      loading.value = false
    }
  }

  async function startBrowserSession(data: RecordingCreateRequest) {
    loading.value = true
    try {
      activeSession.value = await recorderApi.createRecording(data)
      liveEvents.value = []
      generatedRobot.value = null
      panelOpen.value = true
      // Launch headed Playwright browser on the backend
      activeSession.value = await recorderApi.startBrowserRecording(activeSession.value.id)
    } finally {
      loading.value = false
    }
  }

  async function appendEvent(event: RecordingEvent) {
    if (!activeSession.value) return
    liveEvents.value.push(event)
    try {
      activeSession.value = await recorderApi.appendRecordingEvent(
        activeSession.value.id,
        event,
      )
    } catch {
      // Non-critical: event already in local list
    }
  }

  async function stopSession(generateRobot = true) {
    if (!activeSession.value) return
    loading.value = true
    try {
      activeSession.value = await recorderApi.stopRecording(
        activeSession.value.id,
        { generate_robot: generateRobot },
      )
    } finally {
      loading.value = false
    }
  }

  async function cancelSession() {
    if (!activeSession.value) return
    loading.value = true
    try {
      activeSession.value = await recorderApi.cancelRecording(activeSession.value.id)
    } finally {
      loading.value = false
    }
  }

  async function fetchGeneratedRobot() {
    if (!activeSession.value) return
    try {
      generatedRobot.value = await recorderApi.getRecordingRobot(activeSession.value.id)
    } catch {
      generatedRobot.value = null
    }
  }

  async function refreshSession() {
    if (!activeSession.value) return
    try {
      activeSession.value = await recorderApi.getRecording(activeSession.value.id)
    } catch {
      // Session may have been deleted
    }
  }

  function closePanel() {
    panelOpen.value = false
  }

  function reset() {
    activeSession.value = null
    liveEvents.value = []
    generatedRobot.value = null
    loading.value = false
    panelOpen.value = false
  }

  // WebSocket handlers
  function handleRecordingStatusChanged(recordingId: number, status: RecordingStatus) {
    if (activeSession.value?.id === recordingId) {
      activeSession.value = { ...activeSession.value, status }
      if (status === 'completed') {
        fetchGeneratedRobot()
      }
    }
  }

  function handleRecordingEvent(recordingId: number, event: RecordingEvent) {
    if (activeSession.value?.id === recordingId) {
      liveEvents.value.push(event)
    }
  }

  return {
    // State
    activeSession,
    liveEvents,
    generatedRobot,
    loading,
    panelOpen,
    // Computed
    isRecording,
    isProcessing,
    isCompleted,
    hasSession,
    // Actions
    createSession,
    startSession,
    startBrowserSession,
    appendEvent,
    stopSession,
    cancelSession,
    fetchGeneratedRobot,
    refreshSession,
    closePanel,
    reset,
    // WebSocket
    handleRecordingStatusChanged,
    handleRecordingEvent,
  }
})
