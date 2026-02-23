<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useEnvironmentsStore } from '@/stores/environments.store'
import { useToast } from '@/composables/useToast'
import * as envsApi from '@/api/environments.api'
import type { EnvironmentPackage } from '@/types/domain.types'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'

const envs = useEnvironmentsStore()
const toast = useToast()
const { t } = useI18n()

const showAddDialog = ref(false)
const newEnv = ref({ name: '', python_version: '3.12', docker_image: '', description: '' })
const adding = ref(false)
const selectedEnvId = ref<number | null>(null)

// Package install dialog
const showInstallDialog = ref(false)
const installEnvId = ref<number>(0)
const installMode = ref<'search' | 'popular'>('popular')
const searchQuery = ref('')
const searchResults = ref<{ name: string; version: string; summary: string; author: string }[]>([])
const popularPackages = ref<{ name: string; description: string }[]>([])
const searching = ref(false)
const installing = ref<string | null>(null)
const installVersion = ref('')

// Docker image build
const dockerfilePreview = ref<Record<number, string>>({})
const dockerBuilding = ref<Record<number, boolean>>({})

// Pip list
const settingUp = ref(false)

const pipInstalled = ref<Record<number, { name: string; version: string }[]>>({})

let searchTimeout: ReturnType<typeof setTimeout> | null = null
const activePollers = new Set<ReturnType<typeof setInterval>>()

onMounted(async () => {
  await envs.fetchEnvironments()
  try {
    popularPackages.value = await envsApi.getPopularPackages()
  } catch { /* ignore */ }
})

onUnmounted(() => {
  activePollers.forEach(id => clearInterval(id))
  activePollers.clear()
})

async function addEnvironment() {
  adding.value = true
  try {
    await envs.addEnvironment({
      name: newEnv.value.name,
      python_version: newEnv.value.python_version,
      docker_image: newEnv.value.docker_image || undefined,
      description: newEnv.value.description || undefined,
    })
    toast.success(t('environments.toasts.created'))
    showAddDialog.value = false
    newEnv.value = { name: '', python_version: '3.12', docker_image: '', description: '' }
  } catch (e: any) {
    toast.error(t('common.error'), e.response?.data?.detail || t('environments.toasts.createError'))
  } finally {
    adding.value = false
  }
}

async function cloneEnv(id: number, name: string) {
  const newName = prompt(t('environments.toasts.clonePrompt', { name }))
  if (!newName) return
  try {
    await envs.cloneEnvironment(id, newName)
    toast.success(t('environments.toasts.cloned'))
  } catch {
    toast.error(t('environments.toasts.cloneFailed'))
  }
}

async function removeEnv(id: number, name: string) {
  if (!confirm(t('environments.toasts.confirmDelete', { name }))) return
  try {
    await envs.removeEnvironment(id)
    toast.success(t('environments.toasts.deleted'))
  } catch {
    toast.error(t('environments.toasts.deleteFailed'))
  }
}

async function toggleDetails(envId: number) {
  if (selectedEnvId.value === envId) {
    selectedEnvId.value = null
  } else {
    selectedEnvId.value = envId
    await Promise.all([
      envs.fetchPackages(envId),
      envs.fetchVariables(envId),
      loadPipInstalled(envId),
    ])
  }
}

async function loadPipInstalled(envId: number) {
  try {
    pipInstalled.value[envId] = await envsApi.getInstalledPackages(envId)
  } catch {
    pipInstalled.value[envId] = []
  }
}

// Package install dialog
function openInstallDialog(envId: number) {
  installEnvId.value = envId
  installMode.value = 'popular'
  searchQuery.value = ''
  searchResults.value = []
  installVersion.value = ''
  showInstallDialog.value = true
}

watch(searchQuery, (q) => {
  if (searchTimeout) clearTimeout(searchTimeout)
  if (q.length < 2) {
    searchResults.value = []
    return
  }
  searching.value = true
  searchTimeout = setTimeout(async () => {
    try {
      searchResults.value = await envsApi.searchPyPI(q)
    } catch {
      searchResults.value = []
    } finally {
      searching.value = false
    }
  }, 400)
})

async function installPkg(packageName: string, version?: string) {
  installing.value = packageName
  try {
    await envs.installPackage(installEnvId.value, {
      package_name: packageName,
      version: version || undefined,
    })
    toast.success(t('environments.toasts.pkgInstalling'), t('environments.toasts.pkgInstallingMsg', { name: packageName }))
  } catch (e: any) {
    toast.error(t('common.error'), e.response?.data?.detail || t('environments.toasts.installFailed'))
  } finally {
    installing.value = null
  }
}

