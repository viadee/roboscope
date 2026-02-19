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

  return {
    providers,
    activeJob,
    driftResults,
    loading,
    defaultProvider,
    hasProviders,
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
  }
})
