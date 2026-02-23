import apiClient from './client'
import type { EnvCreateRequest, PackageCreateRequest } from '@/types/api.types'
import type { Environment, EnvironmentPackage, EnvironmentVariable } from '@/types/domain.types'

export async function getEnvironments(): Promise<Environment[]> {
  const response = await apiClient.get<Environment[]>('/environments')
  return response.data
}

export async function getEnvironment(id: number): Promise<Environment> {
  const response = await apiClient.get<Environment>(`/environments/${id}`)
  return response.data
}

export async function createEnvironment(data: EnvCreateRequest): Promise<Environment> {
  const response = await apiClient.post<Environment>('/environments', data)
  return response.data
}

export async function updateEnvironment(id: number, data: Partial<Environment>): Promise<Environment> {
  const response = await apiClient.patch<Environment>(`/environments/${id}`, data)
  return response.data
}

export async function deleteEnvironment(id: number): Promise<void> {
  await apiClient.delete(`/environments/${id}`)
}

export async function cloneEnvironment(id: number, newName: string): Promise<Environment> {
  const response = await apiClient.post<Environment>(`/environments/${id}/clone`, null, {
    params: { new_name: newName },
  })
  return response.data
}

export async function setupDefaultEnvironment(): Promise<Environment> {
  const response = await apiClient.post<Environment>('/environments/setup-default')
  return response.data
}

// Packages

export async function getPackages(envId: number): Promise<EnvironmentPackage[]> {
  const response = await apiClient.get<EnvironmentPackage[]>(`/environments/${envId}/packages`)
  return response.data
}

export async function getInstalledPackages(envId: number): Promise<{ name: string; version: string }[]> {
  const response = await apiClient.get(`/environments/${envId}/packages/installed`)
  return response.data
}

export async function installPackage(envId: number, data: PackageCreateRequest): Promise<EnvironmentPackage> {
  const response = await apiClient.post<EnvironmentPackage>(`/environments/${envId}/packages`, data)
  return response.data
}

export async function upgradePackage(envId: number, packageName: string): Promise<EnvironmentPackage> {
  const response = await apiClient.post<EnvironmentPackage>(`/environments/${envId}/packages/${packageName}/upgrade`)
  return response.data
}

export async function uninstallPackage(envId: number, packageName: string): Promise<void> {
  await apiClient.delete(`/environments/${envId}/packages/${packageName}`)
}

export async function retryPackageInstall(envId: number, packageName: string): Promise<EnvironmentPackage> {
  const response = await apiClient.post<EnvironmentPackage>(
    `/environments/${envId}/packages/${encodeURIComponent(packageName)}/retry`
  )
  return response.data
}

// PyPI

export async function searchPyPI(query: string): Promise<{ name: string; version: string; summary: string; author: string }[]> {
  const response = await apiClient.get('/environments/packages/search', { params: { q: query } })
  return response.data
}

export async function getPopularPackages(): Promise<{ name: string; description: string }[]> {
  const response = await apiClient.get('/environments/packages/popular')
  return response.data
}

// Docker Image

export async function getDockerfile(envId: number): Promise<string> {
  const response = await apiClient.get(`/environments/${envId}/dockerfile`, {
    responseType: 'text',
    transformResponse: [(data: string) => data],
  })
  return response.data
}

export async function buildDockerImage(envId: number): Promise<{ status: string; image_tag: string }> {
  const response = await apiClient.post<{ status: string; image_tag: string }>(`/environments/${envId}/docker-build`)
  return response.data
}

// Variables

export async function getVariables(envId: number): Promise<EnvironmentVariable[]> {
  const response = await apiClient.get<EnvironmentVariable[]>(`/environments/${envId}/variables`)
  return response.data
}

export async function createVariable(envId: number, data: { key: string; value: string; is_secret: boolean }): Promise<EnvironmentVariable> {
  const response = await apiClient.post<EnvironmentVariable>(`/environments/${envId}/variables`, data)
  return response.data
}
