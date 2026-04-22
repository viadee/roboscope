import apiClient from './client'
import type { RecordingTransport } from '@/types/recorder.types'

export interface V2SessionResponse {
  session_id: number
  transport: RecordingTransport
  status: string
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
