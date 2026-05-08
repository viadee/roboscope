import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as executionApi from '@/api/execution.api'
import type { ExecutionRun, Schedule, RunListResponse, RunStatus } from '@/types/domain.types'
import type { RunCreateRequest, ScheduleCreateRequest } from '@/types/api.types'

export const useExecutionStore = defineStore('execution', () => {
  const runs = ref<ExecutionRun[]>([])
  const totalRuns = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(5)
  const schedules = ref<Schedule[]>([])
  const loading = ref(false)
  const activeRun = ref<ExecutionRun | null>(null)

  const activeRuns = computed(() =>
    runs.value.filter((r) => r.status === 'pending' || r.status === 'running')
  )

  async function fetchRuns(
    params: { page?: number; repository_id?: number; status?: string; silent?: boolean } = {},
  ) {
    // `silent: true` skips the global loading flag — used by the
    // 5-second auto-poll on the Executions page so the spinner +
    // hidden table don't repeatedly layout-shift the user back to
    // scroll-top while they're reading the list. The first load and
    // any user-initiated fetch (filter, page change) keep the flag.
    const setLoading = !params.silent
    if (setLoading) loading.value = true
    try {
      const response = await executionApi.getRuns({
        page: params.page || currentPage.value,
        page_size: pageSize.value,
        repository_id: params.repository_id,
        status: params.status,
      })
      runs.value = response.items
      totalRuns.value = response.total
      currentPage.value = response.page
    } finally {
      if (setLoading) loading.value = false
    }
  }

  async function startRun(data: RunCreateRequest): Promise<ExecutionRun> {
    const run = await executionApi.createRun(data)
    runs.value.unshift(run)
    return run
  }

  async function cancelRun(id: number) {
    const updated = await executionApi.cancelRun(id)
    const idx = runs.value.findIndex((r) => r.id === id)
    if (idx >= 0) runs.value[idx] = updated
    return updated
  }

  async function cancelAllRuns() {
    const result = await executionApi.cancelAllRuns()
    await fetchRuns()
    return result
  }

  async function retryRun(id: number) {
    const newRun = await executionApi.retryRun(id)
    runs.value.unshift(newRun)
    return newRun
  }

  async function fetchRun(id: number) {
    activeRun.value = await executionApi.getRun(id)
    return activeRun.value
  }

  async function updateRunFromWs(runId: number, status: RunStatus) {
    const idx = runs.value.findIndex((r) => r.id === runId)
    if (idx >= 0) {
      // Immediate status update for responsive UI
      runs.value[idx] = { ...runs.value[idx], status }
    }
    // Reload full data for terminal statuses
    const terminal = ['passed', 'failed', 'error', 'cancelled', 'timeout']
    if (terminal.includes(status)) {
      try {
        const updated = await executionApi.getRun(runId)
        const i = runs.value.findIndex((r) => r.id === runId)
        if (i >= 0) runs.value[i] = updated
        if (activeRun.value?.id === runId) activeRun.value = updated
      } catch {
        // ignore — run may have been deleted
      }
    }
  }

  // Schedules
  async function fetchSchedules() {
    schedules.value = await executionApi.getSchedules()
  }

  async function addSchedule(data: ScheduleCreateRequest): Promise<Schedule> {
    const schedule = await executionApi.createSchedule(data)
    schedules.value.push(schedule)
    return schedule
  }

  async function removeSchedule(id: number) {
    await executionApi.deleteSchedule(id)
    schedules.value = schedules.value.filter((s) => s.id !== id)
  }

  async function updateSchedule(id: number, data: Partial<Schedule>) {
    const updated = await executionApi.updateSchedule(id, data)
    const idx = schedules.value.findIndex((s) => s.id === id)
    if (idx >= 0) schedules.value[idx] = updated
    return updated
  }

  async function toggleSchedule(id: number) {
    const updated = await executionApi.toggleSchedule(id)
    const idx = schedules.value.findIndex((s) => s.id === id)
    if (idx >= 0) schedules.value[idx] = updated
  }

  return {
    runs, totalRuns, currentPage, pageSize, schedules, loading, activeRun, activeRuns,
    fetchRuns, startRun, cancelRun, cancelAllRuns, retryRun, fetchRun, updateRunFromWs,
    fetchSchedules, addSchedule, updateSchedule, removeSchedule, toggleSchedule,
  }
})
