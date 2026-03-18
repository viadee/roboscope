<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as settingsApi from '@/api/settings.api'
import * as authApi from '@/api/auth.api'
import { useToast } from '@/composables/useToast'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import ProviderConfig from '@/components/ai/ProviderConfig.vue'
import { useAiStore } from '@/stores/ai.store'
import { useEnvironmentsStore } from '@/stores/environments.store'
import { useReposStore } from '@/stores/repos.store'
import type { AppSetting, User, Role, DockerStatus, ApiToken, ApiTokenCreated, WebhookConfig } from '@/types/domain.types'
import { formatDateTime } from '@/utils/formatDate'
import * as webhooksApi from '@/api/webhooks.api'

const toast = useToast()
const { t } = useI18n()
const aiStore = useAiStore()
const envStore = useEnvironmentsStore()
const reposStore = useReposStore()

const allRoles: Role[] = ['viewer', 'runner', 'editor', 'admin']
const tokenRoles: Role[] = ['viewer', 'runner', 'editor']
const gitWebhookUrl = computed(() => `${window.location.origin}/api/v1/webhooks/git`)

const settings = ref<AppSetting[]>([])
const users = ref<User[]>([])
const loading = ref(true)
const saving = ref(false)
const activeTab = ref<'general' | 'users' | 'docker' | 'ai' | 'tokens' | 'webhooks'>('general')
const editedValues = ref<Record<string, string>>({})

// --- API Tokens state ---
const tokens = ref<ApiToken[]>([])
const tokensLoading = ref(false)
const showCreateTokenDialog = ref(false)
const creatingToken = ref(false)
const newToken = ref({ name: '', role: 'runner' as Role, expires_in_days: null as number | null })
const createdTokenValue = ref<string | null>(null)

async function loadTokens() {
  tokensLoading.value = true
  try {
    tokens.value = await webhooksApi.getTokens()
  } finally {
    tokensLoading.value = false
  }
}

function openCreateTokenDialog() {
  newToken.value = { name: '', role: 'runner', expires_in_days: null }
  createdTokenValue.value = null
  showCreateTokenDialog.value = true
}

async function createApiToken() {
  creatingToken.value = true
  try {
    const result = await webhooksApi.createToken({
      name: newToken.value.name,
      role: newToken.value.role,
      expires_in_days: newToken.value.expires_in_days,
    })
    createdTokenValue.value = result.token
    tokens.value.unshift(result)
    toast.success(t('settings.tokens.createdToken'))
  } catch (e: any) {
    const detail = e.response?.data?.detail || t('common.error')
    toast.error(detail)
  } finally {
    creatingToken.value = false
  }
}

async function copyToken() {
  if (createdTokenValue.value) {
    await navigator.clipboard.writeText(createdTokenValue.value)
    toast.success(t('settings.tokens.copied'))
  }
}

async function revokeApiToken(token: ApiToken) {
  if (!confirm(t('settings.tokens.revokeConfirm', { name: token.name }))) return
  try {
    await webhooksApi.revokeToken(token.id)
    tokens.value = tokens.value.filter(t => t.id !== token.id)
    toast.success(t('settings.tokens.revoked'))
  } catch {
    toast.error(t('common.error'))
  }
}

// --- Webhooks state ---
const webhooks = ref<WebhookConfig[]>([])
const webhooksLoading = ref(false)
const showCreateWebhookDialog = ref(false)
const creatingWebhook = ref(false)
const availableEvents = ref<string[]>([])
const newWebhook = ref({
  name: '',
  url: '',
  secret: '',
  events: [] as string[],
  repository_id: null as number | null,
})

async function loadWebhooks() {
  webhooksLoading.value = true
  try {
    const [wh, events] = await Promise.all([
      webhooksApi.getWebhooks(),
      webhooksApi.getAvailableEvents(),
    ])
    webhooks.value = wh
    availableEvents.value = events
    await reposStore.fetchRepos()
  } finally {
    webhooksLoading.value = false
  }
}

function openCreateWebhookDialog() {
  newWebhook.value = {
    name: '',
    url: '',
    secret: '',
    events: [...availableEvents.value],
    repository_id: null,
  }
  showCreateWebhookDialog.value = true
}

async function createNewWebhook() {
  creatingWebhook.value = true
  try {
    const wh = await webhooksApi.createWebhook({
      name: newWebhook.value.name,
      url: newWebhook.value.url,
      secret: newWebhook.value.secret || undefined,
      events: newWebhook.value.events,
      repository_id: newWebhook.value.repository_id,
    })
    webhooks.value.unshift(wh)
    showCreateWebhookDialog.value = false
    toast.success(t('settings.webhooks.created'))
  } catch (e: any) {
    const detail = e.response?.data?.detail || t('common.error')
    toast.error(detail)
  } finally {
    creatingWebhook.value = false
  }
}

