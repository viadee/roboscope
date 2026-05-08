import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import SsoErrorView from '@/views/SsoErrorView.vue'
import { useSsoStore } from '@/stores/sso.store'
import de from '@/i18n/locales/de'
import en from '@/i18n/locales/en'

// vue-router mock — override route.query per-test.
let _routeQuery: Record<string, string> = {}
const _routerPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: _routerPush }),
  useRoute: () => ({ query: _routeQuery }),
}))

function createTestI18n(locale: 'de' | 'en' = 'en') {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en',
    messages: { de, en },
  })
}

function mountView(locale: 'de' | 'en' = 'en') {
  return mount(SsoErrorView, {
    global: {
      plugins: [createTestI18n(locale)],
      stubs: {
        BaseButton: {
          template:
            '<button v-bind="$attrs" @click="$emit(\'click\', $event)"><slot /></button>',
          props: ['loading', 'size', 'variant'],
          inheritAttrs: false,
        },
      },
    },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  _routeQuery = {}
  // Default: no public settings endpoint traffic.
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ hide_local_login_form: false, admin_contact_email: '' }),
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SsoErrorView', () => {
  describe('accessibility (AC5)', () => {
    it('renders the alert container with role=alert + aria-live=assertive', async () => {
      const wrapper = mountView()
      await flushPromises()
      const alert = wrapper.find('.sso-error-alert')
      expect(alert.attributes('role')).toBe('alert')
      expect(alert.attributes('aria-live')).toBe('assertive')
    })
  })

  describe('code-specific copy (AC2)', () => {
    it('renders code-specific copy for idp.unreachable', async () => {
      _routeQuery = { code: 'idp.unreachable' }
      const wrapper = mountView()
      await flushPromises()
      expect(wrapper.find('.sso-error-message').text()).toContain(
        "couldn't reach",
      )
    })

    it('renders code-specific copy for state.expired', async () => {
      _routeQuery = { code: 'state.expired' }
      const wrapper = mountView()
      await flushPromises()
      expect(wrapper.find('.sso-error-message').text()).toContain('timed out')
    })

    it('renders code-specific copy for user.disabled', async () => {
      _routeQuery = { code: 'user.disabled' }
      const wrapper = mountView()
      await flushPromises()
      expect(wrapper.find('.sso-error-message').text()).toContain('disabled')
    })

    it('falls back to idp.unreachable copy when code is unknown', async () => {
      _routeQuery = { code: 'completely_made_up_code' }
      const wrapper = mountView()
      await flushPromises()
      // Unknown codes are normalized to idp.unreachable (AC defaults).
      expect(wrapper.find('.sso-error-message').text()).toContain(
        "couldn't reach",
      )
    })

    it('defaults to idp.unreachable when code is missing', async () => {
      const wrapper = mountView()
      await flushPromises()
      expect(wrapper.find('.sso-error-message').text()).toContain(
        "couldn't reach",
      )
    })

    it('never renders the raw error code to the user', async () => {
      _routeQuery = { code: 'claims.azp_missing' }
      const wrapper = mountView()
      await flushPromises()
      // The technical code must not appear in the visible message.
      const visibleText = wrapper.text()
      expect(visibleText).not.toContain('azp')
      expect(visibleText).not.toContain('claims.')
    })
  })

  describe('admin-contact line (AC3)', () => {
    it('hides the admin-contact line when adminContactEmail is empty', async () => {
      const wrapper = mountView()
      await flushPromises()
      expect(wrapper.find('.sso-error-admin').exists()).toBe(false)
    })

    it('renders the admin-contact line when adminContactEmail is set', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          json: () =>
            Promise.resolve({
              hide_local_login_form: false,
              admin_contact_email: 'security@example.com',
            }),
        }),
      )
      const wrapper = mountView()
      await flushPromises()
      const line = wrapper.find('.sso-error-admin')
      expect(line.exists()).toBe(true)
      expect(line.text()).toContain('security@example.com')
    })

    it('falls back gracefully when the settings endpoint errors', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockRejectedValue(new Error('network')),
      )
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const wrapper = mountView()
      await flushPromises()
      // No admin-contact line rendered, no crash.
      expect(wrapper.find('.sso-error-admin').exists()).toBe(false)
      expect(wrapper.find('.sso-error-message').exists()).toBe(true)
      warnSpy.mockRestore()
    })
  })

  describe('Try again button (AC4)', () => {
    it('navigates to /login when no return_to is present', async () => {
      const wrapper = mountView()
      await flushPromises()
      await wrapper.find('.sso-error-retry').trigger('click')
      expect(_routerPush).toHaveBeenCalledWith('/login')
    })

    it('forwards return_to when present in the failure URL', async () => {
      _routeQuery = { code: 'idp.unreachable', return_to: '/reports/42' }
      const wrapper = mountView()
      await flushPromises()
      await wrapper.find('.sso-error-retry').trigger('click')
      expect(_routerPush).toHaveBeenCalledWith({
        path: '/login',
        query: { return_to: '/reports/42' },
      })
    })

    it('drops self-referential return_to=/login (loop guard)', async () => {
      _routeQuery = { code: 'idp.unreachable', return_to: '/login' }
      const wrapper = mountView()
      await flushPromises()
      await wrapper.find('.sso-error-retry').trigger('click')
      expect(_routerPush).toHaveBeenCalledWith('/login')
    })
  })

  describe('i18n (AC2)', () => {
    it('renders German copy when locale is de', async () => {
      _routeQuery = { code: 'idp.unreachable' }
      const wrapper = mountView('de')
      await flushPromises()
      expect(wrapper.find('.sso-error-heading').text()).toBe(
        'Anmeldung nicht möglich',
      )
      expect(wrapper.find('.sso-error-retry').text()).toBe('Erneut versuchen')
    })
  })

  describe('store integration (AC3)', () => {
    it('triggers sso.loadSettings on mount', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          json: () =>
            Promise.resolve({
              hide_local_login_form: false,
              admin_contact_email: 'dev@example.com',
            }),
        }),
      )
      mountView()
      await flushPromises()
      const store = useSsoStore()
      expect(store.adminContactEmail).toBe('dev@example.com')
    })
  })
})
