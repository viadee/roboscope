<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStatsStore } from '@/stores/stats.store'
import { useReposStore } from '@/stores/repos.store'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { formatDuration, formatPercent } from '@/utils/formatDuration'

const stats = useStatsStore()
const repos = useReposStore()
const { t } = useI18n()

const selectedDays = ref(30)
const selectedRepoId = ref<number | null>(null)

onMounted(async () => {
  await repos.fetchRepos()
  await stats.fetchAll()
})

watch([selectedDays, selectedRepoId], async () => {
  stats.setFilter(selectedDays.value, selectedRepoId.value)
  await stats.fetchAll()
})
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
      </div>
    </div>

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
.mini-chart {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 120px;
  padding: 0 8px;
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
</style>
