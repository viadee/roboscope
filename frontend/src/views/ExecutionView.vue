<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useExecutionStore } from '@/stores/execution.store'
import { useReposStore } from '@/stores/repos.store'
import { useEnvironmentsStore } from '@/stores/environments.store'
import { useAuthStore } from '@/stores/auth.store'
import { useReportsStore } from '@/stores/reports.store'
import { useToast } from '@/composables/useToast'
import { getRunOutput } from '@/api/execution.api'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import RunDetailPanel from '@/components/execution/RunDetailPanel.vue'
import CronEditor from '@/components/execution/CronEditor.vue'
import { useRouter } from 'vue-router'
import { formatDuration } from '@/utils/formatDuration'
import { formatTimeAgo } from '@/utils/formatDate'
import type { ExecutionRun, Schedule, RunnerType } from '@/types/domain.types'

const route = useRoute()
const router = useRouter()
const execution = useExecutionStore()
const repos = useReposStore()
const envs = useEnvironmentsStore()
const auth = useAuthStore()
const reportsStore = useReportsStore()
const toast = useToast()
const { t } = useI18n()

const activeTab = ref<'runs' | 'schedules'>('runs')

// Schedule management
const showScheduleDialog = ref(false)
const editingSchedule = ref<Schedule | null>(null)
const scheduleForm = ref({
  name: '',
  cron_expression: '0 8 * * *',
  repository_id: 0,
  environment_id: null as number | null,
  target_path: '.',
  branch: 'main',
  runner_type: 'subprocess' as RunnerType,
})
const savingSchedule = ref(false)

function openScheduleDialog(schedule?: Schedule) {
  if (schedule) {
    editingSchedule.value = schedule
    scheduleForm.value = {
      name: schedule.name,
      cron_expression: schedule.cron_expression,
      repository_id: schedule.repository_id,
      environment_id: schedule.environment_id,
      target_path: schedule.target_path,
      branch: schedule.branch,
      runner_type: schedule.runner_type,
    }
  } else {
    editingSchedule.value = null
    scheduleForm.value = {
      name: '',
      cron_expression: '0 8 * * *',
      repository_id: 0,
      environment_id: null,
      target_path: '.',
      branch: 'main',
      runner_type: 'subprocess' as RunnerType,
    }
  }
  showScheduleDialog.value = true
}

async function saveSchedule() {
  savingSchedule.value = true
  try {
    if (editingSchedule.value) {
      await execution.updateSchedule(editingSchedule.value.id, scheduleForm.value)
      toast.success(t('schedule.toasts.updated'))
    } else {
      await execution.addSchedule(scheduleForm.value)
      toast.success(t('schedule.toasts.created'))
    }
    showScheduleDialog.value = false
  } catch (e: any) {
    toast.error(t('common.error'), e.response?.data?.detail || t('schedule.toasts.saveError'))
  } finally {
    savingSchedule.value = false
  }
}

async function deleteSchedule(id: number) {
  if (!confirm(t('schedule.confirmDelete'))) return
  try {
    await execution.removeSchedule(id)
    toast.success(t('schedule.toasts.deleted'))
  } catch {
    toast.error(t('schedule.toasts.deleteError'))
  }
}

async function toggleScheduleActive(id: number) {
  try {
    await execution.toggleSchedule(id)
  } catch {
    toast.error(t('common.error'))
  }
}

const showRunDialog = ref(false)
const runForm = ref({
  repository_id: 0,
  environment_id: null as number | null,
  target_path: '.',
  branch: 'main',
  runner_type: 'subprocess',
  timeout_seconds: 3600,
})
const starting = ref(false)
const showEnvPrompt = ref(false)
const settingUpDefaultEnv = ref(false)

// Selected run for detail panel
const selectedRunId = ref<number | null>(null)

// Output viewer
const showOutputModal = ref(false)
const outputContent = ref('')
const outputStream = ref<'stdout' | 'stderr'>('stdout')
const outputRunId = ref<number | null>(null)
const loadingOutput = ref(false)

// Delete all reports
const deletingReports = ref(false)

