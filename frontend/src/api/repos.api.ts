import apiClient from './client'
import type { RepoCreateRequest } from '@/types/api.types'
import type { Branch, Repository } from '@/types/domain.types'

export async function getRepos(): Promise<Repository[]> {
  const response = await apiClient.get<Repository[]>('/repos')
  return response.data
}

export async function getRepo(id: number): Promise<Repository> {
  const response = await apiClient.get<Repository>(`/repos/${id}`)
  return response.data
}

export async function createRepo(data: RepoCreateRequest): Promise<Repository> {
  const response = await apiClient.post<Repository>('/repos', data)
  return response.data
}

export async function updateRepo(id: number, data: Partial<Repository>): Promise<Repository> {
  const response = await apiClient.patch<Repository>(`/repos/${id}`, data)
  return response.data
}

export async function deleteRepo(id: number): Promise<void> {
  await apiClient.delete(`/repos/${id}`)
}

export async function syncRepo(id: number): Promise<{ status: string; message: string; task_id: string | null }> {
  const response = await apiClient.post(`/repos/${id}/sync`)
  return response.data
}

export async function getBranches(id: number): Promise<Branch[]> {
  const response = await apiClient.get<Branch[]>(`/repos/${id}/branches`)
  return response.data
}
