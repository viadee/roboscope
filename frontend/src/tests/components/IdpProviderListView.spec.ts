import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import IdpProviderListView from '@/views/IdpProviderListView.vue'
import { useIdpProvidersStore } from '@/stores/idpProviders.store'
import en from '@/i18n/locales/en'
import type { IdpProvider } from '@/types/domain.types'

// Router mock
const push = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => ({ path: '/admin/identity-providers', query: {} }),
}))

// Toast mock
const toastMocks = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}
vi.mock('@/composables/useToast', () => ({
  useToast: () => toastMocks,
}))

// API mock — store delegates here
vi.mock('@/api/idpProviders.api', () => ({
  listIdps: vi.fn(),
  getIdp: vi.fn(),
  createIdp: vi.fn(),
  updateIdp: vi.fn(),
  deleteIdp: vi.fn(),
  dryRunIdp: vi.fn(),
}))
import * as idpApi from '@/api/idpProviders.api'

function createTestI18n() {
  return createI18n({
    legacy: false,
    locale: 'en',
    fallbackLocale: 'en',
    messages: { en },
  })
}

function sampleProvider(overrides: Partial<IdpProvider> = {}): IdpProvider {
  return {
    id: 1,
    name: 'Azure Prod',
    provider_type: 'oidc_azure_ad',
    issuer_url: 'https://login.microsoftonline.com/tenant/v2.0',
    client_id: 'client-id-123',
    scopes: 'openid profile email',
    group_claim_name: 'groups',
    is_enabled: true,
    last_dry_run_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
    last_dry_run_status: 'passed',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

function mountView() {
  return mount(IdpProviderListView, {
    global: {
      plugins: [createTestI18n()],
      stubs: {
        BaseModal: {
          template: '<div data-testid="modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
          props: ['modelValue', 'title'],
        },
        BaseSpinner: true,
      },
    },
  })
}

describe('IdpProviderListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    push.mockReset()
  })

  it('renders the empty state when no providers exist', async () => {
    vi.mocked(idpApi.listIdps).mockResolvedValue([])
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="providers-table"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Add your first identity provider')
  })

  it('renders the data-table when providers exist', async () => {
    vi.mocked(idpApi.listIdps).mockResolvedValue([
      sampleProvider({ id: 1, name: 'Azure Prod' }),
      sampleProvider({ id: 2, name: 'Google Corp', provider_type: 'oidc_google', is_enabled: false, last_dry_run_status: null }),
    ])
    const wrapper = mountView()
    await flushPromises()
    const table = wrapper.find('[data-testid="providers-table"]')
    expect(table.exists()).toBe(true)
    expect(wrapper.find('[data-testid="provider-row-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="provider-row-2"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Azure AD')
    expect(wrapper.text()).toContain('Enabled')
    expect(wrapper.text()).toContain('Draft')
  })

  it('computes status "disabled" when is_enabled=false and last_dry_run_status=passed', async () => {
    vi.mocked(idpApi.listIdps).mockResolvedValue([
      sampleProvider({ id: 3, is_enabled: false, last_dry_run_status: 'passed' }),
    ])
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Disabled')
  })

  it('opens delete modal and calls store.remove on confirm', async () => {
    vi.mocked(idpApi.listIdps).mockResolvedValue([sampleProvider({ id: 42, name: 'Target' })])
    vi.mocked(idpApi.deleteIdp).mockResolvedValue(undefined)
    const wrapper = mountView()
    await flushPromises()

    const deleteBtn = wrapper
      .find('[data-testid="provider-row-42"]')
      .findAll('button')
      .find((b) => b.text() === 'Delete')
    expect(deleteBtn).toBeDefined()
    await deleteBtn!.trigger('click')
    expect(wrapper.find('[data-testid="modal"]').exists()).toBe(true)

    const confirmBtn = wrapper
      .find('[data-testid="modal"]')
      .findAll('button')
      .find((b) => b.text() === 'Delete')
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(idpApi.deleteIdp).toHaveBeenCalledWith(42)
    expect(toastMocks.success).toHaveBeenCalled()
  })

  it('calls store.runDryRun and shows success toast on passed', async () => {
    vi.mocked(idpApi.listIdps).mockResolvedValue([sampleProvider({ id: 7 })])
    vi.mocked(idpApi.dryRunIdp).mockResolvedValue({
      overall_status: 'passed',
      checks: [
        { check_name: 'issuer_reachable', status: 'passed', detail: 'ok' },
        { check_name: 'discovery_valid', status: 'passed', detail: 'ok' },
        { check_name: 'jwks_fetched', status: 'passed', detail: 'ok' },
      ],
      elapsed_ms: 42,
    })
    const wrapper = mountView()
    await flushPromises()

    const dryRunBtn = wrapper
      .find('[data-testid="provider-row-7"]')
      .findAll('button')
      .find((b) => b.text().includes('dry-run'))
    await dryRunBtn!.trigger('click')
    await flushPromises()

    expect(idpApi.dryRunIdp).toHaveBeenCalledWith(7)
    expect(toastMocks.success).toHaveBeenCalled()
  })

  it('shows error toast on failed dry-run with failed check detail', async () => {
    vi.mocked(idpApi.listIdps).mockResolvedValue([sampleProvider({ id: 9 })])
    vi.mocked(idpApi.dryRunIdp).mockResolvedValue({
      overall_status: 'failed',
      checks: [
        { check_name: 'issuer_reachable', status: 'failed', detail: 'Cannot reach IdP' },
        { check_name: 'discovery_valid', status: 'failed', detail: 'Skipped' },
        { check_name: 'jwks_fetched', status: 'failed', detail: 'Skipped' },
      ],
      elapsed_ms: 5000,
    })
    const wrapper = mountView()
    await flushPromises()

    const dryRunBtn = wrapper
      .find('[data-testid="provider-row-9"]')
      .findAll('button')
      .find((b) => b.text().includes('dry-run'))
    await dryRunBtn!.trigger('click')
    await flushPromises()

    expect(toastMocks.error).toHaveBeenCalledWith(expect.stringContaining('Cannot reach IdP'))
  })

  it('navigates to new-provider route when CTA clicked in empty state', async () => {
    vi.mocked(idpApi.listIdps).mockResolvedValue([])
    const wrapper = mountView()
    await flushPromises()
    const cta = wrapper.findAll('button').find((b) => b.text().includes('New Provider'))
    expect(cta).toBeDefined()
    await cta!.trigger('click')
    expect(push).toHaveBeenCalledWith('/admin/identity-providers/new')
  })
})

