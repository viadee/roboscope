<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useReportsStore } from '@/stores/reports.store'
import { getRunReport } from '@/api/execution.api'
import { getReportHtmlUrl, getReportZipUrl } from '@/api/reports.api'
import { useEnvironmentsStore } from '@/stores/environments.store'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import ReportXmlView from '@/components/report/ReportXmlView.vue'
import { formatDuration } from '@/utils/formatDuration'
import { formatDateTime } from '@/utils/formatDate'
import type { ExecutionRun } from '@/types/domain.types'

const props = defineProps<{ run: ExecutionRun }>()
const emit = defineEmits<{
  cancel: [id: number]
  retry: [id: number]
  'view-output': [id: number]
}>()

const { t } = useI18n()
const reports = useReportsStore()
const envs = useEnvironmentsStore()

const envName = computed(() => {
  if (!props.run.environment_id) return t('execution.runDialog.noEnv')
  const env = envs.environments.find(e => e.id === props.run.environment_id)
  return env?.name || '-'
})

const reportId = ref<number | null>(null)
const loadingReport = ref(false)
const activeTab = ref<'summary' | 'html' | 'xml'>('summary')

const hasReport = computed(() => reportId.value !== null)
const isRunFinished = computed(() =>
  ['passed', 'failed', 'error', 'cancelled', 'timeout'].includes(props.run.status)
)
const canHaveReport = computed(() =>
  ['passed', 'failed'].includes(props.run.status)
)

const failedTests = computed(() =>
  reports.activeReport?.test_results.filter(t => t.status === 'FAIL') || []
)

const htmlReportUrl = computed(() =>
  reportId.value ? getReportHtmlUrl(reportId.value) : ''
)

function downloadZip() {
  if (reportId.value) {
    window.open(getReportZipUrl(reportId.value), '_blank')
  }
}

async function fetchReport() {
  if (!canHaveReport.value) return
  loadingReport.value = true
  try {
    const data = await getRunReport(props.run.id)
    reportId.value = data.report_id
    if (reportId.value) {
      await reports.fetchReport(reportId.value)
    }
  } catch {
    reportId.value = null
  } finally {
    loadingReport.value = false
  }
}

onMounted(fetchReport)

watch(() => props.run.id, () => {
  reportId.value = null
  activeTab.value = 'summary'
  reports.activeReport = null
  fetchReport()
})

watch(() => props.run.status, (newStatus, oldStatus) => {
  if (newStatus !== oldStatus && canHaveReport.value && !reportId.value) {
    fetchReport()
  }
})
</script>

