import apiClient from './client'
import type { AnalysisReport, FlakyTest, KpiMeta, OverviewKpi, SuccessRatePoint, TrendPoint } from '@/types/domain.types'

export async function getOverview(params: { days?: number; repository_id?: number } = {}): Promise<OverviewKpi> {
  const response = await apiClient.get<OverviewKpi>('/stats/overview', { params })
  return response.data
}

export async function getSuccessRate(params: { days?: number; repository_id?: number } = {}): Promise<SuccessRatePoint[]> {
  const response = await apiClient.get<SuccessRatePoint[]>('/stats/success-rate', { params })
  return response.data
}

export async function getTrends(params: { days?: number; repository_id?: number } = {}): Promise<TrendPoint[]> {
  const response = await apiClient.get<TrendPoint[]>('/stats/trends', { params })
  return response.data
}

export async function getFlakyTests(params: { days?: number; min_runs?: number; repository_id?: number } = {}): Promise<FlakyTest[]> {
  const response = await apiClient.get<FlakyTest[]>('/stats/flaky', { params })
  return response.data
}

export async function getDurationStats(params: { days?: number; repository_id?: number; limit?: number } = {}): Promise<any[]> {
  const response = await apiClient.get('/stats/duration', { params })
  return response.data
}

export async function getHeatmap(params: { days?: number; repository_id?: number; limit?: number } = {}): Promise<any[]> {
  const response = await apiClient.get('/stats/heatmap', { params })
  return response.data
}

// --- Aggregation & Data Status ---

export async function aggregateKpis(days: number = 365): Promise<{ status: string; aggregated: number }> {
  const response = await apiClient.post<{ status: string; aggregated: number }>('/stats/aggregate', null, {
    params: { days },
  })
  return response.data
}

export async function getDataStatus(): Promise<{ last_aggregated: string | null; last_run_finished: string | null }> {
  const response = await apiClient.get<{ last_aggregated: string | null; last_run_finished: string | null }>('/stats/data-status')
  return response.data
}

// --- Analysis ---

export async function getAvailableKpis(): Promise<Record<string, KpiMeta>> {
  const response = await apiClient.get<Record<string, KpiMeta>>('/stats/analysis/kpis')
  return response.data
}

export async function createAnalysis(data: {
  repository_id?: number | null
  selected_kpis: string[]
  date_from?: string | null
  date_to?: string | null
}): Promise<AnalysisReport> {
  const response = await apiClient.post<AnalysisReport>('/stats/analysis', data)
  return response.data
}

export async function listAnalyses(page = 1, pageSize = 20): Promise<AnalysisReport[]> {
  const response = await apiClient.get<AnalysisReport[]>('/stats/analysis', {
    params: { page, page_size: pageSize },
  })
  return response.data
}

export async function getAnalysis(id: number): Promise<AnalysisReport> {
  const response = await apiClient.get<AnalysisReport>(`/stats/analysis/${id}`)
  return response.data
}
