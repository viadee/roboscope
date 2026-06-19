import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as explorerApi from '@/api/explorer.api'
import type { ProjectKeyword } from '@/api/explorer.api'
import { searchKeywords, invalidateKeywordCache } from '@/api/ai.api'
import { getEnvironmentKeywords } from '@/api/environments.api'
import { useReposStore } from '@/stores/repos.store'
import { useEnvironmentsStore } from '@/stores/environments.store'
import type { FileContent, SearchResult, TestCaseInfo, TreeNode } from '@/types/domain.types'

export interface CachedKeyword {
  name: string
  library: string
  doc: string
  doc_format?: string
  args?: string[]
}

export const useExplorerStore = defineStore('explorer', () => {
  const tree = ref<TreeNode | null>(null)
  const selectedFile = ref<FileContent | null>(null)
  const searchResults = ref<SearchResult[]>([])
  const testCases = ref<TestCaseInfo[]>([])
  const loading = ref(false)
  const currentRepoId = ref<number | null>(null)

  // Keyword cache for the current repo
  const keywords = ref<CachedKeyword[]>([])
  const keywordsLoading = ref(false)
  const keywordsLoaded = ref(false)
  // Which repo the cached `keywords` belong to. Keyword data is repo-scoped
  // (the env's installed libraries + the repo's project keywords don't change
  // between files), so `preloadKeywords` can no-op when this already matches —
  // a plain file switch must NOT refetch the whole repo keyword set.
  const keywordsRepoId = ref<number | null>(null)
  // Latest repo requested via preloadKeywords while a load was already in
  // flight (non-reactive — internal scheduling only). Drained in the loader's
  // `finally` so the newest repo always wins a fast switch.
  let pendingKeywordsRepoId: number | null = null
  // User-defined keywords parsed from the repo's own .robot/.resource files.
  // Shared here (rather than owned by KeywordPalette) so useKeywordSignatures
  // can give them precedence over library/BuiltIn keywords — RF resolves
  // project/resource keywords ABOVE library keywords on a name collision.
  const projectKeywords = ref<ProjectKeyword[]>([])

  function setProjectKeywords(kws: ProjectKeyword[]) {
    projectKeywords.value = kws
  }

  async function fetchTree(repoId: number, path: string = '') {
    loading.value = true
    currentRepoId.value = repoId
    try {
      tree.value = await explorerApi.getTree(repoId, path)
    } finally {
      loading.value = false
    }
  }

  async function openFile(repoId: number, path: string, force?: boolean) {
    loading.value = true
    try {
      selectedFile.value = await explorerApi.getFile(repoId, path, force)
    } finally {
      loading.value = false
    }
  }

  async function searchInRepo(repoId: number, query: string, fileType?: string) {
    loading.value = true
    try {
      searchResults.value = await explorerApi.search(repoId, query, fileType)
    } finally {
      loading.value = false
    }
  }

  async function fetchTestCases(repoId: number) {
    loading.value = true
    try {
      testCases.value = await explorerApi.getTestCases(repoId)
    } finally {
      loading.value = false
    }
  }

  async function saveFile(repoId: number, path: string, content: string) {
    const result = await explorerApi.saveFile(repoId, path, content)
    selectedFile.value = result
    return result
  }

  async function createFile(repoId: number, path: string, content: string = '') {
    const result = await explorerApi.createFile(repoId, path, content)
    // Refresh tree after creating a file
    await fetchTree(repoId)
    return result
  }

  async function deleteFileAction(repoId: number, path: string) {
    await explorerApi.deleteFile(repoId, path)
    if (selectedFile.value?.path === path) {
      selectedFile.value = null
    }
    await fetchTree(repoId)
  }

  async function renameFileAction(repoId: number, oldPath: string, newPath: string) {
    const result = await explorerApi.renameFile(repoId, oldPath, newPath)
    if (selectedFile.value?.path === oldPath) {
      selectedFile.value = result
    }
    await fetchTree(repoId)
    return result
  }

  async function openInEditorAction(repoId: number, path: string) {
    await explorerApi.openInEditor(repoId, path)
  }

  async function openInFileBrowserAction(repoId: number, path: string) {
    await explorerApi.openInFileBrowser(repoId, path)
  }

  function clearSelection() {
    selectedFile.value = null
    searchResults.value = []
  }

  /** Resolve the environment a repo runs in: its own `environment_id`, else
   *  the default environment. Returns null when nothing is resolvable (stores
   *  not loaded yet) — caller then falls back to the rf-knowledge source. */
  function resolveEnvironmentId(repoId: number): number | null {
    try {
      const repo = useReposStore().getRepo(repoId)
      if (repo?.environment_id != null) return repo.environment_id
      const def = useEnvironmentsStore().environments.find((e) => e.is_default)
      return def?.id ?? null
    } catch {
      return null
    }
  }

  /** Preload all available keywords for the current repo's environment.
   *  Offline-first: prefer the libdoc-per-environment endpoint (works without
   *  the optional rf-mcp server); fall back to the rf-knowledge search. */
  async function preloadKeywords(repoId: number) {
    // Repo-scoped idempotency: already cached for THIS repo → nothing to do.
    // Lets a file switch call this freely as an "ensure loaded" without ever
    // triggering a redundant refetch (use `refreshKeywords` to force a reload).
    if (keywordsLoaded.value && keywordsRepoId.value === repoId) return
    // A load is already in flight. If it's for a DIFFERENT repo (fast repo
    // switch mid-fetch), remember the latest wanted repo and re-run when the
    // in-flight load finishes — otherwise the newer repo's load would be
    // silently dropped and the palette would show the previous repo's keywords.
    if (keywordsLoading.value) { pendingKeywordsRepoId = repoId; return }
    keywordsLoading.value = true
    keywordsLoaded.value = false
    try {
      const envId = resolveEnvironmentId(repoId)
      if (envId != null) {
        try {
          const res = await getEnvironmentKeywords(envId)
          if (res.keywords && res.keywords.length > 0) {
            keywords.value = res.keywords.map((k) => ({
              name: k.name,
              library: k.library,
              doc: k.shortdoc || '',
              doc_format: 'text',
              args: k.args || [],
            }))
            keywordsLoaded.value = true
            keywordsRepoId.value = repoId
            return
          }
          // status "building" with no cached keywords yet → fall through to
          // rf-knowledge so the palette isn't empty; next open gets the cache.
        } catch {
          // endpoint unavailable → fall through to rf-knowledge
        }
      }
      const result = await searchKeywords('*', repoId)
      keywords.value = (result.results || []).map(r => ({
        name: r.name,
        library: r.library,
        doc: r.doc || '',
        doc_format: r.doc_format || 'text',
        args: r.args || [],
      }))
      keywordsLoaded.value = true
      keywordsRepoId.value = repoId
    } catch {
      // Non-critical — palette will just be empty. Clear the anchor so it
      // never advertises a repo whose keywords didn't actually load.
      keywords.value = []
      keywordsRepoId.value = null
    } finally {
      keywordsLoading.value = false
      // Service the most recent repo requested while we were loading.
      if (pendingKeywordsRepoId !== null && pendingKeywordsRepoId !== keywordsRepoId.value) {
        const next = pendingKeywordsRepoId
        pendingKeywordsRepoId = null
        void preloadKeywords(next)
      } else {
        pendingKeywordsRepoId = null
      }
    }
  }

  /** Invalidate keyword cache on backend and reload. */
  async function refreshKeywords(repoId: number) {
    try {
      await invalidateKeywordCache(repoId)
    } catch { /* ignore */ }
    keywordsLoaded.value = false
    await preloadKeywords(repoId)
  }

  function clearAll() {
    tree.value = null
    selectedFile.value = null
    searchResults.value = []
    testCases.value = []
    keywords.value = []
    keywordsLoaded.value = false
    keywordsRepoId.value = null
    projectKeywords.value = []
  }

  return {
    tree, selectedFile, searchResults, testCases, loading, currentRepoId,
    keywords, keywordsLoading, keywordsLoaded, keywordsRepoId, projectKeywords,
    fetchTree, openFile, searchInRepo, fetchTestCases, clearSelection, clearAll,
    saveFile, createFile, deleteFileAction, renameFileAction, openInEditorAction, openInFileBrowserAction,
    preloadKeywords, refreshKeywords, setProjectKeywords,
  }
})
