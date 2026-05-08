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

export async function checkoutBranch(id: number, branch: string): Promise<{ status: string; branch: string }> {
  const response = await apiClient.post(`/repos/${id}/checkout`, null, { params: { branch } })
  return response.data
}

export interface BranchValidation {
  valid: boolean
  branch: string
  fallbacks?: string[]
  available_branches: string[]
}

export async function validateBranch(gitUrl: string, branch: string): Promise<BranchValidation> {
  const response = await apiClient.post<BranchValidation>('/repos/validate-branch', null, {
    params: { git_url: gitUrl, branch },
  })
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

// ---------------------------------------------------------------------------
// Story REPO-1 — non-Git-user save loop
// ---------------------------------------------------------------------------

export interface RepoStatus {
  current_branch: string | null
  ahead: number
  behind: number
  modified: string[]
  staged: string[]
  untracked: string[]
  deleted: string[]
  is_dirty: boolean
}

export interface PublishRequest {
  message: string
  paths?: string[]
}

export interface PublishOk {
  commit_hash: string
  message: string
  files: string[]
  pushed: true
  conflict: false
  remote_ref: string
}

/** Returned as `error.response.data.detail` for HTTP 409 from /publish. */
export interface PublishConflict {
  commit_hash: string
  message: string
  files: string[]
  pushed: false
  conflict: true
  reason: string
}

export async function getRepoStatus(id: number): Promise<RepoStatus> {
  const response = await apiClient.get<RepoStatus>(`/repos/${id}/status`)
  return response.data
}

export async function commitRepo(id: number, body: PublishRequest): Promise<{
  commit_hash: string; message: string; files: string[]
}> {
  const response = await apiClient.post(`/repos/${id}/commit`, body)
  return response.data
}

export async function pushRepo(id: number): Promise<{
  branch: string; remote_ref: string; ahead_after: number
}> {
  const response = await apiClient.post(`/repos/${id}/push`)
  return response.data
}

export async function publishRepo(id: number, body: PublishRequest): Promise<PublishOk> {
  const response = await apiClient.post<PublishOk>(`/repos/${id}/publish`, body)
  return response.data
}
