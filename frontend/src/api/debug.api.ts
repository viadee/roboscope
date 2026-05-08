import apiClient from './client'

export interface StartDebugRequest {
  run_id: number
}

export interface DebugSessionStartResponse {
  session_id: string
  robot_file: string
  breakpoint_line: number
  test_name: string | null
}

export interface DebugScopeVariable {
  name: string
  value: string
  type: string
}

export interface DebugScope {
  name: string
  variables: DebugScopeVariable[]
}

export interface DebugCallStackFrame {
  name: string
  file: string | null
  line: number | null
}

export interface DebugPausedAt {
  file: string | null
  line: number | null
  keyword: string | null
}

export interface DebugSessionState {
  session_id: string
  paused: boolean
  terminated: boolean
  paused_at: DebugPausedAt
  scopes: DebugScope[]
  call_stack: DebugCallStackFrame[]
  output_lines: string[]
}

export type DebugControl = 'continue' | 'next' | 'stepIn' | 'stepOut' | 'disconnect'

export async function startDebugSession(
  payload: StartDebugRequest,
): Promise<DebugSessionStartResponse> {
  const response = await apiClient.post<DebugSessionStartResponse>(
    '/debug/sessions',
    payload,
  )
  return response.data
}

export async function postControl(sessionId: string, command: DebugControl): Promise<void> {
  await apiClient.post(`/debug/sessions/${sessionId}/${command}`)
}

export async function getDebugState(sessionId: string): Promise<DebugSessionState> {
  const response = await apiClient.get<DebugSessionState>(
    `/debug/sessions/${sessionId}/state`,
  )
  return response.data
}

/** Tab-close fire-and-forget disconnect. Uses the navigator.sendBeacon
 *  path so an unloaded tab doesn't keep the paused subprocess alive. */
export function disconnectViaBeacon(sessionId: string, token: string): void {
  if (typeof navigator === 'undefined' || !navigator.sendBeacon) return
  // sendBeacon doesn't support custom headers; we encode the JWT into
  // the URL path. The 401 interceptor only fires for axios; sendBeacon
  // failures are silent which is what we want here.
  const url = `/api/v1/debug/sessions/${sessionId}/disconnect?token=${encodeURIComponent(token)}`
  navigator.sendBeacon(url)
}
