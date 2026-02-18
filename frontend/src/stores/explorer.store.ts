import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as explorerApi from '@/api/explorer.api'
import type { FileContent, SearchResult, TestCaseInfo, TreeNode } from '@/types/domain.types'

export const useExplorerStore = defineStore('explorer', () => {
  const tree = ref<TreeNode | null>(null)
  const selectedFile = ref<FileContent | null>(null)
  const searchResults = ref<SearchResult[]>([])
  const testCases = ref<TestCaseInfo[]>([])
  const loading = ref(false)
  const currentRepoId = ref<number | null>(null)

  async function fetchTree(repoId: number, path: string = '') {
    loading.value = true
    currentRepoId.value = repoId
    try {
      tree.value = await explorerApi.getTree(repoId, path)
    } finally {
      loading.value = false
    }
  }

  async function openFile(repoId: number, path: string) {
    loading.value = true
    try {
      selectedFile.value = await explorerApi.getFile(repoId, path)
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

  function clearSelection() {
    selectedFile.value = null
    searchResults.value = []
  }

  return {
    tree, selectedFile, searchResults, testCases, loading, currentRepoId,
    fetchTree, openFile, searchInRepo, fetchTestCases, clearSelection,
    saveFile, createFile, deleteFileAction, renameFileAction, openInEditorAction,
  }
})
