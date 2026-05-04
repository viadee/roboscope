<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth.store'
import ChangePasswordModal from '@/components/auth/ChangePasswordModal.vue'

// Story SECURITY-1 (revised) — non-blocking yellow hint shown to users
// whose `password_change_required` flag is set. Local / single-user
// installs can dismiss it for the session (× button); a separate
// "Don't show again" button persists the dismissal across sessions
// per-user via localStorage. Production deployments rotate via the
// modal and the banner self-clears once the backend flag flips off.

const { t } = useI18n()
const auth = useAuthStore()

const SESSION_KEY = 'roboscope.defaultPwBanner.dismissed'
const PERSIST_KEY_PREFIX = 'roboscope.defaultPwBanner.dismissedFor.'

const sessionDismissed = ref<boolean>(readSessionDismissed())
const persistedDismissed = computed(() => readPersistedDismissed(auth.user?.id))
const modalOpen = ref(false)

function readSessionDismissed(): boolean {
  try {
    return sessionStorage.getItem(SESSION_KEY) === '1'
  } catch {
    return false
  }
}

/**
 * Per-user persistent dismissal key. Scoping by user id avoids
 * one user's dismissal silently hiding the warning for a different
 * user logging in from the same browser.
 */
function readPersistedDismissed(userId: number | undefined): boolean {
  if (userId == null) return false
  try {
    return localStorage.getItem(PERSIST_KEY_PREFIX + userId) === '1'
  } catch {
    return false
  }
}

const visible = computed(
  () =>
    !!auth.user?.password_change_required
    && !sessionDismissed.value
    && !persistedDismissed.value,
)

function dismissForSession() {
  sessionDismissed.value = true
  try {
    sessionStorage.setItem(SESSION_KEY, '1')
  } catch {
    // ignore
  }
}

function dismissForever() {
  // Marks the banner as dismissed across sessions for THIS user
  // on THIS browser. localStorage is scoped per-origin so admins
  // who later run `pip install` on a fresh browser will see it
  // again — that's intentional, the warning is benign there.
  if (auth.user?.id != null) {
    try {
      localStorage.setItem(PERSIST_KEY_PREFIX + auth.user.id, '1')
    } catch {
      // ignore (e.g. private mode with localStorage disabled)
    }
  }
  // Also flip the session flag so the banner hides immediately
  // even if the localStorage write was blocked.
  sessionDismissed.value = true
}
</script>

<template>
  <div v-if="visible" class="default-pw-banner" role="status">
    <span class="icon" aria-hidden="true">⚠</span>
    <span class="msg">{{ t('auth.defaultPwBanner.message') }}</span>
    <button
      type="button"
      class="action-btn"
      @click="modalOpen = true"
    >
      {{ t('auth.defaultPwBanner.action') }}
    </button>
    <button
      type="button"
      class="dont-show-btn"
      :title="t('auth.defaultPwBanner.dontShowAgainTitle')"
      data-testid="default-pw-banner-dont-show"
      @click="dismissForever"
    >
      {{ t('auth.defaultPwBanner.dontShowAgain') }}
    </button>
    <button
      type="button"
      class="dismiss-btn"
      :aria-label="t('common.dismiss')"
      @click="dismissForSession"
    >
      ×
    </button>
  </div>
  <ChangePasswordModal v-model="modalOpen" />
</template>

<style scoped>
.default-pw-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: #fff7e0;
  border-bottom: 1px solid #f0c14b;
  color: #5b4c1f;
  font-size: 13px;
  flex-wrap: wrap;
}
.icon {
  font-size: 16px;
}
.msg {
  flex: 1;
  min-width: 240px;
}
.action-btn {
  background: #f0c14b;
  border: none;
  border-radius: 4px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
  color: #3a2f12;
  font-weight: 500;
}
.action-btn:hover {
  background: #e6b03a;
}
/* Persistent "don't show again" — visually subdued vs. the
   primary action so users default to fixing the issue, not
   suppressing the warning. */
.dont-show-btn {
  background: transparent;
  border: 1px solid #c0a040;
  border-radius: 4px;
  padding: 3px 8px;
  cursor: pointer;
  font-size: 11px;
  color: #5b4c1f;
}
.dont-show-btn:hover {
  background: rgba(192, 160, 64, 0.15);
}
.dismiss-btn {
  background: transparent;
  border: none;
  font-size: 18px;
  line-height: 1;
  padding: 0 4px;
  cursor: pointer;
  color: #5b4c1f;
  opacity: 0.6;
}
.dismiss-btn:hover {
  opacity: 1;
}
</style>
