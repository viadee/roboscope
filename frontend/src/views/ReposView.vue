<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useReposStore } from '@/stores/repos.store'
import { useAuthStore } from '@/stores/auth.store'
import { useEnvironmentsStore } from '@/stores/environments.store'
import { useToast } from '@/composables/useToast'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { formatTimeAgo } from '@/utils/formatDate'
import { checkLibraries } from '@/api/explorer.api'
import { installPackage } from '@/api/environments.api'
import type { LibraryCheckItem, LibraryCheckResponse, ProjectMember, User } from '@/types/domain.types'
import type { RepoCreateRequest } from '@/types/api.types'
import { getUsers } from '@/api/auth.api'

const repos = useReposStore()
const auth = useAuthStore()
const envStore = useEnvironmentsStore()
const toast = useToast()
const { t } = useI18n()

const showAddDialog = ref(false)
const newRepo = ref({
  name: '',
  repo_type: 'local' as 'git' | 'local',
  git_url: '',
  local_path: '',
  default_branch: 'main',
  environment_id: null as number | null,
})
const adding = ref(false)

// Multi-select for bulk delete
const selectedRepoIds = ref<Set<number>>(new Set())
const deletingSelected = ref(false)
const deletingAll = ref(false)

// Library Check state
const showLibCheckDialog = ref(false)
const libCheckRepoId = ref<number | null>(null)
const libCheckEnvId = ref<number | null>(null)
const libCheckResults = ref<LibraryCheckResponse | null>(null)
const libCheckScanning = ref(false)
const libCheckInstallingPkg = ref<string | null>(null)
const libCheckInstallingAll = ref(false)
const settingUpDefaultEnv = ref(false)
const showLibCheckEnvPrompt = ref(false)

// Member management state
const showMembersDialog = ref(false)
const membersRepoId = ref<number | null>(null)
const membersRepoName = ref('')
const allUsers = ref<User[]>([])
const addMemberUserId = ref<number | null>(null)
const addMemberRole = ref('viewer')
const addingMember = ref(false)

function toggleSelect(id: number) {
  if (selectedRepoIds.value.has(id)) {
    selectedRepoIds.value.delete(id)
  } else {
    selectedRepoIds.value.add(id)
  }
}

function isSelected(id: number): boolean {
  return selectedRepoIds.value.has(id)
}

function toggleSelectAll() {
  if (selectedRepoIds.value.size === repos.repos.length) {
    selectedRepoIds.value.clear()
  } else {
    selectedRepoIds.value = new Set(repos.repos.map(r => r.id))
  }
}

async function deleteSelected() {
  const count = selectedRepoIds.value.size
  if (!count) return
  if (!confirm(t('repos.confirmDeleteSelected', { count }))) return
  deletingSelected.value = true
  try {
    const ids = [...selectedRepoIds.value]
    for (const id of ids) {
      await repos.removeRepo(id)
    }
    selectedRepoIds.value.clear()
    toast.success(t('repos.toasts.deleted'), t('repos.toasts.deletedCount', { count }))
  } catch {
    toast.error(t('repos.toasts.deleteError'))
  } finally {
    deletingSelected.value = false
  }
}

async function deleteAll() {
  if (!repos.repos.length) return
  if (!confirm(t('repos.confirmDeleteAll'))) return
  deletingAll.value = true
  try {
    const ids = repos.repos.map(r => r.id)
    for (const id of ids) {
      await repos.removeRepo(id)
    }
    selectedRepoIds.value.clear()
    toast.success(t('repos.toasts.deleted'), t('repos.toasts.deletedCount', { count: ids.length }))
  } catch {
    toast.error(t('repos.toasts.deleteError'))
  } finally {
    deletingAll.value = false
  }
}

onMounted(() => {
  repos.fetchRepos()
  envStore.fetchEnvironments()
})

function openAddDialog() {
  newRepo.value = { name: '', repo_type: 'local', git_url: '', local_path: '', default_branch: 'main', environment_id: getDefaultEnvId() }
  showAddDialog.value = true
}

