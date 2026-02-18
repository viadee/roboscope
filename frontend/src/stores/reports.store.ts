import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as reportsApi from '@/api/reports.api'
import type { Report, ReportDetail } from '@/types/domain.types'

export const useReportsStore = defineStore('reports', () => {
  const reports = ref<Report[]>([])
  const activeReport = ref<ReportDetail | null>(null)
  const loading = ref(false)

  async function fetchReports(params: { page?: number; repository_id?: number } = {}) {
    loading.value = true
    try {
      reports.value = await reportsApi.getReports(params)
    } finally {
      loading.value = false
    }
  }

  async function fetchReport(id: number) {
    loading.value = true
    try {
      activeReport.value = await reportsApi.getReport(id)
    } finally {
      loading.value = false
    }
  }

  async function deleteAllReports() {
    const result = await reportsApi.deleteAllReports()
    reports.value = []
    return result
  }

  async function compareReports(reportA: number, reportB: number) {
    return await reportsApi.compareReports(reportA, reportB)
  }

  return { reports, activeReport, loading, fetchReports, fetchReport, deleteAllReports, compareReports }
})
