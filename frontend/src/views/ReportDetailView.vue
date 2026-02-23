<script setup lang="ts">
import { onMounted, onUnmounted, computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useReportsStore } from '@/stores/reports.store'
import { useAiStore } from '@/stores/ai.store'
import { getReportHtmlUrl, getReportZipUrl } from '@/api/reports.api'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import ReportXmlView from '@/components/report/ReportXmlView.vue'
import { formatDuration } from '@/utils/formatDuration'

const route = useRoute()
const reports = useReportsStore()
const aiStore = useAiStore()
const { t } = useI18n()

const reportId = computed(() => Number(route.params.id))
const activeTab = ref<'summary' | 'detailed' | 'html'>('summary')

onMounted(() => {
  if (reportId.value) reports.fetchReport(reportId.value)
  if (!aiStore.hasProviders) aiStore.fetchProviders()
})

onUnmounted(() => {
  aiStore.stopAnalysisPolling()
})

const failedTests = computed(() =>
  reports.activeReport?.test_results.filter(t => t.status === 'FAIL') || []
)

const passedTests = computed(() =>
  reports.activeReport?.test_results.filter(t => t.status === 'PASS') || []
)

const hasFailures = computed(() => failedTests.value.length > 0)

const htmlReportUrl = computed(() => getReportHtmlUrl(reportId.value))
const zipDownloadUrl = computed(() => getReportZipUrl(reportId.value))
const iframeKey = ref(0)

function reloadIframe() {
  iframeKey.value++
}

function downloadZip() {
  window.open(zipDownloadUrl.value, '_blank')
}

// --- AI Failure Analysis ---

const analysisError = ref('')

async function startAnalysis() {
  analysisError.value = ''
  try {
    await aiStore.analyzeFailures(reportId.value)
  } catch (e: any) {
    analysisError.value = e.response?.data?.detail || 'Analysis failed'
  }
}