async function addRepo() {
  adding.value = true
  try {
    const payload: RepoCreateRequest = {
      name: newRepo.value.name,
      repo_type: newRepo.value.repo_type as 'git' | 'local',
      default_branch: newRepo.value.default_branch,
      ...(newRepo.value.repo_type === 'git' ? { git_url: newRepo.value.git_url } : { local_path: newRepo.value.local_path }),
      ...(newRepo.value.environment_id ? { environment_id: newRepo.value.environment_id } : {}),
    }
    await repos.addRepo(payload)
    const msg = newRepo.value.repo_type === 'git'
      ? t('repos.toasts.cloning', { name: newRepo.value.name })
      : t('repos.toasts.addedLocal', { name: newRepo.value.name })
    toast.success(t('repos.toasts.added'), msg)
    showAddDialog.value = false
  } catch (e: any) {
    toast.error(t('common.error'), e.response?.data?.detail || t('repos.toasts.addError'))
  } finally {
    adding.value = false
  }
}

async function syncRepo(id: number) {
  try {
    await repos.syncRepo(id)
    toast.info(t('repos.toasts.syncStarted'))
    // Poll for sync status updates
    pollSyncStatus(id)
  } catch (e: any) {
    toast.error(t('repos.toasts.syncFailed'), e.response?.data?.detail || '')
  }
}

async function pollSyncStatus(id: number) {
  // Refresh repo list after a delay to pick up sync_status changes
  for (let i = 0; i < 10; i++) {
    await new Promise(r => setTimeout(r, 3000))
    await repos.fetchRepos()
    const repo = repos.repos.find(r => r.id === id)
    if (!repo || repo.sync_status !== 'syncing') {
      if (repo?.sync_status === 'error') {
        toast.error(t('repos.toasts.syncFailed'), repo.sync_error || t('repos.toasts.unknownError'))
      } else if (repo?.sync_status === 'success') {
        toast.success(t('repos.toasts.syncDone'), t('repos.toasts.synced', { name: repo.name }))
      }
      break
    }
  }
}

async function removeRepo(id: number, name: string) {
  if (!confirm(t('repos.confirmDelete', { name }))) return
  try {
    await repos.removeRepo(id)
    toast.success(t('repos.toasts.deleted'), t('repos.toasts.removed', { name }))
  } catch {
    toast.error(t('repos.toasts.deleteError'))
  }
}

// Library Check functions
function openLibCheck(repoId: number, defaultEnvId: number | null) {
  // If no environments exist, prompt to create one first
  if (envStore.environments.length === 0) {
    libCheckRepoId.value = repoId
    showLibCheckEnvPrompt.value = true
    return
  }
  libCheckRepoId.value = repoId
  // Use repo's default env, or fall back to the global default env, or first available
  const defaultEnv = envStore.environments.find(e => e.is_default)
  libCheckEnvId.value = defaultEnvId ?? defaultEnv?.id ?? envStore.environments[0]?.id ?? null
  libCheckResults.value = null
  showLibCheckDialog.value = true
}

async function runLibCheck() {
  if (!libCheckRepoId.value || !libCheckEnvId.value) return
  libCheckScanning.value = true
  libCheckResults.value = null
  try {
    libCheckResults.value = await checkLibraries(libCheckRepoId.value, libCheckEnvId.value)
  } catch (e: any) {
    toast.error(t('common.error'), e.response?.data?.detail || 'Library check failed')
  } finally {
    libCheckScanning.value = false
  }
}

async function installMissingPkg(lib: LibraryCheckItem) {
  if (!libCheckEnvId.value || !lib.pypi_package) return
  libCheckInstallingPkg.value = lib.pypi_package
  try {
    await installPackage(libCheckEnvId.value, { package_name: lib.pypi_package })
    // Optimistic update
    lib.status = 'installed'
    if (libCheckResults.value) {
      libCheckResults.value.missing_count--
      libCheckResults.value.installed_count++
    }
    toast.success(t('common.installed'), lib.pypi_package)
  } catch (e: any) {
    toast.error(t('environments.toasts.installFailed'), e.response?.data?.detail || '')
  } finally {
    libCheckInstallingPkg.value = null
  }
}

