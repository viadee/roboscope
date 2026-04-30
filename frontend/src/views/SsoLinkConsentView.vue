<script setup lang="ts">
/**
 * Story 4-7: consent dialog for linking an SSO identity to an existing
 * local account.
 *
 * The backend's OIDC callback detected an existing local-account user
 * with the same email. It redirected here with a short-lived signed
 * consent token. We show the user's email (decoded client-side for
 * display only — the backend re-validates the signature and checks
 * email match before linking) and offer Yes / No.
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import apiClient from '@/api/client'
import { useAuthStore } from '@/stores/auth.store'
import { useUiStore } from '@/stores/ui.store'
import { extractErrorDetail } from '@/utils/errors'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()

const token = computed(() => (route.query.token as string) ?? '')
const loading = ref(false)

const displayEmail = computed(() => {
  // JWT payload is base64url-encoded JSON between the first two dots. Safe
  // to parse for display only — the server still enforces signature + exp.
  try {
    const parts = token.value.split('.')
    if (parts.length !== 3) return ''
    const padded = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const json = atob(padded + '==='.slice(0, (4 - (padded.length % 4)) % 4))
    return (JSON.parse(json).email as string) ?? ''
  } catch {
    return ''
  }
})

async function submit(approve: boolean) {
  if (!token.value) return
  loading.value = true
  try {
    const resp = await apiClient.post<{
      status: 'linked' | 'cancelled'
      return_to: string
      access_token: string | null
      refresh_token: string | null
    }>('/auth/sso/link-consent', {
      consent_token: token.value,
      approve,
    })
    const body = resp.data
    if (body.status === 'linked' && body.access_token && body.refresh_token) {
      localStorage.setItem('access_token', body.access_token)
      localStorage.setItem('refresh_token', body.refresh_token)
      await auth.fetchCurrentUser()
      router.push(body.return_to || '/dashboard')
    } else {
      // The UI store exposes typed toast helpers (info/error/etc.),
      // not a generic `toast(...)`. The previous `ui.toast?.(...)`
      // optional-chained a method that doesn't exist → toast was
      // silently swallowed.
      ui.info(t('welcome.toast.signInCancelled'), '')
      router.push('/login')
    }
  } catch (e: unknown) {
    ui.error(t('common.error'), extractErrorDetail(e, t('common.error')))
    router.push('/login')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="sso-consent">
    <h1>{{ t('welcome.accountLink.heading', { email: displayEmail }) }}</h1>
    <p class="sso-consent__question">{{ t('welcome.accountLink.question') }}</p>
    <div class="sso-consent__actions">
      <button
        type="button"
        class="sso-consent__cta sso-consent__cta--primary"
        :disabled="loading || !token"
        @click="submit(true)"
      >
        {{ t('welcome.accountLink.confirm') }}
      </button>
      <button
        type="button"
        class="sso-consent__cta sso-consent__cta--secondary"
        :disabled="loading"
        @click="submit(false)"
      >
        {{ t('welcome.accountLink.cancel') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.sso-consent {
  max-width: 480px;
  margin: 4rem auto;
  padding: 2rem;
  text-align: center;
}

.sso-consent__question {
  color: var(--color-text-secondary, #555);
  margin: 1rem 0 2rem;
}

.sso-consent__actions {
  display: flex;
  gap: 0.75rem;
  justify-content: center;
}

.sso-consent__cta {
  padding: 0.6rem 1.5rem;
  border: 1px solid var(--color-primary, #3B7DD8);
  border-radius: 4px;
  font: inherit;
  cursor: pointer;
}

.sso-consent__cta--primary {
  background: var(--color-primary, #3B7DD8);
  color: white;
}

.sso-consent__cta--secondary {
  background: transparent;
  color: var(--color-primary, #3B7DD8);
}

.sso-consent__cta:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
