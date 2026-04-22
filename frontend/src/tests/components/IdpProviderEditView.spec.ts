import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import IdpProviderEditView from '@/views/IdpProviderEditView.vue'
import en from '@/i18n/locales/en'
import type { IdpProvider } from '@/types/domain.types'

const push = vi.fn()
const replace = vi.fn()
let mockRouteId: string | undefined

vi.mock('vue-router', () => ({
  useRouter: () => ({ push, replace }),
  useRoute: () => ({
    params: { id: mockRouteId },
    query: {},
  }),
}))

const toastMocks = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}
vi.mock('@/composables/useToast', () => ({
  useToast: () => toastMocks,
}))

vi.mock('@/api/idpProviders.api', () => ({
  listIdps: vi.fn().mockResolvedValue([]),
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

function sample(overrides: Partial<IdpProvider> = {}): IdpProvider {
  return {
    id: 7,
    name: 'Azure Prod',
    provider_type: 'oidc_azure_ad',
    issuer_url: 'https://login.microsoftonline.com/tenant/v2.0',
    client_id: 'client-7',
    scopes: 'openid profile email',
    group_claim_name: 'groups',
    is_enabled: false,
    last_dry_run_at: null,
    last_dry_run_status: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

function mountView() {
  return mount(IdpProviderEditView, {
    global: {
      plugins: [createTestI18n()],
      stubs: {
        BaseSpinner: true,
        BaseButton: {
          template:
            '<button :disabled="disabled" :data-variant="variant" @click="$emit(\'click\', $event)"><slot /></button>',
          props: ['variant', 'disabled', 'loading'],
        },
        DryRunPanel: {
          template: '<div data-testid="dry-run-panel-stub" :data-stale="stale" :data-loading="loading"></div>',
          props: ['result', 'loading', 'stale'],
        },
      },
    },
  })
}

describe('IdpProviderEditView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    push.mockReset()
    replace.mockReset()
    mockRouteId = undefined
  })

  it('CREATE mode: Save disabled until dry-run passes', async () => {
    mockRouteId = undefined
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('New Identity Provider')
    const saveBtn = wrapper.find('[data-testid="save-btn"]')
    expect(saveBtn.attributes('disabled')).toBeDefined()
  })

  it('CREATE mode: successful dry-run enables Save', async () => {
    mockRouteId = undefined
    vi.mocked(idpApi.createIdp).mockResolvedValue(sample({ id: 101 }))
    vi.mocked(idpApi.dryRunIdp).mockResolvedValue({
      overall_status: 'passed',
      elapsed_ms: 120,
      checks: [
        { check_name: 'issuer_reachable', status: 'passed', detail: '' },
        { check_name: 'discovery_valid', status: 'passed', detail: '' },
        { check_name: 'jwks_fetched', status: 'passed', detail: '' },
      ],
    })

    const wrapper = mountView()
    await flushPromises()

    // Fill the form with valid values
    await wrapper.find('#idp-name').setValue('My IdP')
    await wrapper.find('#idp-issuer-url').setValue('https://idp.example.com')
    await wrapper.find('#idp-client-id').setValue('client-1')
    await wrapper.find('[data-testid="client-secret-input"]').setValue('secret-1')

    // Trigger dry-run
    await wrapper.find('[data-testid="run-dry-run-btn"]').trigger('click')
    await flushPromises()

    expect(idpApi.createIdp).toHaveBeenCalled()
    expect(idpApi.dryRunIdp).toHaveBeenCalledWith(101)
    expect(replace).toHaveBeenCalledWith('/admin/identity-providers/101')

    const saveBtn = wrapper.find('[data-testid="save-btn"]')
    expect(saveBtn.attributes('disabled')).toBeUndefined()
  })

  it('flips DryRunPanel to stale when any field changes after a successful dry-run', async () => {
    mockRouteId = undefined
    vi.mocked(idpApi.createIdp).mockResolvedValue(sample({ id: 202 }))
    vi.mocked(idpApi.dryRunIdp).mockResolvedValue({
      overall_status: 'passed',
      elapsed_ms: 80,
      checks: [
        { check_name: 'issuer_reachable', status: 'passed', detail: '' },
        { check_name: 'discovery_valid', status: 'passed', detail: '' },
        { check_name: 'jwks_fetched', status: 'passed', detail: '' },
      ],
    })

    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('#idp-name').setValue('Another IdP')
    await wrapper.find('#idp-issuer-url').setValue('https://idp.example.com')
    await wrapper.find('#idp-client-id').setValue('cid')
    await wrapper.find('[data-testid="client-secret-input"]').setValue('secret')
    await wrapper.find('[data-testid="run-dry-run-btn"]').trigger('click')
    await flushPromises()

    let panel = wrapper.find('[data-testid="dry-run-panel-stub"]')
    expect(panel.attributes('data-stale')).toBe('false')

    // Mutate a field -> panel should report stale and Save re-disabled
    await wrapper.find('#idp-name').setValue('Another IdP (renamed)')
    await flushPromises()

    panel = wrapper.find('[data-testid="dry-run-panel-stub"]')
    expect(panel.attributes('data-stale')).toBe('true')
    expect(wrapper.find('[data-testid="save-btn"]').attributes('disabled')).toBeDefined()
  })

  it('EDIT mode: pre-fills form from existing provider and leaves Save disabled initially', async () => {
    mockRouteId = '7'
    vi.mocked(idpApi.getIdp).mockResolvedValue(sample({ id: 7, name: 'Existing' }))

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Edit Identity Provider')
    expect((wrapper.find('#idp-name').element as HTMLInputElement).value).toBe('Existing')
    // Secret field stays empty (unchanged-by-default)
    expect(
      (wrapper.find('[data-testid="client-secret-input"]').element as HTMLInputElement).value,
    ).toBe('')
    expect(wrapper.find('[data-testid="save-btn"]').attributes('disabled')).toBeDefined()
  })
})