<template>
  <div class="run-detail-panel">
    <!-- Run Header -->
    <div class="detail-header">
      <h3>Run #{{ run.id }} — {{ run.target_path }}</h3>
    </div>

    <!-- Run Info Section -->
    <div class="detail-section">
      <div class="section-title">{{ t('execution.detail.runInfo') }}</div>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">{{ t('common.status') }}</span>
          <span class="info-value"><BaseBadge :status="run.status" /></span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('execution.branch') }}</span>
          <span class="info-value">{{ run.branch }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('execution.runDialog.environment') }}</span>
          <span class="info-value">{{ envName }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('execution.runner') }}</span>
          <span class="info-value">{{ run.runner_type }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('execution.detail.timeout') }}</span>
          <span class="info-value">{{ run.timeout_seconds }}s</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('execution.detail.started') }}</span>
          <span class="info-value">{{ formatDateTime(run.started_at) }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('execution.detail.finished') }}</span>
          <span class="info-value">{{ formatDateTime(run.finished_at) }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('common.duration') }}</span>
          <span class="info-value">{{ formatDuration(run.duration_seconds) }}</span>
        </div>
        <div class="info-item" v-if="run.error_message">
          <span class="info-label">{{ t('execution.detail.error') }}</span>
          <span class="info-value text-danger">{{ run.error_message }}</span>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="detail-actions">
        <BaseButton
          v-if="run.status === 'pending' || run.status === 'running'"
          variant="danger" size="sm"
          @click="emit('cancel', run.id)"
        >
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton
          v-if="run.status === 'failed' || run.status === 'error'"
          variant="secondary" size="sm"
          @click="emit('retry', run.id)"
        >
          {{ t('common.retry') }}
        </BaseButton>
        <BaseButton
          v-if="isRunFinished"
          variant="ghost" size="sm"
          @click="emit('view-output', run.id)"
        >
          Output
        </BaseButton>
        <BaseButton
          v-if="hasReport"
          variant="ghost" size="sm"
          @click="downloadZip"
        >
          {{ t('reportDetail.downloadZip') }}
        </BaseButton>
      </div>
    </div>

    <!-- Report Section -->
    <div class="detail-section">
      <div class="section-title">{{ t('execution.detail.reportTitle') }}</div>

      <BaseSpinner v-if="loadingReport" />

      <template v-else-if="hasReport && reports.activeReport">
        <!-- Tab Navigation -->
        <div class="tab-nav">
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'summary' }"
            @click="activeTab = 'summary'"
          >
            {{ t('reportDetail.tabs.summary') }}
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'html' }"
            @click="activeTab = 'html'"
          >
            {{ t('reportDetail.tabs.htmlReport') }}
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'xml' }"
            @click="activeTab = 'xml'"
          >
            {{ t('reportDetail.tabs.xmlView') }}
          </button>
        </div>

        <!-- Summary Tab -->
        <div v-show="activeTab === 'summary'" class="tab-content">
          <div class="kpi-row">
            <div class="kpi-card">
              <div class="kpi-value">{{ reports.activeReport.report.total_tests }}</div>
              <div class="kpi-label">{{ t('reportDetail.total') }}</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-value text-success">{{ reports.activeReport.report.passed_tests }}</div>
              <div class="kpi-label">{{ t('reportDetail.passed') }}</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-value text-danger">{{ reports.activeReport.report.failed_tests }}</div>
              <div class="kpi-label">{{ t('reportDetail.failed') }}</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-value">{{ formatDuration(reports.activeReport.report.total_duration_seconds) }}</div>
              <div class="kpi-label">{{ t('common.duration') }}</div>
            </div>
          </div>

          <!-- Failed Tests -->
          <div v-if="failedTests.length" class="failed-tests-section">
            <h4 style="color: var(--color-danger)">{{ t('reportDetail.failedTests', { count: failedTests.length }) }}</h4>
            <table class="data-table">
              <thead>
                <tr>
                  <th>{{ t('reportDetail.test') }}</th>
                  <th>{{ t('reportDetail.suite') }}</th>
                  <th>{{ t('common.duration') }}</th>
                  <th>{{ t('reportDetail.errorCol') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="test in failedTests" :key="test.id">
                  <td><strong>{{ test.test_name }}</strong></td>
                  <td class="text-muted text-sm">{{ test.suite_name }}</td>
                  <td>{{ formatDuration(test.duration_seconds) }}</td>
                  <td class="text-sm error-cell">{{ test.error_message || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- All Tests -->
          <div class="all-tests-section">
            <h4>{{ t('reportDetail.allTests', { count: reports.activeReport.test_results.length }) }}</h4>
            <table class="data-table">
              <thead>
                <tr>
                  <th>{{ t('common.status') }}</th>
                  <th>{{ t('reportDetail.test') }}</th>
                  <th>{{ t('reportDetail.suite') }}</th>
                  <th>{{ t('common.duration') }}</th>
                  <th>{{ t('reportDetail.tags') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="test in reports.activeReport.test_results" :key="test.id">
                  <td><BaseBadge :status="test.status" /></td>
                  <td>{{ test.test_name }}</td>
                  <td class="text-muted text-sm">{{ test.suite_name }}</td>
                  <td>{{ formatDuration(test.duration_seconds) }}</td>
                  <td class="text-sm text-muted">{{ test.tags || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- HTML Report Tab -->
        <div v-show="activeTab === 'html'" class="tab-content">
          <div class="html-report-card">
            <iframe
              :src="htmlReportUrl"
              class="html-report-iframe"
              sandbox="allow-scripts allow-same-origin"
              referrerpolicy="no-referrer"
            ></iframe>
          </div>
        </div>

        <!-- XML View Tab -->
        <div v-show="activeTab === 'xml'" class="tab-content">
          <div class="xml-view-card">
            <ReportXmlView :report-id="reportId!" />
          </div>
        </div>
      </template>

      <p v-else-if="!loadingReport" class="text-muted no-report-msg">
        {{ t('execution.detail.noReport') }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.run-detail-panel {
  padding: 20px;
  border-top: 2px solid var(--color-primary, #3CB5A1);
  background: var(--color-bg-card, #ffffff);
}

.detail-header h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
}

.detail-section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--color-text-muted);
  margin-bottom: 12px;
  letter-spacing: 0.5px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px 20px;
  margin-bottom: 12px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-label {
  font-size: 11px;
  color: var(--color-text-muted);
  font-weight: 500;
  text-transform: uppercase;
}

.info-value {
  font-size: 13px;
  font-weight: 500;
}

.detail-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

/* Report tabs */
.tab-nav {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--color-border, #e2e8f0);
  margin-bottom: 16px;
}

.tab-btn {
  padding: 8px 16px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted);
  transition: all 0.2s;
}

.tab-btn:hover {
  color: var(--color-text);
  background: var(--color-bg-hover, #f8fafc);
}

.tab-btn.active {
  color: var(--color-primary, #3CB5A1);
  border-bottom-color: var(--color-primary, #3CB5A1);
}

.tab-content {
  min-height: 200px;
}

/* KPI row */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.kpi-card {
  text-align: center;
  padding: 14px 10px;
  background: var(--color-bg, #f4f7fa);
  border-radius: var(--radius-sm, 6px);
}

.kpi-value {
  font-size: 24px;
  font-weight: 700;
}

.kpi-value.text-success { color: var(--color-success); }
.kpi-value.text-danger { color: var(--color-danger); }

.kpi-label {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 2px;
  text-transform: uppercase;
}

.error-cell {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-danger);
}

.failed-tests-section,
.all-tests-section {
  margin-bottom: 16px;
}

.failed-tests-section h4,
.all-tests-section h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
}

/* HTML Report iframe */
.html-report-card {
  overflow: hidden;
  border-radius: var(--radius-sm, 6px);
  border: 1px solid var(--color-border, #e2e8f0);
}

.html-report-iframe {
  width: 100%;
  height: 500px;
  border: none;
  display: block;
}

/* XML View */
.xml-view-card {
  max-height: 500px;
  overflow-y: auto;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-sm, 6px);
  padding: 12px;
}

.no-report-msg {
  padding: 20px;
  text-align: center;
  font-style: italic;
}

.text-danger { color: var(--color-danger); }
</style>
