<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStatsStore } from '@/stores/stats.store'
import { useReposStore } from '@/stores/repos.store'
import { useAuthStore } from '@/stores/auth.store'
import { quarantineFlakyTest, unquarantineFlakyTest } from '@/api/stats.api'
import type { FlakyTest } from '@/types/domain.types'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import { formatDuration, formatPercent } from '@/utils/formatDuration'
import { parseBackendDate } from '@/utils/formatDate'
import { fillDailySuccessRate } from '@/utils/chartGaps'
import type { AnalysisReport, KpiMeta } from '@/types/domain.types'

const stats = useStatsStore()
const repos = useReposStore()
const auth = useAuthStore()
const { t } = useI18n()

// Story FLAKY-1 — quarantine toggle state
const togglingQuarantine = ref<Set<string>>(new Set())
const flakyKey = (t: FlakyTest) => `${t.repository_id ?? 'x'}::${t.suite_name}::${t.test_name}`

async function toggleQuarantine(test: FlakyTest) {
  const key = flakyKey(test)
  if (togglingQuarantine.value.has(key)) return
  togglingQuarantine.value.add(key)
  try {
    if (test.is_quarantined && test.quarantine_id) {
      await unquarantineFlakyTest(test.quarantine_id)
    } else if (test.repository_id) {
      await quarantineFlakyTest({
        repository_id: test.repository_id,
        suite_name: test.suite_name,
        test_name: test.test_name,
      })
    }
    await stats.fetchFlakyTests()
  } catch {
    // Surface via toast in a follow-up; silent no-op keeps scope tight
    // and the view still usable.
  } finally {
    togglingQuarantine.value.delete(key)
  }
}

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
  execution: 'stats.analysis.categoryExecution',
  codequality: 'stats.analysis.categoryCodequality',
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

// Pass/Fail Trend table is rendered newest-first. The backend
// returns ascending-by-date (correct for the bar-chart left-to-
// right chronological reading), so we reverse a shallow copy here
// for the table render. Don't sort in place — the same `stats.trends`
// reference is reused by the chart-x-label logic.
const trendsDesc = computed(() => [...stats.trends].slice().reverse())

/**
 * Pick ~5 evenly spaced labels (first, last, and midpoints) and
 * record WHICH bar index each label belongs to. The template then
 * renders one x-axis slot per bar (same flex layout + max-width as
 * `.chart-bar`) and only the matching slots carry text — so each
 * visible label sits geometrically under its bar regardless of how
 * many bars fit in the container width. The previous approach used
 * `justify-content: space-between` which spread labels across the
 * FULL parent width while bars stopped at `max-width: 20px`, so the
 * last label drifted right of the last bar by however much
 * whitespace the bars left unfilled.
 */
// One chart slot per calendar day between the first and last data point.
// Days without executions get a `point: null` slot so they occupy the same
// width but render no bar — a continuous, evenly-spaced time axis instead of
// bars-with-runs jammed side by side.
const chartDays = computed(() => fillDailySuccessRate(stats.successRate))

const chartXLabels = computed<{ idx: number; text: string }[]>(() => {
  const pts = chartDays.value
  if (pts.length === 0) return []
  if (pts.length === 1) return [{ idx: 0, text: formatShortDate(pts[0].date) }]
  if (pts.length === 2) return pts.map((p, i) => ({ idx: i, text: formatShortDate(p.date) }))
  const count = Math.min(5, pts.length)
  const labels: { idx: number; text: string }[] = []
  for (let i = 0; i < count; i++) {
    const idx = Math.round(i * (pts.length - 1) / (count - 1))
    labels.push({ idx, text: formatShortDate(pts[idx].date) })
  }
  return labels
})

function labelForBar(barIdx: number): string {
  return chartXLabels.value.find(l => l.idx === barIdx)?.text ?? ''
}

