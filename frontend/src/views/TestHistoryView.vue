<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getUniqueTests, getTestHistory } from '@/api/reports.api'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { formatDuration } from '@/utils/formatDuration'
import type { UniqueTest, TestHistory } from '@/types/domain.types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const search = ref('')
const uniqueTests = ref<UniqueTest[]>([])
const loadingTests = ref(false)
const selectedTest = ref<UniqueTest | null>(null)
const history = ref<TestHistory | null>(null)
const loadingHistory = ref(false)
const days = ref(90)

async function fetchTests() {
  loadingTests.value = true
  try {
    uniqueTests.value = await getUniqueTests(search.value || undefined)
  } catch {
    uniqueTests.value = []
  } finally {
    loadingTests.value = false
  }
}

async function selectTest(test: UniqueTest) {
  selectedTest.value = test
  loadingHistory.value = true
  try {
    history.value = await getTestHistory(test.test_name, test.suite_name, days.value)
  } catch {
    history.value = null
  } finally {
    loadingHistory.value = false
  }
}

// If test_name is passed via query param, auto-select it
onMounted(async () => {
  await fetchTests()
  const qTest = route.query.test as string | undefined
  const qSuite = route.query.suite as string | undefined
  if (qTest) {
    const match = uniqueTests.value.find(
      t => t.test_name === qTest && (!qSuite || t.suite_name === qSuite)
    )
    if (match) {
      selectTest(match)
    } else {
      // Direct lookup even if not in the top list
      selectedTest.value = { test_name: qTest, suite_name: qSuite || '', last_status: '', run_count: 0 }
      loadingHistory.value = true
      try {
        history.value = await getTestHistory(qTest, qSuite, days.value)
      } catch {
        history.value = null
      } finally {
        loadingHistory.value = false
      }
    }
  }
})

let searchTimeout: ReturnType<typeof setTimeout>
watch(search, () => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(fetchTests, 300)
})