describe('idpProviders store (derived behavior)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetch populates providers and clears error on success', async () => {
    vi.mocked(idpApi.listIdps).mockResolvedValue([sampleProvider()])
    const store = useIdpProvidersStore()
    await store.fetch()
    expect(store.providers.length).toBe(1)
    expect(store.error).toBeNull()
  })

  it('remove strips the provider from local state', async () => {
    vi.mocked(idpApi.listIdps).mockResolvedValue([
      sampleProvider({ id: 1 }),
      sampleProvider({ id: 2 }),
    ])
    vi.mocked(idpApi.deleteIdp).mockResolvedValue(undefined)
    const store = useIdpProvidersStore()
    await store.fetch()
    await store.remove(1)
    expect(store.providers.map((p) => p.id)).toEqual([2])
  })

  it('isDryRunInFlight toggles during runDryRun', async () => {
    vi.mocked(idpApi.listIdps).mockResolvedValue([sampleProvider({ id: 5 })])
    let resolveDryRun!: (v: unknown) => void
    vi.mocked(idpApi.dryRunIdp).mockImplementation(
      () => new Promise((r) => { resolveDryRun = r as (v: unknown) => void }) as Promise<never>,
    )
    const store = useIdpProvidersStore()
    await store.fetch()
    const p = store.runDryRun(5)
    expect(store.isDryRunInFlight(5)).toBe(true)
    resolveDryRun({ overall_status: 'passed', checks: [], elapsed_ms: 10 })
    await p
    expect(store.isDryRunInFlight(5)).toBe(false)
  })
})