const stalenessText = computed(() => {
  if (!stats.lastRunFinished || !stats.lastAggregated) return ''
  // `parseBackendDate` treats naive ISO (no `Z` / no offset) as UTC.
  // Without it `now − runDate` is off by the user's UTC offset and a
  // fresh aggregation can render as "5 hours ago" for a CEST user.
  const runDate = parseBackendDate(stats.lastRunFinished)
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
      <BaseButton variant="ghost" size="sm" @click="stats.aggregateKpis()">{{ t('stats.refreshNow') }}</BaseButton>
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
                <!-- Bars: one slot per calendar day. Days without
                     executions render a bar-less placeholder so the gap
                     keeps its width instead of collapsing. -->
                <div class="mini-chart">
                  <div
                    v-for="(day, i) in chartDays"
                    :key="day.date"
                    class="chart-bar"
                    :style="day.point ? { height: `${day.point.success_rate}%` } : undefined"
                    :class="day.point
                      ? (day.point.success_rate >= 80 ? 'bar-success' : 'bar-danger')
                      : 'bar-empty'"
                    :title="day.point
                      ? `${day.point.date}: ${formatPercent(day.point.success_rate)} (${t('stats.runsTooltip', { total: day.point.total_runs })})`
                      : `${day.date}: ${t('stats.noRunsDay')}`"
                  ></div>
                </div>
                <!-- X-axis: one slot per day (same flex layout +
                     max-width as `.chart-bar`) so visible labels sit
                     directly under their bars. Empty slots preserve
                     the alignment when only a subset of bars carry
                     text. -->
                <div class="chart-x-axis">
                  <span
                    v-for="(day, i) in chartDays"
                    :key="day.date"
                    class="chart-x-slot"
                  >{{ labelForBar(i) }}</span>
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
              <tr v-for="point in trendsDesc" :key="point.date">
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
                <th>{{ t('stats.quarantine.column') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="test in stats.flakyTests" :key="flakyKey(test)" :class="{ 'row-quarantined': test.is_quarantined }">
                <td><strong>{{ test.test_name }}</strong></td>
                <td class="text-muted text-sm">{{ test.suite_name }}</td>
                <td>{{ test.total_runs }}</td>
                <td class="text-success">{{ test.pass_count }}</td>
                <td class="text-danger">{{ test.fail_count }}</td>
                <td>
                  <BaseBadge variant="warning">{{ formatPercent(test.flaky_rate) }}</BaseBadge>
                </td>
                <td><BaseBadge :status="test.last_status" /></td>
                <td>
                  <span v-if="test.is_quarantined" class="quarantine-badge">
                    🔕 {{ t('stats.quarantine.quarantined') }}
                  </span>
                  <span v-else class="text-muted text-sm">—</span>
                  <button
                    v-if="auth.hasMinRole('editor') && test.repository_id"
                    class="quarantine-btn"
                    :disabled="togglingQuarantine.has(flakyKey(test))"
                    @click="toggleQuarantine(test)"
                  >
                    {{ test.is_quarantined ? t('stats.quarantine.unmute') : t('stats.quarantine.mute') }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="text-muted text-center p-4">{{ t('stats.noFlaky') }}</p>
        </div>

        <!-- Story SH-6 — heal-rate KPI card. Moved to the bottom of
             the overview so it doesn't dominate the page; styled like
             every other card (no purple accent / gradient) so it
             reads as one of N rather than as a hero metric. -->
        <div v-if="stats.healRate && stats.healRate.total_runs_in_window > 0" class="card heal-kpi mt-4">
          <div class="card-header">
            <h3>{{ t('stats.healRate.heading') }}</h3>
          </div>
          <div class="heal-kpi__row">
            <div class="heal-kpi__body">
              <div class="heal-kpi__value">
                🩹 <span class="heal-kpi__big">{{ stats.healRate.total_heals }}</span>
                <span class="heal-kpi__label">{{ t('stats.healRate.total') }}</span>
              </div>
              <p class="heal-kpi__sub">
                {{ t('stats.healRate.healedOf', {
                  healed: stats.healRate.runs_with_heals,
                  total: stats.healRate.total_runs_in_window,
                }) }}
              </p>
              <div class="heal-kpi__badges">
                <span class="heal-kpi__badge heal-kpi__badge--confirmed">
                  🩹 {{ stats.healRate.confirmed_heals }} {{ t('stats.healRate.confirmed') }}
                </span>
                <span
                  v-if="stats.healRate.suspect_heals > 0"
                  class="heal-kpi__badge heal-kpi__badge--suspect"
                >
                  ⚠️ {{ stats.healRate.suspect_heals }} {{ t('stats.healRate.suspect') }}
                </span>
              </div>
            </div>
            <div class="heal-kpi__sparkline" aria-hidden="true">
              <div
                v-for="p in stats.healRate.trend"
                :key="p.date"
                class="heal-kpi__bar"
                :title="`${p.date}: ${p.heals} (🩹 ${p.confirmed} · ⚠️ ${p.suspect})`"
                :style="{
                  height: (p.heals === 0 ? 2 : Math.min(100, 8 + p.heals * 12)) + '%',
                }"
              ></div>
            </div>
          </div>
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

          <!-- Test Pass Rate Trend -->
          <div v-if="stats.currentAnalysis.results.test_pass_rate_trend" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiTestPassRate') }}</h3></div>
            <div class="p-3">
              <div class="text-sm text-muted mb-2">
                {{ t('stats.analysis.totalTests') }}: {{ stats.currentAnalysis.results.test_pass_rate_trend.total_tests }}
              </div>
              <div v-for="test in stats.currentAnalysis.results.test_pass_rate_trend.tests" :key="test.test_name" class="pass-rate-row">
                <div class="pass-rate-label" :title="test.test_name">{{ test.test_name }}</div>
                <div class="pass-rate-bar-track">
                  <div class="pass-rate-bar pass-bar" :style="{ width: `${test.pass_rate}%` }"></div>
                  <div class="pass-rate-bar fail-bar" :style="{ width: `${100 - test.pass_rate}%` }"></div>
                </div>
                <div class="pass-rate-value">{{ test.pass_rate }}%</div>
              </div>
            </div>
          </div>

          <!-- Slowest Tests -->
          <div v-if="stats.currentAnalysis.results.slowest_tests" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiSlowestTests') }}</h3></div>
            <div class="p-3">
              <div v-for="test in stats.currentAnalysis.results.slowest_tests.tests" :key="test.test_name" class="duration-bar-row">
                <div class="duration-bar-label" :title="test.test_name">{{ test.test_name }}</div>
                <div class="duration-bar-track">
                  <div class="duration-bar-fill" :style="{ width: `${Math.min(test.avg_duration / Math.max(...stats.currentAnalysis!.results!.slowest_tests.tests.map((t: any) => t.avg_duration), 1) * 100, 100)}%` }"></div>
                </div>
                <div class="duration-bar-value">{{ formatDuration(test.avg_duration) }}</div>
              </div>
            </div>
          </div>

          <!-- Flakiness Score -->
          <div v-if="stats.currentAnalysis.results.flakiness_score" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiFlakinessScore') }}</h3></div>
            <div class="p-3">
              <div v-if="stats.currentAnalysis.results.flakiness_score.tests.length">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>{{ t('stats.analysis.testName') }}</th>
                      <th>{{ t('stats.analysis.flakinessScoreLabel') }}</th>
                      <th>{{ t('stats.analysis.transitions') }}</th>
                      <th>{{ t('stats.runs') }}</th>
                      <th>{{ t('stats.analysis.timeline') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="test in stats.currentAnalysis.results.flakiness_score.tests" :key="test.test_name">
                      <td><strong>{{ test.test_name }}</strong><br><span class="text-sm text-muted">{{ test.suite_name }}</span></td>
                      <td><BaseBadge variant="warning">{{ (test.flakiness_score * 100).toFixed(0) }}%</BaseBadge></td>
                      <td>{{ test.transitions }}</td>
                      <td>{{ test.total_runs }}</td>
                      <td>
                        <div class="status-timeline">
                          <span v-for="(run, i) in test.timeline" :key="i"
                            class="status-dot"
                            :class="run.status === 'PASS' ? 'dot-pass' : run.status === 'FAIL' ? 'dot-fail' : 'dot-skip'"
                            :title="run.status"
                          ></span>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-else class="text-muted text-center p-3">{{ t('stats.analysis.noFlakiness') }}</p>
            </div>
          </div>

          <!-- Failure Heatmap -->
          <div v-if="stats.currentAnalysis.results.failure_heatmap" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiFailureHeatmap') }}</h3></div>
            <div class="p-3">
              <div v-if="stats.currentAnalysis.results.failure_heatmap.tests.length" class="heatmap-container">
                <!-- Date header row -->
                <div class="heatmap-row heatmap-header">
                  <div class="heatmap-label"></div>
                  <div class="heatmap-cells">
                    <div v-for="d in stats.currentAnalysis.results.failure_heatmap.dates" :key="d" class="heatmap-cell heatmap-date-label" :title="d">
                      {{ d.slice(5) }}
                    </div>
                  </div>
                </div>
                <!-- Test rows -->
                <div v-for="test in stats.currentAnalysis.results.failure_heatmap.tests" :key="test.test_name" class="heatmap-row">
                  <div class="heatmap-label" :title="test.test_name">{{ test.test_name }}</div>
                  <div class="heatmap-cells">
                    <div v-for="cell in test.cells" :key="cell.date"
                      class="heatmap-cell"
                      :class="cell.status === 'PASS' ? 'cell-pass' : cell.status === 'FAIL' ? 'cell-fail' : 'cell-none'"
                      :title="`${test.test_name} — ${cell.date}: ${cell.status}`"
                    ></div>
                  </div>
                </div>
              </div>
              <p v-else class="text-muted text-center p-3">{{ t('stats.analysis.noHeatmapData') }}</p>
            </div>
          </div>

          <!-- Suite Duration Treemap -->
          <div v-if="stats.currentAnalysis.results.suite_duration_treemap" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiSuiteDuration') }}</h3></div>
            <div class="p-3">
              <div class="text-sm text-muted mb-2">
                {{ t('stats.analysis.totalDuration') }}: {{ formatDuration(stats.currentAnalysis.results.suite_duration_treemap.total_duration) }}
              </div>
              <div class="treemap-container">
                <div v-for="suite in stats.currentAnalysis.results.suite_duration_treemap.suites" :key="suite.suite_name"
                  class="treemap-block"
                  :style="{ flexBasis: `${Math.max(suite.percentage, 5)}%` }"
                  :title="`${suite.suite_name}: ${formatDuration(suite.total_duration)} (${suite.percentage}%)`"
                >
                  <div class="treemap-label">{{ suite.suite_name }}</div>
                  <div class="treemap-value">{{ formatDuration(suite.total_duration) }}</div>
                  <div class="treemap-pct">{{ suite.percentage }}%</div>
                </div>
              </div>
            </div>
          </div>

          <!-- Keyword Reuse Rate -->
          <div v-if="stats.currentAnalysis.results.keyword_reuse_rate" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiKeywordReuseRate') }}</h3></div>
            <div class="p-3">
              <div class="grid grid-2 mb-3">
                <div class="text-center"><div class="kpi-value-sm">{{ stats.currentAnalysis.results.keyword_reuse_rate.reuse_rate }}%</div><div class="kpi-label">{{ t('stats.analysis.reuseRate') }}</div></div>
                <div class="text-center"><div class="kpi-value-sm">{{ stats.currentAnalysis.results.keyword_reuse_rate.most_used_keywords.length }}</div><div class="kpi-label">{{ t('stats.analysis.mostUsedKeywords') }}</div></div>
              </div>
              <table v-if="stats.currentAnalysis.results.keyword_reuse_rate.most_used_keywords.length" class="data-table">
                <thead><tr><th>{{ t('stats.analysis.keyword') }}</th><th>{{ t('stats.analysis.sourceFilePath') }}</th><th>{{ t('stats.analysis.count') }}</th></tr></thead>
                <tbody>
                  <tr v-for="kw in stats.currentAnalysis.results.keyword_reuse_rate.most_used_keywords" :key="kw.name">
                    <td><strong>{{ kw.name }}</strong></td><td class="text-muted text-sm">{{ kw.file }}</td><td>{{ kw.total_usages }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Unused Keywords -->
          <div v-if="stats.currentAnalysis.results.unused_keywords" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiUnusedKeywords') }}</h3></div>
            <div class="p-3">
              <div class="text-sm text-muted mb-2">
                {{ t('stats.analysis.totalUnused') }}: {{ stats.currentAnalysis.results.unused_keywords.total_unused }}
              </div>
              <table v-if="stats.currentAnalysis.results.unused_keywords.unused_keywords.length" class="data-table">
                <thead><tr><th>{{ t('stats.analysis.keyword') }}</th><th>{{ t('stats.analysis.sourceFilePath') }}</th></tr></thead>
                <tbody>
                  <tr v-for="kw in stats.currentAnalysis.results.unused_keywords.unused_keywords" :key="kw.name + kw.file">
                    <td><strong>{{ kw.name }}</strong></td><td class="text-muted text-sm">{{ kw.source }}</td>
                  </tr>
                </tbody>
              </table>
              <p v-else class="text-muted text-center">{{ t('stats.analysis.noCodequalityData') }}</p>
            </div>
          </div>

          <!-- Keyword Duplicates -->
          <div v-if="stats.currentAnalysis.results.keyword_duplicates" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiKeywordDuplicates') }}</h3></div>
            <div class="p-3">
              <div class="text-sm text-muted mb-2">
                {{ t('stats.analysis.totalDuplicates') }}: {{ stats.currentAnalysis.results.keyword_duplicates.total_duplicates }}
              </div>
              <table v-if="stats.currentAnalysis.results.keyword_duplicates.duplicates.length" class="data-table">
                <thead><tr><th>{{ t('stats.analysis.keyword') }}</th><th>{{ t('stats.analysis.sourceFilePath') }}</th><th>{{ t('stats.analysis.count') }}</th></tr></thead>
                <tbody>
                  <tr v-for="kw in stats.currentAnalysis.results.keyword_duplicates.duplicates" :key="kw.name + kw.file">
                    <td><strong>{{ kw.name }}</strong></td><td class="text-muted text-sm">{{ kw.source }}</td><td>{{ kw.total_usages }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Keyword Similarity -->
          <div v-if="stats.currentAnalysis.results.keyword_similarity" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiKeywordSimilarity') }}</h3></div>
            <div class="p-3">
              <div class="text-sm text-muted mb-2">
                {{ t('stats.analysis.totalSimilarPairs') }}: {{ stats.currentAnalysis.results.keyword_similarity.total_similar_pairs }} |
                {{ t('stats.analysis.similarityThreshold') }}: {{ stats.currentAnalysis.results.keyword_similarity.threshold * 100 }}%
              </div>
              <table v-if="stats.currentAnalysis.results.keyword_similarity.pairs.length" class="data-table">
                <thead><tr><th>{{ t('stats.analysis.keyword') }} A</th><th>{{ t('stats.analysis.keyword') }} B</th><th>{{ t('stats.analysis.similarityScore') }}</th></tr></thead>
                <tbody>
                  <tr v-for="(pair, i) in stats.currentAnalysis.results.keyword_similarity.pairs" :key="i">
                    <td><strong>{{ pair.keyword_a }}</strong><div class="text-muted text-sm">{{ pair.source_a }}</div></td>
                    <td><strong>{{ pair.keyword_b }}</strong><div class="text-muted text-sm">{{ pair.source_b }}</div></td>
                    <td><BaseBadge :variant="pair.score >= 95 ? 'danger' : pair.score >= 90 ? 'warning' : 'info'">{{ pair.score }}%</BaseBadge></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Documentation Coverage -->
          <div v-if="stats.currentAnalysis.results.documentation_coverage" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiDocCoverage') }}</h3></div>
            <div class="p-3">
              <div class="grid grid-2 mb-3">
                <div class="text-center"><div class="kpi-value-sm">{{ stats.currentAnalysis.results.documentation_coverage.coverage_rate }}%</div><div class="kpi-label">{{ t('stats.analysis.coverageRate') }}</div></div>
                <div class="text-center"><div class="kpi-value-sm">{{ stats.currentAnalysis.results.documentation_coverage.total_undocumented }}</div><div class="kpi-label">{{ t('stats.analysis.totalUndocumented') }}</div></div>
              </div>
              <div class="progress-container mb-3">
                <div class="progress-bar" :style="{ width: `${stats.currentAnalysis.results.documentation_coverage.coverage_rate}%`, background: stats.currentAnalysis.results.documentation_coverage.coverage_rate >= 80 ? 'var(--color-success)' : stats.currentAnalysis.results.documentation_coverage.coverage_rate >= 50 ? 'var(--color-warning)' : 'var(--color-danger)' }"></div>
              </div>
              <table v-if="stats.currentAnalysis.results.documentation_coverage.undocumented.length" class="data-table">
                <thead><tr><th>{{ t('stats.analysis.keyword') }}</th><th>{{ t('stats.analysis.sourceFilePath') }}</th></tr></thead>
                <tbody>
                  <tr v-for="kw in stats.currentAnalysis.results.documentation_coverage.undocumented" :key="kw.name + kw.file">
                    <td><strong>{{ kw.name }}</strong></td><td class="text-muted text-sm">{{ kw.source }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Robocop Violations -->
          <div v-if="stats.currentAnalysis.results.robocop_violations" class="card mb-3">
            <div class="card-header"><h3>{{ t('stats.analysis.kpiRobocopViolations') }}</h3></div>
            <div class="p-3">
              <div class="text-sm text-muted mb-2">
                {{ t('stats.analysis.totalViolations') }}: {{ stats.currentAnalysis.results.robocop_violations.total_violations }}
              </div>
              <!-- Category breakdown -->
              <div v-if="stats.currentAnalysis.results.robocop_violations.by_category.length" class="mb-3">
                <h4 class="text-sm mb-2">{{ t('stats.analysis.violationsByCategory') }}</h4>
                <div v-for="cat in stats.currentAnalysis.results.robocop_violations.by_category" :key="cat.category" class="lib-bar-row">
                  <div class="lib-bar-label">{{ cat.category }}</div>
                  <div class="lib-bar-track">
                    <div class="lib-bar-fill" :style="{ width: `${Math.min(cat.count / Math.max(...stats.currentAnalysis!.results!.robocop_violations.by_category.map((c: any) => c.count), 1) * 100, 100)}%` }"></div>
                  </div>
                  <div class="lib-bar-value">{{ cat.count }}</div>
                </div>
              </div>
              <!-- Top violations -->
              <table v-if="stats.currentAnalysis.results.robocop_violations.top_violations.length" class="data-table">
                <thead><tr><th>{{ t('stats.analysis.violationRule') }}</th><th>{{ t('stats.analysis.violationMessage') }}</th><th>{{ t('stats.analysis.violationSeverity') }}</th><th>{{ t('stats.analysis.sourceFilePath') }}</th></tr></thead>
                <tbody>
                  <tr v-for="(v, i) in stats.currentAnalysis.results.robocop_violations.top_violations.slice(0, 20)" :key="i">
                    <td><code>{{ v.rule_id }}</code></td>
                    <td class="text-sm">{{ v.message }}</td>
                    <td><BaseBadge :variant="v.severity === 'ERROR' ? 'danger' : v.severity === 'WARNING' ? 'warning' : 'info'">{{ v.severity }}</BaseBadge></td>
                    <td class="text-muted text-sm">{{ v.file }}</td>
                  </tr>
                </tbody>
              </table>
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
/* Day with no executions: keeps its slot width (so the time axis stays
   evenly spaced) but shows only a faint baseline tick instead of a bar. */
.bar-empty {
  height: 3px;
  background: var(--color-border);
  opacity: 0.6;
  cursor: default;
}
.bar-empty:hover { opacity: 1; }

.chart-x-axis {
  /* Same flex layout as `.mini-chart` so the slots align with bars
     1:1. `align-items: flex-start` keeps labels glued to the top of
     the row (right under the bar bases). */
  display: flex;
  align-items: flex-start;
  gap: 3px;
  margin-top: 6px;
}

.chart-x-slot {
  flex: 1;
  min-width: 4px;
  max-width: 20px;
  text-align: center;
  font-size: 11px;
  color: var(--color-text-muted);
  /* Long-date strings (`12.5.`) easily exceed 20px — let the slot
     keep its grid position but render the text overflowing without
     pushing siblings out of alignment. */
  overflow: visible;
  white-space: nowrap;
}

/* Backward compat for any direct consumers of the old class. */
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
  color: var(--color-primary, #3B7DD8);
  border-bottom-color: var(--color-primary, #3B7DD8);
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
  background: var(--color-primary, #3B7DD8);
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
.lib-bar-fill { height: 100%; background: var(--color-primary, #3B7DD8); border-radius: 3px; transition: width 0.3s; }
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
.histogram-fill { height: 100%; background: var(--color-accent, #D4883E); border-radius: 3px; }
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
  background: var(--color-primary, #3B7DD8);
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

/* Pass Rate Trend (stacked horizontal bars) */
.pass-rate-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.pass-rate-label { width: 180px; font-size: 12px; text-align: right; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pass-rate-bar-track { flex: 1; height: 18px; display: flex; border-radius: 3px; overflow: hidden; }
.pass-rate-bar { height: 100%; transition: width 0.3s; }
.pass-bar { background: var(--color-success); }
.fail-bar { background: var(--color-danger); opacity: 0.7; }
.pass-rate-value { width: 50px; font-size: 12px; color: var(--color-text-muted); text-align: right; }

/* Duration Bar (slowest tests) */
.duration-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.duration-bar-label { width: 180px; font-size: 12px; text-align: right; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.duration-bar-track { flex: 1; height: 18px; background: var(--color-bg, #f4f7fa); border-radius: 3px; overflow: hidden; }
.duration-bar-fill { height: 100%; background: var(--color-accent, #D4883E); border-radius: 3px; transition: width 0.3s; }
.duration-bar-value { width: 80px; font-size: 12px; color: var(--color-text-muted); }

/* Status Timeline (flakiness) */
.status-timeline { display: flex; gap: 3px; align-items: center; flex-wrap: wrap; }
.status-dot {
  width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
}
.dot-pass { background: var(--color-success); }
.dot-fail { background: var(--color-danger); }
.dot-skip { background: var(--color-text-muted); opacity: 0.4; }

/* Failure Heatmap */
.heatmap-container { overflow-x: auto; }
.heatmap-row { display: flex; align-items: center; margin-bottom: 2px; }
.heatmap-header { margin-bottom: 4px; }
.heatmap-label { width: 160px; font-size: 11px; text-align: right; flex-shrink: 0; padding-right: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.heatmap-cells { display: flex; gap: 2px; flex: 1; }
.heatmap-cell { width: 20px; height: 20px; border-radius: 3px; flex-shrink: 0; }
.heatmap-date-label { font-size: 9px; color: var(--color-text-muted); text-align: center; line-height: 20px; background: none !important; }
.cell-pass { background: var(--color-success); opacity: 0.7; }
.cell-fail { background: var(--color-danger); opacity: 0.8; }
.cell-none { background: var(--color-bg, #f4f7fa); }

/* Suite Duration Treemap */
.treemap-container {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-height: 80px;
}
.treemap-block {
  background: var(--color-primary, #3B7DD8);
  color: white;
  border-radius: 6px;
  padding: 10px;
  min-width: 60px;
  min-height: 60px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  flex-grow: 1;
  cursor: default;
  transition: opacity 0.2s;
}
.treemap-block:hover { opacity: 0.85; }
.treemap-block:nth-child(2n) { background: var(--color-accent, #D4883E); }
.treemap-block:nth-child(3n) { background: var(--color-navy, #1A2D50); }
.treemap-label { font-size: 11px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.treemap-value { font-size: 13px; font-weight: 700; }
.treemap-pct { font-size: 10px; opacity: 0.8; }

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

/* Story SH-6 — heal-rate card. Neutral styling that matches the
   other cards in StatsView (no gradient, no accent border, no
   purple text); sits at the bottom of the overview tab as one of
   N stats rather than as a hero metric. */
.heal-kpi__row {
  display: flex;
  align-items: stretch;
  gap: 20px;
  padding: 16px 20px;
}
.heal-kpi__body { flex: 1; }
.heal-kpi__value {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 15px;
  color: var(--color-text);
}
.heal-kpi__big {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-navy, #1A2D50);
}
.heal-kpi__label {
  color: var(--color-text-muted);
  font-size: 13px;
}
.heal-kpi__sub {
  margin: 4px 0 10px;
  color: var(--color-text-muted);
  font-size: 13px;
}
.heal-kpi__badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.heal-kpi__badge {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.heal-kpi__badge--confirmed {
  background: #dcfce7;
  color: #166534;
}
.heal-kpi__badge--suspect {
  background: #fee2e2;
  color: #991b1b;
}
.heal-kpi__sparkline {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  min-width: 180px;
  height: 64px;
  padding: 0 4px;
  border-left: 1px dashed var(--color-border);
}
.heal-kpi__bar {
  flex: 1;
  background: var(--color-primary, #3B7DD8);
  border-radius: 2px 2px 0 0;
  min-height: 2px;
  transition: height 0.2s ease;
  opacity: 0.7;
}

/* Story FLAKY-1 — quarantine column + row styling */
.row-quarantined {
  background: rgba(148, 163, 184, 0.08);
}
.row-quarantined td {
  color: var(--color-text-muted);
}
.row-quarantined td strong {
  text-decoration: line-through dotted rgba(148, 163, 184, 0.55);
}
.quarantine-badge {
  display: inline-block;
  padding: 2px 8px;
  background: #fef3c7;
  color: #854d0e;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  margin-right: 6px;
}
.quarantine-btn {
  padding: 3px 9px;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 11px;
  color: var(--color-text);
  cursor: pointer;
  margin-left: 4px;
}
.quarantine-btn:hover:not(:disabled) {
  background: var(--color-primary, #3B7DD8);
  color: white;
  border-color: var(--color-primary, #3B7DD8);
}
.quarantine-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