async function installAllMissing() {
  if (!libCheckResults.value || !libCheckEnvId.value) return
  libCheckInstallingAll.value = true
  const missing = libCheckResults.value.libraries.filter(l => l.status === 'missing' && l.pypi_package)
  for (const lib of missing) {
    try {
      await installPackage(libCheckEnvId.value, { package_name: lib.pypi_package! })
      lib.status = 'installed'
      libCheckResults.value.missing_count--
      libCheckResults.value.installed_count++
    } catch {
      // continue with next
    }
  }
  libCheckInstallingAll.value = false
}

async function setupDefaultFromLibCheck() {
  settingUpDefaultEnv.value = true
  try {
    const env = await envStore.setupDefault()
    libCheckEnvId.value = env.id
    toast.success(t('environments.setupDefault.toastSuccess'))
    // If prompted from env-prompt dialog, transition to lib check dialog
    if (showLibCheckEnvPrompt.value) {
      showLibCheckEnvPrompt.value = false
      libCheckResults.value = null
      showLibCheckDialog.value = true
    }
  } catch (e: any) {
    if (e.response?.status === 409) {
      toast.error(t('environments.setupDefault.alreadyExists'))
    } else {
      toast.error(t('environments.setupDefault.toastError'))
    }
  } finally {
    settingUpDefaultEnv.value = false
  }
}

async function changeRepoEnv(repoId: number, envId: number | null) {
  try {
    await repos.updateRepo(repoId, { environment_id: envId } as any)
  } catch {
    toast.error(t('common.error'))
  }
}

function getDefaultEnvId(): number | null {
  const defaultEnv = envStore.environments.find(e => e.is_default)
  return defaultEnv?.id ?? null
}

// Member management functions
async function openMembersDialog(repoId: number, repoName: string) {
  membersRepoId.value = repoId
  membersRepoName.value = repoName
  addMemberUserId.value = null
  addMemberRole.value = 'viewer'
  showMembersDialog.value = true
  await repos.fetchMembers(repoId)
  try {
    allUsers.value = await getUsers()
  } catch {
    allUsers.value = []
  }
}

function availableUsers(): User[] {
  if (!membersRepoId.value) return []
  const currentMembers = repos.members[membersRepoId.value] || []
  const memberUserIds = new Set(currentMembers.map(m => m.user_id))
  return allUsers.value.filter(u => !memberUserIds.has(u.id))
}

async function addMember() {
  if (!membersRepoId.value || !addMemberUserId.value) return
  addingMember.value = true
  try {
    await repos.addMember(membersRepoId.value, addMemberUserId.value, addMemberRole.value)
    addMemberUserId.value = null
    addMemberRole.value = 'viewer'
    toast.success(t('repos.members.toasts.added'))
  } catch (e: any) {
    toast.error(t('common.error'), e.response?.data?.detail || t('repos.members.toasts.addError'))
  } finally {
    addingMember.value = false
  }
}

async function updateMemberRole(member: ProjectMember, newRole: string) {
  if (!membersRepoId.value) return
  try {
    await repos.updateMember(membersRepoId.value, member.id, newRole)
    toast.success(t('repos.members.toasts.updated'))
  } catch {
    toast.error(t('repos.members.toasts.updateError'))
  }
}

