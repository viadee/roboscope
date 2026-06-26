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
  transport?: RecordingTransport,
): Promise<StartBrowserResponse> {
  // `transport` MUST be threaded through for non-web sessions: the backend
  // `/start-browser` endpoint defaults to `web_playwright`, so omitting it on a
  // `desktop_windows` session would dispatch the WEB recorder instead of the
  // Windows desktop capture task (Story D-5 fix).
  const response = await apiClient.post<StartBrowserResponse>(
    `/recordings/sessions/${sessionId}/start-browser`,
    { target_url: targetUrl ?? null, transport: transport ?? null },
  )
  return response.data
}

/**
 * Story RECORDER-VIS-1 — restart the Chromium process for an active
 * session without losing captured commands. Backend kills the current
 * browser, spawns a fresh one, and emits `browser_restarting` →
 * `browser_starting` → `browser_ready` lifecycle events on the SSE
 * stream. The session row stays in RECORDING; the queue is preserved.
 */
export async function restartV2Browser(
  sessionId: number,
): Promise<StartBrowserResponse> {
  const response = await apiClient.post<StartBrowserResponse>(
    `/recordings/sessions/${sessionId}/restart-browser`,
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


export interface ResetStuckSessionsResponse {
  aborted: number
}

/**
 * RECORDER-RESET-1 — panic-button cleanup of stuck v2 recording
 * sessions for the current user. Idempotent: zero stuck rows ⇒
 * `{aborted: 0}`.
 */
export async function resetStuckSessions(): Promise<ResetStuckSessionsResponse> {
  const response = await apiClient.post<ResetStuckSessionsResponse>(
    '/recordings/sessions/reset',
  )
  return response.data
}