function renderMarkdown(md: string): string {
  // Escape HTML
  let html = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // Code blocks
  html = html.replace(/```[\w]*\n([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  // Headers
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  // Unordered lists
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
  // Collapse adjacent </ul><ul>
  html = html.replace(/<\/ul>\s*<ul>/g, '')
  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
  // Paragraphs — double newlines
  html = html.replace(/\n\n/g, '</p><p>')
  html = '<p>' + html + '</p>'
  // Clean up empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, '')
  return html
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
          :class="{ active: activeTab === 'detailed' }"
          @click="activeTab = 'detailed'"
        >
          {{ t('reportDetail.tabs.detailedReport') }}
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'html' }"
          @click="activeTab = 'html'"
        >
          {{ t('reportDetail.tabs.htmlReport') }}
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
          <div class="table-responsive">
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
                <td><router-link :to="{ path: '/test-history', query: { test: test.test_name, suite: test.suite_name } }" class="test-link"><strong>{{ test.test_name }}</strong></router-link></td>
                <td class="text-muted text-sm">{{ test.suite_name }}</td>
                <td>{{ formatDuration(test.duration_seconds) }}</td>
                <td class="text-sm error-cell">{{ test.error_message || '-' }}</td>
              </tr>
            </tbody>
          </table>
          </div>
        </div>

        <!-- All Tests -->
        <div class="card mb-4">
          <div class="card-header">
            <h3>{{ t('reportDetail.allTests', { count: reports.activeReport.test_results.length }) }}</h3>
          </div>
          <div class="table-responsive">
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
                <td><router-link :to="{ path: '/test-history', query: { test: test.test_name, suite: test.suite_name } }" class="test-link">{{ test.test_name }}</router-link></td>
                <td class="text-muted text-sm">{{ test.suite_name }}</td>
                <td>{{ formatDuration(test.duration_seconds) }}</td>
                <td class="text-sm text-muted">{{ test.tags || '-' }}</td>
              </tr>
            </tbody>
          </table>
          </div>
        </div>

        <!-- AI Failure Analysis -->
        <div v-if="hasFailures" class="card analysis-card">
          <div class="card-header analysis-header">
            <h3>{{ t('reportDetail.analysis.title') }}</h3>
          </div>
          <div class="analysis-body">
            <!-- No provider configured -->
            <div v-if="!aiStore.hasProviders" class="analysis-hint">
              <p class="text-muted">{{ t('reportDetail.analysis.noProvider') }}</p>
            </div>

            <!-- Error state -->
            <div v-else-if="analysisError" class="analysis-error">
              <p class="text-danger"><strong>{{ t('reportDetail.analysis.failed') }}:</strong> {{ analysisError }}</p>
              <BaseButton variant="secondary" size="sm" @click="startAnalysis">{{ t('common.retry') }}</BaseButton>
            </div>

            <!-- Loading state -->
            <div v-else-if="aiStore.analysisJob && (aiStore.analysisJob.status === 'pending' || aiStore.analysisJob.status === 'running')" class="analysis-loading">
              <BaseSpinner />
              <p class="text-muted">{{ t('reportDetail.analysis.analyzing') }}</p>
            </div>

            <!-- Failed job -->
            <div v-else-if="aiStore.analysisJob && aiStore.analysisJob.status === 'failed'" class="analysis-error">
              <p class="text-danger"><strong>{{ t('reportDetail.analysis.failed') }}:</strong> {{ aiStore.analysisJob.error_message }}</p>
              <BaseButton variant="secondary" size="sm" @click="startAnalysis">{{ t('common.retry') }}</BaseButton>
            </div>

            <!-- Result state -->
            <div v-else-if="aiStore.analysisJob && aiStore.analysisJob.status === 'completed' && aiStore.analysisJob.result_preview" class="analysis-result">
              <div class="analysis-content" v-html="renderMarkdown(aiStore.analysisJob.result_preview)"></div>
              <div class="analysis-footer">
                <span v-if="aiStore.analysisJob.token_usage" class="text-muted text-sm">
                  {{ t('reportDetail.analysis.tokensUsed', { tokens: aiStore.analysisJob.token_usage }) }}
                </span>
                <BaseButton variant="ghost" size="sm" @click="startAnalysis">{{ t('reportDetail.analysis.reanalyze') }}</BaseButton>
              </div>
            </div>

            <!-- Initial state — show button -->
            <div v-else class="analysis-initial">
              <BaseButton variant="primary" @click="startAnalysis">
                {{ t('reportDetail.analysis.analyzeButton') }}
              </BaseButton>
            </div>
          </div>
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

      <!-- Detailed Report Tab -->
      <div v-show="activeTab === 'detailed'" class="tab-content">
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
.test-link { color: var(--color-text); text-decoration: none; }
.test-link:hover { color: var(--color-primary); }

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
  color: var(--color-primary, #3B7DD8);
  border-bottom-color: var(--color-primary, #3B7DD8);
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

/* AI Analysis Card */
.analysis-card {
  border-left: 4px solid var(--color-primary, #3B7DD8);
}

.analysis-header h3 {
  color: var(--color-primary, #3B7DD8);
}

.analysis-body {
  padding: 16px 20px;
}

.analysis-hint {
  padding: 12px 0;
}

.analysis-loading {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 0;
}

.analysis-error {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
}

.analysis-initial {
  padding: 8px 0;
}

.analysis-result {
  padding: 4px 0;
}

.analysis-content {
  line-height: 1.7;
  font-size: 14px;
}

.analysis-content :deep(h1),
.analysis-content :deep(h2),
.analysis-content :deep(h3),
.analysis-content :deep(h4) {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
}

.analysis-content :deep(h2) { font-size: 18px; }
.analysis-content :deep(h3) { font-size: 16px; }
.analysis-content :deep(h4) { font-size: 14px; }

.analysis-content :deep(pre) {
  background: var(--color-bg, #f4f7fa);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  margin: 8px 0;
}

.analysis-content :deep(code) {
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  font-size: 13px;
}

.analysis-content :deep(ul) {
  padding-left: 20px;
  margin: 8px 0;
}

.analysis-content :deep(li) {
  margin-bottom: 4px;
}

.analysis-content :deep(strong) {
  font-weight: 600;
}

.analysis-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border, #e2e8f0);
}
</style>
