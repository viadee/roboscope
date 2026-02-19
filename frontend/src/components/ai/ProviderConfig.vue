<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAiStore } from '@/stores/ai.store'
import type { AiProvider } from '@/types/domain.types'
import type { AiProviderCreateRequest } from '@/types/api.types'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'

const { t } = useI18n()
const aiStore = useAiStore()

const showAddDialog = ref(false)
const showEditDialog = ref(false)
const editingProvider = ref<AiProvider | null>(null)
const loading = ref(false)
const error = ref('')

const form = ref<AiProviderCreateRequest>({
  name: '',
  provider_type: 'openai',
  api_base_url: null,
  api_key: null,
  model_name: 'gpt-4o',
  temperature: 0.3,
  max_tokens: 4096,
  is_default: false,
})

const providerTypes = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'ollama', label: 'Ollama (Local)' },
]

const defaultModels: Record<string, string> = {
  openai: 'gpt-4o',
  anthropic: 'claude-sonnet-4-20250514',
  openrouter: 'anthropic/claude-sonnet-4-20250514',
  ollama: 'llama3',
}

onMounted(async () => {
  await aiStore.fetchProviders()
})

function resetForm() {
  form.value = {
    name: '',
    provider_type: 'openai',
    api_base_url: null,
    api_key: null,
    model_name: 'gpt-4o',
    temperature: 0.3,
    max_tokens: 4096,
    is_default: false,
  }
  error.value = ''
}

function openAddDialog() {
  resetForm()
  showAddDialog.value = true
}

function openEditDialog(provider: AiProvider) {
  editingProvider.value = provider
  form.value = {
    name: provider.name,
    provider_type: provider.provider_type as any,
    api_base_url: provider.api_base_url,
    api_key: null,
    model_name: provider.model_name,
    temperature: provider.temperature,
    max_tokens: provider.max_tokens,
    is_default: provider.is_default,
  }
  error.value = ''
  showEditDialog.value = true
}

function onProviderTypeChange() {
  form.value.model_name = defaultModels[form.value.provider_type] || ''
}

async function handleAdd() {
  loading.value = true
  error.value = ''
  try {
    await aiStore.addProvider(form.value)
    showAddDialog.value = false
  } catch (e: any) {
    error.value = e.response?.data?.detail || t('common.error')
  } finally {
    loading.value = false
  }
}

async function handleEdit() {
  if (!editingProvider.value) return
  loading.value = true
  error.value = ''
  try {
    const data: any = { ...form.value }
    if (!data.api_key) delete data.api_key
    await aiStore.editProvider(editingProvider.value.id, data)
    showEditDialog.value = false
  } catch (e: any) {
    error.value = e.response?.data?.detail || t('common.error')
  } finally {
    loading.value = false
  }
}

async function handleDelete(provider: AiProvider) {
  if (!confirm(t('ai.confirmDeleteProvider', { name: provider.name }))) return
  try {
    await aiStore.removeProvider(provider.id)
  } catch (e: any) {
    error.value = e.response?.data?.detail || t('common.error')
  }
}

async function handleSetDefault(provider: AiProvider) {
  try {
    await aiStore.editProvider(provider.id, { is_default: true })
  } catch {
    // ignore
  }
}
</script>

