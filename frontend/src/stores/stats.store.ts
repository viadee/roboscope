import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as statsApi from '@/api/stats.api'
import type { FlakyTest, OverviewKpi, SuccessRatePoint, TrendPoint } from '@/types/domain.types'

export const useStatsStore = defineStore('stats', () => {
  const overview = ref<OverviewKpi | null>(null)
  const successRate = ref<SuccessRatePoint[]>([])
  const trends = ref<TrendPoint[]>([])
  const flakyTests = ref<FlakyTest[]>([])
  const loading = ref(false)

  // Filter state
  const filterDays = ref(30)
  const filterRepoId = ref<number | null>(null)

  async function fetchOverview() {
    overview.value = await statsApi.getOverview({ days: filterDays.value, repository_id: filterRepoId.value ?? undefined })
  }

  async function fetchSuccessRate() {
    successRate.value = await statsApi.getSuccessRate({ days: filterDays.value, repository_id: filterRepoId.value ?? undefined })
  }

  async function fetchTrends() {
    trends.value = await statsApi.getTrends({ days: filterDays.value, repository_id: filterRepoId.value ?? undefined })
  }

  async function fetchFlakyTests() {
    flakyTests.value = await statsApi.getFlakyTests({ days: filterDays.value, repository_id: filterRepoId.value ?? undefined })
  }

  async function fetchAll() {
    loading.value = true
    try {
      await Promise.all([fetchOverview(), fetchSuccessRate(), fetchTrends(), fetchFlakyTests()])
    } finally {
      loading.value = false
    }
  }

  function setFilter(days: number, repoId: number | null) {
    filterDays.value = days
    filterRepoId.value = repoId
  }

  return {
    overview, successRate, trends, flakyTests, loading, filterDays, filterRepoId,
    fetchOverview, fetchSuccessRate, fetchTrends, fetchFlakyTests, fetchAll, setFilter,
  }
})
