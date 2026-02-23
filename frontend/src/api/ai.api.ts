import apiClient from './client'
import type {
  AiJob,
  AiProvider,
  DriftResponse,
  ValidateSpecResponse,
} from '@/types/domain.types'
import type {
  AiAnalyzeRequest,
  AiGenerateRequest,
  AiProviderCreateRequest,
  AiProviderUpdateRequest,
  AiReverseRequest,
  AiValidateSpecRequest,
} from '@/types/api.types'

// --- Providers ---

export async function getProviders(): Promise<AiProvider[]> {
  const response = await apiClient.get<AiProvider[]>('/ai/providers')
  return response.data
}

export async function createProvider(data: AiProviderCreateRequest): Promise<AiProvider> {
  const response = await apiClient.post<AiProvider>('/ai/providers', data)
  return response.data
}

export async function updateProvider(
  id: number,
  data: AiProviderUpdateRequest,
): Promise<AiProvider> {
  const response = await apiClient.patch<AiProvider>(`/ai/providers/${id}`, data)
  return response.data
}

export async function deleteProvider(id: number): Promise<void> {
  await apiClient.delete(`/ai/providers/${id}`)
}

// --- Generation ---

export async function generateRobot(data: AiGenerateRequest): Promise<AiJob> {
  const response = await apiClient.post<AiJob>('/ai/generate', data)
  return response.data
}

export async function reverseRobot(data: AiReverseRequest): Promise<AiJob> {
  const response = await apiClient.post<AiJob>('/ai/reverse', data)
  return response.data
}

// --- Analysis ---

export async function analyzeFailures(data: AiAnalyzeRequest): Promise<AiJob> {
  const response = await apiClient.post<AiJob>('/ai/analyze', data)
  return response.data
}

// --- Job status ---

export async function getJobStatus(jobId: number): Promise<AiJob> {
  const response = await apiClient.get<AiJob>(`/ai/status/${jobId}`)
  return response.data
}

export async function acceptJob(jobId: number): Promise<{ status: string; target_path: string; hash: string }> {
  const response = await apiClient.post<{ status: string; target_path: string; hash: string }>(
    '/ai/accept',
    { job_id: jobId },
  )
  return response.data
}

// --- Validation ---

export async function validateSpec(content: string): Promise<ValidateSpecResponse> {
  const response = await apiClient.post<ValidateSpecResponse>('/ai/validate', {
    content,
  } as AiValidateSpecRequest)
  return response.data
}

// --- Drift detection ---

export async function checkDrift(repoId: number): Promise<DriftResponse> {
  const response = await apiClient.get<DriftResponse>(`/ai/drift/${repoId}`)
  return response.data
}

// --- rf-mcp knowledge ---

export interface RfKnowledgeStatus {
  available: boolean
  url: string
}

export interface RfKeywordResult {
  name: string
  library: string
  doc: string
}

export interface RfKeywordSearchResponse {
  results: RfKeywordResult[]
}

export interface RfRecommendResponse {
  libraries: string[]
}

export async function getRfKnowledgeStatus(): Promise<RfKnowledgeStatus> {
  const response = await apiClient.get<RfKnowledgeStatus>('/ai/rf-knowledge/status')
  return response.data
}

export async function searchKeywords(query: string): Promise<RfKeywordSearchResponse> {
  const response = await apiClient.get<RfKeywordSearchResponse>('/ai/rf-knowledge/keywords', {
    params: { q: query },
  })
  return response.data
}

export async function recommendLibraries(description: string): Promise<RfRecommendResponse> {
  const response = await apiClient.post<RfRecommendResponse>('/ai/rf-knowledge/recommend', {
    description,
  })
  return response.data
}

// --- rf-mcp server management ---

export interface RfMcpDetailedStatus {
  status: string // stopped, installing, starting, running, error
  running: boolean
  port: number | null
  pid: number | null
  url: string
  environment_id: number | null
  environment_name: string | null
  error_message: string
  installed_version: string | null
}

export async function getRfMcpStatus(): Promise<RfMcpDetailedStatus> {
  const response = await apiClient.get<RfMcpDetailedStatus>('/ai/rf-mcp/status')
  return response.data
}

export async function setupRfMcp(environmentId: number, port: number = 9090): Promise<RfMcpDetailedStatus> {
  const response = await apiClient.post<RfMcpDetailedStatus>('/ai/rf-mcp/setup', {
    environment_id: environmentId,
    port,
  })
  return response.data
}

export async function stopRfMcp(): Promise<RfMcpDetailedStatus> {
  const response = await apiClient.post<RfMcpDetailedStatus>('/ai/rf-mcp/stop')
  return response.data
}

// --- Xray bridge ---

export async function exportToXray(content: string): Promise<Record<string, unknown>> {
  const response = await apiClient.post<Record<string, unknown>>('/ai/xray/export', {
    content,
  })
  return response.data
}

export async function importFromXray(xrayData: Record<string, unknown>): Promise<{ content: string }> {
  const response = await apiClient.post<{ content: string }>('/ai/xray/import', xrayData)
  return response.data
}
