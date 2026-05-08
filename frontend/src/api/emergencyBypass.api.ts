import apiClient from './client'

export interface BypassStatus {
  active: boolean
  expires_at: string | null
  max_hours: number
}

export async function getBypassStatus(): Promise<BypassStatus> {
  const response = await apiClient.get<BypassStatus>('/settings/sso-emergency-bypass')
  return response.data
}

export async function activateBypass(hours: number): Promise<BypassStatus> {
  const response = await apiClient.post<BypassStatus>('/settings/sso-emergency-bypass', { hours })
  return response.data
}

export async function deactivateBypass(): Promise<BypassStatus> {
  const response = await apiClient.delete<BypassStatus>('/settings/sso-emergency-bypass')
  return response.data
}
