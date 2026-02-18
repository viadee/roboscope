import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as statsApi from '@/api/stats.api'
import type { AnalysisReport, FlakyTest, KpiMeta, OverviewKpi, SuccessRatePoint, TrendPoint } from '@/types/domain.types'

export const useStatsStore = defineStore('stats', () => {
  const overview = ref<OverviewKpi | null>(null)
  const successRate = ref<SuccessRatePoint[]>([])
  const trends = ref<TrendPoint[]>([])
  const flakyTests = ref<FlakyTest[]>([])
  const loading = ref(false)

  // Filter state
  const filterDays = ref(30)
  const filterRepoId = ref<number | null>(null)

  // Data status (staleness)
  const lastAggregated = ref<string | null>(null)
  const lastRunFinished = ref<string | null>(null)
  const aggregating = ref(false)

  // Analysis state
  const analyses = ref<AnalysisReport[]>([])
  const currentAnalysis = ref<AnalysisReport | null>(null)
  const availableKpis = ref<Record<string, KpiMeta>>({})
  const analysisLoading = ref(false)

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
      await Promise.all([fetchOverview(), fetchSuccessRate(), fetchTrends(), fetchFlakyTests(), fetchDataStatus()])
    } finally {
      loading.value = false
    }
  }

  function setFilter(days: number, repoId: number | null) {
    filterDays.value = days
    filterRepoId.value = repoId
  }

  async function fetchDataStatus() {
    const status = await statsApi.getDataStatus()
    lastAggregated.value = status.last_aggregated
    lastRunFinished.value = status.last_run_finished
  }

  async function aggregateKpis() {
    aggregating.value = true
    try {
      await statsApi.aggregateKpis(filterDays.value)
      await Promise.all([fetchAll(), fetchDataStatus()])
    } finally {
      aggregating.value = false
    }
  }

  // Analysis actions

  async function fetchAvailableKpis() {
    if (Object.keys(availableKpis.value).length > 0) return
    availableKpis.value = await statsApi.getAvailableKpis()
  }

  async function fetchAnalyses() {
    analysisLoading.value = true
    try {
      analyses.value = await statsApi.listAnalyses()
    } finally {
      analysisLoading.value = false
    }
  }

  async function createAnalysis(data: { repository_id?: number | null; selected_kpis: string[]; date_from?: string | null; date_to?: string | null }) {
    const analysis = await statsApi.createAnalysis(data)
    analyses.value.unshift(analysis)
    return analysis
  }

  async function fetchAnalysis(id: number) {
    analysisLoading.value = true
    try {
      currentAnalysis.value = await statsApi.getAnalysis(id)
    } finally {
      analysisLoading.value = false
    }
  }

  function updateAnalysisFromWs(id: number, status: string, progress: number) {
    const idx = analyses.value.findIndex(a => a.id === id)
    if (idx >= 0) {
      analyses.value[idx] = { ...analyses.value[idx], status: status as any, progress }
    }
    if (currentAnalysis.value?.id === id) {
      currentAnalysis.value = { ...currentAnalysis.value, status: status as any, progress }
    }
  }

  return {
    overview, successRate, trends, flakyTests, loading, filterDays, filterRepoId,
    lastAggregated, lastRunFinished, aggregating,
    fetchOverview, fetchSuccessRate, fetchTrends, fetchFlakyTests, fetchAll, setFilter,
    fetchDataStatus, aggregateKpis,
    analyses, currentAnalysis, availableKpis, analysisLoading,
    fetchAvailableKpis, fetchAnalyses, createAnalysis, fetchAnalysis, updateAnalysisFromWs,
  }
})
