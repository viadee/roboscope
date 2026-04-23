import apiClient from './client'
import type { RecordingTransport } from '@/types/recorder.types'

export interface V2SessionResponse {
  session_id: number
  transport: RecordingTransport
  status: string
}

export interface V2Capabilities {
  web_playwright_viable: boolean
  desktop_windows_viable: boolean
  desktop_macos_viable: boolean
}

export async function getV2Capabilities(): Promise<V2Capabilities> {
  const response = await apiClient.get<V2Capabilities>('/recordings/sessions/capabilities')
  return response.data
}

export async function createV2Session(
  transport: RecordingTransport,
  repoId: number,
): Promise<V2SessionResponse> {
  const response = await apiClient.post<V2SessionResponse>('/recordings/sessions', {
    transport,
    repo_id: repoId,
  })
  return response.data
}

export async function abortV2Session(sessionId: number): Promise<void> {
  await apiClient.delete(`/recordings/sessions/${sessionId}`)
}

export interface StartBrowserResponse {
  session_id: number
  task_id: string | null
}

export async function startV2Browser(
  sessionId: number,
  targetUrl?: string,
): Promise<StartBrowserResponse> {
  const response = await apiClient.post<StartBrowserResponse>(
    `/recordings/sessions/${sessionId}/start-browser`,
    { target_url: targetUrl ?? null },
  )
  return response.data
}

export interface SaveResponse {
  saved_path: string
  bytes_written: number
}

export async function saveV2Flow(
  flow: unknown,
  repoId: number,
  path: string,
): Promise<SaveResponse> {
  const response = await apiClient.post<SaveResponse>('/recordings/save', {
    flow,
    repo_id: repoId,
    path,
  })
  return response.data
}
