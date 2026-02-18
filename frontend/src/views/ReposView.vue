<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useReposStore } from '@/stores/repos.store'
import { useAuthStore } from '@/stores/auth.store'
import { useToast } from '@/composables/useToast'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { formatTimeAgo } from '@/utils/formatDate'

const repos = useReposStore()
const auth = useAuthStore()
const toast = useToast()
const { t } = useI18n()

const showAddDialog = ref(false)
const newRepo = ref({
  name: '',
  repo_type: 'git' as 'git' | 'local',
  git_url: '',
  local_path: '',
  default_branch: 'main',
})
const adding = ref(false)

onMounted(() => repos.fetchRepos())

function openAddDialog() {
  newRepo.value = { name: '', repo_type: 'git', git_url: '', local_path: '', default_branch: 'main' }
  showAddDialog.value = true
}

async function addRepo() {
  adding.value = true
  try {
    const payload: Record<string, any> = {
      name: newRepo.value.name,
      repo_type: newRepo.value.repo_type,
      default_branch: newRepo.value.default_branch,
    }
    if (newRepo.value.repo_type === 'git') {
      payload.git_url = newRepo.value.git_url
    } else {
      payload.local_path = newRepo.value.local_path
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
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('repos.title') }}</h1>
      <BaseButton v-if="auth.hasMinRole('editor')" @click="openAddDialog">
        {{ t('repos.addRepo') }}
      </BaseButton>
    </div>

    <BaseSpinner v-if="repos.loading" />

    <div v-else-if="repos.repos.length" class="grid grid-2">
      <div v-for="repo in repos.repos" :key="repo.id" class="card">
        <div class="card-header">
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
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showAddDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton :loading="adding" @click="addRepo">{{ t('common.add') }}</BaseButton>
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
</style>
