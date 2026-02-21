<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAiStore } from '@/stores/ai.store'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import DiffPreview from './DiffPreview.vue'

const props = defineProps<{
  modelValue: boolean
  repoId: number
  filePath: string
  mode: 'generate' | 'reverse'
  existingContent?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  accepted: [targetPath: string]
}>()

const { t } = useI18n()
const aiStore = useAiStore()

const selectedProviderId = ref<number | null>(null)
const force = ref(false)
const error = ref('')
const accepted = ref(false)
const rfMcpChecked = ref(false)

const isRunning = computed(() =>
  aiStore.activeJob?.status === 'pending' || aiStore.activeJob?.status === 'running'
)
const isCompleted = computed(() => aiStore.activeJob?.status === 'completed')
const isFailed = computed(() => aiStore.activeJob?.status === 'failed')
const resultPreview = computed(() => aiStore.activeJob?.result_preview || '')

watch(() => props.modelValue, async (v) => {
  if (v) {
    error.value = ''
    accepted.value = false
    rfMcpChecked.value = false
    aiStore.activeJob = null
    aiStore.fetchProviders()
    if (aiStore.defaultProvider) {
      selectedProviderId.value = aiStore.defaultProvider.id
    }
    await aiStore.fetchRfKnowledgeStatus()
    rfMcpChecked.value = true
  } else {
    aiStore.stopPolling()
  }
})

async function handleStart() {
  error.value = ''
  try {
    if (props.mode === 'generate') {
      await aiStore.generate(
        props.repoId,
        props.filePath,
        selectedProviderId.value || undefined,
        force.value,
      )
    } else {
      await aiStore.reverse(
        props.repoId,
        props.filePath,
        selectedProviderId.value || undefined,
      )
    }
  } catch (e: any) {
    if (e.response?.status === 409) {
      error.value = e.response.data.detail
    } else {
      error.value = e.response?.data?.detail || t('common.error')
    }
  }
}

async function handleAccept() {
  if (!aiStore.activeJob) return
  try {
    const result = await aiStore.acceptJob(aiStore.activeJob.id)
    accepted.value = true
    emit('accepted', result.target_path)
    setTimeout(() => emit('update:modelValue', false), 1000)
  } catch (e: any) {
    error.value = e.response?.data?.detail || t('common.error')
  }
}

function close() {
  aiStore.stopPolling()
  emit('update:modelValue', false)
}
</script>

<template>
  <BaseModal :model-value="modelValue" @update:model-value="close"
    :title="mode === 'generate' ? t('ai.generateTitle') : t('ai.reverseTitle')" size="lg">

    <!-- Config section (before start) -->
    <div v-if="!aiStore.activeJob" class="config-section">
      <div class="form-group">
        <label>{{ t('ai.sourceFile') }}</label>
        <code class="file-path">{{ filePath }}</code>
      </div>

      <div class="form-group">
        <label>{{ t('ai.provider') }}</label>
        <select v-model="selectedProviderId" class="form-select">
          <option v-for="p in aiStore.providers" :key="p.id" :value="p.id">
            {{ p.name }} ({{ p.model_name }})
          </option>
        </select>
        <p v-if="!aiStore.hasProviders" class="text-warning text-sm mt-1">
          {{ t('ai.noProvidersHint') }}
        </p>
      </div>

      <div v-if="mode === 'generate'" class="form-group">
        <label class="checkbox-label">
          <input v-model="force" type="checkbox" />
          {{ t('ai.forceOverwrite') }}
        </label>
      </div>

      <!-- rf-mcp status -->
      <div v-if="rfMcpChecked" class="rf-mcp-status" :class="{ active: aiStore.rfMcpAvailable }">
        <span class="rf-mcp-dot"></span>
        <span v-if="aiStore.rfMcpAvailable" class="rf-mcp-text">
          {{ t('ai.rfMcpConnected') }}
        </span>
        <span v-else class="rf-mcp-text">
          {{ t('ai.rfMcpNotConfigured') }}
        </span>
        <a href="https://github.com/manykarim/rf-mcp" target="_blank" rel="noopener noreferrer" class="rf-mcp-link">
          rf-mcp
        </a>
        <span class="rf-mcp-author">{{ t('ai.rfMcpBy') }}</span>
      </div>

      <div v-if="error" class="alert alert-danger">{{ error }}</div>
    </div>

    <!-- Progress -->
    <div v-else-if="isRunning" class="progress-section">
      <div class="spinner-container">
        <div class="spinner"></div>
        <p>{{ t('ai.generating') }}</p>
      </div>
      <p class="text-muted text-sm">{{ t('ai.generatingHint') }}</p>
    </div>

    <!-- Error -->
    <div v-else-if="isFailed" class="error-section">
      <div class="alert alert-danger">
        <strong>{{ t('ai.generationFailed') }}</strong><br />
        {{ aiStore.activeJob?.error_message }}
      </div>
    </div>

    <!-- Result -->
    <div v-else-if="isCompleted && !accepted" class="result-section">
      <div class="result-header">
        <span class="badge badge-success">{{ t('ai.completed') }}</span>
        <span v-if="aiStore.activeJob?.token_usage" class="text-muted text-sm">
          {{ aiStore.activeJob.token_usage }} tokens
        </span>
      </div>
      <DiffPreview
        :before="existingContent || ''"
        :after="resultPreview"
        :file-name="aiStore.activeJob?.target_path || filePath"
      />
    </div>

    <!-- Accepted -->
    <div v-else-if="accepted" class="accepted-section">
      <p class="text-success">{{ t('ai.fileWritten') }}</p>
    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="close">
        {{ isCompleted && !accepted ? t('ai.reject') : t('common.cancel') }}
      </BaseButton>
      <BaseButton v-if="!aiStore.activeJob" :disabled="!aiStore.hasProviders" @click="handleStart">
        {{ mode === 'generate' ? t('ai.startGenerate') : t('ai.startReverse') }}
      </BaseButton>
      <BaseButton v-if="isCompleted && !accepted" @click="handleAccept">
        {{ t('ai.acceptWrite') }}
      </BaseButton>
      <BaseButton v-if="isFailed" @click="handleStart">
        {{ t('ai.retry') }}
      </BaseButton>
    </template>
  </BaseModal>
</template>

<style scoped>
.config-section, .progress-section, .error-section, .result-section, .accepted-section {
  min-height: 120px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 4px;
  color: var(--color-text);
}

.file-path {
  display: inline-block;
  padding: 4px 10px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
}

.spinner-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  gap: 12px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge-success {
  background: #e8f5e9;
  color: var(--color-success);
}

.alert-danger {
  background: #fce4e4;
  color: var(--color-danger);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.text-warning { color: var(--color-warning); }
.text-success { color: var(--color-success); font-weight: 600; }
.text-muted { color: var(--color-text-muted); }
.text-sm { font-size: 12px; }
.mt-1 { margin-top: 4px; }

/* rf-mcp status */
.rf-mcp-status {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-text-muted);
  margin-bottom: 12px;
}

.rf-mcp-status.active {
  background: #e8f5e9;
  border-color: #c8e6c9;
}

.rf-mcp-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-muted);
  flex-shrink: 0;
}

.rf-mcp-status.active .rf-mcp-dot {
  background: var(--color-success, #2e7d32);
}

.rf-mcp-text {
  flex-shrink: 0;
}

.rf-mcp-link {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 600;
}

.rf-mcp-link:hover {
  text-decoration: underline;
}

.rf-mcp-author {
  color: var(--color-text-muted);
  font-size: 11px;
}
</style>
