import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as idpApi from '@/api/idpProviders.api'
import type {
  DryRunProbeResponse,
  IdpProvider,
  IdpProviderCreate,
  IdpProviderUpdate,
} from '@/types/domain.types'

export const useIdpProvidersStore = defineStore('idpProviders', () => {
  const providers = ref<IdpProvider[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const dryRunInFlight = ref<Set<number>>(new Set())
  const lastDryRunResult = ref<DryRunProbeResponse | null>(null)

  async function fetch() {
    loading.value = true
    error.value = null
    try {
      providers.value = await idpApi.listIdps()
    } catch (e) {
      error.value = (e as Error).message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function create(data: IdpProviderCreate): Promise<IdpProvider> {
    const idp = await idpApi.createIdp(data)
    providers.value.push(idp)
    return idp
  }

  async function update(id: number, data: IdpProviderUpdate): Promise<IdpProvider> {
    const idp = await idpApi.updateIdp(id, data)
    const idx = providers.value.findIndex((p) => p.id === id)
    if (idx >= 0) providers.value[idx] = idp
    return idp
  }

  async function remove(id: number): Promise<void> {
    try {
      await idpApi.deleteIdp(id)
    } catch (e) {
      // Recover from concurrent-delete: if another admin removed it first,
      // treat as a successful local delete and refetch for eventual consistency.
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        providers.value = providers.value.filter((p) => p.id !== id)
        await fetch()
        return
      }
      throw e
    }
    providers.value = providers.value.filter((p) => p.id !== id)
  }

  async function runDryRun(id: number): Promise<DryRunProbeResponse> {
    dryRunInFlight.value.add(id)
    try {
      const result = await idpApi.dryRunIdp(id)
      lastDryRunResult.value = result
      // Refresh is best-effort — a failing refresh must not mask a successful
      // probe. Swallow refresh errors; caller can always retry fetch().
      try {
        await fetch()
      } catch {
        // Intentionally swallowed: the probe itself persisted server-side.
      }
      return result
    } finally {
      dryRunInFlight.value.delete(id)
    }
  }

  function isDryRunInFlight(id: number): boolean {
    return dryRunInFlight.value.has(id)
  }

  return {
    providers,
    loading,
    error,
    lastDryRunResult,
    fetch,
    create,
    update,
    remove,
    runDryRun,
    isDryRunInFlight,
  }
})
