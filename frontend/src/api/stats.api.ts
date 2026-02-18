import apiClient from './client'
import type { FlakyTest, OverviewKpi, SuccessRatePoint, TrendPoint } from '@/types/domain.types'

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
