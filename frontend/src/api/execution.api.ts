import apiClient from './client'
import type { RunCreateRequest, ScheduleCreateRequest } from '@/types/api.types'
import type { ExecutionRun, RunListResponse, Schedule } from '@/types/domain.types'

export async function createRun(data: RunCreateRequest): Promise<ExecutionRun> {
  const response = await apiClient.post<ExecutionRun>('/runs', data)
  return response.data
}

export async function getRuns(params: {
  page?: number
  page_size?: number
  repository_id?: number
  status?: string
} = {}): Promise<RunListResponse> {
  const response = await apiClient.get<RunListResponse>('/runs', { params })
  return response.data
}

export async function getRun(id: number): Promise<ExecutionRun> {
  const response = await apiClient.get<ExecutionRun>(`/runs/${id}`)
  return response.data
}

export async function cancelRun(id: number): Promise<ExecutionRun> {
  const response = await apiClient.post<ExecutionRun>(`/runs/${id}/cancel`)
  return response.data
}

export async function retryRun(id: number): Promise<ExecutionRun> {
  const response = await apiClient.post<ExecutionRun>(`/runs/${id}/retry`)
  return response.data
}

export async function getRunOutput(id: number, stream: 'stdout' | 'stderr' = 'stdout'): Promise<string> {
  const response = await apiClient.get(`/runs/${id}/output`, { params: { stream } })
  return response.data
}

export async function getRunReport(id: number): Promise<{ report_id: number | null }> {
  const response = await apiClient.get(`/runs/${id}/report`)
  return response.data
}

// Schedules

export async function getSchedules(): Promise<Schedule[]> {
  const response = await apiClient.get<Schedule[]>('/schedules')
  return response.data
}

export async function createSchedule(data: ScheduleCreateRequest): Promise<Schedule> {
  const response = await apiClient.post<Schedule>('/schedules', data)
  return response.data
}

export async function updateSchedule(id: number, data: Partial<Schedule>): Promise<Schedule> {
  const response = await apiClient.patch<Schedule>(`/schedules/${id}`, data)
  return response.data
}

export async function deleteSchedule(id: number): Promise<void> {
  await apiClient.delete(`/schedules/${id}`)
}

export async function cancelAllRuns(): Promise<{ cancelled: number }> {
  const response = await apiClient.post<{ cancelled: number }>('/runs/cancel-all')
  return response.data
}

export async function toggleSchedule(id: number): Promise<Schedule> {
  const response = await apiClient.post<Schedule>(`/schedules/${id}/toggle`)
  return response.data
}
