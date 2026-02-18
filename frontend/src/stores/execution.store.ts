import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as executionApi from '@/api/execution.api'
import type { ExecutionRun, Schedule, RunListResponse } from '@/types/domain.types'
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

  async function fetchRuns(params: { page?: number; repository_id?: number; status?: string } = {}) {
    loading.value = true
    try {
      const response = await executionApi.getRuns({
        page: params.page || currentPage.value,
        page_size: pageSize.value,
        ...params,
      })
      runs.value = response.items
      totalRuns.value = response.total
      currentPage.value = response.page
    } finally {
      loading.value = false
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

  async function updateRunFromWs(runId: number, status: string) {
    const idx = runs.value.findIndex((r) => r.id === runId)
    if (idx >= 0) {
      // Immediate status update for responsive UI
      runs.value[idx] = { ...runs.value[idx], status: status as any }
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

  async function toggleSchedule(id: number) {
    const updated = await executionApi.toggleSchedule(id)
    const idx = schedules.value.findIndex((s) => s.id === id)
    if (idx >= 0) schedules.value[idx] = updated
  }

  return {
    runs, totalRuns, currentPage, pageSize, schedules, loading, activeRun, activeRuns,
    fetchRuns, startRun, cancelRun, cancelAllRuns, retryRun, fetchRun, updateRunFromWs,
    fetchSchedules, addSchedule, removeSchedule, toggleSchedule,
  }
})
