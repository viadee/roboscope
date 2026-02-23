import apiClient from './client'
import type { FileContent, LibraryCheckResponse, SearchResult, TestCaseInfo, TreeNode } from '@/types/domain.types'

export async function getTree(repoId: number, path: string = ''): Promise<TreeNode> {
  const response = await apiClient.get<TreeNode>(`/explorer/${repoId}/tree`, {
    params: { path },
  })
  return response.data
}

export async function getFile(repoId: number, path: string, force?: boolean): Promise<FileContent> {
  const response = await apiClient.get<FileContent>(`/explorer/${repoId}/file`, {
    params: { path, ...(force && { force: true }) },
  })
  return response.data
}

export async function search(repoId: number, q: string, fileType?: string): Promise<SearchResult[]> {
  const response = await apiClient.get<SearchResult[]>(`/explorer/${repoId}/search`, {
    params: { q, file_type: fileType },
  })
  return response.data
}

export async function getTestCases(repoId: number): Promise<TestCaseInfo[]> {
  const response = await apiClient.get<TestCaseInfo[]>(`/explorer/${repoId}/testcases`)
  return response.data
}

export async function createFile(repoId: number, path: string, content: string = ''): Promise<FileContent> {
  const response = await apiClient.post<FileContent>(`/explorer/${repoId}/file`, { path, content })
  return response.data
}

export async function saveFile(repoId: number, path: string, content: string): Promise<FileContent> {
  const response = await apiClient.put<FileContent>(`/explorer/${repoId}/file`, { path, content })
  return response.data
}

export async function deleteFile(repoId: number, path: string): Promise<void> {
  await apiClient.delete(`/explorer/${repoId}/file`, { params: { path } })
}

export async function renameFile(repoId: number, oldPath: string, newPath: string): Promise<FileContent> {
  const response = await apiClient.post<FileContent>(`/explorer/${repoId}/file/rename`, {
    old_path: oldPath,
    new_path: newPath,
  })
  return response.data
}

export async function openInEditor(repoId: number, path: string): Promise<void> {
  await apiClient.post(`/explorer/${repoId}/file/open`, { path })
}

export async function openInFileBrowser(repoId: number, path: string): Promise<void> {
  await apiClient.post(`/explorer/${repoId}/folder/open`, { path })
}

export async function checkLibraries(repoId: number, environmentId: number): Promise<LibraryCheckResponse> {
  const response = await apiClient.get<LibraryCheckResponse>(`/explorer/${repoId}/library-check`, {
    params: { environment_id: environmentId },
  })
  return response.data
}
