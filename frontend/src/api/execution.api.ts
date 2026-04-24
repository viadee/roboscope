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

export interface PendingBuildInfo {
  environment_id: number
  environment_name: string
  status: string | null
  log_tail: string
}

export interface PendingActivity {
  status: string
  queue_position: number | null
  ahead_count: number
  active_build: PendingBuildInfo | null
  effective_runner_type: string | null
}

export async function getRunPendingActivity(id: number): Promise<PendingActivity> {
  const response = await apiClient.get<PendingActivity>(`/runs/${id}/pending-activity`)
  return response.data
}

export interface SelectorCandidateSnippet {
  strategy: string
  value: string
  quality_score: number | null
}

export interface SelectorHealthHit {
  raw_locator: string
  candidates: SelectorCandidateSnippet[]
}

export interface SelectorHealth {
  has_sidecar: boolean
  sidecar_path: string | null
  failed_locators: SelectorHealthHit[]
}

export async function getRunSelectorHealth(id: number): Promise<SelectorHealth> {
  const response = await apiClient.get<SelectorHealth>(`/runs/${id}/selector-health`)
  return response.data
}

// Story SH-2 — runtime heal report.

export type HealOutcome = 'confirmed' | 'suspect' | 'skipped' | 'unknown'

export interface HealAuditEntry {
  timestamp: string
  test_name: string
  keyword: string
  original_selector: string
  healed_selector: string
  confidence: number
  source: string
  outcome: HealOutcome
}

export interface HealReport {
  total_heals: number
  confirmed: number
  suspect: number
  entries: HealAuditEntry[]
}

export async function getRunHealReport(id: number): Promise<HealReport> {
  const response = await apiClient.get<HealReport>(`/runs/${id}/heal-report`)
  return response.data
}

export interface HealPatchApplyResponse {
  file_path: string
  line_number: number
  applied: boolean
  reason?: string | null
}

export async function applyHealPatch(
  runId: number,
  healIndex: number,
): Promise<HealPatchApplyResponse> {
  const response = await apiClient.post<HealPatchApplyResponse>(
    `/runs/${runId}/heal-report/${healIndex}/apply`,
  )
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
