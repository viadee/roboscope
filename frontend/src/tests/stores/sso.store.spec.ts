import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSsoStore } from '@/stores/sso.store'

vi.mock('@/api/idpProviders.api', () => ({
  listPublicSsoProviders: vi.fn(),
}))

import { listPublicSsoProviders } from '@/api/idpProviders.api'

describe('sso.store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('loadProviders', () => {
    it('populates providers on API success', async () => {
      const providers = [
        { id: 1, name: 'Azure AD', provider_type: 'oidc_azure_ad' },
        { id: 2, name: 'Google', provider_type: 'oidc_google' },
      ]
      vi.mocked(listPublicSsoProviders).mockResolvedValueOnce(providers)

      const store = useSsoStore()
      await store.loadProviders()

      expect(store.providers).toEqual(providers)
      expect(store.loaded).toBe(true)
    })

    it('silently sets loaded=true on error without throwing', async () => {
      vi.mocked(listPublicSsoProviders).mockRejectedValueOnce(new Error('network'))
      // Suppress the expected warn log for a clean test output.
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      const store = useSsoStore()
      await expect(store.loadProviders()).resolves.toBeUndefined()

      expect(store.providers).toEqual([])
      expect(store.loaded).toBe(true)
      warnSpy.mockRestore()
    })
  })

  describe('loadSettings', () => {
    it('loads hideLocalLoginForm=true on public-settings success', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.resolve({ hide_local_login_form: true }),
        }),
      )
      const store = useSsoStore()
      await store.loadSettings()
      expect(store.hideLocalLoginForm).toBe(true)
      vi.unstubAllGlobals()
    })

    it('coerces missing hide_local_login_form to false', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          json: () => Promise.resolve({}),
        }),
      )
      const store = useSsoStore()
      await store.loadSettings()
      expect(store.hideLocalLoginForm).toBe(false)
      vi.unstubAllGlobals()
    })

    it('fails safe to false on HTTP error', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: false,
          status: 500,
          json: () => Promise.resolve({}),
        }),
      )
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const store = useSsoStore()
      await store.loadSettings()
      expect(store.hideLocalLoginForm).toBe(false)
      warnSpy.mockRestore()
      vi.unstubAllGlobals()
    })

    it('fails safe to false on network error', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockRejectedValue(new Error('network unreachable')),
      )
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const store = useSsoStore()
      await store.loadSettings()
      expect(store.hideLocalLoginForm).toBe(false)
      warnSpy.mockRestore()
      vi.unstubAllGlobals()
    })
  })
})
