import apiClient from './client'

export interface AuditLogEntry {
  id: number
  user_id: number | null
  username: string | null
  action: string
  resource_type: string
  resource_id: number | null
  detail: string | null
  ip_address: string | null
  timestamp: string
}

export interface AuditLogListResponse {
  items: AuditLogEntry[]
  total: number
  page: number
  page_size: number
}

export interface AuditFilters {
  actions: string[]
  resource_types: string[]
}

export async function getAuditLogs(params: {
  page?: number
  page_size?: number
  user_id?: number
  action?: string
  resource_type?: string
  date_from?: string
  date_to?: string
}): Promise<AuditLogListResponse> {
  const response = await apiClient.get<AuditLogListResponse>('/audit', { params })
  return response.data
}

export async function getAuditFilters(): Promise<AuditFilters> {
  const response = await apiClient.get<AuditFilters>('/audit/filters')
  return response.data
}

export async function exportAuditCsv(params?: {
  user_id?: number
  action?: string
  resource_type?: string
  date_from?: string
  date_to?: string
}): Promise<Blob> {
  const response = await apiClient.get('/audit/export', {
    params,
    responseType: 'blob',
  })
  return response.data
}

export async function triggerRetention(dryRun = true): Promise<Record<string, unknown>> {
  const response = await apiClient.post('/audit/retention/run', null, {
    params: { dry_run: dryRun },
  })
  return response.data
}
