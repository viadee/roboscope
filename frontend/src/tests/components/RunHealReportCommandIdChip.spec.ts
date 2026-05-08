/**
 * RECORDER-IDMAP — verify the runtime heal-report panel renders the
 * `rbs:<id>` chip ONLY when the audit entry carries a non-null
 * `command_id`. Legacy entries (parser surfaces `null`) and entries
 * with an explicitly null/empty value must hide the chip.
 *
 * Pinned because the parser already normalises three input shapes
 * to `null` (missing key, JSON null, empty string), but the FE's
 * `v-if="entry.command_id"` truthy check is what users actually see;
 * an accidental change to `v-if="entry.command_id !== undefined"`
 * would silently regress legacy runs to a useless `rbs:null` chip.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import RunHealReport from '@/components/execution/RunHealReport.vue'
import en from '@/i18n/locales/en'
import de from '@/i18n/locales/de'

vi.mock('@/api/execution.api', () => ({
  getRunHealReport: vi.fn(),
  applyHealPatch: vi.fn(),
}))

import { getRunHealReport } from '@/api/execution.api'

function makeEntry(overrides: Record<string, unknown> = {}) {
  return {
    timestamp: '2026-04-30T01:00:00Z',
    test_name: 'T1',
    keyword: 'Click',
    original_selector: 'id=submit',
    healed_selector: '[data-testid=submit]',
    confidence: 0.9,
    source: 'sidecar',
    outcome: 'confirmed',
    command_id: null,
    ...overrides,
  }
}

function createTestI18n(locale: 'de' | 'en' = 'en') {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en',
    messages: { de, en },
  })
}

async function mountReport(entries: ReturnType<typeof makeEntry>[]) {
  const total = entries.length
  const confirmed = entries.filter(e => e.outcome === 'confirmed').length
  const suspect = entries.filter(e => e.outcome === 'suspect').length
  ;(getRunHealReport as ReturnType<typeof vi.fn>).mockResolvedValue({
    total_heals: total,
    confirmed,
    suspect,
    entries,
  })
  const wrapper = mount(RunHealReport, {
    global: {
      plugins: [createTestI18n('en'), createPinia()],
    },
    props: { runId: 1, status: 'passed' },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  document.body.innerHTML = ''
  setActivePinia(createPinia())
})

describe('RunHealReport — RECORDER-IDMAP rbs chip visibility', () => {
  it('renders rbs:<id> chip when entry has a command_id', async () => {
    const wrapper = await mountReport([
      makeEntry({ command_id: 'abc123def456' }),
    ])
    const chip = wrapper.find('[data-testid="heal-command-id"]')
    expect(chip.exists()).toBe(true)
    expect(chip.text()).toBe('rbs:abc123def456')
  })

  it('hides chip when command_id is null (legacy run)', async () => {
    const wrapper = await mountReport([makeEntry({ command_id: null })])
    expect(wrapper.find('[data-testid="heal-command-id"]').exists()).toBe(false)
  })

  it('hides chip when command_id is undefined (key omitted entirely)', async () => {
    const e = makeEntry()
    delete (e as Record<string, unknown>).command_id
    const wrapper = await mountReport([e])
    expect(wrapper.find('[data-testid="heal-command-id"]').exists()).toBe(false)
  })

  it('hides chip when command_id is the empty string', async () => {
    // Defensive — the backend parser already normalises empty
    // strings to null, but if a buggy client ever wrote one
    // through, the chip would render `rbs:` with no id.
    const wrapper = await mountReport([makeEntry({ command_id: '' })])
    expect(wrapper.find('[data-testid="heal-command-id"]').exists()).toBe(false)
  })

  it('renders chip per-entry: legacy + new + legacy interleaved', async () => {
    const wrapper = await mountReport([
      makeEntry({ test_name: 'T1', command_id: null }),
      makeEntry({ test_name: 'T2', command_id: 'newcmdaaaaaa' }),
      makeEntry({ test_name: 'T3', command_id: null }),
      makeEntry({ test_name: 'T4', command_id: 'newcmdbbbbbb' }),
    ])
    const chips = wrapper.findAll('[data-testid="heal-command-id"]')
    expect(chips).toHaveLength(2)
    expect(chips[0].text()).toBe('rbs:newcmdaaaaaa')
    expect(chips[1].text()).toBe('rbs:newcmdbbbbbb')
  })
})
