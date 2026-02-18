import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as envsApi from '@/api/environments.api'
import type { Environment, EnvironmentPackage, EnvironmentVariable } from '@/types/domain.types'
import type { EnvCreateRequest, PackageCreateRequest } from '@/types/api.types'

export const useEnvironmentsStore = defineStore('environments', () => {
  const environments = ref<Environment[]>([])
  const packages = ref<Record<number, EnvironmentPackage[]>>({})
  const variables = ref<Record<number, EnvironmentVariable[]>>({})
  const loading = ref(false)

  async function fetchEnvironments() {
    loading.value = true
    try {
      environments.value = await envsApi.getEnvironments()
    } finally {
      loading.value = false
    }
  }

  async function addEnvironment(data: EnvCreateRequest): Promise<Environment> {
    const env = await envsApi.createEnvironment(data)
    environments.value.push(env)
    return env
  }

  async function removeEnvironment(id: number) {
    await envsApi.deleteEnvironment(id)
    environments.value = environments.value.filter((e) => e.id !== id)
  }

  async function cloneEnvironment(id: number, newName: string): Promise<Environment> {
    const env = await envsApi.cloneEnvironment(id, newName)
    environments.value.push(env)
    return env
  }

  async function fetchPackages(envId: number) {
    packages.value[envId] = await envsApi.getPackages(envId)
  }

  async function installPackage(envId: number, data: PackageCreateRequest) {
    const pkg = await envsApi.installPackage(envId, data)
    if (!packages.value[envId]) packages.value[envId] = []
    packages.value[envId].push(pkg)
  }

  async function uninstallPackage(envId: number, packageName: string) {
    await envsApi.uninstallPackage(envId, packageName)
    if (packages.value[envId]) {
      packages.value[envId] = packages.value[envId].filter((p) => p.package_name !== packageName)
    }
  }

  async function fetchVariables(envId: number) {
    variables.value[envId] = await envsApi.getVariables(envId)
  }

  return {
    environments, packages, variables, loading,
    fetchEnvironments, addEnvironment, removeEnvironment, cloneEnvironment,
    fetchPackages, installPackage, uninstallPackage, fetchVariables,
  }
})
