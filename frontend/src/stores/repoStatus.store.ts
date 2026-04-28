/**
 * Story REPO-1 — caches `git status` snapshots per repo so the
 * Explorer can show a "Save N changes" badge without polling on every
 * keystroke.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getRepoStatus, type RepoStatus } from '@/api/repos.api'

export const useRepoStatusStore = defineStore('repoStatus', () => {
  // Per-repo cache. Key = repo id.
  const byId = ref<Map<number, RepoStatus>>(new Map())
  const loading = ref<Set<number>>(new Set())
  const error = ref<Map<number, string>>(new Map())

  function get(repoId: number): RepoStatus | null {
    return byId.value.get(repoId) ?? null
  }

  function isLoading(repoId: number): boolean {
    return loading.value.has(repoId)
  }

  async function refresh(repoId: number): Promise<RepoStatus | null> {
    loading.value.add(repoId)
    error.value.delete(repoId)
    try {
      const status = await getRepoStatus(repoId)
      byId.value.set(repoId, status)
      // Force reactivity for Map mutations (Pinia + Vue 3 reactive Map
      // proxies do track .set / .delete, but consumers reading the
      // computed below can be brittle on identity vs. reference).
      byId.value = new Map(byId.value)
      return status
    } catch (e) {
      error.value.set(repoId, e instanceof Error ? e.message : 'unknown')
      return null
    } finally {
      loading.value.delete(repoId)
    }
  }

  function clear(repoId: number) {
    byId.value.delete(repoId)
    error.value.delete(repoId)
    byId.value = new Map(byId.value)
  }

  function dirtyCount(repoId: number): number {
    const s = byId.value.get(repoId)
    if (!s || !s.is_dirty) return 0
    return s.modified.length + s.untracked.length + s.deleted.length
  }

  return {
    byId,
    get,
    isLoading,
    refresh,
    clear,
    dirtyCount,
    error: computed(() => error.value),
  }
})