async function toggleWebhookActive(wh: WebhookConfig) {
  try {
    const updated = await webhooksApi.updateWebhook(wh.id, { is_active: !wh.is_active })
    const idx = webhooks.value.findIndex(w => w.id === wh.id)
    if (idx >= 0) webhooks.value[idx] = updated
  } catch {
    toast.error(t('common.error'))
  }
}

async function testWebhookPing(wh: WebhookConfig) {
  try {
    const result = await webhooksApi.testWebhook(wh.id)
    if (result.success) {
      toast.success(t('settings.webhooks.testSuccess', { code: result.status_code }))
    } else {
      toast.error(t('settings.webhooks.testFailed', { error: result.error || 'Unknown' }))
    }
  } catch {
    toast.error(t('common.error'))
  }
}

async function deleteWebhookItem(wh: WebhookConfig) {
  if (!confirm(t('settings.webhooks.deleteConfirm', { name: wh.name }))) return
  try {
    await webhooksApi.deleteWebhook(wh.id)
    webhooks.value = webhooks.value.filter(w => w.id !== wh.id)
    toast.success(t('settings.webhooks.deleted'))
  } catch {
    toast.error(t('common.error'))
  }
}

function toggleEvent(event: string) {
  const idx = newWebhook.value.events.indexOf(event)
  if (idx >= 0) {
    newWebhook.value.events.splice(idx, 1)
  } else {
    newWebhook.value.events.push(event)
  }
}

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

// rf-mcp server
const rfMcpEnvId = ref<number | null>(null)
const rfMcpSetupLoading = ref(false)

async function loadRfMcpTab() {
  await Promise.all([
    aiStore.fetchRfMcpStatus(),
    envStore.fetchEnvironments(),
  ])
  if (aiStore.rfMcpEnvId) {
    rfMcpEnvId.value = aiStore.rfMcpEnvId
  } else if (!rfMcpEnvId.value) {
    // Auto-select first environment with a venv
    const withVenv = envStore.environments.filter(e => e.venv_path)
    if (withVenv.length > 0) {
      rfMcpEnvId.value = withVenv[0].id
    }
  }
}

async function handleRfMcpSetup() {
  if (!rfMcpEnvId.value) {
    toast.error(t('ai.rfMcp.selectEnvFirst'))
    return
  }
  rfMcpSetupLoading.value = true
  try {
    await aiStore.setupRfMcpServer(rfMcpEnvId.value)
    toast.success(t('ai.rfMcp.setupStarted'))
  } catch (e: any) {
    const detail = e.response?.data?.detail || t('ai.rfMcp.setupFailed')
    toast.error(detail)
  } finally {
    rfMcpSetupLoading.value = false
  }
}

