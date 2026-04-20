import apiClient from './client'
import type {
  DryRunProbeResponse,
  IdpProvider,
  IdpProviderCreate,
  IdpProviderUpdate,
} from '@/types/domain.types'

const BASE = '/auth/idp-providers'

export async function listIdps(): Promise<IdpProvider[]> {
  const response = await apiClient.get<IdpProvider[]>(BASE)
  return response.data
}

export async function getIdp(id: number): Promise<IdpProvider> {
  const response = await apiClient.get<IdpProvider>(`${BASE}/${id}`)
  return response.data
}

export async function createIdp(data: IdpProviderCreate): Promise<IdpProvider> {
  const response = await apiClient.post<IdpProvider>(BASE, data)
  return response.data
}

export async function updateIdp(id: number, data: IdpProviderUpdate): Promise<IdpProvider> {
  const response = await apiClient.patch<IdpProvider>(`${BASE}/${id}`, data)
  return response.data
}

export async function deleteIdp(id: number): Promise<void> {
  await apiClient.delete(`${BASE}/${id}`)
}

export async function dryRunIdp(id: number): Promise<DryRunProbeResponse> {
  // AC2 of Story 1.4: probe has a ~10s budget; allow some client-side headroom.
  const response = await apiClient.post<DryRunProbeResponse>(`${BASE}/${id}/dry-run`, undefined, {
    timeout: 15000,
  })
  return response.data
}
