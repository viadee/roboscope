import apiClient from './client'
import type { RecordingCreateRequest } from '@/types/api.types'
import type { RecordingSession, RecordingListResponse } from '@/types/domain.types'

export async function createRecording(data: RecordingCreateRequest): Promise<RecordingSession> {
  const response = await apiClient.post<RecordingSession>('/recordings', data)
  return response.data
}

export async function getRecordings(params: {
  page?: number
  page_size?: number
  repository_id?: number
  status?: string
} = {}): Promise<RecordingListResponse> {
  const response = await apiClient.get<RecordingListResponse>('/recordings', { params })
  return response.data
}

export async function getRecording(id: number): Promise<RecordingSession> {
  const response = await apiClient.get<RecordingSession>(`/recordings/${id}`)
  return response.data
}

export async function deleteRecording(id: number): Promise<void> {
  await apiClient.delete(`/recordings/${id}`)
}

export async function startRecording(id: number): Promise<RecordingSession> {
  const response = await apiClient.post<RecordingSession>(`/recordings/${id}/start`)
  return response.data
}

export async function startBrowserRecording(id: number): Promise<RecordingSession> {
  const response = await apiClient.post<RecordingSession>(`/recordings/${id}/start-browser`)
  return response.data
}

export async function appendRecordingEvent(id: number, event: {
  event_type: string
  selector?: string
  value?: string
  url?: string
  tag?: string
  timestamp?: number
}): Promise<RecordingSession> {
  const response = await apiClient.post<RecordingSession>(`/recordings/${id}/event`, event)
  return response.data
}

export async function stopRecording(id: number, options: {
  generate_robot?: boolean
  save_to_file?: boolean
} = {}): Promise<RecordingSession> {
  const response = await apiClient.post<RecordingSession>(`/recordings/${id}/stop`, options)
  return response.data
}

export async function cancelRecording(id: number): Promise<RecordingSession> {
  const response = await apiClient.post<RecordingSession>(`/recordings/${id}/cancel`)
  return response.data
}

export async function getRecordingRobot(id: number): Promise<string> {
  const response = await apiClient.get(`/recordings/${id}/robot`)
  return response.data
}

export async function getRecordingEvents(id: number): Promise<{
  recording_id: number
  events: any[]
  count: number
}> {
  const response = await apiClient.get(`/recordings/${id}/events`)
  return response.data
}