async function retryInstall(envId: number, pkg: EnvironmentPackage) {
  try {
    await envsApi.retryPackageInstall(envId, pkg.package_name)
    toast.success(t('environments.toasts.pkgInstalling'), t('environments.toasts.pkgInstallingMsg', { name: pkg.package_name }))
  } catch (e: any) {
    toast.error(t('common.error'), e.response?.data?.detail || t('environments.toasts.installFailed'))
  }
}

async function upgradePkg(envId: number, packageName: string) {
  try {
    await envsApi.upgradePackage(envId, packageName)
    toast.success(t('environments.toasts.upgradeStarted'), t('environments.toasts.upgradeMsg', { name: packageName }))
  } catch (e: any) {
    toast.error(t('common.error'), e.response?.data?.detail || t('environments.toasts.upgradeFailed'))
  }
}

async function removePkg(envId: number, packageName: string) {
  if (!confirm(t('environments.toasts.confirmRemovePkg', { name: packageName }))) return
  try {
    await envs.uninstallPackage(envId, packageName)
    toast.success(t('environments.toasts.pkgRemoved'), t('environments.toasts.pkgRemovedMsg', { name: packageName }))
    setTimeout(() => loadPipInstalled(envId), 2000)
  } catch {
    toast.error(t('environments.toasts.uninstallFailed'))
  }
}

async function loadDockerfile(envId: number) {
  if (dockerfilePreview.value[envId]) return
  try {
    dockerfilePreview.value[envId] = await envsApi.getDockerfile(envId)
  } catch {
    dockerfilePreview.value[envId] = '# Error loading Dockerfile'
  }
}

async function buildDockerImg(envId: number) {
  dockerBuilding.value[envId] = true
  try {
    const result = await envsApi.buildDockerImage(envId)
    toast.success(t('environments.docker.buildStarted'), t('environments.docker.buildStartedMsg'))

    // Poll until docker_image changes
    const poll = setInterval(async () => {
      try {
        const updated = await envsApi.getEnvironment(envId)
        if (updated.docker_image === result.image_tag) {
          clearInterval(poll)
          activePollers.delete(poll)
          dockerBuilding.value[envId] = false
          // Refresh environments list to show updated docker_image
          await envs.fetchEnvironments()
          toast.success(t('environments.docker.buildComplete'))
        }
      } catch {
        // keep polling
      }
    }, 3000)
    activePollers.add(poll)

    // Safety timeout: stop polling after 5 minutes
    setTimeout(() => {
      clearInterval(poll)
      activePollers.delete(poll)
      dockerBuilding.value[envId] = false
    }, 300000)
  } catch (e: any) {
    toast.error(t('environments.docker.buildFailed'), e.response?.data?.detail || '')
    dockerBuilding.value[envId] = false
  }
}

async function setupDefaultEnv() {
  settingUp.value = true
  try {
    await envs.setupDefault()
    toast.success(t('environments.setupDefault.toastSuccess'))
  } catch (e: any) {
    if (e.response?.status === 409) {
      toast.error(t('environments.setupDefault.alreadyExists'))
    } else {
      toast.error(t('environments.setupDefault.toastError'))
    }
  } finally {
    settingUp.value = false
  }
}

async function updateEnvField(envId: number, field: string, value: string | number) {
  try {
    await envsApi.updateEnvironment(envId, { [field]: value })
    const idx = envs.environments.findIndex(e => e.id === envId)
    if (idx !== -1) {
      ;(envs.environments[idx] as any)[field] = value
    }
  } catch (e: any) {
    toast.error(t('common.error'), e.response?.data?.detail || t('common.error'))
  }
}

