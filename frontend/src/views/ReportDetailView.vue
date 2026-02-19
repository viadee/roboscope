<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useReportsStore } from '@/stores/reports.store'
import { getReportHtmlUrl, getReportZipUrl } from '@/api/reports.api'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import ReportXmlView from '@/components/report/ReportXmlView.vue'
import { formatDuration } from '@/utils/formatDuration'

const route = useRoute()
const reports = useReportsStore()
const { t } = useI18n()

const reportId = computed(() => Number(route.params.id))
const activeTab = ref<'summary' | 'html' | 'xml'>('summary')

onMounted(() => {
  if (reportId.value) reports.fetchReport(reportId.value)
})

const failedTests = computed(() =>
  reports.activeReport?.test_results.filter(t => t.status === 'FAIL') || []
)

const passedTests = computed(() =>
  reports.activeReport?.test_results.filter(t => t.status === 'PASS') || []
)

const htmlReportUrl = computed(() => getReportHtmlUrl(reportId.value))
const zipDownloadUrl = computed(() => getReportZipUrl(reportId.value))
const iframeKey = ref(0)

function reloadIframe() {
  iframeKey.value++
}

function downloadZip() {
  window.open(zipDownloadUrl.value, '_blank')
}
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('reportDetail.title', { id: reportId }) }}</h1>
      <div class="header-actions">
        <BaseButton variant="secondary" @click="downloadZip" class="zip-btn">
          &#128230; {{ t('reportDetail.downloadZip') }}
        </BaseButton>
        <router-link to="/reports">
          <BaseButton variant="secondary">&larr; {{ t('common.back') }}</BaseButton>
        </router-link>
      </div>
    </div>

    <BaseSpinner v-if="reports.loading" />

    <template v-else-if="reports.activeReport">
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
        <div class="grid grid-4 mb-4">
          <div class="card kpi-card">
            <div class="kpi-value">{{ reports.activeReport.report.total_tests }}</div>
            <div class="kpi-label">{{ t('reportDetail.total') }}</div>
          </div>
          <div class="card kpi-card">
            <div class="kpi-value text-success">{{ reports.activeReport.report.passed_tests }}</div>
            <div class="kpi-label">{{ t('reportDetail.passed') }}</div>
          </div>
          <div class="card kpi-card">
            <div class="kpi-value text-danger">{{ reports.activeReport.report.failed_tests }}</div>
            <div class="kpi-label">{{ t('reportDetail.failed') }}</div>
          </div>
          <div class="card kpi-card">
            <div class="kpi-value">{{ formatDuration(reports.activeReport.report.total_duration_seconds) }}</div>
            <div class="kpi-label">{{ t('common.duration') }}</div>
          </div>
        </div>

        <!-- Failed Tests -->
        <div v-if="failedTests.length" class="card mb-4">
          <div class="card-header">
            <h3 style="color: var(--color-danger)">{{ t('reportDetail.failedTests', { count: failedTests.length }) }}</h3>
          </div>
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
        <div class="card">
          <div class="card-header">
            <h3>{{ t('reportDetail.allTests', { count: reports.activeReport.test_results.length }) }}</h3>
          </div>
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
        <div class="iframe-toolbar">
          <BaseButton variant="secondary" size="sm" @click="activeTab = 'summary'">
            &larr; {{ t('reportDetail.tabs.summary') }}
          </BaseButton>
          <BaseButton variant="ghost" size="sm" @click="reloadIframe">
            &#8635; {{ t('reportDetail.reloadReport') }}
          </BaseButton>
        </div>
        <div class="card html-report-card">
          <iframe
            :key="iframeKey"
            :src="htmlReportUrl"
            class="html-report-iframe"
            sandbox="allow-scripts allow-same-origin"
            referrerpolicy="no-referrer"
          ></iframe>
        </div>
      </div>

      <!-- XML View Tab -->
      <div v-show="activeTab === 'xml'" class="tab-content">
        <div class="card xml-view-card">
          <ReportXmlView :report-id="reportId" />
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.zip-btn {
  white-space: nowrap;
}

.kpi-card { text-align: center; padding: 20px 16px; }
.kpi-value { font-size: 28px; font-weight: 700; }
.kpi-value.text-success { color: var(--color-success); }
.kpi-value.text-danger { color: var(--color-danger); }
.kpi-label { font-size: 12px; color: var(--color-text-muted); margin-top: 4px; text-transform: uppercase; }
.error-cell { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--color-danger); }

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
  min-height: 300px;
}

/* HTML Report toolbar */
.iframe-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

/* HTML Report iframe */
.html-report-card {
  padding: 0;
  overflow: hidden;
}

.html-report-iframe {
  width: 100%;
  height: calc(100vh - 250px);
  min-height: 500px;
  border: none;
  display: block;
}

/* XML View */
.xml-view-card {
  padding: 16px;
  max-height: calc(100vh - 250px);
  overflow-y: auto;
}
</style>
