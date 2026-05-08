import { defineStore } from 'pinia'
import { ref } from 'vue'
import { listPublicSsoProviders } from '@/api/idpProviders.api'
import type { SsoProviderPublic } from '@/types/domain.types'

/**
 * Public SSO state used by `LoginView` on the unauthenticated login page.
 *
 * `loadProviders()` is silent on failure (logs to console, never throws) so
 * a transient backend error doesn't wedge the login form behind a toast.
 * `loadSettings()` fetches the public `/auth/sso/public-settings` payload
 * (Story 2-5); on any failure it fails safe to `hide_local_login_form=false`
 * so an outage of the settings endpoint never locks users out.
 */
export const useSsoStore = defineStore('sso', () => {
  const providers = ref<SsoProviderPublic[]>([])
  const loaded = ref(false)
  const hideLocalLoginForm = ref(false)
  const adminContactEmail = ref('')

  async function loadProviders(): Promise<void> {
    try {
      providers.value = await listPublicSsoProviders()
    } catch (err) {
      // Silent: login must still render. AC3 — zero-IdP fallback path.
      providers.value = []
      // eslint-disable-next-line no-console
      console.warn('[sso.store] listPublicSsoProviders failed, falling back to local login only', err)
    } finally {
      loaded.value = true
    }
  }

  async function loadSettings(): Promise<void> {
    try {
      const res = await fetch('/api/v1/auth/sso/public-settings', {
        signal: AbortSignal.timeout(5000),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = (await res.json()) as {
        hide_local_login_form?: boolean
        admin_contact_email?: string
      }
      hideLocalLoginForm.value = Boolean(data.hide_local_login_form)
      adminContactEmail.value = data.admin_contact_email ?? ''
    } catch (err) {
      hideLocalLoginForm.value = false
      adminContactEmail.value = ''
      // eslint-disable-next-line no-console
      console.warn(
        '[sso.store] public-settings fetch failed, defaulting to hide_local_login_form=false',
        err,
      )
    }
  }

  return {
    providers,
    loaded,
    hideLocalLoginForm,
    adminContactEmail,
    loadProviders,
    loadSettings,
  }
})
