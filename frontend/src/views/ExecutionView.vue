<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useExecutionStore } from '@/stores/execution.store'
import { useReposStore } from '@/stores/repos.store'
import { useEnvironmentsStore } from '@/stores/environments.store'
import { useAuthStore } from '@/stores/auth.store'
import { useToast } from '@/composables/useToast'
import { getRunOutput, getRunReport } from '@/api/execution.api'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { formatDuration } from '@/utils/formatDuration'
import { formatTimeAgo } from '@/utils/formatDate'

const execution = useExecutionStore()
const repos = useReposStore()
const envs = useEnvironmentsStore()
const auth = useAuthStore()
const toast = useToast()
const { t } = useI18n()

const showRunDialog = ref(false)
const runForm = ref({
  repository_id: 0,
  target_path: '.',
  branch: 'main',
  runner_type: 'subprocess',
  timeout_seconds: 3600,
})
const starting = ref(false)

// Output viewer
const showOutputModal = ref(false)
const outputContent = ref('')
const outputStream = ref<'stdout' | 'stderr'>('stdout')
const outputRunId = ref<number | null>(null)
const loadingOutput = ref(false)

// Report cache
const reportMap = ref<Record<number, number | null>>({})

onMounted(async () => {
  await Promise.all([
    execution.fetchRuns(),
    repos.fetchRepos(),
    envs.fetchEnvironments(),
  ])
  // Fetch report IDs for completed runs
  for (const run of execution.runs) {
    if (['passed', 'failed'].includes(run.status)) {
      fetchReportId(run.id)
    }
  }
})

async function fetchReportId(runId: number) {
  if (reportMap.value[runId] !== undefined) return
  try {
    const data = await getRunReport(runId)
    reportMap.value[runId] = data.report_id
  } catch {
    reportMap.value[runId] = null
  }
}

async function startRun() {
  starting.value = true
  try {
    const run = await execution.startRun(runForm.value)
    toast.success(t('execution.toasts.started'), t('execution.toasts.startedMsg', { id: run.id }))
    showRunDialog.value = false
  } catch (e: any) {
    toast.error(t('common.error'), e.response?.data?.detail || t('execution.toasts.startError'))
  } finally {
    starting.value = false
  }
}

async function cancelRun(id: number) {
  try {
    await execution.cancelRun(id)
    toast.info(t('execution.toasts.cancelled'))
  } catch {
    toast.error(t('execution.toasts.cancelFailed'))
  }
}

async function killAll() {
  try {
    const result = await execution.cancelAllRuns()
    if (result.cancelled > 0) {
      toast.success(t('execution.toasts.allCancelled'), t('execution.toasts.cancelledCount', { count: result.cancelled }))
    } else {
      toast.info(t('execution.toasts.noActiveRuns'), t('execution.toasts.noActiveRunsMsg'))
    }
  } catch {
    toast.error(t('common.error'), t('execution.toasts.cancelAllError'))
  }
}

async function retryRun(id: number) {
  try {
    const newRun = await execution.retryRun(id)
    toast.success(t('execution.toasts.retryStarted'), t('execution.toasts.retryMsg', { id: newRun.id }))
  } catch {
    toast.error(t('execution.toasts.retryFailed'))
  }
}

async function viewOutput(runId: number, stream: 'stdout' | 'stderr' = 'stdout') {
  outputRunId.value = runId
  outputStream.value = stream
  loadingOutput.value = true
  showOutputModal.value = true
  try {
    outputContent.value = await getRunOutput(runId, stream)
    if (!outputContent.value) {
      outputContent.value = t('execution.noOutput', { stream })
    }
  } catch {
    outputContent.value = t('execution.outputError')
  } finally {
    loadingOutput.value = false
  }
}

async function switchStream(stream: 'stdout' | 'stderr') {
  if (!outputRunId.value) return
  await viewOutput(outputRunId.value, stream)
}

function changePage(page: number) {
  execution.fetchRuns({ page })
}