function isInstalled(envId: number, packageName: string): boolean {
  return envs.packages[envId]?.some(p => p.package_name === packageName) || false
}
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('environments.title') }}</h1>
      <BaseButton @click="showAddDialog = true">{{ t('environments.newEnv') }}</BaseButton>
    </div>

    <BaseSpinner v-if="envs.loading" />

    <div v-else class="env-list">
      <div v-for="env in envs.environments" :key="env.id" class="card mb-4">
        <div class="card-header" style="cursor: pointer" @click="toggleDetails(env.id)">
          <div>
            <h3>{{ env.name }} <BaseBadge v-if="env.is_default" variant="info">{{ t('environments.default') }}</BaseBadge></h3>
            <p class="text-muted text-sm">Python {{ env.python_version }} {{ env.docker_image ? `| Docker: ${env.docker_image}` : '' }}</p>
          </div>
          <span>{{ selectedEnvId === env.id ? '▲' : '▼' }}</span>
        </div>

        <div v-if="env.description" class="text-muted text-sm p-2" style="padding: 0 20px;">
          {{ env.description }}
        </div>

        <!-- Details Panel -->
        <div v-if="selectedEnvId === env.id" class="env-details">
          <!-- Packages -->
          <div class="detail-section">
            <div class="section-header">
              <h4>{{ t('environments.packages') }}</h4>
              <BaseButton size="sm" @click="openInstallDialog(env.id)">{{ t('environments.installPkg') }}</BaseButton>
            </div>
            <div v-if="envs.packages[env.id]?.length" class="pkg-list">
              <div v-for="pkg in envs.packages[env.id]" :key="pkg.id" class="pkg-item">
                <div class="pkg-info">
                  <strong>{{ pkg.package_name }}</strong>
                  <span v-if="pkg.install_status === 'failed'" class="pkg-error">
                    {{ t('environments.installError') }}
                    <span class="pkg-error-detail" :title="pkg.install_error || ''">{{ pkg.install_error }}</span>
                  </span>
                  <span v-else-if="pkg.install_status === 'installing' || pkg.install_status === 'pending'" class="text-muted text-sm">
                    <span class="pkg-spinner"></span> {{ t('environments.installing') }}
                  </span>
                  <span v-else class="text-muted text-sm">{{ pkg.installed_version || pkg.version }}</span>
                </div>
                <div class="pkg-actions">
                  <BaseButton v-if="pkg.install_status === 'failed'" variant="ghost" size="sm" @click="retryInstall(env.id, pkg)">
                    {{ t('common.retry') }}
                  </BaseButton>
                  <BaseButton v-else variant="ghost" size="sm" @click="upgradePkg(env.id, pkg.package_name)">{{ t('common.upgrade') }}</BaseButton>
                  <BaseButton variant="ghost" size="sm" @click="removePkg(env.id, pkg.package_name)">{{ t('common.remove') }}</BaseButton>
                </div>
              </div>
            </div>
            <p v-else class="text-muted text-sm">{{ t('environments.noPackages') }}</p>

            <!-- Show all pip-installed packages (collapsible) -->
            <details v-if="pipInstalled[env.id]?.length" class="pip-details">
              <summary class="text-muted text-sm">{{ t('environments.showAllPip', { count: pipInstalled[env.id]?.length || 0 }) }}</summary>
              <div class="pip-list">
                <div v-for="pkg in pipInstalled[env.id]" :key="pkg.name" class="pip-item">
                  <span>{{ pkg.name }}</span>
                  <span class="text-muted text-sm">{{ pkg.version }}</span>
                </div>
              </div>
            </details>
          </div>

          <!-- Variables -->
          <div class="detail-section">
            <h4>{{ t('environments.variables') }}</h4>
            <div v-if="envs.variables[env.id]?.length">
              <div v-for="v in envs.variables[env.id]" :key="v.id" class="pkg-item">
                <span>{{ v.key }}</span>
                <span class="text-muted text-sm">{{ v.is_secret ? '********' : v.value }}</span>
              </div>
            </div>
            <p v-else class="text-muted text-sm">{{ t('environments.noVariables') }}</p>
          </div>

          <!-- Docker Image -->
          <div v-if="envs.packages[env.id]?.length" class="detail-section">
            <h4>{{ t('environments.docker.dockerImage') }}</h4>
            <div v-if="env.docker_image" class="docker-current">
              <span class="text-sm">{{ t('environments.docker.currentImage') }}:</span>
              <code class="docker-tag">{{ env.docker_image }}</code>
            </div>
            <div class="docker-settings">
              <div class="docker-setting-row">
                <label class="text-sm">{{ t('environments.docker.defaultRunner') }}</label>
                <select
                  class="form-select form-select-sm"
                  :value="env.default_runner_type"
                  @change="updateEnvField(env.id, 'default_runner_type', ($event.target as HTMLSelectElement).value)"
                >
                  <option value="subprocess">{{ t('environments.docker.runnerSubprocess') }}</option>
                  <option value="docker">{{ t('environments.docker.runnerDocker') }}</option>
                </select>
              </div>
              <div class="docker-setting-row">
                <label class="text-sm">{{ t('environments.docker.maxContainers') }}</label>
                <input
                  type="number"
                  class="form-input form-input-sm"
                  min="1"
                  max="10"
                  :value="env.max_docker_containers"
                  @change="updateEnvField(env.id, 'max_docker_containers', Number(($event.target as HTMLInputElement).value))"
                  style="width: 80px"
                />
                <span class="text-muted text-sm">{{ t('environments.docker.maxContainersHint') }}</span>
              </div>
            </div>
            <details class="docker-preview" @toggle="($event.target as HTMLDetailsElement).open && loadDockerfile(env.id)">
              <summary class="text-muted text-sm">{{ t('environments.docker.previewDockerfile') }}</summary>
              <pre v-if="dockerfilePreview[env.id]" class="dockerfile-code">{{ dockerfilePreview[env.id] }}</pre>
              <BaseSpinner v-else />
            </details>
            <div class="docker-build-action">
              <BaseButton
                size="sm"
                :loading="dockerBuilding[env.id]"
                @click="buildDockerImg(env.id)"
              >
                {{ dockerBuilding[env.id] ? t('environments.docker.building') : t('environments.docker.buildImage') }}
              </BaseButton>
            </div>
          </div>

          <!-- Actions -->
          <div class="env-actions">
            <BaseButton variant="secondary" size="sm" @click="cloneEnv(env.id, env.name)">{{ t('common.clone') }}</BaseButton>
            <BaseButton variant="danger" size="sm" @click="removeEnv(env.id, env.name)">{{ t('common.delete') }}</BaseButton>
          </div>
        </div>
      </div>

      <div v-if="!envs.environments.length" class="setup-default-card">
        <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="setup-icon">
          <path d="M16.5 9.4l-9-5.19M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
          <line x1="12" y1="22.08" x2="12" y2="12"/>
        </svg>
        <h3 class="setup-title">{{ t('environments.setupDefault.title') }}</h3>
        <p class="setup-description">{{ t('environments.setupDefault.description') }}</p>
        <div class="setup-packages">
          <span class="setup-pkg-tag">robotframework</span>
          <span class="setup-pkg-tag">seleniumlibrary</span>
          <span class="setup-pkg-tag">browser</span>
          <span class="setup-pkg-tag">requests</span>
        </div>
        <BaseButton :loading="settingUp" @click="setupDefaultEnv">
          {{ t('environments.setupDefault.button') }}
        </BaseButton>
        <p class="setup-hint">{{ t('environments.setupDefault.hint') }}</p>
      </div>
    </div>

    <!-- Add Environment Dialog -->
    <BaseModal v-model="showAddDialog" :title="t('environments.addDialog.title')">
      <form @submit.prevent="addEnvironment">
        <div class="form-group">
          <label class="form-label">{{ t('common.name') }}</label>
          <input v-model="newEnv.name" class="form-input" placeholder="production" required />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('environments.addDialog.pythonVersion') }}</label>
          <input v-model="newEnv.python_version" class="form-input" placeholder="3.12" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('environments.addDialog.dockerImage') }}</label>
          <input v-model="newEnv.docker_image" class="form-input" placeholder="python:3.12-slim" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('environments.addDialog.description') }}</label>
          <textarea v-model="newEnv.description" class="form-textarea" rows="2"></textarea>
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showAddDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton :loading="adding" @click="addEnvironment">{{ t('common.create') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Install Package Dialog -->
    <BaseModal v-model="showInstallDialog" :title="t('environments.installDialog.title')" size="lg">
      <div class="install-tabs">
        <button class="tab" :class="{ active: installMode === 'popular' }" @click="installMode = 'popular'">
          {{ t('environments.installDialog.popularLibs') }}
        </button>
        <button class="tab" :class="{ active: installMode === 'search' }" @click="installMode = 'search'">
          {{ t('environments.installDialog.searchPyPI') }}
        </button>
      </div>

      <!-- Popular packages -->
      <div v-if="installMode === 'popular'" class="install-list">
        <div v-for="pkg in popularPackages" :key="pkg.name" class="install-item">
          <div class="install-info">
            <strong>{{ pkg.name }}</strong>
            <span class="text-muted text-sm">{{ pkg.description }}</span>
          </div>
          <BaseButton
            v-if="!isInstalled(installEnvId, pkg.name)"
            size="sm"
            :loading="installing === pkg.name"
            @click="installPkg(pkg.name)"
          >
            {{ t('common.install') }}
          </BaseButton>
          <BaseBadge v-else variant="success">{{ t('common.installed') }}</BaseBadge>
        </div>
      </div>

      <!-- Search PyPI -->
      <div v-if="installMode === 'search'">
        <div class="form-group">
          <input
            v-model="searchQuery"
            class="form-input"
            :placeholder="t('environments.installDialog.searchPlaceholder')"
            autofocus
          />
        </div>

        <BaseSpinner v-if="searching" />

        <div v-else-if="searchResults.length" class="install-list">
          <div v-for="pkg in searchResults" :key="pkg.name" class="install-item">
            <div class="install-info">
              <strong>{{ pkg.name }}</strong>
              <span v-if="pkg.version" class="text-muted text-sm">v{{ pkg.version }}</span>
              <span v-if="pkg.summary" class="text-muted text-sm">{{ pkg.summary }}</span>
            </div>
            <BaseButton
              v-if="!isInstalled(installEnvId, pkg.name)"
              size="sm"
              :loading="installing === pkg.name"
              @click="installPkg(pkg.name)"
            >
              {{ t('common.install') }}
            </BaseButton>
            <BaseBadge v-else variant="success">{{ t('common.installed') }}</BaseBadge>
          </div>
        </div>

        <p v-else-if="searchQuery.length >= 2" class="text-muted text-sm text-center">
          {{ t('environments.installDialog.noResults') }}
        </p>
        <p v-else class="text-muted text-sm text-center">
          {{ t('environments.installDialog.minChars') }}
        </p>
      </div>

      <template #footer>
        <BaseButton variant="secondary" @click="showInstallDialog = false">{{ t('common.close') }}</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.env-details {
  padding: 16px 20px;
  border-top: 1px solid var(--color-border-light);
}

.detail-section {
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.detail-section h4 {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 0;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.pkg-list {
  display: flex;
  flex-direction: column;
}

.pkg-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  font-size: 13px;
  border-bottom: 1px solid var(--color-border-light);
}

.pkg-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.pkg-actions {
  display: flex;
  gap: 4px;
}

.pkg-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  vertical-align: middle;
  margin-right: 4px;
}

@keyframes spin { to { transform: rotate(360deg); } }

.pkg-error {
  color: var(--color-danger, #e53e3e);
  font-size: 12px;
}

.pkg-error-detail {
  display: block;
  font-size: 11px;
  color: var(--color-text-muted);
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pip-details {
  margin-top: 8px;
}

.pip-details summary {
  cursor: pointer;
  padding: 4px 0;
}

.pip-list {
  max-height: 200px;
  overflow-y: auto;
  margin-top: 4px;
}

.pip-item {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  font-size: 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.env-actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-light);
}

/* Docker image section */
.docker-current {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.docker-tag {
  display: inline-block;
  padding: 2px 8px;
  background: rgba(60, 181, 161, 0.1);
  color: var(--color-primary, #3B7DD8);
  border-radius: 4px;
  font-size: 12px;
  font-family: monospace;
}

.docker-settings {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
}

.docker-setting-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.docker-setting-row label {
  min-width: 120px;
  font-weight: 500;
}

.form-select-sm,
.form-input-sm {
  padding: 4px 8px;
  font-size: 12px;
  border: 1px solid var(--color-border, #d0d5dd);
  border-radius: var(--radius-sm, 6px);
  background: var(--color-bg-card, #fff);
}

.docker-preview {
  margin-bottom: 8px;
}

.docker-preview summary {
  cursor: pointer;
  padding: 4px 0;
}

.dockerfile-code {
  background: var(--color-navy-dark, #0F1A30);
  color: #e0e6f0;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  font-family: monospace;
  overflow-x: auto;
  margin-top: 4px;
  white-space: pre;
}

.docker-build-action {
  margin-top: 4px;
}

/* Install dialog */
.install-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid var(--color-border);
  margin-bottom: 16px;
}

.tab {
  padding: 8px 16px;
  border: none;
  background: none;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
}

.tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.install-list {
  max-height: 400px;
  overflow-y: auto;
}

.install-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border-light);
}

.install-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.install-info span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Setup default card */
.setup-default-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 40px 24px;
  border: 2px dashed var(--color-border, #d0d5dd);
  border-radius: var(--radius-md, 10px);
  background: var(--color-bg-card, #ffffff);
}

.setup-icon {
  color: var(--color-primary, #3B7DD8);
  margin-bottom: 16px;
}

.setup-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
}

.setup-description {
  color: var(--color-text-muted, #5C688C);
  font-size: 14px;
  max-width: 400px;
  margin-bottom: 16px;
}

.setup-packages {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-bottom: 20px;
}

.setup-pkg-tag {
  display: inline-block;
  padding: 4px 12px;
  background: rgba(60, 181, 161, 0.1);
  color: var(--color-primary, #3B7DD8);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.setup-hint {
  color: var(--color-text-muted, #5C688C);
  font-size: 12px;
  margin-top: 12px;
}
</style>
