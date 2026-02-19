<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import * as settingsApi from '@/api/settings.api'
import * as authApi from '@/api/auth.api'
import { useToast } from '@/composables/useToast'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import ProviderConfig from '@/components/ai/ProviderConfig.vue'
import type { AppSetting, User, Role, DockerStatus } from '@/types/domain.types'
import { formatDateTime } from '@/utils/formatDate'

const toast = useToast()
const { t } = useI18n()

const allRoles: Role[] = ['viewer', 'runner', 'editor', 'admin']

const settings = ref<AppSetting[]>([])
const users = ref<User[]>([])
const loading = ref(true)
const saving = ref(false)
const activeTab = ref<'general' | 'users' | 'docker' | 'ai'>('general')
const editedValues = ref<Record<string, string>>({})

// Docker status
const dockerStatus = ref<DockerStatus | null>(null)
const dockerLoading = ref(false)

// Create user dialog
const showCreateDialog = ref(false)
const creating = ref(false)
const newUser = ref({ email: '', username: '', password: '', role: 'runner' as Role })

// Edit user dialog
const showEditDialog = ref(false)
const editingUser = ref(false)
const editUser = ref<{ id: number; email: string; username: string; role: Role }>({
  id: 0, email: '', username: '', role: 'runner',
})

// Reset password dialog
const showResetPwDialog = ref(false)
const resettingPw = ref(false)
const resetPwUser = ref<{ id: number; username: string }>({ id: 0, username: '' })
const resetPwValue = ref('')

onMounted(async () => {
  loading.value = true
  try {
    const [s, u] = await Promise.all([settingsApi.getSettings(), authApi.getUsers()])
    settings.value = s
    users.value = u
    for (const setting of s) {
      editedValues.value[setting.key] = setting.value
    }
  } finally {
    loading.value = false
  }
})

const categories = computed(() => {
  const cats = new Set(settings.value.map(s => s.category))
  return Array.from(cats).sort()
})

function getSettingsByCategory(cat: string) {
  return settings.value.filter(s => s.category === cat)
}

async function saveSettings() {
  saving.value = true
  try {
    const updates = Object.entries(editedValues.value).map(([key, value]) => ({ key, value }))
    await settingsApi.updateSettings(updates)
    toast.success(t('settings.toasts.saved'))
  } catch {
    toast.error(t('settings.toasts.saveError'))
  } finally {
    saving.value = false
  }
}

async function toggleUserActive(user: User) {
  try {
    const updated = await authApi.updateUser(user.id, { is_active: !user.is_active })
    const idx = users.value.findIndex(u => u.id === user.id)
    if (idx >= 0) users.value[idx] = updated
    toast.success(t('settings.toasts.userActivated', { status: updated.is_active ? t('settings.activate').toLowerCase() : t('settings.deactivate').toLowerCase() }))
  } catch {
    toast.error(t('common.error'))
  }
}

function openCreateDialog() {
  newUser.value = { email: '', username: '', password: '', role: 'runner' }
  showCreateDialog.value = true
}

async function createNewUser() {
  creating.value = true
  try {
    const created = await authApi.createUser(newUser.value)
    users.value.push(created)
    showCreateDialog.value = false
    toast.success(t('settings.toasts.userCreated'), t('settings.toasts.userCreatedMsg', { name: created.username }))
  } catch (e: any) {
    const detail = e.response?.data?.detail || t('settings.toasts.userCreateError')
    toast.error(t('common.error'), detail)
  } finally {
    creating.value = false
  }
}

function openEditDialog(user: User) {
  editUser.value = { id: user.id, email: user.email, username: user.username, role: user.role }
  showEditDialog.value = true
}

async function saveEditedUser() {
  editingUser.value = true
  try {
    const updated = await authApi.updateUser(editUser.value.id, {
      email: editUser.value.email,
      username: editUser.value.username,
      role: editUser.value.role,
    })
    const idx = users.value.findIndex(u => u.id === updated.id)
    if (idx >= 0) users.value[idx] = updated
    showEditDialog.value = false
    toast.success(t('settings.toasts.userUpdated'))
  } catch (e: any) {
    const detail = e.response?.data?.detail || t('settings.toasts.userUpdateError')
    toast.error(t('common.error'), detail)
  } finally {
    editingUser.value = false
  }
}

