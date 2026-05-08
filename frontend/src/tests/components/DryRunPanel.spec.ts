import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import DryRunPanel from '@/components/idp/DryRunPanel.vue'
import en from '@/i18n/locales/en'
import type { DryRunProbeResponse } from '@/types/domain.types'

function createTestI18n() {
  return createI18n({
    legacy: false,
    locale: 'en',
    fallbackLocale: 'en',
    messages: { en },
  })
}

function mountPanel(props: {
  result: DryRunProbeResponse | null
  loading: boolean
  stale: boolean
}) {
  return mount(DryRunPanel, {
    props,
    global: {
      plugins: [createTestI18n()],
      stubs: {
        BaseBadge: {
          template: '<span class="badge" :data-variant="variant"><slot /></span>',
          props: ['variant'],
        },
      },
    },
  })
}

const PASSED_RESULT: DryRunProbeResponse = {
  overall_status: 'passed',
  elapsed_ms: 234,
  checks: [
    { check_name: 'issuer_reachable', status: 'passed', detail: 'OK' },
    { check_name: 'discovery_valid', status: 'passed', detail: 'All keys present' },
    { check_name: 'jwks_fetched', status: 'passed', detail: '3 keys' },
  ],
}

const FAILED_RESULT: DryRunProbeResponse = {
  overall_status: 'failed',
  elapsed_ms: 5123,
  checks: [
    { check_name: 'issuer_reachable', status: 'failed', detail: 'Cannot reach issuer.' },
    { check_name: 'discovery_valid', status: 'failed', detail: 'Skipped' },
    { check_name: 'jwks_fetched', status: 'failed', detail: 'Skipped' },
  ],
}

describe('DryRunPanel', () => {
  it('renders loading state with Running verdict', () => {
    const w = mountPanel({ result: null, loading: true, stale: false })
    expect(w.text()).toContain('Dry-Run Report')
    expect(w.text()).toContain('Running')
    const rows = w.findAll('[data-testid^="check-row-"]')
    expect(rows.length).toBe(3)
  })

  it('renders a passed result with 3 green rows and elapsed footer', () => {
    const w = mountPanel({ result: PASSED_RESULT, loading: false, stale: false })
    expect(w.text()).toContain('Passed')
    expect(w.findAll('[data-testid^="check-row-"]').length).toBe(3)
    expect(w.text()).toContain('234')
    expect(w.text()).toContain('OK')
    expect(w.text()).toContain('3 keys')
  })

  it('renders a failed result with at least one failed row', () => {
    const w = mountPanel({ result: FAILED_RESULT, loading: false, stale: false })
    expect(w.text()).toContain('Failed')
    expect(w.text()).toContain('Cannot reach issuer.')
  })

  it('renders stale banner when stale=true', () => {
    const w = mountPanel({ result: PASSED_RESULT, loading: false, stale: true })
    expect(w.find('[data-testid="dry-run-stale-banner"]').exists()).toBe(true)
    expect(w.text()).toContain('Stale')
    expect(w.text()).toContain('re-run required')
  })

  it('renders an idle/empty state when no result and not loading', () => {
    const w = mountPanel({ result: null, loading: false, stale: false })
    // Header + title still visible, but no check rows and no stale banner
    expect(w.text()).toContain('Dry-Run Report')
    expect(w.text()).toContain('Not run')
    expect(w.findAll('[data-testid^="check-row-"]').length).toBe(0)
    expect(w.find('[data-testid="dry-run-stale-banner"]').exists()).toBe(false)
  })

  it('exposes aria-live polite region while loading or after a result', () => {
    const w = mountPanel({ result: null, loading: true, stale: false })
    const live = w.find('[aria-live="polite"]')
    expect(live.exists()).toBe(true)
    expect(live.text()).toContain('Dry-run started')
  })
})