function isFinished(status: string) {
  return ['passed', 'failed', 'error', 'cancelled', 'timeout'].includes(status)
}
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('execution.title') }}</h1>
      <div class="flex gap-2">
        <BaseButton v-if="auth.hasMinRole('runner')" @click="showRunDialog = true">
          {{ t('execution.newRun') }}
        </BaseButton>
        <BaseButton
          v-if="auth.hasMinRole('runner') && execution.activeRuns.length > 0"
          variant="danger"
          @click="killAll"
        >
          {{ t('execution.cancelAll') }}
        </BaseButton>
      </div>
    </div>

    <BaseSpinner v-if="execution.loading" />

    <div v-else class="card">
      <table class="data-table" v-if="execution.runs.length">
        <thead>
          <tr>
            <th>{{ t('common.id') }}</th>
            <th>{{ t('execution.target') }}</th>
            <th>{{ t('execution.branch') }}</th>
            <th>{{ t('execution.runner') }}</th>
            <th>{{ t('common.status') }}</th>
            <th>{{ t('common.duration') }}</th>
            <th>{{ t('common.created') }}</th>
            <th>{{ t('common.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="run in execution.runs" :key="run.id">
            <td>#{{ run.id }}</td>
            <td class="text-sm" style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;">
              {{ run.target_path }}
            </td>
            <td class="text-sm">{{ run.branch }}</td>
            <td class="text-sm">{{ run.runner_type }}</td>
            <td><BaseBadge :status="run.status" /></td>
            <td>{{ formatDuration(run.duration_seconds) }}</td>
            <td class="text-muted text-sm">{{ formatTimeAgo(run.created_at) }}</td>
            <td>
              <div class="flex gap-1">
                <BaseButton
                  v-if="run.status === 'pending' || run.status === 'running'"
                  variant="danger" size="sm"
                  @click="cancelRun(run.id)"
                >
                  {{ t('common.cancel') }}
                </BaseButton>
                <BaseButton
                  v-if="run.status === 'failed' || run.status === 'error'"
                  variant="secondary" size="sm"
                  @click="retryRun(run.id)"
                >
                  {{ t('common.retry') }}
                </BaseButton>
                <!-- stdout / stderr viewer -->
                <BaseButton
                  v-if="isFinished(run.status)"
                  variant="ghost" size="sm"
                  @click="viewOutput(run.id)"
                >
                  Output
                </BaseButton>
                <!-- Report link -->
                <router-link
                  v-if="reportMap[run.id]"
                  :to="`/reports/${reportMap[run.id]}`"
                >
                  <BaseButton variant="ghost" size="sm">Report</BaseButton>
                </router-link>
                <span
                  v-else-if="['passed','failed'].includes(run.status) && reportMap[run.id] === undefined"
                  class="text-muted text-sm"
                  style="line-height: 28px"
                >...</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="text-muted text-center p-4">{{ t('execution.noRuns') }}</p>

      <!-- Pagination -->
      <div v-if="execution.totalRuns > 20" class="pagination">
        <BaseButton
          variant="ghost" size="sm"
          :disabled="execution.currentPage <= 1"
          @click="changePage(execution.currentPage - 1)"
        >
          {{ t('common.prevPage') }}
        </BaseButton>
        <span class="text-sm text-muted">
          {{ t('common.pageOf', { current: execution.currentPage, total: Math.ceil(execution.totalRuns / 20) }) }}
        </span>
        <BaseButton
          variant="ghost" size="sm"
          :disabled="execution.currentPage * 20 >= execution.totalRuns"
          @click="changePage(execution.currentPage + 1)"
        >
          {{ t('common.nextPage') }}
        </BaseButton>
      </div>
    </div>

    <!-- New Run Dialog -->
    <BaseModal v-model="showRunDialog" :title="t('execution.runDialog.title')" size="lg">
      <form @submit.prevent="startRun">
        <div class="grid grid-2">
          <div class="form-group">
            <label class="form-label">{{ t('execution.runDialog.repository') }}</label>
            <select v-model="runForm.repository_id" class="form-select" required>
              <option :value="0" disabled>{{ t('execution.runDialog.selectRepo') }}</option>
              <option v-for="repo in repos.repos" :key="repo.id" :value="repo.id">{{ repo.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('execution.branch') }}</label>
            <input v-model="runForm.branch" class="form-input" placeholder="main" />
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('execution.runDialog.targetPath') }}</label>
            <input v-model="runForm.target_path" class="form-input" :placeholder="t('execution.runDialog.targetPlaceholder')" required />
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('execution.runner') }}</label>
            <select v-model="runForm.runner_type" class="form-select">
              <option value="subprocess">Subprocess</option>
              <option value="docker">Docker</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('execution.runDialog.timeout') }}</label>
            <input v-model.number="runForm.timeout_seconds" type="number" class="form-input" min="30" max="86400" />
          </div>
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showRunDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton :loading="starting" @click="startRun">{{ t('common.start') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Output Viewer Modal -->
    <BaseModal v-model="showOutputModal" :title="t('execution.outputTitle', { id: outputRunId })" size="lg">
      <div class="output-tabs">
        <button
          class="output-tab"
          :class="{ active: outputStream === 'stdout' }"
          @click="switchStream('stdout')"
        >stdout</button>
        <button
          class="output-tab"
          :class="{ active: outputStream === 'stderr' }"
          @click="switchStream('stderr')"
        >stderr</button>
      </div>
      <div class="output-viewer">
        <BaseSpinner v-if="loadingOutput" />
        <pre v-else class="output-content">{{ outputContent }}</pre>
      </div>
      <template #footer>
        <BaseButton variant="secondary" size="sm" @click="showOutputModal = false">{{ t('common.close') }}</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 16px;
  border-top: 1px solid var(--color-border-light);
}

.output-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--color-border-light);
  margin-bottom: 0;
}

.output-tab {
  padding: 8px 20px;
  border: none;
  background: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  color: var(--color-text-muted);
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}

.output-tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.output-tab:hover {
  color: var(--color-text);
}

.output-viewer {
  max-height: 400px;
  overflow: auto;
  background: #1e1e2e;
  border-radius: 0 0 var(--radius-sm) var(--radius-sm);
}

.output-content {
  padding: 16px;
  margin: 0;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #cdd6f4;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
