import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as reposApi from '@/api/repos.api'
import type { Branch, Repository } from '@/types/domain.types'
import type { RepoCreateRequest } from '@/types/api.types'

export const useReposStore = defineStore('repos', () => {
  const repos = ref<Repository[]>([])
  const loading = ref(false)
  const branches = ref<Record<number, Branch[]>>({})

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

  return { repos, loading, branches, fetchRepos, addRepo, updateRepo, syncRepo, removeRepo, fetchBranches, getRepo }
})