async function removeMember(member: ProjectMember) {
  if (!membersRepoId.value) return
  if (!confirm(t('repos.members.confirmRemove', { name: member.username }))) return
  try {
    await repos.removeMember(membersRepoId.value, member.id)
    toast.success(t('repos.members.toasts.removed'))
  } catch {
    toast.error(t('repos.members.toasts.removeError'))
  }
}
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('repos.title') }}</h1>
      <div class="flex gap-2">
        <BaseButton
          v-if="auth.hasMinRole('admin') && selectedRepoIds.size > 0"
          variant="danger"
          size="sm"
          :loading="deletingSelected"
          @click="deleteSelected"
        >
          {{ t('repos.deleteSelected', { count: selectedRepoIds.size }) }}
        </BaseButton>
        <BaseButton
          v-if="auth.hasMinRole('admin') && repos.repos.length > 0"
          variant="danger"
          size="sm"
          :loading="deletingAll"
          @click="deleteAll"
        >
          {{ t('repos.deleteAll') }}
        </BaseButton>
        <BaseButton v-if="auth.hasMinRole('editor')" @click="openAddDialog">
          {{ t('repos.addRepo') }}
        </BaseButton>
      </div>
    </div>

    <BaseSpinner v-if="repos.loading" />

    <div v-else-if="repos.repos.length">
      <div v-if="auth.hasMinRole('admin')" class="select-all-bar">
        <label class="checkbox-label">
          <input
            type="checkbox"
            :checked="selectedRepoIds.size === repos.repos.length"
            :indeterminate="selectedRepoIds.size > 0 && selectedRepoIds.size < repos.repos.length"
            @change="toggleSelectAll"
          />
          {{ t('repos.selectAll') }}
        </label>
      </div>
      <div class="grid grid-2">
      <div
        v-for="repo in repos.repos"
        :key="repo.id"
        class="card"
        :class="{ 'card-selected': isSelected(repo.id) }"
      >
        <div class="card-header">
          <div class="card-header-left">
            <input
              v-if="auth.hasMinRole('admin')"
              type="checkbox"
              class="repo-checkbox"
              :checked="isSelected(repo.id)"
              @change="toggleSelect(repo.id)"
              @click.stop
            />
            <div>
              <h3>
                {{ repo.name }}
                <BaseBadge :variant="repo.repo_type === 'git' ? 'info' : 'default'" style="margin-left: 8px; vertical-align: middle;">
                  {{ repo.repo_type === 'git' ? 'Git' : t('repos.local') }}
                </BaseBadge>
              </h3>
              <p class="text-muted text-sm">{{ repo.repo_type === 'git' ? repo.git_url : repo.local_path }}</p>
            </div>
          </div>
        </div>
        <div class="repo-details">
          <div v-if="repo.repo_type === 'git'" class="detail-row">
            <span>{{ t('repos.branch') }}</span>
            <strong>{{ repo.default_branch }}</strong>
          </div>
          <div v-if="repo.repo_type === 'git'" class="detail-row">
            <span>{{ t('repos.lastSync') }}</span>
            <span>{{ formatTimeAgo(repo.last_synced_at) }}</span>
          </div>
          <div v-if="repo.repo_type === 'git'" class="detail-row">
            <span>{{ t('repos.autoSync') }}</span>
            <span>{{ repo.auto_sync ? t('repos.autoSyncYes', { minutes: repo.sync_interval_minutes }) : t('common.no') }}</span>
          </div>
          <div class="detail-row">
            <span>{{ t('repos.defaultEnv') }}</span>
            <select
              class="env-inline-select"
              :value="repo.environment_id"
              @change="changeRepoEnv(repo.id, ($event.target as HTMLSelectElement).value ? Number(($event.target as HTMLSelectElement).value) : null)"
            >
              <option :value="''">{{ t('repos.noEnv') }}</option>
              <option v-for="env in envStore.environments" :key="env.id" :value="env.id">
                {{ env.name }}
              </option>
            </select>
          </div>
          <div v-if="repo.sync_status === 'error'" class="sync-error">
            <span class="sync-error-label">{{ t('repos.syncError') }}</span>
            <span class="sync-error-msg">{{ repo.sync_error }}</span>
          </div>
          <div v-if="repo.sync_status === 'syncing'" class="sync-syncing">
            {{ t('repos.syncing') }}
          </div>
          <div v-if="repo.repo_type === 'local'" class="detail-row">
            <span>{{ t('repos.path') }}</span>
            <span class="text-sm">{{ repo.local_path }}</span>
          </div>
        </div>
        <div class="repo-actions">
          <router-link :to="`/explorer/${repo.id}`">
            <BaseButton variant="secondary" size="sm">{{ t('repos.explorer') }}</BaseButton>
          </router-link>
          <BaseButton
            variant="secondary" size="sm"
            @click="openLibCheck(repo.id, repo.environment_id)"
          >
            {{ t('repos.libraryCheck.title') }}
          </BaseButton>
          <BaseButton
            v-if="auth.hasMinRole('editor')"
            variant="secondary" size="sm"
            @click="openMembersDialog(repo.id, repo.name)"
          >
            {{ t('repos.members.title') }}
          </BaseButton>
          <BaseButton
            v-if="auth.hasMinRole('editor') && repo.repo_type === 'git'"
            variant="secondary" size="sm" @click="syncRepo(repo.id)"
          >
            {{ t('repos.sync') }}
          </BaseButton>
          <BaseButton v-if="auth.hasMinRole('admin')" variant="danger" size="sm" @click="removeRepo(repo.id, repo.name)">
            {{ t('common.delete') }}
          </BaseButton>
        </div>
      </div>
      </div>
    </div>
    <div v-else class="card text-center p-6">
      <p class="text-muted">{{ t('repos.noRepos') }}</p>
      <BaseButton v-if="auth.hasMinRole('editor')" class="mt-4" @click="openAddDialog">
        {{ t('repos.addFirst') }}
      </BaseButton>
    </div>

    <!-- Add Dialog -->
    <BaseModal v-model="showAddDialog" :title="t('repos.addDialog.title')">
      <form @submit.prevent="addRepo">
        <div class="form-group">
          <label class="form-label">{{ t('common.type') }}</label>
          <div class="type-toggle">
            <button
              type="button"
              class="toggle-btn"
              :class="{ active: newRepo.repo_type === 'git' }"
              @click="newRepo.repo_type = 'git'"
            >
              {{ t('repos.addDialog.gitRepo') }}
            </button>
            <button
              type="button"
              class="toggle-btn"
              :class="{ active: newRepo.repo_type === 'local' }"
              @click="newRepo.repo_type = 'local'"
            >
              {{ t('repos.addDialog.localFolder') }}
            </button>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('common.name') }}</label>
          <input v-model="newRepo.name" class="form-input" placeholder="mein-projekt" required />
        </div>
        <div v-if="newRepo.repo_type === 'git'" class="form-group">
          <label class="form-label">{{ t('repos.addDialog.gitUrl') }}</label>
          <input v-model="newRepo.git_url" class="form-input" placeholder="https://github.com/user/repo.git" required />
        </div>
        <div v-if="newRepo.repo_type === 'local'" class="form-group">
          <label class="form-label">{{ t('repos.addDialog.localPath') }}</label>
          <input v-model="newRepo.local_path" class="form-input" placeholder="/pfad/zum/ordner" required />
        </div>
        <div v-if="newRepo.repo_type === 'git'" class="form-group">
          <label class="form-label">{{ t('repos.addDialog.defaultBranch') }}</label>
          <input v-model="newRepo.default_branch" class="form-input" placeholder="main" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('repos.addDialog.defaultEnv') }}</label>
          <select v-model="newRepo.environment_id" class="form-input">
            <option :value="null">{{ t('repos.addDialog.noEnv') }}</option>
            <option v-for="env in envStore.environments" :key="env.id" :value="env.id">
              {{ env.name }}
            </option>
          </select>
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showAddDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton :loading="adding" @click="addRepo">{{ t('common.add') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Library Check Dialog -->
    <BaseModal v-model="showLibCheckDialog" :title="t('repos.libraryCheck.title')" size="lg">
      <div v-if="envStore.environments.length === 0" class="lib-check-no-env">
        <p class="text-muted">{{ t('environments.setupDefault.libCheckMessage') }}</p>
        <BaseButton :loading="settingUpDefaultEnv" @click="setupDefaultFromLibCheck">
          {{ t('environments.setupDefault.button') }}
        </BaseButton>
      </div>
      <div v-else class="lib-check-controls">
        <div class="form-group" style="margin-bottom: 12px;">
          <label class="form-label">{{ t('repos.libraryCheck.selectEnv') }}</label>
          <select v-model="libCheckEnvId" class="form-input">
            <option :value="null" disabled>{{ t('repos.addDialog.noEnv') }}</option>
            <option v-for="env in envStore.environments" :key="env.id" :value="env.id">
              {{ env.name }}
            </option>
          </select>
        </div>
        <div class="flex gap-2">
          <BaseButton
            :loading="libCheckScanning"
            :disabled="!libCheckEnvId"
            @click="runLibCheck"
          >
            {{ libCheckScanning ? t('repos.libraryCheck.scanning') : t('repos.libraryCheck.scan') }}
          </BaseButton>
          <BaseButton
            v-if="libCheckResults && libCheckResults.missing_count > 0"
            variant="secondary"
            :loading="libCheckInstallingAll"
            @click="installAllMissing"
          >
            {{ t('repos.libraryCheck.installAll') }}
          </BaseButton>
        </div>
      </div>

      <div v-if="libCheckResults" class="lib-check-results">
        <p class="lib-check-summary text-muted text-sm" style="margin: 12px 0;">
          {{ t('repos.libraryCheck.summary', {
            total: libCheckResults.total_libraries,
            installed: libCheckResults.installed_count,
            missing: libCheckResults.missing_count,
            builtin: libCheckResults.builtin_count,
          }) }}
        </p>

        <div v-if="libCheckResults.libraries.length === 0" class="text-muted text-center" style="padding: 24px;">
          {{ t('repos.libraryCheck.noLibraries') }}
        </div>

        <table v-else class="data-table">
          <thead>
            <tr>
              <th>{{ t('repos.libraryCheck.library') }}</th>
              <th>{{ t('repos.libraryCheck.pypiPackage') }}</th>
              <th>{{ t('repos.libraryCheck.status') }}</th>
              <th>{{ t('common.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="lib in libCheckResults.libraries" :key="lib.library_name" class="lib-check-item">
              <td>
                <div class="lib-check-info">
                  <strong>{{ lib.library_name }}</strong>
                  <span class="text-muted text-sm">{{ lib.files.length }} file(s)</span>
                </div>
              </td>
              <td class="text-sm">{{ lib.pypi_package || '—' }}</td>
              <td>
                <BaseBadge
                  :variant="lib.status === 'installed' ? 'success' : lib.status === 'missing' ? 'danger' : 'default'"
                  class="lib-check-status"
                >
                  {{ t(`repos.libraryCheck.${lib.status}`) }}
                </BaseBadge>
                <span v-if="lib.installed_version" class="text-muted text-sm" style="margin-left: 4px;">
                  {{ lib.installed_version }}
                </span>
              </td>
              <td>
                <BaseButton
                  v-if="lib.status === 'missing' && lib.pypi_package"
                  size="sm"
                  :loading="libCheckInstallingPkg === lib.pypi_package"
                  @click="installMissingPkg(lib)"
                >
                  {{ t('common.install') }}
                </BaseButton>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <template #footer>
        <BaseButton variant="secondary" @click="showLibCheckDialog = false">{{ t('common.close') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Environment Setup Prompt (for Library Check when no envs exist) -->
    <BaseModal v-model="showLibCheckEnvPrompt" :title="t('execution.envPrompt.title')">
      <div class="env-prompt-body">
        <p>{{ t('execution.envPrompt.message') }}</p>
      </div>
      <template #footer>
        <BaseButton variant="secondary" @click="showLibCheckEnvPrompt = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton :loading="settingUpDefaultEnv" @click="setupDefaultFromLibCheck">{{ t('execution.envPrompt.setup') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Members Dialog -->
    <BaseModal v-model="showMembersDialog" :title="t('repos.members.dialogTitle', { name: membersRepoName })" size="lg">
      <div class="members-section">
        <!-- Add Member Form -->
        <div class="members-add-row">
          <select v-model="addMemberUserId" class="form-input members-user-select">
            <option :value="null" disabled>{{ t('repos.members.selectUser') }}</option>
            <option v-for="user in availableUsers()" :key="user.id" :value="user.id">
              {{ user.username }} ({{ user.email }})
            </option>
          </select>
          <select v-model="addMemberRole" class="form-input members-role-select">
            <option value="viewer">Viewer</option>
            <option value="runner">Runner</option>
            <option value="editor">Editor</option>
          </select>
          <BaseButton size="sm" :loading="addingMember" :disabled="!addMemberUserId" @click="addMember">
            {{ t('common.add') }}
          </BaseButton>
        </div>

        <!-- Members List -->
        <div v-if="membersRepoId && repos.members[membersRepoId]?.length" class="members-list">
          <table class="data-table">
            <thead>
              <tr>
                <th>{{ t('settings.username') }}</th>
                <th>{{ t('settings.email') }}</th>
                <th>{{ t('settings.role') }}</th>
                <th>{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="member in repos.members[membersRepoId]" :key="member.id">
                <td>{{ member.username }}</td>
                <td class="text-muted text-sm">{{ member.email }}</td>
                <td>
                  <select
                    class="form-input members-role-select"
                    :value="member.role"
                    @change="updateMemberRole(member, ($event.target as HTMLSelectElement).value)"
                  >
                    <option value="viewer">Viewer</option>
                    <option value="runner">Runner</option>
                    <option value="editor">Editor</option>
                  </select>
                </td>
                <td>
                  <BaseButton variant="danger" size="sm" @click="removeMember(member)">
                    {{ t('common.remove') }}
                  </BaseButton>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="text-muted text-center" style="padding: 16px 0;">
          {{ t('repos.members.noMembers') }}
        </p>
      </div>
      <template #footer>
        <BaseButton variant="secondary" @click="showMembersDialog = false">{{ t('common.close') }}</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.repo-details {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.detail-row span:first-child {
  color: var(--color-text-muted);
}

.repo-actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-light);
  flex-wrap: wrap;
}

.type-toggle {
  display: flex;
  gap: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.toggle-btn {
  flex: 1;
  padding: 8px 16px;
  border: none;
  background: var(--color-bg);
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.toggle-btn.active {
  background: var(--color-primary);
  color: white;
}

.toggle-btn:not(.active):hover {
  background: var(--color-border-light);
}

.sync-error {
  background: rgba(220, 53, 69, 0.08);
  border: 1px solid rgba(220, 53, 69, 0.2);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  margin-top: 4px;
  font-size: 12px;
}

.sync-error-label {
  color: #dc3545;
  font-weight: 600;
}

.sync-error-msg {
  color: var(--color-text-muted);
  display: block;
  margin-top: 2px;
  word-break: break-word;
}

.sync-syncing {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 500;
  margin-top: 4px;
}

.select-all-bar {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--color-bg, #f4f7fa);
  border-radius: var(--radius-sm, 6px);
  display: inline-flex;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  color: var(--color-text-muted);
}

.card-header-left {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.repo-checkbox {
  width: 16px;
  height: 16px;
  margin-top: 4px;
  cursor: pointer;
  accent-color: var(--color-primary, #3CB5A1);
  flex-shrink: 0;
}

.card-selected {
  outline: 2px solid var(--color-primary, #3CB5A1);
  outline-offset: -2px;
  background: rgba(60, 181, 161, 0.04);
}

/* Library Check styles */
.lib-check-controls {
  margin-bottom: 16px;
}

.lib-check-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.lib-check-item td {
  vertical-align: middle;
}

.lib-check-status {
  white-space: nowrap;
}

.lib-check-summary {
  font-weight: 500;
}

.env-inline-select {
  font-size: 13px;
  padding: 2px 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm, 6px);
  background: var(--color-bg-card, #fff);
  color: var(--color-text);
  cursor: pointer;
  max-width: 180px;
}

.env-inline-select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(60, 181, 161, 0.15);
}

.lib-check-no-env {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 24px 16px;
  gap: 16px;
}

/* Members dialog styles */
.members-add-row {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  align-items: center;
}

.members-user-select {
  flex: 1;
  min-width: 0;
}

.members-role-select {
  width: 120px;
  flex-shrink: 0;
}

.members-list {
  margin-top: 8px;
}

.members-list .data-table td {
  vertical-align: middle;
}

.members-list .members-role-select {
  padding: 4px 8px;
  font-size: 13px;
}
</style>
