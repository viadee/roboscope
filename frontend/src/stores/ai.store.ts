import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as aiApi from '@/api/ai.api'
import type { AiJob, AiProvider, DriftResponse, ValidateSpecResponse } from '@/types/domain.types'
import type { AiProviderCreateRequest, AiProviderUpdateRequest } from '@/types/api.types'

export const useAiStore = defineStore('ai', () => {
  const providers = ref<AiProvider[]>([])
  const activeJob = ref<AiJob | null>(null)
  const driftResults = ref<DriftResponse | null>(null)
  const loading = ref(false)
  const pollInterval = ref<ReturnType<typeof setInterval> | null>(null)

  // rf-mcp state
  const rfMcpAvailable = ref(false)
  const rfMcpUrl = ref('')

  // rf-mcp server management state
  const rfMcpStatus = ref<string>('stopped')
  const rfMcpRunning = ref(false)
  const rfMcpPort = ref<number | null>(null)
  const rfMcpPid = ref<number | null>(null)
  const rfMcpEnvId = ref<number | null>(null)
  const rfMcpEnvName = ref<string | null>(null)
  const rfMcpError = ref('')
  const rfMcpInstalledVersion = ref<string | null>(null)
  const rfMcpPolling = ref<ReturnType<typeof setInterval> | null>(null)

  const defaultProvider = computed(() => providers.value.find((p) => p.is_default) || null)
  const hasProviders = computed(() => providers.value.length > 0)

  // --- Providers ---

  async function fetchProviders() {
    providers.value = await aiApi.getProviders()
  }

  async function addProvider(data: AiProviderCreateRequest): Promise<AiProvider> {
    const provider = await aiApi.createProvider(data)
    providers.value.push(provider)
    if (provider.is_default) {
      providers.value.forEach((p) => {
        if (p.id !== provider.id) p.is_default = false
      })
    }
    return provider
  }

  async function editProvider(id: number, data: AiProviderUpdateRequest): Promise<AiProvider> {
    const updated = await aiApi.updateProvider(id, data)
    const idx = providers.value.findIndex((p) => p.id === id)
    if (idx >= 0) providers.value[idx] = updated
    if (updated.is_default) {
      providers.value.forEach((p) => {
        if (p.id !== updated.id) p.is_default = false
      })
    }
    return updated
  }

  async function removeProvider(id: number) {
    await aiApi.deleteProvider(id)
    providers.value = providers.value.filter((p) => p.id !== id)
  }

  // --- Generation ---

  async function generate(repoId: number, specPath: string, providerId?: number, force?: boolean) {
    loading.value = true
    try {
      const job = await aiApi.generateRobot({
        repository_id: repoId,
        spec_path: specPath,
        provider_id: providerId,
        force,
      })
      activeJob.value = job
      startPolling(job.id)
      return job
    } finally {
      loading.value = false
    }
  }

  async function reverse(repoId: number, robotPath: string, providerId?: number, outputPath?: string) {
    loading.value = true
    try {
      const job = await aiApi.reverseRobot({
        repository_id: repoId,
        robot_path: robotPath,
        provider_id: providerId,
        output_path: outputPath,
      })
      activeJob.value = job
      startPolling(job.id)
      return job
    } finally {
      loading.value = false
    }
  }

  async function acceptJob(jobId: number) {
    return await aiApi.acceptJob(jobId)
  }

  // --- Polling ---

  function startPolling(jobId: number) {
    stopPolling()
    pollInterval.value = setInterval(async () => {
      try {
        const job = await aiApi.getJobStatus(jobId)
        activeJob.value = job
        if (job.status === 'completed' || job.status === 'failed') {
          stopPolling()
        }
      } catch {
        stopPolling()
      }
    }, 2000)
  }

  function stopPolling() {
    if (pollInterval.value) {
      clearInterval(pollInterval.value)
      pollInterval.value = null
    }
  }

  // --- Validation & Drift ---

  async function validateSpec(content: string): Promise<ValidateSpecResponse> {
    return await aiApi.validateSpec(content)
  }

  async function fetchDrift(repoId: number) {
    driftResults.value = await aiApi.checkDrift(repoId)
    return driftResults.value
  }

  // --- rf-mcp knowledge ---

  async function fetchRfKnowledgeStatus() {
    try {
      const status = await aiApi.getRfKnowledgeStatus()
      rfMcpAvailable.value = status.available
      rfMcpUrl.value = status.url
    } catch {
      rfMcpAvailable.value = false
      rfMcpUrl.value = ''
    }
  }

  async function searchKeywords(query: string) {
    return await aiApi.searchKeywords(query)
  }

  async function recommendLibraries(description: string) {
    return await aiApi.recommendLibraries(description)
  }

  // --- rf-mcp server management ---

  async function fetchRfMcpStatus() {
    try {
      const status = await aiApi.getRfMcpStatus()
      rfMcpStatus.value = status.status
      rfMcpRunning.value = status.running
      rfMcpPort.value = status.port
      rfMcpPid.value = status.pid
      rfMcpUrl.value = status.url
      rfMcpEnvId.value = status.environment_id
      rfMcpEnvName.value = status.environment_name
      rfMcpError.value = status.error_message
      rfMcpInstalledVersion.value = status.installed_version
      rfMcpAvailable.value = status.running
    } catch {
      rfMcpStatus.value = 'stopped'
      rfMcpRunning.value = false
    }
  }

  async function setupRfMcpServer(environmentId: number, port: number = 9090) {
    try {
      const status = await aiApi.setupRfMcp(environmentId, port)
      // Update state immediately from response (no 2s gap before first poll)
      rfMcpStatus.value = status.status
      rfMcpRunning.value = status.running
      rfMcpEnvId.value = status.environment_id
      rfMcpEnvName.value = status.environment_name
      rfMcpError.value = status.error_message || ''
      // Start polling for status updates
      startRfMcpPolling()
    } catch (e: any) {
      rfMcpError.value = e.response?.data?.detail || 'Setup failed'
      rfMcpStatus.value = 'error'
      throw e
    }
  }

  async function stopRfMcpServer() {
    try {
      await aiApi.stopRfMcp()
      stopRfMcpPolling()
      await fetchRfMcpStatus()
    } catch (e: any) {
      rfMcpError.value = e.response?.data?.detail || 'Stop failed'
      throw e
    }
  }

  function startRfMcpPolling() {
    stopRfMcpPolling()
    rfMcpPolling.value = setInterval(async () => {
      await fetchRfMcpStatus()
      if (rfMcpStatus.value === 'running' || rfMcpStatus.value === 'error' || rfMcpStatus.value === 'stopped') {
        stopRfMcpPolling()
      }
    }, 2000)
  }

  function stopRfMcpPolling() {
    if (rfMcpPolling.value) {
      clearInterval(rfMcpPolling.value)
      rfMcpPolling.value = null
    }
  }

  // --- Xray bridge ---

  async function exportToXray(content: string) {
    return await aiApi.exportToXray(content)
  }

  async function importFromXray(xrayData: Record<string, unknown>) {
    return await aiApi.importFromXray(xrayData)
  }

  return {
    providers,
    activeJob,
    driftResults,
    loading,
    defaultProvider,
    hasProviders,
    rfMcpAvailable,
    rfMcpUrl,
    rfMcpStatus,
    rfMcpRunning,
    rfMcpPort,
    rfMcpPid,
    rfMcpEnvId,
    rfMcpEnvName,
    rfMcpError,
    rfMcpInstalledVersion,
    fetchProviders,
    addProvider,
    editProvider,
    removeProvider,
    generate,
    reverse,
    acceptJob,
    startPolling,
    stopPolling,
    validateSpec,
    fetchDrift,
    fetchRfKnowledgeStatus,
    fetchRfMcpStatus,
    setupRfMcpServer,
    stopRfMcpServer,
    startRfMcpPolling,
    stopRfMcpPolling,
    searchKeywords,
    recommendLibraries,
    exportToXray,
    importFromXray,
  }
})
