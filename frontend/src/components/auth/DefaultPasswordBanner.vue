<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth.store'
import ChangePasswordModal from '@/components/auth/ChangePasswordModal.vue'

// Story SECURITY-1 (revised) — non-blocking yellow hint shown to users
// whose `password_change_required` flag is set. Local / single-user
// installs can dismiss it for the session; production deployments
// click "Change password" and rotate via the modal.

const { t } = useI18n()
const auth = useAuthStore()

const SESSION_KEY = 'roboscope.defaultPwBanner.dismissed'

const dismissed = ref<boolean>(readDismissed())
const modalOpen = ref(false)

function readDismissed(): boolean {
  try {
    return sessionStorage.getItem(SESSION_KEY) === '1'
  } catch {
    return false
  }
}

const visible = computed(
  () => !!auth.user?.password_change_required && !dismissed.value,
)

function dismiss() {
  dismissed.value = true
  try {
    sessionStorage.setItem(SESSION_KEY, '1')
  } catch {
    // ignore
  }
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
      class="dismiss-btn"
      :aria-label="t('common.dismiss')"
      @click="dismiss"
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
