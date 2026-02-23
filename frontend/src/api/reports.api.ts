import apiClient from './client'
import type { Report, ReportDetail, TestHistory, TestResult, UniqueTest, XmlReportData } from '@/types/domain.types'

export async function getReports(params: {
  page?: number
  page_size?: number
  repository_id?: number
} = {}): Promise<Report[]> {
  const response = await apiClient.get<Report[]>('/reports', { params })
  return response.data
}

export async function getReport(id: number): Promise<ReportDetail> {
  const response = await apiClient.get<ReportDetail>(`/reports/${id}`)
  return response.data
}

export function getReportHtmlUrl(id: number): string {
  const baseUrl = apiClient.defaults.baseURL || '/api/v1'
  const token = localStorage.getItem('access_token') || ''
  return `${baseUrl}/reports/${id}/html?token=${encodeURIComponent(token)}`
}

export function getReportZipUrl(id: number): string {
  const baseUrl = apiClient.defaults.baseURL || '/api/v1'
  const token = localStorage.getItem('access_token') || ''
  return `${baseUrl}/reports/${id}/zip?token=${encodeURIComponent(token)}`
}

export function getReportAssetUrl(reportId: number, filename: string): string {
  const baseUrl = apiClient.defaults.baseURL || '/api/v1'
  return `${baseUrl}/reports/${reportId}/assets/${encodeURIComponent(filename)}`
}

export async function getReportXmlData(id: number): Promise<XmlReportData> {
  const response = await apiClient.get<XmlReportData>(`/reports/${id}/xml-data`)
  return response.data
}

export async function getReportTests(id: number, status?: string): Promise<TestResult[]> {
  const response = await apiClient.get<TestResult[]>(`/reports/${id}/tests`, {
    params: status ? { status } : {},
  })
  return response.data
}

export async function deleteAllReports(): Promise<{ deleted: number; dirs_cleaned: number }> {
  const response = await apiClient.delete<{ deleted: number; dirs_cleaned: number }>('/reports/all')
  return response.data
}

export async function uploadReportArchive(file: File): Promise<ReportDetail> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiClient.post<ReportDetail>('/reports/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function getUniqueTests(search?: string, limit = 50): Promise<UniqueTest[]> {
  const response = await apiClient.get<UniqueTest[]>('/reports/tests/unique', {
    params: { search, limit },
  })
  return response.data
}

export async function getTestHistory(
  testName: string,
  suiteName?: string,
  days = 90,
): Promise<TestHistory> {
  const response = await apiClient.get<TestHistory>('/reports/tests/history', {
    params: { test_name: testName, suite_name: suiteName, days },
  })
  return response.data
}

export async function compareReports(reportA: number, reportB: number): Promise<{
  report_a: Report
  report_b: Report
  new_failures: string[]
  fixed_tests: string[]
  consistent_failures: string[]
  duration_diff_seconds: number
}> {
  const response = await apiClient.get('/reports/compare', {
    params: { report_a: reportA, report_b: reportB },
  })
  return response.data
}
