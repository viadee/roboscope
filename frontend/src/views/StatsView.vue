<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStatsStore } from '@/stores/stats.store'
import { useReposStore } from '@/stores/repos.store'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import { formatDuration, formatPercent } from '@/utils/formatDuration'
import type { AnalysisReport, KpiMeta } from '@/types/domain.types'

const stats = useStatsStore()
const repos = useReposStore()
const { t } = useI18n()

const selectedDays = ref(30)
const selectedRepoId = ref<number | null>(null)
const activeTab = ref<'overview' | 'analysis'>('overview')

// New analysis modal
const showNewAnalysis = ref(false)
const newAnalysisRepo = ref<number | null>(null)
const newAnalysisDateFrom = ref('')
const newAnalysisDateTo = ref('')
const selectedKpis = ref<string[]>([])
const creatingAnalysis = ref(false)

// Analysis detail
const viewingAnalysis = ref<AnalysisReport | null>(null)

// Polling
let pollInterval: ReturnType<typeof setInterval> | null = null

const kpisByCategory = computed(() => {
  const cats: Record<string, KpiMeta[]> = {}
  for (const kpi of Object.values(stats.availableKpis)) {
    if (!cats[kpi.category]) cats[kpi.category] = []
    cats[kpi.category].push(kpi)
  }
  return cats
})

const categoryLabels: Record<string, string> = {
  keywords: 'stats.analysis.categoryKeywords',
  quality: 'stats.analysis.categoryQuality',
  maintenance: 'stats.analysis.categoryMaintenance',
  source: 'stats.analysis.categorySource',
}

const isStale = computed(() => {
  if (!stats.lastRunFinished) return false
  if (!stats.lastAggregated) return true
  // Compare: last run finished vs last aggregation date
  const runDate = new Date(stats.lastRunFinished)
  const aggDate = new Date(stats.lastAggregated + 'T23:59:59')
  return runDate > aggDate
})

function formatShortDate(d: string | Date): string {
  const dt = typeof d === 'string' ? new Date(d) : d
  return `${dt.getDate()}.${dt.getMonth() + 1}.`
}

const chartXLabels = computed(() => {
  const pts = stats.successRate
  if (pts.length === 0) return []
  if (pts.length === 1) return [{ text: formatShortDate(pts[0].date) }]
  if (pts.length === 2) return pts.map(p => ({ text: formatShortDate(p.date) }))
  // Pick ~5 evenly spaced labels (first, last, and midpoints)
  const count = Math.min(5, pts.length)
  const labels: { text: string }[] = []
  for (let i = 0; i < count; i++) {
    const idx = Math.round(i * (pts.length - 1) / (count - 1))
    labels.push({ text: formatShortDate(pts[idx].date) })
  }
  return labels
})

const stalenessText = computed(() => {
  if (!stats.lastRunFinished || !stats.lastAggregated) return ''
  const runDate = new Date(stats.lastRunFinished)
  const now = new Date()
  const diffMs = now.getTime() - runDate.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return t('stats.staleJustNow')
  if (diffMin < 60) return t('stats.staleMinutes', { count: diffMin })
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours < 24) return t('stats.staleHours', { count: diffHours })
  const diffDays = Math.floor(diffHours / 24)
  return t('stats.staleDays', { count: diffDays })
})

onMounted(async () => {
  await repos.fetchRepos()
  // Auto-aggregate on page load, then fetch stats
  await stats.aggregateKpis()
})

watch([selectedDays, selectedRepoId], async () => {
  stats.setFilter(selectedDays.value, selectedRepoId.value)
  await stats.fetchAll()
})

