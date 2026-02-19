import apiClient from './client'
import type { RepoCreateRequest } from '@/types/api.types'
import type { Branch, ProjectMember, Repository } from '@/types/domain.types'

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

// Project Members
export async function getProjectMembers(repoId: number): Promise<ProjectMember[]> {
  const response = await apiClient.get<ProjectMember[]>(`/repos/${repoId}/members`)
  return response.data
}

export async function addProjectMember(
  repoId: number,
  userId: number,
  role: string,
): Promise<ProjectMember> {
  const response = await apiClient.post<ProjectMember>(`/repos/${repoId}/members`, {
    user_id: userId,
    role,
  })
  return response.data
}

export async function updateProjectMember(
  repoId: number,
  memberId: number,
  role: string,
): Promise<ProjectMember> {
  const response = await apiClient.patch<ProjectMember>(`/repos/${repoId}/members/${memberId}`, {
    role,
  })
  return response.data
}

export async function removeProjectMember(repoId: number, memberId: number): Promise<void> {
  await apiClient.delete(`/repos/${repoId}/members/${memberId}`)
}
