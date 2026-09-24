import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import en from '@/i18n/locales/en'
import type { Schedule } from '@/types/domain.types'

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))

const SCHEDULE: Schedule = {
  id: 7,
  name: 'Nightly',
  cron_expression: '0 2 * * *',
  repository_id: 1,
  environment_id: null,
  target_path: 'tests',
  branch: 'main',
  runner_type: 'subprocess',
  tags_include: null,
  tags_exclude: null,
  is_active: true,
  last_run_at: '2026-09-24T02:00:00',
  next_run_at: '2026-09-25T02:00:00',
  created_by: 1,
  created_at: '2026-09-01T00:00:00',
}

vi.mock('@/api/execution.api', () => ({
  getRuns: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }),
  getSchedules: vi.fn(),
  runScheduleNow: vi.fn(),
  getRunOutput: vi.fn(),
  listModifiers: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/api/repos.api', () => ({ getRepos: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/environments.api', () => ({
  getEnvironments: vi.fn().mockResolvedValue([]),
  buildDockerImage: vi.fn(),
}))
vi.mock('@/api/reports.api', () => ({}))
vi.mock('@/api/explorer.api', () => ({ getRepoTags: vi.fn().mockResolvedValue([]) }))
vi.mock('@/composables/useFeatureFlags', () => ({
  useFeatureFlags: () => ({ isEnabled: () => false }),
}))
vi.mock('@/utils/formatDate', async (orig) => {
  const mod = await orig<typeof import('@/utils/formatDate')>()
  return { ...mod, parseBackendDate: vi.fn(mod.parseBackendDate) }
})

import * as executionApi from '@/api/execution.api'
import { parseBackendDate } from '@/utils/formatDate'
import ExecutionView from '@/views/ExecutionView.vue'
import { useAuthStore } from '@/stores/auth.store'

async function mountView() {
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en } })
  const wrapper = shallowMount(ExecutionView, { global: { plugins: [i18n] } })
  await flushPromises()
  return wrapper
}

describe('Schedules tab: Run now + Last/Next run', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(executionApi.getSchedules).mockResolvedValue([SCHEDULE])
    const auth = useAuthStore()
    auth.user = { id: 1, role: 'runner' } as never
  })

  it('renders Last/Next run through parseBackendDate', async () => {
    const wrapper = await mountView()
    expect(parseBackendDate).toHaveBeenCalledWith('2026-09-24T02:00:00')
    expect(parseBackendDate).toHaveBeenCalledWith('2026-09-25T02:00:00')
    const expected = new Date('2026-09-25T02:00:00Z')
      .toLocaleString('en', { dateStyle: 'short', timeStyle: 'short' })
    expect(wrapper.find('.schedule-next-run').text()).toBe(expected)
  })

  it('Run now calls runScheduleNow with the schedule id', async () => {
    vi.mocked(executionApi.runScheduleNow).mockResolvedValue({ id: 99 } as never)
    const wrapper = await mountView()
    await wrapper.find('.schedule-run-now').trigger('click')
    await flushPromises()
    expect(executionApi.runScheduleNow).toHaveBeenCalledWith(7)
  })

  it('hides Run now for viewers', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, role: 'viewer' } as never
    const wrapper = await mountView()
    expect(wrapper.find('.schedule-run-now').exists()).toBe(false)
  })
})