watch(activeTab, async (tab) => {
  if (tab === 'analysis') {
    await stats.fetchAvailableKpis()
    await stats.fetchAnalyses()
    startPolling()
  } else {
    stopPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})

function startPolling() {
  stopPolling()
  pollInterval = setInterval(async () => {
    const hasRunning = stats.analyses.some(a => a.status === 'pending' || a.status === 'running')
    if (hasRunning) {
      await stats.fetchAnalyses()
      if (viewingAnalysis.value) {
        const updated = stats.analyses.find(a => a.id === viewingAnalysis.value!.id)
        if (updated && updated.status === 'completed' && viewingAnalysis.value.status !== 'completed') {
          await stats.fetchAnalysis(viewingAnalysis.value.id)
          viewingAnalysis.value = stats.currentAnalysis
        } else if (updated) {
          viewingAnalysis.value = { ...viewingAnalysis.value!, status: updated.status, progress: updated.progress }
        }
      }
    }
  }, 3000)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

function selectAllKpis() {
  selectedKpis.value = Object.keys(stats.availableKpis)
}

function deselectAllKpis() {
  selectedKpis.value = []
}

function openNewAnalysisDialog() {
  // Default: all KPIs selected, last 30 days
  selectedKpis.value = Object.keys(stats.availableKpis)
  const today = new Date()
  const thirtyDaysAgo = new Date(today)
  thirtyDaysAgo.setDate(today.getDate() - 30)
  newAnalysisDateFrom.value = thirtyDaysAgo.toISOString().slice(0, 10)
  newAnalysisDateTo.value = today.toISOString().slice(0, 10)
  newAnalysisRepo.value = selectedRepoId.value
  showNewAnalysis.value = true
}

async function handleCreateAnalysis() {
  if (selectedKpis.value.length === 0) return
  creatingAnalysis.value = true
  try {
    const analysis = await stats.createAnalysis({
      repository_id: newAnalysisRepo.value,
      selected_kpis: selectedKpis.value,
      date_from: newAnalysisDateFrom.value || null,
      date_to: newAnalysisDateTo.value || null,
    })
    showNewAnalysis.value = false
    selectedKpis.value = []
    newAnalysisDateFrom.value = ''
    newAnalysisDateTo.value = ''
    startPolling()
  } finally {
    creatingAnalysis.value = false
  }
}

async function viewAnalysis(analysis: AnalysisReport) {
  await stats.fetchAnalysis(analysis.id)
  viewingAnalysis.value = stats.currentAnalysis
}

function closeAnalysisDetail() {
  viewingAnalysis.value = null
  stats.currentAnalysis = null
}

function statusVariant(status: string) {
  switch (status) {
    case 'completed': return 'success'
    case 'running': return 'info'
    case 'pending': return 'warning'
    case 'error': return 'danger'
    default: return 'default'
  }
}

function formatDate(d: string | null) {
  if (!d) return '-'
  return new Date(d).toLocaleString()
}
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('stats.title') }}</h1>
      <div class="flex gap-2 items-center">
        <select v-model="selectedRepoId" class="form-select" style="width: 180px">
          <option :value="null">{{ t('stats.allRepos') }}</option>
          <option v-for="repo in repos.repos" :key="repo.id" :value="repo.id">{{ repo.name }}</option>
        </select>
        <select v-model="selectedDays" class="form-select" style="width: 140px">
          <option :value="7">{{ t('stats.days7') }}</option>
          <option :value="14">{{ t('stats.days14') }}</option>
          <option :value="30">{{ t('stats.days30') }}</option>
          <option :value="90">{{ t('stats.days90') }}</option>
          <option :value="365">{{ t('stats.year1') }}</option>
        </select>
        <BaseButton
          variant="secondary"
          size="sm"
          :loading="stats.aggregating"
          @click="stats.aggregateKpis()"
        >
          {{ t('stats.refresh') }}
        </BaseButton>
      </div>
    </div>

    <!-- Staleness Banner -->
    <div v-if="isStale && !stats.aggregating" class="stale-banner mb-4">
      <span>{{ t('stats.staleMessage') }}</span>
      <span class="stale-detail">{{ stalenessText }}</span>
      <BaseButton variant="ghost" size="sm" @click="stats.aggregateKpis()">{{ t('stats.refresh') }}</BaseButton>
    </div>

    <!-- Tab Navigation -->
    <div class="tab-nav">
      <button class="tab-btn" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">
        {{ t('stats.analysis.tabOverview') }}
      </button>
      <button class="tab-btn" :class="{ active: activeTab === 'analysis' }" @click="activeTab = 'analysis'">
        {{ t('stats.analysis.tabAnalysis') }}
      </button>
    </div>

    <!-- Overview Tab -->
    <div v-show="activeTab === 'overview'">
      <BaseSpinner v-if="stats.loading" />

      <template v-else>
        <!-- Overview KPIs -->
        <div v-if="stats.overview" class="grid grid-4 mb-4">
          <div class="card kpi-card">
            <div class="kpi-value">{{ stats.overview.total_runs }}</div>
            <div class="kpi-label">{{ t('stats.totalRuns') }}</div>
          </div>
          <div class="card kpi-card">
            <div class="kpi-value" :class="stats.overview.success_rate >= 80 ? 'text-success' : 'text-danger'">
              {{ formatPercent(stats.overview.success_rate) }}
            </div>
            <div class="kpi-label">{{ t('stats.successRate') }}</div>
          </div>
          <div class="card kpi-card">
            <div class="kpi-value">{{ formatDuration(stats.overview.avg_duration_seconds) }}</div>
            <div class="kpi-label">{{ t('stats.avgDuration') }}</div>
          </div>
          <div class="card kpi-card">
            <div class="kpi-value">{{ stats.overview.total_tests }}</div>
            <div class="kpi-label">{{ t('stats.testsExecuted') }}</div>
          </div>
        </div>

        <!-- Success Rate Trend -->
        <div class="card mb-4">
          <div class="card-header">
            <h3>{{ t('stats.successOverTime') }}</h3>
          </div>
          <div v-if="stats.successRate.length" class="chart-placeholder">
            <div class="chart-wrapper">
              <!-- Y-axis labels -->
              <div class="chart-y-axis">
                <span>100%</span>
                <span>75%</span>
                <span>50%</span>
                <span>25%</span>
                <span>0%</span>
              </div>
              <div class="chart-body">
                <!-- Gridlines -->
                <div class="chart-grid">
                  <div class="chart-gridline" style="bottom: 100%"></div>
                  <div class="chart-gridline" style="bottom: 75%"></div>
                  <div class="chart-gridline" style="bottom: 50%"></div>
                  <div class="chart-gridline" style="bottom: 25%"></div>
                  <div class="chart-gridline" style="bottom: 0%"></div>
                </div>
                <!-- Bars -->
                <div class="mini-chart">
                  <div
                    v-for="(point, i) in stats.successRate"
                    :key="i"
                    class="chart-bar"
                    :style="{ height: `${point.success_rate}%` }"
                    :class="point.success_rate >= 80 ? 'bar-success' : 'bar-danger'"
                    :title="`${point.date}: ${formatPercent(point.success_rate)} (${t('stats.runsTooltip', { total: point.total_runs })})`"
                  ></div>
                </div>
                <!-- X-axis: only first, last, and a few midpoints -->
                <div class="chart-x-axis">
                  <span v-for="label in chartXLabels" :key="label.text" class="chart-x-label">
                    {{ label.text }}
                  </span>
                </div>
              </div>
            </div>
          </div>
          <p v-else class="text-muted text-center p-4">{{ t('stats.noDataPeriod') }}</p>
        </div>

        <!-- Trends -->
        <div class="card mb-4">
          <div class="card-header">
            <h3>{{ t('stats.passFailTrend') }}</h3>
          </div>
          <table class="data-table" v-if="stats.trends.length">
            <thead>
              <tr>
                <th>{{ t('common.date') }}</th>
                <th>{{ t('stats.passed') }}</th>
                <th>{{ t('stats.failed') }}</th>
                <th>{{ t('stats.errorCol') }}</th>
                <th>{{ t('stats.total') }}</th>
                <th>{{ t('stats.avgDuration') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="point in stats.trends" :key="point.date">
                <td>{{ point.date }}</td>
                <td class="text-success">{{ point.passed }}</td>
                <td :class="point.failed > 0 ? 'text-danger' : ''">{{ point.failed }}</td>
                <td>{{ point.error }}</td>
                <td><strong>{{ point.total }}</strong></td>
                <td>{{ formatDuration(point.avg_duration) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else class="text-muted text-center p-4">{{ t('stats.noTrends') }}</p>
        </div>

        <!-- Flaky Tests -->
        <div class="card">
          <div class="card-header">
            <h3>{{ t('stats.flakyTests') }}</h3>
          </div>
          <table class="data-table" v-if="stats.flakyTests.length">
            <thead>
              <tr>
                <th>{{ t('stats.test') }}</th>
                <th>{{ t('stats.suite') }}</th>
                <th>{{ t('stats.runs') }}</th>
                <th>{{ t('stats.passed') }}</th>
                <th>{{ t('stats.failed') }}</th>
                <th>{{ t('stats.flakyRate') }}</th>
                <th>{{ t('stats.lastStatus') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="test in stats.flakyTests" :key="test.test_name">
                <td><strong>{{ test.test_name }}</strong></td>
                <td class="text-muted text-sm">{{ test.suite_name }}</td>
                <td>{{ test.total_runs }}</td>
                <td class="text-success">{{ test.pass_count }}</td>
                <td class="text-danger">{{ test.fail_count }}</td>
                <td>
                  <BaseBadge variant="warning">{{ formatPercent(test.flaky_rate) }}</BaseBadge>
                </td>
                <td><BaseBadge :status="test.last_status" /></td>
              </tr>
            </tbody>
          </table>
          <p v-else class="text-muted text-center p-4">{{ t('stats.noFlaky') }}</p>
        </div>
      </template>
    </div>

    <!-- Analysis Tab -->
    <div v-show="activeTab === 'analysis'">
      <!-- Analysis Detail View -->
      <template v-if="viewingAnalysis">
        <div class="mb-3 flex gap-2 items-center">
          <BaseButton variant="ghost" size="sm" @click="closeAnalysisDetail">{{ t('common.back') }}</BaseButton>
          <h3 style="margin: 0">{{ t('stats.analysis.analysisDetail') }} #{{ viewingAnalysis.id }}</h3>
          <BaseBadge :variant="statusVariant(viewingAnalysis.status)">
            {{ t(`stats.analysis.status${viewingAnalysis.status.charAt(0).toUpperCase() + viewingAnalysis.status.slice(1)}`) }}
          </BaseBadge>
        </div>

        <!-- Progress bar -->
        <div v-if="viewingAnalysis.status === 'running' || viewingAnalysis.status === 'pending'" class="card mb-3">
          <div class="progress-container">
            <div class="progress-bar" :style="{ width: `${viewingAnalysis.progress}%` }"></div>
          </div>
          <div class="text-sm text-muted p-2">
            {{ viewingAnalysis.progress }}% — {{ t('stats.analysis.reportsAnalyzed') }}: {{ viewingAnalysis.reports_analyzed }}
          </div>
        </div>

        <!-- Error -->
        <div v-if="viewingAnalysis.status === 'error'" class="card mb-3" style="border-left: 3px solid var(--color-danger)">
          <div class="p-3 text-danger">{{ viewingAnalysis.error_message }}</div>
        </div>

        <!-- Results -->
        <template v-if="stats.currentAnalysis?.results">
          <!-- Keyword Frequency -->
          <div v-if="stats.currentAnalysis.results.keyword_frequency" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiKeywordFrequency') }}</h3></div>
            <div class="p-3">
              <div class="text-sm text-muted mb-2">
                {{ t('stats.analysis.totalKeywordCalls') }}: {{ stats.currentAnalysis.results.keyword_frequency.total_calls }} |
                {{ t('stats.analysis.uniqueKeywords') }}: {{ stats.currentAnalysis.results.keyword_frequency.unique_keywords }}
              </div>
              <table class="data-table">
                <thead><tr><th>#</th><th>{{ t('stats.analysis.keyword') }}</th><th>{{ t('stats.analysis.library') }}</th><th>{{ t('stats.analysis.count') }}</th><th>%</th></tr></thead>
                <tbody>
                  <tr v-for="(kw, i) in stats.currentAnalysis.results.keyword_frequency.top_keywords" :key="i">
                    <td>{{ i + 1 }}</td><td><strong>{{ kw.name }}</strong></td><td class="text-muted text-sm">{{ kw.library }}</td><td>{{ kw.count }}</td><td>{{ kw.percentage }}%</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Keyword Duration Impact -->
          <div v-if="stats.currentAnalysis.results.keyword_duration_impact" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiKeywordDuration') }}</h3></div>
            <div class="p-3">
              <table class="data-table">
                <thead><tr><th>{{ t('stats.analysis.keyword') }}</th><th>{{ t('stats.analysis.library') }}</th><th>{{ t('stats.analysis.totalTime') }}</th><th>{{ t('stats.analysis.avgTime') }}</th><th>{{ t('stats.analysis.calls') }}</th></tr></thead>
                <tbody>
                  <tr v-for="kw in stats.currentAnalysis.results.keyword_duration_impact.top_by_duration" :key="kw.name">
                    <td><strong>{{ kw.name }}</strong></td><td class="text-muted text-sm">{{ kw.library }}</td><td>{{ formatDuration(kw.total_duration) }}</td><td>{{ formatDuration(kw.avg_duration) }}</td><td>{{ kw.calls }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Library Distribution -->
          <div v-if="stats.currentAnalysis.results.library_distribution" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiLibraryDist') }}</h3></div>
            <div class="p-3">
              <div v-for="lib in stats.currentAnalysis.results.library_distribution.libraries" :key="lib.library" class="lib-bar-row">
                <div class="lib-bar-label">{{ lib.library }}</div>
                <div class="lib-bar-track">
                  <div class="lib-bar-fill" :style="{ width: `${lib.percentage}%` }"></div>
                </div>
                <div class="lib-bar-value">{{ lib.percentage }}% ({{ lib.count }})</div>
              </div>
            </div>
          </div>

          <!-- Test Complexity -->
          <div v-if="stats.currentAnalysis.results.test_complexity" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiTestComplexity') }}</h3></div>
            <div class="p-3">
              <div class="grid grid-3 mb-3">
                <div class="text-center"><div class="kpi-value-sm">{{ stats.currentAnalysis.results.test_complexity.avg }}</div><div class="kpi-label">{{ t('stats.analysis.avgSteps') }}</div></div>
                <div class="text-center"><div class="kpi-value-sm">{{ stats.currentAnalysis.results.test_complexity.min }}</div><div class="kpi-label">{{ t('stats.analysis.minSteps') }}</div></div>
                <div class="text-center"><div class="kpi-value-sm">{{ stats.currentAnalysis.results.test_complexity.max }}</div><div class="kpi-label">{{ t('stats.analysis.maxSteps') }}</div></div>
              </div>
              <div class="histogram">
                <div v-for="bucket in stats.currentAnalysis.results.test_complexity.histogram" :key="bucket.bucket" class="histogram-bar-row">
                  <div class="histogram-label">{{ bucket.bucket }}</div>
                  <div class="histogram-track">
                    <div class="histogram-fill" :style="{ width: `${Math.min(bucket.count / Math.max(...stats.currentAnalysis!.results!.test_complexity.histogram.map((b: any) => b.count), 1) * 100, 100)}%` }"></div>
                  </div>
                  <div class="histogram-value">{{ bucket.count }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- Assertion Density -->
          <div v-if="stats.currentAnalysis.results.assertion_density" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiAssertionDensity') }}</h3></div>
            <div class="p-3">
              <div class="text-sm text-muted mb-2">
                {{ t('stats.analysis.avgDensity') }}: {{ stats.currentAnalysis.results.assertion_density.avg_density }}% |
                {{ t('stats.analysis.testsWithoutAssertions') }}: {{ stats.currentAnalysis.results.assertion_density.tests_without_assertions }} / {{ stats.currentAnalysis.results.assertion_density.total_tests }}
              </div>
              <table v-if="stats.currentAnalysis.results.assertion_density.no_assertion_tests.length" class="data-table">
                <thead><tr><th>{{ t('stats.analysis.testName') }}</th><th>{{ t('stats.analysis.suite') }}</th><th>{{ t('stats.analysis.keywords') }}</th></tr></thead>
                <tbody>
                  <tr v-for="test in stats.currentAnalysis.results.assertion_density.no_assertion_tests" :key="test.name">
                    <td><strong>{{ test.name }}</strong></td><td class="text-muted text-sm">{{ test.suite }}</td><td>{{ test.total_keywords }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Tag Coverage -->
          <div v-if="stats.currentAnalysis.results.tag_coverage" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiTagCoverage') }}</h3></div>
            <div class="p-3">
              <div class="text-sm text-muted mb-2">
                {{ t('stats.analysis.totalTests') }}: {{ stats.currentAnalysis.results.tag_coverage.total_tests }} |
                {{ t('stats.analysis.untagged') }}: {{ stats.currentAnalysis.results.tag_coverage.untagged_count }} |
                {{ t('stats.analysis.avgTags') }}: {{ stats.currentAnalysis.results.tag_coverage.avg_tags_per_test }}
              </div>
              <div class="tag-cloud">
                <span v-for="tag in stats.currentAnalysis.results.tag_coverage.tags" :key="tag.tag" class="tag-pill">
                  {{ tag.tag }} <span class="tag-count">{{ tag.count }}</span>
                </span>
              </div>
            </div>
          </div>

          <!-- Error Patterns -->
          <div v-if="stats.currentAnalysis.results.error_patterns" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiErrorPatterns') }}</h3></div>
            <div class="p-3">
              <div class="text-sm text-muted mb-2">
                {{ t('stats.analysis.totalErrors') }}: {{ stats.currentAnalysis.results.error_patterns.total_errors }} |
                {{ t('stats.analysis.uniquePatterns') }}: {{ stats.currentAnalysis.results.error_patterns.unique_patterns }}
              </div>
              <div v-for="(pattern, i) in stats.currentAnalysis.results.error_patterns.patterns" :key="i" class="error-pattern-item">
                <div class="flex gap-2 items-center mb-1">
                  <BaseBadge variant="danger">{{ pattern.count }}x</BaseBadge>
                  <code class="text-sm">{{ pattern.pattern }}</code>
                </div>
                <div class="text-sm text-muted" style="padding-left: 12px">
                  {{ t('stats.analysis.exampleTests') }}: {{ pattern.example_tests.join(', ') }}
                </div>
              </div>
            </div>
          </div>

          <!-- Redundancy Detection -->
          <div v-if="stats.currentAnalysis.results.redundancy_detection" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiRedundancy') }}</h3></div>
            <div class="p-3">
              <div class="text-sm text-muted mb-2">
                {{ t('stats.analysis.sharedSequences') }}: {{ stats.currentAnalysis.results.redundancy_detection.total_shared_sequences }}
              </div>
              <table v-if="stats.currentAnalysis.results.redundancy_detection.sequences.length" class="data-table">
                <thead><tr><th>{{ t('stats.analysis.sequence') }}</th><th>{{ t('stats.analysis.occurrences') }}</th><th>{{ t('stats.analysis.tests') }}</th></tr></thead>
                <tbody>
                  <tr v-for="(seq, i) in stats.currentAnalysis.results.redundancy_detection.sequences" :key="i">
                    <td><code class="text-sm">{{ seq.keywords.join(' → ') }}</code></td>
                    <td>{{ seq.occurrence_count }}</td>
                    <td class="text-sm text-muted">{{ seq.tests.join(', ') }}</td>
                  </tr>
                </tbody>
              </table>
              <p v-else class="text-muted text-center p-3">{{ t('stats.analysis.noRedundancy') }}</p>
            </div>
          </div>

          <!-- Source Test Stats -->
          <div v-if="stats.currentAnalysis.results.source_test_stats" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiSourceTestStats') }}</h3></div>
            <div class="p-3">
              <div class="grid grid-4 mb-3">
                <div class="text-center"><div class="kpi-value-sm">{{ stats.currentAnalysis.results.source_test_stats.total_files }}</div><div class="kpi-label">{{ t('stats.analysis.sourceFiles') }}</div></div>
                <div class="text-center"><div class="kpi-value-sm">{{ stats.currentAnalysis.results.source_test_stats.total_tests }}</div><div class="kpi-label">{{ t('stats.analysis.sourceTestCases') }}</div></div>
                <div class="text-center"><div class="kpi-value-sm">{{ stats.currentAnalysis.results.source_test_stats.avg_steps }}</div><div class="kpi-label">{{ t('stats.analysis.avgSteps') }}</div></div>
                <div class="text-center"><div class="kpi-value-sm">{{ stats.currentAnalysis.results.source_test_stats.avg_lines }}</div><div class="kpi-label">{{ t('stats.analysis.sourceAvgLines') }}</div></div>
              </div>

              <!-- Step Histogram -->
              <div v-if="stats.currentAnalysis.results.source_test_stats.step_histogram.length" class="mb-3">
                <div class="text-sm text-muted mb-1">{{ t('stats.analysis.sourceStepDist') }}</div>
                <div class="histogram">
                  <div v-for="bucket in stats.currentAnalysis.results.source_test_stats.step_histogram" :key="bucket.bucket" class="histogram-bar-row">
                    <div class="histogram-label">{{ bucket.bucket }}</div>
                    <div class="histogram-track">
                      <div class="histogram-fill" :style="{ width: `${Math.min(bucket.count / Math.max(...stats.currentAnalysis!.results!.source_test_stats.step_histogram.map((b: any) => b.count), 1) * 100, 100)}%` }"></div>
                    </div>
                    <div class="histogram-value">{{ bucket.count }}</div>
                  </div>
                </div>
              </div>

              <!-- Top Keywords -->
              <div v-if="stats.currentAnalysis.results.source_test_stats.top_keywords.length" class="mb-3">
                <div class="text-sm text-muted mb-1">{{ t('stats.analysis.sourceTopKeywords') }}</div>
                <table class="data-table">
                  <thead><tr><th>#</th><th>{{ t('stats.analysis.keyword') }}</th><th>{{ t('stats.analysis.library') }}</th><th>{{ t('stats.analysis.count') }}</th><th>%</th></tr></thead>
                  <tbody>
                    <tr v-for="(kw, i) in stats.currentAnalysis.results.source_test_stats.top_keywords" :key="i">
                      <td>{{ i + 1 }}</td><td><strong>{{ kw.name }}</strong></td><td class="text-muted text-sm">{{ kw.library }}</td><td>{{ kw.count }}</td><td>{{ kw.percentage }}%</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- Per-file summary -->
              <div v-if="stats.currentAnalysis.results.source_test_stats.files.length">
                <div class="text-sm text-muted mb-1">{{ t('stats.analysis.sourceFileBreakdown') }}</div>
                <table class="data-table">
                  <thead><tr><th>{{ t('stats.analysis.sourceFilePath') }}</th><th>{{ t('stats.analysis.sourceTestCases') }}</th><th>{{ t('stats.analysis.avgSteps') }}</th></tr></thead>
                  <tbody>
                    <tr v-for="f in stats.currentAnalysis.results.source_test_stats.files" :key="f.path">
                      <td><code class="text-sm">{{ f.path }}</code></td><td>{{ f.test_count }}</td><td>{{ f.avg_steps }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- Source Library Distribution -->
          <div v-if="stats.currentAnalysis.results.source_library_distribution" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiSourceLibDist') }}</h3></div>
            <div class="p-3">
              <div class="text-sm text-muted mb-2">
                {{ t('stats.analysis.sourceTotalLibs') }}: {{ stats.currentAnalysis.results.source_library_distribution.total_libraries }}
              </div>
              <div v-for="lib in stats.currentAnalysis.results.source_library_distribution.libraries" :key="lib.library" class="lib-bar-row">
                <div class="lib-bar-label">{{ lib.library }}</div>
                <div class="lib-bar-track">
                  <div class="lib-bar-fill" :style="{ width: `${lib.percentage}%` }"></div>
                </div>
                <div class="lib-bar-value">{{ lib.file_count }} {{ t('stats.analysis.sourceFiles') }}</div>
              </div>
            </div>
          </div>
        </template>

        <p v-else-if="viewingAnalysis.status === 'completed'" class="text-muted text-center p-4">{{ t('stats.analysis.noResults') }}</p>
      </template>

      <!-- Analysis List View -->
      <template v-else>
        <div class="flex gap-2 items-center mb-3" style="justify-content: flex-end">
          <BaseButton variant="primary" @click="openNewAnalysisDialog">{{ t('stats.analysis.newAnalysis') }}</BaseButton>
        </div>

        <BaseSpinner v-if="stats.analysisLoading" />

        <div v-else-if="stats.analyses.length" class="card">
          <table class="data-table">
            <thead>
              <tr>
                <th>{{ t('common.id') }}</th>
                <th>{{ t('common.status') }}</th>
                <th>{{ t('stats.analysis.kpis') }}</th>
                <th>{{ t('stats.analysis.reportsAnalyzed') }}</th>
                <th>{{ t('stats.analysis.progress') }}</th>
                <th>{{ t('common.created') }}</th>
                <th>{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="analysis in stats.analyses" :key="analysis.id">
                <td>#{{ analysis.id }}</td>
                <td>
                  <BaseBadge :variant="statusVariant(analysis.status)">
                    {{ t(`stats.analysis.status${analysis.status.charAt(0).toUpperCase() + analysis.status.slice(1)}`) }}
                  </BaseBadge>
                </td>
                <td>{{ analysis.selected_kpis.length }} KPIs</td>
                <td>{{ analysis.reports_analyzed }}</td>
                <td>
                  <div v-if="analysis.status === 'running'" class="progress-container-sm">
                    <div class="progress-bar" :style="{ width: `${analysis.progress}%` }"></div>
                  </div>
                  <span v-else>{{ analysis.progress }}%</span>
                </td>
                <td class="text-sm text-muted">{{ formatDate(analysis.created_at) }}</td>
                <td>
                  <BaseButton size="sm" variant="secondary" @click="viewAnalysis(analysis)">
                    {{ t('stats.analysis.view') }}
                  </BaseButton>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-else class="text-muted text-center p-4">{{ t('stats.analysis.noAnalyses') }}</p>
      </template>
    </div>

    <!-- New Analysis Modal -->
    <BaseModal v-model="showNewAnalysis" :title="t('stats.analysis.newAnalysis')" size="lg">
      <div class="p-3">
        <!-- Repository -->
        <div class="form-group mb-3">
          <label class="form-label">{{ t('stats.analysis.repository') }}</label>
          <select v-model="newAnalysisRepo" class="form-input">
            <option :value="null">{{ t('stats.allRepos') }}</option>
            <option v-for="repo in repos.repos" :key="repo.id" :value="repo.id">{{ repo.name }}</option>
          </select>
        </div>

        <!-- Date Range -->
        <div class="flex gap-3 mb-3">
          <div class="form-group" style="flex: 1">
            <label class="form-label">{{ t('stats.analysis.dateFrom') }}</label>
            <input type="date" v-model="newAnalysisDateFrom" class="form-input" />
          </div>
          <div class="form-group" style="flex: 1">
            <label class="form-label">{{ t('stats.analysis.dateTo') }}</label>
            <input type="date" v-model="newAnalysisDateTo" class="form-input" />
          </div>
        </div>

        <!-- KPI Selection -->
        <div class="mb-3">
          <div class="flex gap-2 items-center mb-2">
            <label class="form-label" style="margin: 0">{{ t('stats.analysis.selectKpis') }}</label>
            <BaseButton size="sm" variant="ghost" @click="selectAllKpis">{{ t('stats.analysis.selectAll') }}</BaseButton>
            <BaseButton size="sm" variant="ghost" @click="deselectAllKpis">{{ t('stats.analysis.deselectAll') }}</BaseButton>
          </div>

          <div v-for="(kpis, category) in kpisByCategory" :key="category" class="kpi-category-group">
            <div class="kpi-category-label">{{ t(categoryLabels[category] || category) }}</div>
            <div v-for="kpi in kpis" :key="kpi.id" class="kpi-checkbox">
              <label class="checkbox-label">
                <input type="checkbox" :value="kpi.id" v-model="selectedKpis" />
                <span class="checkbox-text">
                  <strong>{{ kpi.name }}</strong>
                  <span class="text-sm text-muted"> — {{ kpi.description }}</span>
                </span>
              </label>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex gap-2" style="justify-content: flex-end">
          <BaseButton variant="secondary" @click="showNewAnalysis = false">{{ t('common.cancel') }}</BaseButton>
          <BaseButton variant="primary" :loading="creatingAnalysis" :disabled="selectedKpis.length === 0" @click="handleCreateAnalysis">
            {{ t('stats.analysis.generateAnalysis') }}
          </BaseButton>
        </div>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.kpi-card { text-align: center; padding: 24px 16px; }
.kpi-value { font-size: 28px; font-weight: 700; }
.kpi-value.text-success { color: var(--color-success); }
.kpi-value.text-danger { color: var(--color-danger); }
.kpi-label { font-size: 12px; color: var(--color-text-muted); margin-top: 4px; text-transform: uppercase; }
.text-success { color: var(--color-success); font-weight: 500; }
.text-danger { color: var(--color-danger); font-weight: 500; }

.chart-placeholder { padding: 16px; }

.chart-wrapper {
  display: flex;
  gap: 0;
}

.chart-y-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
  padding-right: 8px;
  height: 140px;
  flex-shrink: 0;
}

.chart-y-axis span {
  font-size: 10px;
  color: var(--color-text-muted);
  line-height: 1;
}

.chart-body {
  flex: 1;
  position: relative;
  min-width: 0;
}

.chart-grid {
  position: absolute;
  inset: 0;
  bottom: 0;
  height: 140px;
}

.chart-gridline {
  position: absolute;
  left: 0;
  right: 0;
  border-bottom: 1px dashed var(--color-border-light, #e8ecf0);
}

.mini-chart {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 140px;
  position: relative;
  z-index: 1;
}

.chart-bar {
  flex: 1;
  min-width: 4px;
  max-width: 20px;
  border-radius: 2px 2px 0 0;
  transition: height 0.3s ease;
  cursor: pointer;
}
.bar-success { background: var(--color-success); opacity: 0.7; }
.bar-success:hover { opacity: 1; }
.bar-danger { background: var(--color-danger); opacity: 0.7; }
.bar-danger:hover { opacity: 1; }

.chart-x-axis {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  padding: 0 2px;
}

.chart-x-label {
  font-size: 11px;
  color: var(--color-text-muted);
  white-space: nowrap;
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
}
.tab-btn:hover {
  color: var(--color-text);
  background: var(--color-bg-hover, #f8fafc);
}
.tab-btn.active {
  color: var(--color-primary, #3CB5A1);
  border-bottom-color: var(--color-primary, #3CB5A1);
}

/* Progress */
.progress-container {
  height: 8px;
  background: var(--color-bg, #f4f7fa);
  border-radius: 4px;
  overflow: hidden;
  margin: 8px 12px;
}
.progress-container-sm {
  height: 6px;
  width: 80px;
  background: var(--color-bg, #f4f7fa);
  border-radius: 3px;
  overflow: hidden;
  display: inline-block;
}
.progress-bar {
  height: 100%;
  background: var(--color-primary, #3CB5A1);
  border-radius: 4px;
  transition: width 0.3s ease;
}

/* KPI Selection */
.kpi-category-group { margin-bottom: 16px; }
.kpi-category-label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--color-text-muted);
  margin-bottom: 8px;
  letter-spacing: 0.5px;
}
.kpi-checkbox { margin-bottom: 6px; }
.checkbox-label {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  cursor: pointer;
}
.checkbox-label input { margin-top: 3px; }
.checkbox-text { line-height: 1.4; }

/* Library Distribution */
.lib-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.lib-bar-label { width: 140px; font-size: 13px; text-align: right; flex-shrink: 0; }
.lib-bar-track { flex: 1; height: 18px; background: var(--color-bg, #f4f7fa); border-radius: 3px; overflow: hidden; }
.lib-bar-fill { height: 100%; background: var(--color-primary, #3CB5A1); border-radius: 3px; transition: width 0.3s; }
.lib-bar-value { width: 100px; font-size: 12px; color: var(--color-text-muted); }

/* Histogram */
.histogram-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.histogram-label { width: 60px; font-size: 12px; text-align: right; flex-shrink: 0; }
.histogram-track { flex: 1; height: 16px; background: var(--color-bg, #f4f7fa); border-radius: 3px; overflow: hidden; }
.histogram-fill { height: 100%; background: var(--color-accent, #DFAA40); border-radius: 3px; }
.histogram-value { width: 40px; font-size: 12px; color: var(--color-text-muted); }

/* Small KPI values */
.kpi-value-sm { font-size: 22px; font-weight: 700; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }

/* Tag cloud */
.tag-cloud { display: flex; flex-wrap: wrap; gap: 6px; }
.tag-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--color-bg, #f4f7fa);
  border-radius: 20px;
  font-size: 13px;
}
.tag-count {
  background: var(--color-primary, #3CB5A1);
  color: white;
  border-radius: 10px;
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 600;
}

/* Error patterns */
.error-pattern-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border, #e2e8f0);
}
.error-pattern-item:last-child { border-bottom: none; }

/* Form */
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-label { font-size: 13px; font-weight: 500; color: var(--color-text); }

/* Staleness banner */
.stale-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: rgba(223, 170, 64, 0.1);
  border: 1px solid rgba(223, 170, 64, 0.3);
  border-radius: var(--radius-sm, 6px);
  font-size: 13px;
  color: var(--color-text);
}
.stale-detail {
  color: var(--color-text-muted);
  font-size: 12px;
}
</style>