function openResetPwDialog(user: User) {
  resetPwUser.value = { id: user.id, username: user.username }
  resetPwValue.value = ''
  showResetPwDialog.value = true
}

async function saveResetPassword() {
  resettingPw.value = true
  try {
    await authApi.updateUser(resetPwUser.value.id, { password: resetPwValue.value } as any)
    showResetPwDialog.value = false
    toast.success(t('settings.toasts.passwordReset'), t('settings.toasts.passwordResetMsg', { name: resetPwUser.value.username }))
  } catch (e: any) {
    const detail = e.response?.data?.detail || t('settings.toasts.passwordResetError')
    toast.error(t('common.error'), detail)
  } finally {
    resettingPw.value = false
  }
}

async function deleteUser(user: User) {
  if (!confirm(t('settings.toasts.confirmDelete', { name: user.username }))) return
  try {
    await authApi.deleteUser(user.id)
    users.value = users.value.filter(u => u.id !== user.id)
    toast.success(t('settings.toasts.userDeleted'), t('settings.toasts.userDeletedMsg', { name: user.username }))
  } catch (e: any) {
    const detail = e.response?.data?.detail || t('settings.toasts.userDeleteError')
    toast.error(t('common.error'), detail)
  }
}

async function loadDockerStatus() {
  dockerLoading.value = true
  try {
    dockerStatus.value = await settingsApi.getDockerStatus()
  } catch {
    dockerStatus.value = { connected: false, error: 'Failed to reach backend', default_image: '' }
  } finally {
    dockerLoading.value = false
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  const kb = bytes / 1024
  if (kb < 1024) return kb.toFixed(1) + ' KB'
  const mb = kb / 1024
  if (mb < 1024) return mb.toFixed(1) + ' MB'
  const gb = mb / 1024
  return gb.toFixed(2) + ' GB'
}
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('settings.title') }}</h1>
    </div>

    <div class="tabs mb-4">
      <button class="tab" :class="{ active: activeTab === 'general' }" @click="activeTab = 'general'">
        {{ t('settings.general') }}
      </button>
      <button class="tab" :class="{ active: activeTab === 'users' }" @click="activeTab = 'users'">
        {{ t('settings.users') }}
      </button>
      <button class="tab" :class="{ active: activeTab === 'docker' }" @click="activeTab = 'docker'; if (!dockerStatus) loadDockerStatus()">
        {{ t('settings.docker.docker') }}
      </button>
      <button class="tab" :class="{ active: activeTab === 'ai' }" @click="activeTab = 'ai'">
        {{ t('ai.settingsTab') }}
      </button>
    </div>

    <BaseSpinner v-if="loading" />

    <!-- Settings Tab -->
    <template v-else-if="activeTab === 'general'">
      <div v-for="cat in categories" :key="cat" class="card mb-4">
        <div class="card-header">
          <h3 style="text-transform: capitalize">{{ cat }}</h3>
        </div>
        <div class="settings-list">
          <div v-for="setting in getSettingsByCategory(cat)" :key="setting.key" class="setting-row">
            <div class="setting-info">
              <strong>{{ setting.key }}</strong>
              <span class="text-muted text-sm">{{ setting.description }}</span>
            </div>
            <div class="setting-input">
              <select
                v-if="setting.value_type === 'bool'"
                v-model="editedValues[setting.key]"
                class="form-select"
                style="width: 120px"
              >
                <option value="true">{{ t('common.yes') }}</option>
                <option value="false">{{ t('common.no') }}</option>
              </select>
              <input
                v-else
                v-model="editedValues[setting.key]"
                class="form-input"
                style="width: 200px"
              />
            </div>
          </div>
        </div>
      </div>
      <BaseButton :loading="saving" @click="saveSettings">{{ t('common.save') }}</BaseButton>
    </template>

    <!-- Users Tab -->
    <template v-else-if="activeTab === 'users'">
      <div class="card">
        <div class="card-header">
          <h3>{{ t('settings.userManagement') }}</h3>
          <BaseButton size="sm" @click="openCreateDialog">{{ t('settings.addUser') }}</BaseButton>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ t('settings.username') }}</th>
              <th>{{ t('settings.email') }}</th>
              <th>{{ t('settings.role') }}</th>
              <th>{{ t('common.status') }}</th>
              <th>{{ t('common.created') }}</th>
              <th>{{ t('settings.lastLogin') }}</th>
              <th>{{ t('common.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td><strong>{{ user.username }}</strong></td>
              <td class="text-sm">{{ user.email }}</td>
              <td><BaseBadge variant="info">{{ user.role }}</BaseBadge></td>
              <td>
                <BaseBadge :variant="user.is_active ? 'success' : 'danger'">
                  {{ user.is_active ? t('settings.active') : t('settings.inactive') }}
                </BaseBadge>
              </td>
              <td class="text-sm text-muted">{{ formatDateTime(user.created_at) }}</td>
              <td class="text-sm text-muted">{{ user.last_login_at ? formatDateTime(user.last_login_at) : '—' }}</td>
              <td>
                <div class="action-buttons">
                  <BaseButton variant="secondary" size="sm" @click="openEditDialog(user)">
                    {{ t('common.edit') }}
                  </BaseButton>
                  <BaseButton variant="secondary" size="sm" @click="openResetPwDialog(user)">
                    {{ t('settings.resetPassword') }}
                  </BaseButton>
                  <BaseButton
                    :variant="user.is_active ? 'danger' : 'primary'"
                    size="sm"
                    @click="toggleUserActive(user)"
                  >
                    {{ user.is_active ? t('settings.deactivate') : t('settings.activate') }}
                  </BaseButton>
                  <BaseButton variant="ghost" size="sm" @click="deleteUser(user)">
                    {{ t('common.delete') }}
                  </BaseButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Docker Tab -->
    <template v-else-if="activeTab === 'docker'">
      <BaseSpinner v-if="dockerLoading" />
      <template v-else-if="dockerStatus">
        <div class="card mb-4">
          <div class="card-header">
            <h3>{{ t('settings.docker.dockerStatus') }}</h3>
            <BaseButton size="sm" @click="loadDockerStatus">{{ t('settings.docker.refresh') }}</BaseButton>
          </div>
          <div class="settings-list">
            <div class="setting-row">
              <div class="setting-info"><strong>{{ t('common.status') }}</strong></div>
              <div>
                <BaseBadge :variant="dockerStatus.connected ? 'success' : 'danger'">
                  {{ dockerStatus.connected ? t('settings.docker.connected') : t('settings.docker.disconnected') }}
                </BaseBadge>
              </div>
            </div>
            <template v-if="dockerStatus.connected">
              <div class="setting-row">
                <div class="setting-info"><strong>{{ t('settings.docker.version') }}</strong></div>
                <div class="text-sm">{{ dockerStatus.version }}</div>
              </div>
              <div class="setting-row">
                <div class="setting-info"><strong>{{ t('settings.docker.apiVersion') }}</strong></div>
                <div class="text-sm">{{ dockerStatus.api_version }}</div>
              </div>
              <div class="setting-row">
                <div class="setting-info"><strong>{{ t('settings.docker.os') }} / {{ t('settings.docker.arch') }}</strong></div>
                <div class="text-sm">{{ dockerStatus.os }} / {{ dockerStatus.arch }}</div>
              </div>
              <div class="setting-row">
                <div class="setting-info"><strong>{{ t('settings.docker.defaultImage') }}</strong></div>
                <div class="text-sm"><code>{{ dockerStatus.default_image }}</code></div>
              </div>
              <div class="setting-row">
                <div class="setting-info"><strong>{{ t('settings.docker.runningContainers') }}</strong></div>
                <div class="text-sm">{{ dockerStatus.running_containers }}</div>
              </div>
            </template>
            <template v-else>
              <div class="setting-row">
                <div class="setting-info">
                  <strong>{{ t('settings.docker.dockerError') }}</strong>
                  <span class="text-muted text-sm">{{ dockerStatus.error }}</span>
                </div>
              </div>
            </template>
          </div>
        </div>

        <div v-if="dockerStatus.connected" class="card">
          <div class="card-header">
            <h3>{{ t('settings.docker.images') }}</h3>
          </div>
          <table v-if="dockerStatus.images && dockerStatus.images.length" class="data-table">
            <thead>
              <tr>
                <th>{{ t('settings.docker.imageName') }}</th>
                <th>{{ t('settings.docker.imageSize') }}</th>
                <th>{{ t('settings.docker.imageCreated') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(img, idx) in dockerStatus.images" :key="idx">
                <td><code>{{ img.repository }}:{{ img.tag }}</code></td>
                <td class="text-sm">{{ formatSize(img.size) }}</td>
                <td class="text-sm text-muted">{{ formatDateTime(img.created) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="settings-list">
            <p class="text-muted" style="padding: 16px 0">{{ t('settings.docker.noImages') }}</p>
          </div>
        </div>
      </template>
    </template>

    <!-- AI & Generation Tab -->
    <template v-else-if="activeTab === 'ai'">
      <div class="card">
        <div class="card-header">
          <h3>{{ t('ai.settingsTitle') }}</h3>
        </div>
        <div style="padding: 16px 20px">
          <p class="text-muted text-sm mb-4">{{ t('ai.settingsDescription') }}</p>
          <ProviderConfig />
        </div>
      </div>
    </template>

    <!-- Create User Dialog -->
    <BaseModal v-model="showCreateDialog" :title="t('settings.createDialog.title')">
      <form @submit.prevent="createNewUser">
        <div class="form-group">
          <label class="form-label">{{ t('settings.username') }}</label>
          <input v-model="newUser.username" class="form-input" placeholder="max.mustermann" required />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('settings.email') }}</label>
          <input v-model="newUser.email" type="email" class="form-input" placeholder="max@example.com" required />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('settings.password') }}</label>
          <input v-model="newUser.password" type="password" class="form-input" :placeholder="t('settings.minChars')" required minlength="6" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('settings.role') }}</label>
          <select v-model="newUser.role" class="form-select">
            <option v-for="role in allRoles" :key="role" :value="role">{{ role }}</option>
          </select>
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showCreateDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton :loading="creating" @click="createNewUser">{{ t('common.create') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Edit User Dialog -->
    <BaseModal v-model="showEditDialog" :title="t('settings.editDialog.title')">
      <form @submit.prevent="saveEditedUser">
        <div class="form-group">
          <label class="form-label">{{ t('settings.username') }}</label>
          <input v-model="editUser.username" class="form-input" required />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('settings.email') }}</label>
          <input v-model="editUser.email" type="email" class="form-input" required />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('settings.role') }}</label>
          <select v-model="editUser.role" class="form-select">
            <option v-for="role in allRoles" :key="role" :value="role">{{ role }}</option>
          </select>
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showEditDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton :loading="editingUser" @click="saveEditedUser">{{ t('common.save') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Reset Password Dialog -->
    <BaseModal v-model="showResetPwDialog" :title="t('settings.resetPwDialog.title')">
      <p class="text-muted text-sm mb-3">{{ t('settings.resetPwDialog.description', { name: resetPwUser.username }) }}</p>
      <form @submit.prevent="saveResetPassword">
        <div class="form-group">
          <label class="form-label">{{ t('settings.resetPwDialog.newPassword') }}</label>
          <input v-model="resetPwValue" type="password" class="form-input" :placeholder="t('settings.minChars')" required minlength="6" />
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showResetPwDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton :loading="resettingPw" @click="saveResetPassword">{{ t('settings.resetPwDialog.save') }}</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid var(--color-border);
  padding-bottom: 0;
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

.tab:hover:not(.active) {
  color: var(--color-text);
}

.settings-list { padding: 0 20px 16px; }

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border-light);
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.action-buttons {
  display: flex;
  gap: 6px;
}
</style>