// Poll for updates when there are active (pending/running) runs
let pollTimer: ReturnType<typeof setInterval> | null = null

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    if (execution.activeRuns.length > 0) {
      execution.fetchRuns()
    } else {
      stopPolling()
    }
  }, 5000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

watch(() => execution.activeRuns.length, (count) => {
  if (count > 0) startPolling()
  else stopPolling()
})

onMounted(async () => {
  await Promise.all([
    execution.fetchRuns(),
    execution.fetchSchedules(),
    repos.fetchRepos(),
    envs.fetchEnvironments(),
  ])
  // Auto-select run from query param (e.g. /runs?run=42)
  const runParam = route.query.run
  if (runParam) {
    const runId = Number(runParam)
    if (runId && execution.runs.find(r => r.id === runId)) {
      selectedRunId.value = runId
    }
  }
  // Start polling if there are already active runs
  if (execution.activeRuns.length > 0) startPolling()
})

onUnmounted(() => {
  stopPolling()
})

function toggleRunDetail(run: ExecutionRun) {
  if (selectedRunId.value === run.id) {
    selectedRunId.value = null
  } else {
    selectedRunId.value = run.id
  }
}

function getSelectedRun(): ExecutionRun | undefined {
  return execution.runs.find(r => r.id === selectedRunId.value)
}

function handleStartClick() {
  if (!runForm.value.environment_id && envs.environments.length === 0) {
    showEnvPrompt.value = true
    return
  }
  doStartRun()
}

