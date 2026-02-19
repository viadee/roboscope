import apiClient from './client'
import type {
  AiJob,
  AiProvider,
  DriftResponse,
  ValidateSpecResponse,
} from '@/types/domain.types'
import type {
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
