<!--
  SsoErrorView (Story 2-7).

  The backend SSO callback (`backend/src/auth/sso_router.py`) redirects
  failed attempts to `/sso-error?code=<reason>`. We render a user-facing,
  localized message with a [Try again] button that drops the user back at
  `/login` (forwarding `return_to` if present).

  Known codes are mapped to specific copy under `auth.ssoError.<code>`.
  Unknown codes fall back to `auth.ssoError.generic` — never render the raw
  code to the user.
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useSsoStore } from '@/stores/sso.store'
import BaseButton from '@/components/ui/BaseButton.vue'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const sso = useSsoStore()

const loaded = ref(false)

// Map dotted backend error codes (programmer-facing vocabulary) to
// camelCased i18n keys (required because vue-i18n treats `.` as a path
// separator when looking up messages). Unknown codes map to 'generic'.
const CODE_TO_I18N_KEY: Record<string, string> = {
  'idp.unreachable': 'idpUnreachable',
  'state.expired': 'stateExpired',
  'state.not_found': 'stateNotFound',
  'return_to.invalid': 'returnToInvalid',
  'token_exchange.failed': 'tokenExchangeFailed',
  'claims.email_unverified': 'claimsEmailUnverified',
  'claims.azp_missing': 'claimsAzpMissing',
  'user.disabled': 'userDisabled',
  'idp.not_found': 'idpNotFound',
  'sync.failed': 'syncFailed',
}

const code = computed<string>(() => {
  const raw = route.query.code as string | undefined
  return raw && raw in CODE_TO_I18N_KEY ? raw : 'idp.unreachable'
})

const message = computed(() => {
  const key = CODE_TO_I18N_KEY[code.value] ?? 'generic'
  return t(`auth.ssoError.${key}`)
})

const adminContact = computed(() => sso.adminContactEmail ?? '')

const returnTo = computed<string | undefined>(() => {
  const raw = route.query.return_to as string | undefined
  return raw && raw !== '/login' ? raw : undefined
})

function handleTryAgain() {
  if (returnTo.value) {
    router.push({ path: '/login', query: { return_to: returnTo.value } })
  } else {
    router.push('/login')
  }
}

onMounted(async () => {
  await sso.loadSettings()
  loaded.value = true
})
</script>

<template>
  <div class="sso-error-card">
    <div
      class="sso-error-alert"
      role="alert"
      aria-live="assertive"
    >
      <div class="sso-error-icon">
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h2 class="sso-error-heading">{{ t('auth.ssoError.heading') }}</h2>
      <p class="sso-error-message">{{ message }}</p>
      <p v-if="adminContact" class="sso-error-admin">
        {{ t('auth.ssoError.contactAdmin', { email: adminContact }) }}
      </p>
      <div class="sso-error-actions">
        <BaseButton
          variant="primary"
          size="lg"
          class="sso-error-retry"
          @click="handleTryAgain"
        >
          {{ t('auth.ssoError.tryAgain') }}
        </BaseButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sso-error-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 36px 32px;
  box-shadow:
    0 20px 50px -10px rgba(16, 25, 51, 0.25),
    0 0 0 1px rgba(255, 255, 255, 0.05);
}

.sso-error-alert {
  text-align: center;
}

.sso-error-icon {
  width: 48px;
  height: 48px;
  background: var(--color-danger-bg);
  color: var(--color-danger);
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
}

.sso-error-heading {
  margin: 0 0 10px;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-navy);
}

.sso-error-message {
  margin: 0 0 14px;
  color: var(--color-text);
  line-height: 1.55;
}

.sso-error-admin {
  margin: 0 0 18px;
  font-size: 13px;
  color: var(--color-text-muted);
}

.sso-error-actions {
  display: flex;
  justify-content: center;
}

.sso-error-retry {
  min-width: 180px;
}
</style>