async function handleRfMcpStop() {
  try {
    await aiStore.stopRfMcpServer()
    toast.success(t('ai.rfMcp.stopped'))
  } catch {
    toast.error(t('ai.rfMcp.stopFailed'))
  }
}

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
      <button class="tab" :class="{ active: activeTab === 'tokens' }" @click="activeTab = 'tokens'; loadTokens()">
        {{ t('settings.tokens.title') }}
      </button>
      <button class="tab" :class="{ active: activeTab === 'webhooks' }" @click="activeTab = 'webhooks'; loadWebhooks()">
        {{ t('settings.webhooks.title') }}
      </button>
      <button class="tab" :class="{ active: activeTab === 'ai' }" @click="activeTab = 'ai'; loadRfMcpTab()">
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

    <!-- Tokens Tab -->
    <template v-else-if="activeTab === 'tokens'">
      <div class="card">
        <div class="card-header">
          <div>
            <h3>{{ t('settings.tokens.title') }}</h3>
            <p class="text-muted text-sm" style="margin-top: 4px">{{ t('settings.tokens.description') }}</p>
          </div>
          <BaseButton size="sm" @click="openCreateTokenDialog">{{ t('settings.tokens.addToken') }}</BaseButton>
        </div>
        <BaseSpinner v-if="tokensLoading" />
        <template v-else>
          <table v-if="tokens.length" class="data-table">
            <thead>
              <tr>
                <th>{{ t('settings.tokens.name') }}</th>
                <th>{{ t('settings.tokens.prefix') }}</th>
                <th>{{ t('settings.tokens.role') }}</th>
                <th>{{ t('settings.tokens.expiresAt') }}</th>
                <th>{{ t('settings.tokens.lastUsed') }}</th>
                <th>{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="token in tokens" :key="token.id">
                <td><strong>{{ token.name }}</strong></td>
                <td><code>{{ token.prefix }}...</code></td>
                <td><BaseBadge variant="info">{{ token.role }}</BaseBadge></td>
                <td class="text-sm text-muted">{{ token.expires_at ? formatDateTime(token.expires_at) : t('settings.tokens.noExpiry') }}</td>
                <td class="text-sm text-muted">{{ token.last_used_at ? formatDateTime(token.last_used_at) : t('settings.tokens.never') }}</td>
                <td>
                  <BaseButton variant="danger" size="sm" @click="revokeApiToken(token)">{{ t('common.delete') }}</BaseButton>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="text-muted" style="padding: 20px">{{ t('settings.tokens.noTokens') }}</p>
        </template>
      </div>
    </template>

    <!-- Webhooks Tab -->
    <template v-else-if="activeTab === 'webhooks'">
      <!-- Git Inbound Webhook Info -->
      <div class="card mb-4">
        <div class="card-header">
          <h3>{{ t('settings.webhooks.gitInbound.title') }}</h3>
        </div>
        <div style="padding: 16px 20px">
          <p class="text-muted text-sm mb-3">{{ t('settings.webhooks.gitInbound.description') }}</p>
          <div class="setting-row">
            <div class="setting-info"><strong>{{ t('settings.webhooks.gitInbound.urlLabel') }}</strong></div>
            <code class="text-sm">{{ gitWebhookUrl }}</code>
          </div>
          <p class="text-muted text-sm mt-1">{{ t('settings.webhooks.gitInbound.urlHelp') }}</p>
        </div>
      </div>

      <!-- Outbound Webhooks -->
      <div class="card">
        <div class="card-header">
          <div>
            <h3>{{ t('settings.webhooks.title') }}</h3>
            <p class="text-muted text-sm" style="margin-top: 4px">{{ t('settings.webhooks.description') }}</p>
          </div>
          <BaseButton size="sm" @click="openCreateWebhookDialog">{{ t('settings.webhooks.addWebhook') }}</BaseButton>
        </div>
        <BaseSpinner v-if="webhooksLoading" />
        <template v-else>
          <table v-if="webhooks.length" class="data-table">
            <thead>
              <tr>
                <th>{{ t('settings.webhooks.name') }}</th>
                <th>{{ t('settings.webhooks.url') }}</th>
                <th>{{ t('settings.webhooks.events') }}</th>
                <th>{{ t('settings.webhooks.status') }}</th>
                <th>{{ t('settings.webhooks.lastTriggered') }}</th>
                <th>{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="wh in webhooks" :key="wh.id">
                <td>
                  <strong>{{ wh.name }}</strong>
                  <BaseBadge v-if="wh.has_secret" variant="info" class="ml-1">{{ t('settings.webhooks.hasSecret') }}</BaseBadge>
                </td>
                <td class="text-sm"><code>{{ wh.url.length > 50 ? wh.url.slice(0, 50) + '...' : wh.url }}</code></td>
                <td class="text-sm">{{ wh.events.length }} events</td>
                <td>
                  <BaseBadge :variant="wh.is_active ? 'success' : 'danger'" style="cursor: pointer" @click="toggleWebhookActive(wh)">
                    {{ wh.is_active ? t('settings.webhooks.active') : t('settings.webhooks.inactive') }}
                  </BaseBadge>
                </td>
                <td class="text-sm text-muted">
                  <template v-if="wh.last_triggered_at">
                    {{ formatDateTime(wh.last_triggered_at) }}
                    <BaseBadge v-if="wh.last_status_code" :variant="wh.last_status_code < 400 ? 'success' : 'danger'">
                      {{ wh.last_status_code }}
                    </BaseBadge>
                  </template>
                  <template v-else>—</template>
                </td>
                <td>
                  <div class="action-buttons">
                    <BaseButton variant="secondary" size="sm" @click="testWebhookPing(wh)">{{ t('settings.webhooks.test') }}</BaseButton>
                    <BaseButton variant="ghost" size="sm" @click="deleteWebhookItem(wh)">{{ t('common.delete') }}</BaseButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="text-muted" style="padding: 20px">{{ t('settings.webhooks.noWebhooks') }}</p>
        </template>
      </div>
    </template>

    <!-- AI & Generation Tab -->
    <template v-else-if="activeTab === 'ai'">
      <!-- rf-mcp Server Management -->
      <div class="card mb-4">
        <div class="card-header">
          <h3>{{ t('ai.rfMcp.title') }}</h3>
          <BaseBadge
            :variant="aiStore.rfMcpRunning ? 'success' : aiStore.rfMcpStatus === 'error' ? 'danger' : 'default'"
          >
            {{ aiStore.rfMcpRunning ? t('ai.rfMcp.running')
              : aiStore.rfMcpStatus === 'installing' ? t('ai.rfMcp.installing')
              : aiStore.rfMcpStatus === 'starting' ? t('ai.rfMcp.starting')
              : aiStore.rfMcpStatus === 'error' ? t('ai.rfMcp.error')
              : t('ai.rfMcp.notRunning') }}
          </BaseBadge>
        </div>
        <div style="padding: 16px 20px">
          <p class="text-muted text-sm mb-3">{{ t('ai.rfMcp.description') }}</p>

          <!-- Status info when running -->
          <div v-if="aiStore.rfMcpRunning" class="rf-mcp-info mb-3">
            <div class="setting-row">
              <div class="setting-info"><strong>URL</strong></div>
              <code class="text-sm">{{ aiStore.rfMcpUrl }}</code>
            </div>
            <div class="setting-row">
              <div class="setting-info"><strong>{{ t('ai.rfMcp.environment') }}</strong></div>
              <span class="text-sm">{{ aiStore.rfMcpEnvName }}</span>
            </div>
            <div v-if="aiStore.rfMcpInstalledVersion" class="setting-row">
              <div class="setting-info"><strong>{{ t('ai.rfMcp.version') }}</strong></div>
              <span class="text-sm">{{ aiStore.rfMcpInstalledVersion }}</span>
            </div>
            <div class="setting-row">
              <div class="setting-info"><strong>PID</strong></div>
              <span class="text-sm">{{ aiStore.rfMcpPid }}</span>
            </div>
          </div>

          <!-- Error message -->
          <div v-if="aiStore.rfMcpStatus === 'error' && aiStore.rfMcpError" class="alert alert-danger mb-3">
            {{ aiStore.rfMcpError }}
          </div>

          <!-- Installing/starting spinner -->
          <div v-if="aiStore.rfMcpStatus === 'installing' || aiStore.rfMcpStatus === 'starting'" class="rf-mcp-progress mb-3">
            <BaseSpinner />
            <span class="text-muted text-sm">
              {{ aiStore.rfMcpStatus === 'installing' ? t('ai.rfMcp.installingMsg') : t('ai.rfMcp.startingMsg') }}
            </span>
          </div>

          <!-- Environment selector + action (when not running) -->
          <div v-if="!aiStore.rfMcpRunning && aiStore.rfMcpStatus !== 'installing' && aiStore.rfMcpStatus !== 'starting'" class="rf-mcp-setup">
            <div class="form-group mb-3">
              <label class="form-label">{{ t('ai.rfMcp.environment') }}</label>
              <select v-model="rfMcpEnvId" class="form-select" style="max-width: 300px">
                <option :value="null" disabled>{{ t('ai.rfMcp.selectEnv') }}</option>
                <option v-for="env in envStore.environments.filter(e => e.venv_path)" :key="env.id" :value="env.id">
                  {{ env.name }}
                </option>
              </select>
              <p v-if="!envStore.environments.filter(e => e.venv_path).length" class="text-warning text-sm mt-1">
                {{ t('ai.rfMcp.noEnvs') }}
              </p>
            </div>
            <BaseButton
              :disabled="!rfMcpEnvId"
              :loading="rfMcpSetupLoading"
              @click="handleRfMcpSetup"
            >
              {{ t('ai.rfMcp.installAndStart') }}
            </BaseButton>
          </div>

          <!-- Stop button when running -->
          <BaseButton v-if="aiStore.rfMcpRunning" variant="danger" @click="handleRfMcpStop">
            {{ t('ai.rfMcp.stop') }}
          </BaseButton>

          <!-- Attribution -->
          <p class="text-muted text-sm mt-3">
            <a href="https://github.com/manykarim/rf-mcp" target="_blank" rel="noopener noreferrer" class="rf-mcp-link">rf-mcp</a>
            {{ t('ai.rfMcpBy') }}
          </p>
        </div>
      </div>

      <!-- LLM Providers -->
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

    <!-- Create Token Dialog -->
    <BaseModal v-model="showCreateTokenDialog" :title="createdTokenValue ? t('settings.tokens.createdToken') : t('settings.tokens.createDialog.title')">
      <template v-if="createdTokenValue">
        <p class="text-muted text-sm mb-3">{{ t('settings.tokens.copyWarning') }}</p>
        <div class="token-display">
          <code>{{ createdTokenValue }}</code>
          <BaseButton size="sm" variant="secondary" @click="copyToken">Copy</BaseButton>
        </div>
      </template>
      <template v-else>
        <form @submit.prevent="createApiToken">
          <div class="form-group">
            <label class="form-label">{{ t('settings.tokens.createDialog.nameLabel') }}</label>
            <input v-model="newToken.name" class="form-input" :placeholder="t('settings.tokens.createDialog.namePlaceholder')" required />
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('settings.tokens.createDialog.roleLabel') }}</label>
            <select v-model="newToken.role" class="form-select">
              <option v-for="role in tokenRoles" :key="role" :value="role">{{ role }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('settings.tokens.createDialog.expiryLabel') }}</label>
            <select v-model="newToken.expires_in_days" class="form-select">
              <option :value="null">{{ t('settings.tokens.createDialog.expiryNone') }}</option>
              <option :value="30">{{ t('settings.tokens.createDialog.expiryDays', { days: 30 }) }}</option>
              <option :value="90">{{ t('settings.tokens.createDialog.expiryDays', { days: 90 }) }}</option>
              <option :value="180">{{ t('settings.tokens.createDialog.expiryDays', { days: 180 }) }}</option>
              <option :value="365">{{ t('settings.tokens.createDialog.expiryDays', { days: 365 }) }}</option>
            </select>
          </div>
        </form>
      </template>
      <template #footer>
        <BaseButton variant="secondary" @click="showCreateTokenDialog = false; createdTokenValue = null">{{ t('common.close') }}</BaseButton>
        <BaseButton v-if="!createdTokenValue" :loading="creatingToken" @click="createApiToken">{{ t('common.create') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Create Webhook Dialog -->
    <BaseModal v-model="showCreateWebhookDialog" :title="t('settings.webhooks.createDialog.title')">
      <form @submit.prevent="createNewWebhook">
        <div class="form-group">
          <label class="form-label">{{ t('settings.webhooks.createDialog.nameLabel') }}</label>
          <input v-model="newWebhook.name" class="form-input" :placeholder="t('settings.webhooks.createDialog.namePlaceholder')" required />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('settings.webhooks.createDialog.urlLabel') }}</label>
          <input v-model="newWebhook.url" class="form-input" :placeholder="t('settings.webhooks.createDialog.urlPlaceholder')" type="url" required />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('settings.webhooks.createDialog.secretLabel') }}</label>
          <input v-model="newWebhook.secret" class="form-input" :placeholder="t('settings.webhooks.createDialog.secretPlaceholder')" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('settings.webhooks.createDialog.eventsLabel') }}</label>
          <div class="events-grid">
            <label v-for="event in availableEvents" :key="event" class="event-checkbox">
              <input
                type="checkbox"
                :checked="newWebhook.events.includes(event)"
                @change="toggleEvent(event)"
              />
              <code>{{ event }}</code>
            </label>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('settings.webhooks.createDialog.repoLabel') }}</label>
          <select v-model="newWebhook.repository_id" class="form-select">
            <option :value="null">{{ t('settings.webhooks.createDialog.repoAll') }}</option>
            <option v-for="repo in reposStore.repos" :key="repo.id" :value="repo.id">{{ repo.name }}</option>
          </select>
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showCreateWebhookDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton :loading="creatingWebhook" @click="createNewWebhook">{{ t('common.create') }}</BaseButton>
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

/* rf-mcp */
.rf-mcp-info {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 4px 16px;
}

.rf-mcp-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.rf-mcp-link {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 600;
}

.rf-mcp-link:hover {
  text-decoration: underline;
}

.alert-danger {
  background: #fce4e4;
  color: var(--color-danger);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.mb-3 { margin-bottom: 12px; }
.mb-4 { margin-bottom: 16px; }
.mt-1 { margin-top: 4px; }
.mt-3 { margin-top: 12px; }
.ml-1 { margin-left: 4px; }
.text-warning { color: var(--color-warning); }

/* Token display */
.token-display {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  word-break: break-all;
}

.token-display code {
  flex: 1;
  font-size: 13px;
}

/* Webhook event checkboxes */
.events-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
}

.event-checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 13px;
}

.event-checkbox input[type="checkbox"] {
  accent-color: var(--color-primary);
}
</style>
