<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useStatsStore } from '@/stores/stats.store'
import { useExecutionStore } from '@/stores/execution.store'
import { useReposStore } from '@/stores/repos.store'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import { formatDuration } from '@/utils/formatDuration'
import { formatTimeAgo } from '@/utils/formatDate'

const router = useRouter()
const stats = useStatsStore()
const execution = useExecutionStore()
const repos = useReposStore()
const { t } = useI18n()

function goToRun(runId: number) {
  router.push({ path: '/runs', query: { run: String(runId) } })
}

function goToExplorer(repoId: number) {
  router.push({ name: 'explorer', params: { repoId: String(repoId) } })
}

onMounted(async () => {
  await Promise.all([
    stats.fetchAll(),
    execution.fetchRuns({ page: 1 }),
    repos.fetchRepos(),
  ])
})
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('dashboard.title') }}</h1>
    </div>

    <BaseSpinner v-if="stats.loading" />

    <template v-else-if="stats.overview">
      <!-- KPI Cards -->
      <div class="grid grid-4 mb-4">
        <div class="card kpi-card">
          <div class="kpi-value">{{ stats.overview.total_runs }}</div>
          <div class="kpi-label">{{ t('dashboard.runs30d') }}</div>
        </div>
        <div class="card kpi-card">
          <div class="kpi-value" :class="stats.overview.success_rate >= 80 ? 'text-success' : 'text-danger'">
            {{ stats.overview.success_rate }}%
          </div>
          <div class="kpi-label">{{ t('dashboard.successRate') }}</div>
        </div>
        <div class="card kpi-card">
          <div class="kpi-value">{{ formatDuration(stats.overview.avg_duration_seconds) }}</div>
          <div class="kpi-label">{{ t('dashboard.avgDuration') }}</div>
        </div>
        <div class="card kpi-card">
          <div class="kpi-value">{{ stats.overview.active_repos }}</div>
          <div class="kpi-label">{{ t('dashboard.activeRepos') }}</div>
        </div>
      </div>

      <!-- Recent Runs -->
      <div class="card mb-4">
        <div class="card-header">
          <h3>{{ t('dashboard.recentRuns') }}</h3>
          <router-link to="/runs" class="text-sm">{{ t('dashboard.showAll') }}</router-link>
        </div>
        <div v-if="execution.runs.length" class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ t('common.id') }}</th>
              <th>{{ t('dashboard.target') }}</th>
              <th>{{ t('common.status') }}</th>
              <th>{{ t('common.duration') }}</th>
              <th>{{ t('common.created') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="run in execution.runs.slice(0, 10)"
              :key="run.id"
              class="clickable-row"
              @click="goToRun(run.id)"
            >
              <td>#{{ run.id }}</td>
              <td class="text-sm">{{ run.target_path }}</td>
              <td><BaseBadge :status="run.status" /></td>
              <td>{{ formatDuration(run.duration_seconds) }}</td>
              <td class="text-muted text-sm">{{ formatTimeAgo(run.created_at) }}</td>
            </tr>
          </tbody>
        </table>
        </div>
        <p v-else class="text-muted text-center p-4">{{ t('dashboard.noRuns') }}</p>
      </div>

      <!-- Repos Overview -->
      <div class="card">
        <div class="card-header">
          <h3>{{ t('dashboard.repositories') }}</h3>
          <router-link to="/repos" class="text-sm">{{ t('dashboard.manage') }}</router-link>
        </div>
        <div class="repo-grid" v-if="repos.repos.length">
          <button
            v-for="repo in repos.repos"
            :key="repo.id"
            type="button"
            class="repo-item"
            :title="t('dashboard.openInExplorer', { name: repo.name })"
            data-testid="dashboard-repo-card"
            @click="goToExplorer(repo.id)"
          >
            <strong>{{ repo.name }}</strong>
            <span class="text-muted text-sm">{{ repo.default_branch }}</span>
            <span class="text-muted text-sm">{{ formatTimeAgo(repo.last_synced_at) }}</span>
          </button>
        </div>
        <p v-else class="text-muted text-center p-4">{{ t('dashboard.noRepos') }}</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.kpi-card {
  text-align: center;
  padding: 24px 16px;
}

.kpi-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text);
}

.kpi-value.text-success { color: var(--color-success); }
.kpi-value.text-danger { color: var(--color-danger); }

.kpi-label {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.clickable-row {
  cursor: pointer;
  transition: background-color 0.15s;
}

.clickable-row:hover {
  background: var(--color-bg-hover, #f8fafc);
}

.repo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

/* Repo card. Now a <button> so it's keyboard-focusable and the
   click handler navigates to /explorer/:repoId. The button reset
   strips the default UA styling so it renders identically to the
   pre-button card layout, then we layer on a hover affordance. */
.repo-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 12px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  background: var(--color-bg-card, #fff);
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.15s, border-color 0.15s, transform 0.05s;
}
.repo-item:hover {
  background: var(--color-bg-hover, #f8fafc);
  border-color: var(--color-primary, #3B7DD8);
}
.repo-item:active {
  transform: translateY(1px);
}
.repo-item:focus-visible {
  outline: 2px solid var(--color-primary, #3B7DD8);
  outline-offset: 2px;
}
</style>