function statusColor(status: string): string {
  if (status === 'PASS') return 'var(--color-success)'
  if (status === 'FAIL') return 'var(--color-danger)'
  return 'var(--color-text-muted)'
}
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('testHistory.title') }}</h1>
      <router-link to="/stats">
        <BaseButton variant="secondary">&larr; {{ t('nav.stats') }}</BaseButton>
      </router-link>
    </div>

    <div class="history-layout">
      <!-- Test List Panel -->
      <div class="card test-list-panel">
        <div class="search-box">
          <input
            v-model="search"
            class="form-input"
            :placeholder="t('testHistory.searchPlaceholder')"
          />
        </div>

        <BaseSpinner v-if="loadingTests" />

        <div v-else class="test-list">
          <div
            v-for="test in uniqueTests"
            :key="`${test.suite_name}::${test.test_name}`"
            class="test-list-item"
            :class="{ active: selectedTest?.test_name === test.test_name && selectedTest?.suite_name === test.suite_name }"
            @click="selectTest(test)"
          >
            <div class="test-list-name">
              <strong>{{ test.test_name }}</strong>
              <span class="text-muted text-sm">{{ test.suite_name }}</span>
            </div>
            <div class="test-list-meta">
              <BaseBadge :status="test.last_status" />
              <span class="text-muted text-sm">{{ test.run_count }}x</span>
            </div>
          </div>
          <p v-if="!uniqueTests.length" class="text-muted text-center p-4">
            {{ t('testHistory.noTests') }}
          </p>
        </div>
      </div>

      <!-- History Detail Panel -->
      <div class="history-detail-panel">
        <template v-if="selectedTest">
          <div class="card mb-4">
            <h2>{{ selectedTest.test_name }}</h2>
            <p class="text-muted text-sm">{{ selectedTest.suite_name }}</p>
          </div>

          <BaseSpinner v-if="loadingHistory" />

          <template v-else-if="history">
            <!-- KPI Summary -->
            <div class="grid grid-4 mb-4">
              <div class="card kpi-card">
                <div class="kpi-value">{{ history.total_runs }}</div>
                <div class="kpi-label">{{ t('testHistory.totalRuns') }}</div>
              </div>
              <div class="card kpi-card">
                <div class="kpi-value text-success">{{ history.pass_count }}</div>
                <div class="kpi-label">{{ t('reportDetail.passed') }}</div>
              </div>
              <div class="card kpi-card">
                <div class="kpi-value text-danger">{{ history.fail_count }}</div>
                <div class="kpi-label">{{ t('reportDetail.failed') }}</div>
              </div>
              <div class="card kpi-card">
                <div class="kpi-value" :class="history.pass_rate >= 80 ? 'text-success' : 'text-danger'">
                  {{ history.pass_rate }}%
                </div>
                <div class="kpi-label">{{ t('testHistory.passRate') }}</div>
              </div>
            </div>

            <!-- Timeline Bar -->
            <div class="card mb-4">
              <div class="card-header">
                <h3>{{ t('testHistory.timeline') }}</h3>
              </div>
              <div class="timeline-bar">
                <div
                  v-for="(point, idx) in history.history"
                  :key="idx"
                  class="timeline-block"
                  :style="{ backgroundColor: statusColor(point.status) }"
                  :title="`${point.date.split('T')[0]} — ${point.status} (${formatDuration(point.duration_seconds)})`"
                ></div>
              </div>
              <div class="timeline-legend">
                <span class="text-muted text-sm" v-if="history.history.length">
                  {{ history.history[0].date.split('T')[0] }}
                </span>
                <span class="text-muted text-sm" v-if="history.history.length > 1">
                  {{ history.history[history.history.length - 1].date.split('T')[0] }}
                </span>
              </div>
            </div>

            <!-- History Table -->
            <div class="card">
              <div class="card-header">
                <h3>{{ t('testHistory.runs') }}</h3>
              </div>
              <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>{{ t('testHistory.date') }}</th>
                    <th>{{ t('common.status') }}</th>
                    <th>{{ t('common.duration') }}</th>
                    <th>{{ t('reportDetail.errorCol') }}</th>
                    <th>{{ t('testHistory.report') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="point in [...history.history].reverse()" :key="point.report_id">
                    <td class="text-sm">{{ point.date.split('T')[0] }}</td>
                    <td><BaseBadge :status="point.status" /></td>
                    <td>{{ formatDuration(point.duration_seconds) }}</td>
                    <td class="text-sm error-cell">{{ point.error_message || '-' }}</td>
                    <td>
                      <router-link :to="`/reports/${point.report_id}`" class="text-sm">
                        #{{ point.report_id }}
                      </router-link>
                    </td>
                  </tr>
                </tbody>
              </table>
              </div>
            </div>
          </template>
        </template>

        <div v-else class="card text-center p-6">
          <p class="text-muted">{{ t('testHistory.selectTest') }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-layout {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 16px;
  align-items: start;
}

.test-list-panel {
  padding: 0;
  max-height: calc(100vh - 180px);
  display: flex;
  flex-direction: column;
}

.search-box {
  padding: 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.test-list {
  overflow-y: auto;
  flex: 1;
}

.test-list-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  border-bottom: 1px solid var(--color-border-light);
  transition: background 0.1s;
}

.test-list-item:hover {
  background: var(--color-bg);
}

.test-list-item.active {
  background: var(--color-primary-bg);
  border-left: 3px solid var(--color-primary);
}

.test-list-name {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  overflow: hidden;
}

.test-list-name strong {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 13px;
}

.test-list-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.kpi-card { text-align: center; padding: 20px 16px; }
.kpi-value { font-size: 28px; font-weight: 700; }
.kpi-value.text-success { color: var(--color-success); }
.kpi-value.text-danger { color: var(--color-danger); }
.kpi-label { font-size: 12px; color: var(--color-text-muted); margin-top: 4px; text-transform: uppercase; }

.timeline-bar {
  display: flex;
  gap: 2px;
  min-height: 32px;
  align-items: stretch;
}

.timeline-block {
  flex: 1;
  min-width: 4px;
  border-radius: 3px;
  transition: opacity 0.15s;
}

.timeline-block:hover {
  opacity: 0.7;
}

.timeline-legend {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
}

.error-cell {
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-danger);
}

@media (max-width: 768px) {
  .history-layout {
    grid-template-columns: 1fr;
  }

  .test-list-panel {
    max-height: 300px;
  }
}
</style>