<template>
  <div class="provider-config">
    <div class="section-header">
      <h3>{{ t('ai.providers') }}</h3>
      <BaseButton size="sm" @click="openAddDialog">+ {{ t('ai.addProvider') }}</BaseButton>
    </div>

    <p v-if="!aiStore.hasProviders" class="text-muted">
      {{ t('ai.noProviders') }}
    </p>

    <table v-else class="data-table">
      <thead>
        <tr>
          <th>{{ t('common.name') }}</th>
          <th>{{ t('ai.providerType') }}</th>
          <th>{{ t('ai.model') }}</th>
          <th>{{ t('ai.apiKey') }}</th>
          <th>{{ t('ai.default') }}</th>
          <th>{{ t('common.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in aiStore.providers" :key="p.id">
          <td>{{ p.name }}</td>
          <td>
            <span class="badge badge-info">{{ p.provider_type }}</span>
          </td>
          <td>{{ p.model_name }}</td>
          <td>
            <span :class="p.has_api_key ? 'text-success' : 'text-muted'">
              {{ p.has_api_key ? '***' : '-' }}
            </span>
          </td>
          <td>
            <span v-if="p.is_default" class="badge badge-success">{{ t('ai.default') }}</span>
            <button v-else class="btn-link text-sm" @click="handleSetDefault(p)">
              {{ t('ai.setDefault') }}
            </button>
          </td>
          <td class="actions">
            <button class="btn-icon" :title="t('common.edit')" @click="openEditDialog(p)">&#9998;</button>
            <button class="btn-icon text-danger" :title="t('common.delete')" @click="handleDelete(p)">&times;</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Add Dialog -->
    <BaseModal v-model="showAddDialog" :title="t('ai.addProvider')" size="md">
      <div v-if="error" class="alert alert-danger mb-4">{{ error }}</div>
      <div class="form-grid">
        <div class="form-group">
          <label>{{ t('common.name') }}</label>
          <input v-model="form.name" class="form-input" :placeholder="t('ai.providerNamePlaceholder')" />
        </div>
        <div class="form-group">
          <label>{{ t('ai.providerType') }}</label>
          <select v-model="form.provider_type" class="form-select" @change="onProviderTypeChange">
            <option v-for="pt in providerTypes" :key="pt.value" :value="pt.value">{{ pt.label }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>{{ t('ai.model') }}</label>
          <input v-model="form.model_name" class="form-input" />
        </div>
        <div class="form-group">
          <label>{{ t('ai.apiKey') }}</label>
          <input v-model="form.api_key" type="password" class="form-input" :placeholder="t('ai.apiKeyPlaceholder')" />
        </div>
        <div class="form-group">
          <label>{{ t('ai.baseUrl') }} <span class="text-muted text-sm">({{ t('common.optional') }})</span></label>
          <input v-model="form.api_base_url" class="form-input" placeholder="https://..." />
        </div>
        <div class="form-group">
          <label>{{ t('ai.temperature') }}</label>
          <input v-model.number="form.temperature" type="number" step="0.1" min="0" max="2" class="form-input" />
        </div>
        <div class="form-group">
          <label>{{ t('ai.maxTokens') }}</label>
          <input v-model.number="form.max_tokens" type="number" min="256" max="128000" class="form-input" />
        </div>
        <div class="form-group">
          <label class="checkbox-label">
            <input v-model="form.is_default" type="checkbox" />
            {{ t('ai.setAsDefault') }}
          </label>
        </div>
      </div>
      <template #footer>
        <BaseButton variant="secondary" @click="showAddDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton :loading="loading" @click="handleAdd">{{ t('common.save') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Edit Dialog -->
    <BaseModal v-model="showEditDialog" :title="t('ai.editProvider')" size="md">
      <div v-if="error" class="alert alert-danger mb-4">{{ error }}</div>
      <div class="form-grid">
        <div class="form-group">
          <label>{{ t('common.name') }}</label>
          <input v-model="form.name" class="form-input" />
        </div>
        <div class="form-group">
          <label>{{ t('ai.providerType') }}</label>
          <select v-model="form.provider_type" class="form-select" @change="onProviderTypeChange">
            <option v-for="pt in providerTypes" :key="pt.value" :value="pt.value">{{ pt.label }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>{{ t('ai.model') }}</label>
          <input v-model="form.model_name" class="form-input" />
        </div>
        <div class="form-group">
          <label>{{ t('ai.apiKey') }} <span class="text-muted text-sm">({{ t('ai.leaveBlankKeep') }})</span></label>
          <input v-model="form.api_key" type="password" class="form-input" />
        </div>
        <div class="form-group">
          <label>{{ t('ai.baseUrl') }}</label>
          <input v-model="form.api_base_url" class="form-input" placeholder="https://..." />
        </div>
        <div class="form-group">
          <label>{{ t('ai.temperature') }}</label>
          <input v-model.number="form.temperature" type="number" step="0.1" min="0" max="2" class="form-input" />
        </div>
        <div class="form-group">
          <label>{{ t('ai.maxTokens') }}</label>
          <input v-model.number="form.max_tokens" type="number" min="256" max="128000" class="form-input" />
        </div>
        <div class="form-group">
          <label class="checkbox-label">
            <input v-model="form.is_default" type="checkbox" />
            {{ t('ai.setAsDefault') }}
          </label>
        </div>
      </div>
      <template #footer>
        <BaseButton variant="secondary" @click="showEditDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton :loading="loading" @click="handleEdit">{{ t('common.save') }}</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.provider-config {
  margin-top: 8px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-navy);
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-group label {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
}

.checkbox-label {
  flex-direction: row !important;
  align-items: center;
  gap: 8px !important;
  cursor: pointer;
}

.actions {
  display: flex;
  gap: 6px;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  transition: background 0.15s;
}

.btn-icon:hover {
  background: var(--color-border-light);
}

.btn-link {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-primary);
  text-decoration: underline;
  font-size: 13px;
}

.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge-info {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.badge-success {
  background: #e8f5e9;
  color: var(--color-success);
}

.text-success { color: var(--color-success); }
.text-danger { color: var(--color-danger); }
.text-sm { font-size: 12px; }

.alert-danger {
  background: #fce4e4;
  color: var(--color-danger);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.mb-4 { margin-bottom: 16px; }
</style>
