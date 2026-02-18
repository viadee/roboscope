<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useEnvironmentsStore } from '@/stores/environments.store'
import { useToast } from '@/composables/useToast'
import * as envsApi from '@/api/environments.api'
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

// Pip list
const pipInstalled = ref<Record<number, { name: string; version: string }[]>>({})

let searchTimeout: ReturnType<typeof setTimeout> | null = null

onMounted(async () => {
  await envs.fetchEnvironments()
  try {
    popularPackages.value = await envsApi.getPopularPackages()
  } catch { /* ignore */ }
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
    // Refresh packages after a short delay
    setTimeout(() => {
      envs.fetchPackages(installEnvId.value)
      loadPipInstalled(installEnvId.value)
    }, 3000)
  } catch (e: any) {
    toast.error(t('common.error'), e.response?.data?.detail || t('environments.toasts.installFailed'))
  } finally {
    installing.value = null
  }
}

async function upgradePkg(envId: number, packageName: string) {
  try {
    await envsApi.upgradePackage(envId, packageName)
    toast.success(t('environments.toasts.upgradeStarted'), t('environments.toasts.upgradeMsg', { name: packageName }))
    setTimeout(() => {
      envs.fetchPackages(envId)
      loadPipInstalled(envId)
    }, 3000)
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
                  <span class="text-muted text-sm">{{ pkg.installed_version || pkg.version || t('environments.installing') }}</span>
                </div>
                <div class="pkg-actions">
                  <BaseButton variant="ghost" size="sm" @click="upgradePkg(env.id, pkg.package_name)">{{ t('common.upgrade') }}</BaseButton>
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

          <!-- Actions -->
          <div class="env-actions">
            <BaseButton variant="secondary" size="sm" @click="cloneEnv(env.id, env.name)">{{ t('common.clone') }}</BaseButton>
            <BaseButton variant="danger" size="sm" @click="removeEnv(env.id, env.name)">{{ t('common.delete') }}</BaseButton>
          </div>
        </div>
      </div>

      <div v-if="!envs.environments.length" class="card text-center p-6">
        <p class="text-muted">{{ t('environments.noEnvs') }}</p>
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
</style>
