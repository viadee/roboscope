import apiClient from './client'
import type {
  ApiToken,
  ApiTokenCreated,
  WebhookConfig,
  WebhookDelivery,
  WebhookTestResult,
} from '@/types/domain.types'

// --- API Tokens ---

export async function createToken(data: {
  name: string
  role: string
  expires_in_days?: number | null
}): Promise<ApiTokenCreated> {
  const response = await apiClient.post<ApiTokenCreated>('/webhooks/tokens', data)
  return response.data
}

export async function getTokens(): Promise<ApiToken[]> {
  const response = await apiClient.get<ApiToken[]>('/webhooks/tokens')
  return response.data
}

export async function revokeToken(id: number): Promise<void> {
  await apiClient.delete(`/webhooks/tokens/${id}`)
}

// --- Webhooks ---

export async function getWebhooks(repositoryId?: number): Promise<WebhookConfig[]> {
  const params = repositoryId ? { repository_id: repositoryId } : {}
  const response = await apiClient.get<WebhookConfig[]>('/webhooks/hooks', { params })
  return response.data
}

export async function createWebhook(data: {
  name: string
  url: string
  secret?: string
  events?: string[]
  is_active?: boolean
  repository_id?: number | null
}): Promise<WebhookConfig> {
  const response = await apiClient.post<WebhookConfig>('/webhooks/hooks', data)
  return response.data
}

export async function updateWebhook(
  id: number,
  data: Partial<{
    name: string
    url: string
    secret: string | null
    events: string[]
    is_active: boolean
    repository_id: number | null
  }>,
): Promise<WebhookConfig> {
  const response = await apiClient.patch<WebhookConfig>(`/webhooks/hooks/${id}`, data)
  return response.data
}

export async function deleteWebhook(id: number): Promise<void> {
  await apiClient.delete(`/webhooks/hooks/${id}`)
}

export async function testWebhook(id: number): Promise<WebhookTestResult> {
  const response = await apiClient.post<WebhookTestResult>(`/webhooks/hooks/${id}/test`)
  return response.data
}

export async function getDeliveries(webhookId: number, limit = 20): Promise<WebhookDelivery[]> {
  const response = await apiClient.get<WebhookDelivery[]>(
    `/webhooks/hooks/${webhookId}/deliveries`,
    { params: { limit } },
  )
  return response.data
}

export async function getAvailableEvents(): Promise<string[]> {
  const response = await apiClient.get<{ events: string[] }>('/webhooks/events')
  return response.data.events
}
