/**
 * V14.3 — "Export CSV" / "Export JSON" on the report detail view call the
 * export API with the right format and trigger a blob download.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import ReportDetailView from '@/views/ReportDetailView.vue'
import en from '@/i18n/locales/en'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '7' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/api/reports.api', () => ({
  getReport: vi.fn(() => new Promise(() => {})),
  getReportHtmlBlobUrl: vi.fn(async () => ''),
  getReportZipBlobUrl: vi.fn(),
  getMissingLibraries: vi.fn(async () => ({ environment_id: null, environment_name: null, libraries: [] })),
  exportReportResults: vi.fn(async () => new Blob(['x'])),
}))

vi.mock('@/api/ai.api', () => ({
  getProviders: vi.fn(async () => []),
  listProviders: vi.fn(async () => []),
}))

import { exportReportResults } from '@/api/reports.api'

beforeEach(() => {
  vi.clearAllMocks()
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
})

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(ReportDetailView, {
    global: {
      plugins: [createI18n({ legacy: false, locale: 'en', messages: { en } }), pinia],
      stubs: { 'router-link': true, ReportXmlView: true, RunDiagnosticBanner: true, AnalysisPatches: true },
    },
  })
  await flushPromises()
  return wrapper
}

describe('ReportDetailView — export buttons', () => {
  it.each(['csv', 'json'] as const)('Export %s downloads report_<id>_results.<fmt>', async (fmt) => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.download).toBe(`report_7_results.${fmt}`)
    })
    const wrapper = await mountView()

    await wrapper.find(`[data-testid="export-${fmt}"]`).trigger('click')
    await flushPromises()

    expect(exportReportResults).toHaveBeenCalledWith(7, fmt)
    expect(click).toHaveBeenCalledTimes(1)
    click.mockRestore()
  })
})