async function doStartRun() {
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

async function deleteAllReports() {
  if (!confirm(t('reports.confirmDeleteAll'))) return
  deletingReports.value = true
  try {
    const result = await reportsStore.deleteAllReports()
    toast.success(t('reports.toasts.deleted'), t('reports.toasts.deletedMsg', { deleted: result.deleted, dirs: result.dirs_cleaned }))
  } catch {
    toast.error(t('common.error'), t('reports.toasts.deleteError'))
  } finally {
    deletingReports.value = false
  }
}

function changePage(page: number) {
  selectedRunId.value = null
  execution.fetchRuns({ page })
}

function changePageSize(size: number) {
  execution.pageSize = size
  selectedRunId.value = null
  execution.fetchRuns({ page: 1 })
}

async function setupDefaultFromExecution() {
  settingUpDefaultEnv.value = true
  try {
    const env = await envs.setupDefault()
    runForm.value.environment_id = env.id
    showEnvPrompt.value = false
    toast.success(t('environments.setupDefault.toastSuccess'))
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

function skipEnvAndStart() {
  showEnvPrompt.value = false
  doStartRun()
}

function getEnvName(envId: number | null): string {
  if (!envId) return '-'
  const env = envs.environments.find(e => e.id === envId)
  return env?.name || '-'
}

function getRepoName(repoId: number): string {
  const repo = repos.repos.find(r => r.id === repoId)
  return repo?.name || `#${repoId}`
}

function openInExplorer(run: ExecutionRun, event: Event) {
  event.stopPropagation()
  router.push(`/explorer/${run.repository_id}`)
}

function retryFromTable(run: ExecutionRun, event: Event) {
  event.stopPropagation()
  retryRun(run.id)
}

function isTerminal(status: string): boolean {
  return ['passed', 'failed', 'error', 'cancelled', 'timeout'].includes(status)
}
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('execution.title') }}</h1>
      <div class="flex gap-2">
        <template v-if="activeTab === 'runs'">
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
          <BaseButton
            v-if="auth.hasMinRole('admin')"
            variant="danger"
            size="sm"
            :loading="deletingReports"
            @click="deleteAllReports"
          >
            {{ t('execution.deleteAllReports') }}
          </BaseButton>
        </template>
        <template v-else>
          <BaseButton v-if="auth.hasMinRole('editor')" @click="openScheduleDialog()">
            {{ t('schedule.addSchedule') }}
          </BaseButton>
        </template>
      </div>
    </div>

    <!-- Tab Navigation -->
    <div class="tab-nav">
      <button class="tab-btn" :class="{ active: activeTab === 'runs' }" @click="activeTab = 'runs'">
        {{ t('schedule.tabRuns') }}
      </button>
      <button class="tab-btn" :class="{ active: activeTab === 'schedules' }" @click="activeTab = 'schedules'">
        {{ t('schedule.tabSchedules') }}
        <span v-if="execution.schedules.length" class="tab-badge">{{ execution.schedules.length }}</span>
      </button>
    </div>

    <BaseSpinner v-if="execution.loading" />

    <!-- Runs Tab -->
    <div v-show="activeTab === 'runs' && !execution.loading" class="card">
      <div v-if="execution.runs.length" class="table-responsive">
      <table class="data-table">
        <thead>
          <tr>
            <th>{{ t('common.id') }}</th>
            <th>{{ t('execution.target') }}</th>
            <th>{{ t('execution.runDialog.environment') }}</th>
            <th>{{ t('common.status') }}</th>
            <th>{{ t('common.created') }}</th>
            <th>{{ t('common.duration') }}</th>
            <th style="width: 70px;"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="run in execution.runs"
            :key="run.id"
            class="clickable-row"
            :class="{ 'selected-row': selectedRunId === run.id }"
            @click="toggleRunDetail(run)"
          >
            <td>#{{ run.id }}</td>
            <td class="text-sm" style="max-width: 250px; overflow: hidden; text-overflow: ellipsis;">
              {{ run.target_path }}
            </td>
            <td class="text-sm text-muted">{{ getEnvName(run.environment_id) }}</td>
            <td>
              <span class="status-cell">
                <span v-if="run.status === 'running' || run.status === 'pending'" class="inline-spinner"></span>
                <BaseBadge :status="run.status" />
              </span>
            </td>
            <td class="text-muted text-sm">{{ formatTimeAgo(run.created_at) }}</td>
            <td>{{ formatDuration(run.duration_seconds) }}</td>
            <td class="row-actions">
              <button
                v-if="isTerminal(run.status) && auth.hasMinRole('runner')"
                class="icon-btn"
                :title="t('common.retry')"
                @click="retryFromTable(run, $event)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
              </button>
              <button
                class="icon-btn"
                :title="t('execution.openInExplorer')"
                @click="openInExplorer(run, $event)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      </div>
      <p v-else class="text-muted text-center p-4">{{ t('execution.noRuns') }}</p>

      <!-- Pagination -->
      <div v-if="execution.runs.length" class="pagination">
        <div class="page-size-selector">
          <label class="text-sm text-muted">{{ t('execution.rowsPerPage') }}</label>
          <select
            class="page-size-select"
            :value="execution.pageSize"
            @change="changePageSize(Number(($event.target as HTMLSelectElement).value))"
          >
            <option :value="5">5</option>
            <option :value="10">10</option>
            <option :value="20">20</option>
          </select>
        </div>
        <div class="page-nav" v-if="execution.totalRuns > execution.pageSize">
          <BaseButton
            variant="ghost" size="sm"
            :disabled="execution.currentPage <= 1"
            @click="changePage(execution.currentPage - 1)"
          >
            {{ t('common.prevPage') }}
          </BaseButton>
          <span class="text-sm text-muted">
            {{ t('common.pageOf', { current: execution.currentPage, total: Math.ceil(execution.totalRuns / execution.pageSize) }) }}
          </span>
          <BaseButton
            variant="ghost" size="sm"
            :disabled="execution.currentPage * execution.pageSize >= execution.totalRuns"
            @click="changePage(execution.currentPage + 1)"
          >
            {{ t('common.nextPage') }}
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- Detail Panel -->
    <div v-if="selectedRunId && getSelectedRun()" class="card detail-card">
      <RunDetailPanel
        :run="getSelectedRun()!"
        @cancel="cancelRun"
        @retry="retryRun"
        @view-output="viewOutput"
      />
    </div>

    <!-- Schedules Tab -->
    <div v-show="activeTab === 'schedules' && !execution.loading">
      <div v-if="execution.schedules.length" class="card">
        <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ t('common.name') }}</th>
              <th>{{ t('schedule.cronExpression') }}</th>
              <th>{{ t('schedule.target') }}</th>
              <th>{{ t('common.status') }}</th>
              <th style="width: 120px;">{{ t('common.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="schedule in execution.schedules" :key="schedule.id">
              <td><strong>{{ schedule.name }}</strong></td>
              <td><code class="cron-code">{{ schedule.cron_expression }}</code></td>
              <td class="text-sm text-muted">
                {{ getRepoName(schedule.repository_id) }} / {{ schedule.target_path }}
              </td>
              <td>
                <span class="schedule-status" :class="{ active: schedule.is_active, inactive: !schedule.is_active }">
                  {{ schedule.is_active ? t('schedule.active') : t('schedule.inactive') }}
                </span>
              </td>
              <td class="row-actions">
                <button
                  class="icon-btn"
                  :title="schedule.is_active ? t('schedule.pause') : t('schedule.resume')"
                  @click="toggleScheduleActive(schedule.id)"
                >
                  <span v-if="schedule.is_active">&#9646;&#9646;</span>
                  <span v-else>&#9654;</span>
                </button>
                <button
                  v-if="auth.hasMinRole('editor')"
                  class="icon-btn"
                  :title="t('common.edit')"
                  @click="openScheduleDialog(schedule)"
                >
                  &#9998;
                </button>
                <button
                  v-if="auth.hasMinRole('editor')"
                  class="icon-btn icon-btn-danger"
                  :title="t('common.delete')"
                  @click="deleteSchedule(schedule.id)"
                >
                  &#10005;
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        </div>
      </div>
      <div v-else class="card">
        <p class="text-muted text-center p-4">{{ t('schedule.noSchedules') }}</p>
      </div>
    </div>

    <!-- Schedule Dialog -->
    <BaseModal v-model="showScheduleDialog" :title="editingSchedule ? t('schedule.editDialog') : t('schedule.addDialog')" size="lg">
      <form @submit.prevent="saveSchedule">
        <div class="form-group mb-3">
          <label class="form-label">{{ t('common.name') }}</label>
          <input v-model="scheduleForm.name" class="form-input" :placeholder="t('schedule.namePlaceholder')" required />
        </div>
        <div class="form-group mb-3">
          <label class="form-label">{{ t('schedule.cronExpression') }}</label>
          <CronEditor v-model="scheduleForm.cron_expression" />
        </div>
        <div class="grid grid-2">
          <div class="form-group">
            <label class="form-label">{{ t('execution.runDialog.repository') }}</label>
            <select v-model="scheduleForm.repository_id" class="form-select" required>
              <option :value="0" disabled>{{ t('execution.runDialog.selectRepo') }}</option>
              <option v-for="repo in repos.repos" :key="repo.id" :value="repo.id">{{ repo.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('execution.runDialog.environment') }}</label>
            <select v-model="scheduleForm.environment_id" class="form-select">
              <option :value="null">{{ t('execution.runDialog.noEnv') }}</option>
              <option v-for="env in envs.environments" :key="env.id" :value="env.id">{{ env.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('execution.runDialog.targetPath') }}</label>
            <input v-model="scheduleForm.target_path" class="form-input" :placeholder="t('execution.runDialog.targetPlaceholder')" required />
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('execution.branch') }}</label>
            <input v-model="scheduleForm.branch" class="form-input" placeholder="main" />
          </div>
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showScheduleDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton :loading="savingSchedule" @click="saveSchedule">{{ t('common.save') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- New Run Dialog -->
    <BaseModal v-model="showRunDialog" :title="t('execution.runDialog.title')" size="lg">
      <form @submit.prevent="handleStartClick">
        <div class="grid grid-2">
          <div class="form-group">
            <label class="form-label">{{ t('execution.runDialog.repository') }}</label>
            <select v-model="runForm.repository_id" class="form-select" required>
              <option :value="0" disabled>{{ t('execution.runDialog.selectRepo') }}</option>
              <option v-for="repo in repos.repos" :key="repo.id" :value="repo.id">{{ repo.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('execution.runDialog.environment') }}</label>
            <select v-model="runForm.environment_id" class="form-select">
              <option :value="null">{{ t('execution.runDialog.noEnv') }}</option>
              <option v-for="env in envs.environments" :key="env.id" :value="env.id">{{ env.name }}</option>
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
        <BaseButton :loading="starting" @click="handleStartClick">{{ t('common.start') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Environment Setup Prompt -->
    <BaseModal v-model="showEnvPrompt" :title="t('execution.envPrompt.title')">
      <div class="env-prompt-body">
        <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="env-prompt-icon">
          <path d="M16.5 9.4l-9-5.19M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
          <line x1="12" y1="22.08" x2="12" y2="12"/>
        </svg>
        <p>{{ t('execution.envPrompt.message') }}</p>
        <div class="env-prompt-packages">
          <span class="env-prompt-tag">robotframework</span>
          <span class="env-prompt-tag">seleniumlibrary</span>
          <span class="env-prompt-tag">browser</span>
          <span class="env-prompt-tag">requests</span>
        </div>
      </div>
      <template #footer>
        <BaseButton variant="secondary" @click="skipEnvAndStart">{{ t('execution.envPrompt.skip') }}</BaseButton>
        <BaseButton :loading="settingUpDefaultEnv" @click="setupDefaultFromExecution">{{ t('execution.envPrompt.setup') }}</BaseButton>
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
.clickable-row {
  cursor: pointer;
  transition: background-color 0.15s;
}

.clickable-row:hover {
  background: var(--color-bg-hover, #f8fafc);
}

.selected-row {
  background: rgba(60, 181, 161, 0.08) !important;
  border-left: 3px solid var(--color-primary, #3B7DD8);
}

.detail-card {
  margin-top: 16px;
  padding: 0;
  overflow: hidden;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-top: 1px solid var(--color-border-light);
}

.page-size-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-size-select {
  padding: 4px 8px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-sm, 6px);
  font-size: 13px;
  background: var(--color-bg-card, #ffffff);
  color: var(--color-text);
  cursor: pointer;
}

.page-size-select:focus {
  outline: none;
  border-color: var(--color-primary, #3B7DD8);
  box-shadow: 0 0 0 2px rgba(60, 181, 161, 0.15);
}

.page-nav {
  display: flex;
  align-items: center;
  gap: 12px;
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

.env-prompt-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 8px 0;
  gap: 12px;
}

.env-prompt-icon {
  color: var(--color-primary, #3B7DD8);
}

.env-prompt-body p {
  color: var(--color-text-muted, #5C688C);
  font-size: 14px;
  max-width: 380px;
  line-height: 1.5;
}

.env-prompt-packages {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
}

.env-prompt-tag {
  display: inline-block;
  padding: 3px 10px;
  background: rgba(60, 181, 161, 0.1);
  color: var(--color-primary, #3B7DD8);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.row-actions {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: var(--radius-sm, 6px);
  background: transparent;
  color: var(--color-text-muted, #5C688C);
  cursor: pointer;
  transition: all 0.15s;
}

.icon-btn:hover {
  background: var(--color-bg-hover, #f0f2f5);
  color: var(--color-primary, #3B7DD8);
}

.status-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.inline-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--color-border, #e2e8f0);
  border-top-color: var(--color-primary, #3B7DD8);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Tabs */
.tab-nav {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--color-border, #e2e8f0);
  margin-bottom: 20px;
}

.tab-btn {
  padding: 10px 20px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-muted);
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tab-btn:hover {
  color: var(--color-text);
  background: var(--color-bg-hover, #f8fafc);
}

.tab-btn.active {
  color: var(--color-primary, #3B7DD8);
  border-bottom-color: var(--color-primary, #3B7DD8);
}

.tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: var(--color-border-light, #edf2f7);
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
}

.tab-btn.active .tab-badge {
  background: rgba(60, 181, 161, 0.15);
  color: var(--color-primary);
}

/* Schedule table */
.cron-code {
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  padding: 2px 8px;
  background: var(--color-bg, #f4f7fa);
  border-radius: 4px;
  color: var(--color-primary);
}

.schedule-status {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.schedule-status.active {
  background: rgba(60, 181, 161, 0.12);
  color: var(--color-success, #22c55e);
}

.schedule-status.inactive {
  background: var(--color-border-light, #edf2f7);
  color: var(--color-text-muted);
}

.icon-btn-danger:hover {
  color: var(--color-danger, #ef4444) !important;
}

.mb-3 {
  margin-bottom: 16px;
}
</style>
