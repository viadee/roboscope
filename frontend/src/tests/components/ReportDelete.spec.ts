/**
 * V14.4 — "Delete report" on the report detail view: confirming calls
 * `deleteReport` and navigates to the Execution page; cancelling does nothing.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import ReportDetailView from '@/views/ReportDetailView.vue'
import { useAuthStore } from '@/stores/auth.store'
import en from '@/i18n/locales/en'

const { push } = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '7' } }),
  useRouter: () => ({ push }),
}))

vi.mock('@/api/reports.api', () => ({
  getReport: vi.fn(() => new Promise(() => {})),
  getReportHtmlBlobUrl: vi.fn(async () => ''),
  getReportZipBlobUrl: vi.fn(),
  getMissingLibraries: vi.fn(async () => ({ environment_id: null, environment_name: null, libraries: [] })),
  exportReportResults: vi.fn(),
  deleteReport: vi.fn(async () => undefined),
}))

vi.mock('@/api/ai.api', () => ({
  getProviders: vi.fn(async () => []),
  listProviders: vi.fn(async () => []),
}))

import { deleteReport } from '@/api/reports.api'

async function mountView(role: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = { role } as never
  const wrapper = mount(ReportDetailView, {
    global: {
      plugins: [createI18n({ legacy: false, locale: 'en', messages: { en } }), pinia],
      stubs: { 'router-link': true, ReportXmlView: true, RunDiagnosticBanner: true, AnalysisPatches: true },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ReportDetailView — delete report', () => {
  it('confirm → calls deleteReport and navigates to /runs', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const wrapper = await mountView('editor')
    await wrapper.find('[data-testid="delete-report"]').trigger('click')
    await flushPromises()

    expect(deleteReport).toHaveBeenCalledWith(7)
    expect(push).toHaveBeenCalledWith('/runs')
  })

  it('cancel → no API call, no navigation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = await mountView('editor')
    await wrapper.find('[data-testid="delete-report"]').trigger('click')
    await flushPromises()

    expect(deleteReport).not.toHaveBeenCalled()
    expect(push).not.toHaveBeenCalled()
  })

  it('hidden for viewers', async () => {
    const wrapper = await mountView('viewer')
    expect(wrapper.find('[data-testid="delete-report"]').exists()).toBe(false)
  })
})
