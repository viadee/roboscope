/**
 * RunDiagnosticBanner — surfaces an actionable banner above the
 * failed tests in the ReportDetail view when the backend's
 * `detect_report_diagnostic` returns a non-null payload. Today
 * the only registered code is `playwright_browser_missing`.
 *
 * Pins (in order of importance):
 *  - title, description, action label resolve from i18n keys
 *    keyed on the diagnostic code (so a new code = new locale
 *    section, NO component change)
 *  - the action button posts to the EXACT endpoint the backend
 *    advertised — the frontend doesn't hardcode `/environments/N/
 *    rfbrowser-init` since the backend can vary the path per
 *    diagnostic (a future "out-of-disk-space" code might POST to
 *    `/system/cleanup` instead)
 *  - on POST success the banner flips to a "started" state with
 *    no further auto-polling (the Environments view owns the
 *    install-progress UI; the banner just triggers)
 *  - on POST error the user-facing message includes the backend
 *    error detail so they can self-diagnose without devtools
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import RunDiagnosticBanner from '@/components/reports/RunDiagnosticBanner.vue'
import en from '@/i18n/locales/en'
import de from '@/i18n/locales/de'
import type { RunDiagnostic } from '@/types/domain.types'

vi.mock('@/api/client', () => ({
  default: { request: vi.fn() },
}))

import apiClient from '@/api/client'

const mockedRequest = (apiClient as unknown as { request: ReturnType<typeof vi.fn> }).request

function i18n(locale: 'en' | 'de' = 'en') {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en',
    messages: { en, de },
  })
}

function mkDiagnostic(overrides: Partial<RunDiagnostic> = {}): RunDiagnostic {
  return {
    code: 'playwright_browser_missing',
    action: {
      type: 'rfbrowser_init',
      env_id: 42,
      endpoint: '/environments/42/rfbrowser-init',
      method: 'POST',
    },
    ...overrides,
  } as RunDiagnostic
}

function mountWith(diagnostic: RunDiagnostic, locale: 'en' | 'de' = 'en') {
  return mount(RunDiagnosticBanner, {
    props: { diagnostic },
    global: { plugins: [i18n(locale)] },
  })
}

beforeEach(() => {
  mockedRequest.mockReset()
})

describe('RunDiagnosticBanner', () => {
  it('renders the localised title + description + action for the diagnostic code', () => {
    const w = mountWith(mkDiagnostic(), 'en')
    expect(w.text()).toContain('Browser binaries missing')
    expect(w.text()).toMatch(/Run rfbrowser init/i)
  })

  it('falls back to German wording when locale is `de`', () => {
    const w = mountWith(mkDiagnostic(), 'de')
    expect(w.text()).toContain('Browser-Binaries fehlen')
    expect(w.text()).toContain('rfbrowser init ausführen')
  })

  it('posts to the exact endpoint the backend advertised on click', async () => {
    mockedRequest.mockResolvedValue({ data: { status: 'pending' } })
    const w = mountWith(mkDiagnostic())
    await w.find('[data-testid="run-diagnostic-trigger"]').trigger('click')
    await flushPromises()
    expect(mockedRequest).toHaveBeenCalledTimes(1)
    expect(mockedRequest).toHaveBeenCalledWith({
      url: '/environments/42/rfbrowser-init',
      method: 'POST',
    })
  })

  it('flips to "started" state on success and shows the started badge', async () => {
    mockedRequest.mockResolvedValue({ data: { status: 'pending' } })
    const w = mountWith(mkDiagnostic())
    await w.find('[data-testid="run-diagnostic-trigger"]').trigger('click')
    await flushPromises()
    // Button is gone; badge is shown.
    expect(w.find('[data-testid="run-diagnostic-trigger"]').exists()).toBe(false)
    expect(w.find('[data-testid="run-diagnostic-started"]').exists()).toBe(true)
  })

  it('shows the backend error detail and keeps the button visible on failure', async () => {
    mockedRequest.mockRejectedValue({
      response: { data: { detail: 'robotframework-browser is not installed' } },
    })
    const w = mountWith(mkDiagnostic())
    await w.find('[data-testid="run-diagnostic-trigger"]').trigger('click')
    await flushPromises()
    // Button stays present so the user can retry after fixing.
    expect(w.find('[data-testid="run-diagnostic-trigger"]').exists()).toBe(true)
    expect(w.text()).toMatch(/Trigger failed/i)
    expect(w.text()).toContain('robotframework-browser is not installed')
  })

  it('does not double-trigger when clicked rapidly while in flight', async () => {
    // `triggering` phase guards against re-entry — without it a
    // quick double-click would race two POSTs against the same
    // env and the second would typically error out with
    // "rfbrowser init is already running" noise.
    let resolveOuter: (v: unknown) => void = () => {}
    const pending = new Promise((res) => { resolveOuter = res })
    mockedRequest.mockReturnValue(pending)
    const w = mountWith(mkDiagnostic())
    const btn = w.find('[data-testid="run-diagnostic-trigger"]')
    await btn.trigger('click')
    await btn.trigger('click')
    await btn.trigger('click')
    expect(mockedRequest).toHaveBeenCalledTimes(1)
    // Settle the request so unmount cleanup is clean.
    resolveOuter({ data: { status: 'pending' } })
    await flushPromises()
  })
})
