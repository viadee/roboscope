import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as reposApi from '@/api/repos.api'
import type { Branch, ProjectMember, Repository } from '@/types/domain.types'
import type { RepoCreateRequest } from '@/types/api.types'

export const useReposStore = defineStore('repos', () => {
  const repos = ref<Repository[]>([])
  const loading = ref(false)
  const branches = ref<Record<number, Branch[]>>({})
  const members = ref<Record<number, ProjectMember[]>>({})

  async function fetchRepos() {
    loading.value = true
    try {
      repos.value = await reposApi.getRepos()
    } finally {
      loading.value = false
    }
  }

  async function addRepo(data: RepoCreateRequest): Promise<Repository> {
    const repo = await reposApi.createRepo(data)
    repos.value.push(repo)
    return repo
  }

  async function syncRepo(id: number) {
    return await reposApi.syncRepo(id)
  }

  async function updateRepo(id: number, data: Partial<Repository>): Promise<Repository> {
    const updated = await reposApi.updateRepo(id, data)
    const idx = repos.value.findIndex((r) => r.id === id)
    if (idx >= 0) repos.value[idx] = updated
    return updated
  }

  async function removeRepo(id: number) {
    await reposApi.deleteRepo(id)
    repos.value = repos.value.filter((r) => r.id !== id)
  }

  async function fetchBranches(repoId: number) {
    branches.value[repoId] = await reposApi.getBranches(repoId)
  }

  function getRepo(id: number): Repository | undefined {
    return repos.value.find((r) => r.id === id)
  }

  async function fetchMembers(repoId: number) {
    members.value[repoId] = await reposApi.getProjectMembers(repoId)
  }

  async function addMember(repoId: number, userId: number, role: string) {
    const member = await reposApi.addProjectMember(repoId, userId, role)
    if (!members.value[repoId]) members.value[repoId] = []
    const idx = members.value[repoId].findIndex((m) => m.user_id === userId)
    if (idx >= 0) members.value[repoId][idx] = member
    else members.value[repoId].push(member)
    return member
  }

  async function updateMember(repoId: number, memberId: number, role: string) {
    const member = await reposApi.updateProjectMember(repoId, memberId, role)
    const idx = members.value[repoId]?.findIndex((m) => m.id === memberId)
    if (idx !== undefined && idx >= 0) members.value[repoId][idx] = member
    return member
  }

  async function removeMember(repoId: number, memberId: number) {
    await reposApi.removeProjectMember(repoId, memberId)
    if (members.value[repoId]) {
      members.value[repoId] = members.value[repoId].filter((m) => m.id !== memberId)
    }
  }

  return { repos, loading, branches, members, fetchRepos, addRepo, updateRepo, syncRepo, removeRepo, fetchBranches, getRepo, fetchMembers, addMember, updateMember, removeMember }
})
