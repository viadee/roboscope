<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth.store'
import BaseButton from '@/components/ui/BaseButton.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { t } = useI18n()

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const showError = ref(false)

const DEFAULT_EMAIL = 'admin@roboscope.local'
const DEFAULT_PASSWORD = 'admin123'

onMounted(async () => {
  try {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: DEFAULT_EMAIL, password: DEFAULT_PASSWORD }),
    })
    if (res.ok) {
      email.value = DEFAULT_EMAIL
      password.value = DEFAULT_PASSWORD
    }
  } catch {
    // default credentials not active — leave fields empty
  }
})

async function handleLogin() {
  error.value = ''
  showError.value = false
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (e: any) {
    error.value = e.response?.data?.detail || t('auth.loginFailed')
    showError.value = true
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-card">
    <div class="login-header">
      <div class="login-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
      </div>
      <h2>{{ t('auth.login') }}</h2>
      <p class="login-desc">{{ t('auth.loginDesc') }}</p>
    </div>

    <form @submit.prevent="handleLogin">
      <div class="form-group">
        <label class="form-label">{{ t('auth.email') }}</label>
        <input
          v-model="email"
          type="text"
          class="form-input"
          placeholder="admin@roboscope.local"
          required
          autofocus
        />
      </div>
      <div class="form-group">
        <label class="form-label">{{ t('auth.password') }}</label>
        <input
          v-model="password"
          type="password"
          class="form-input"
          :placeholder="t('auth.password')"
          required
        />
      </div>

      <Transition name="shake">
        <p v-if="showError" class="error-text">{{ error }}</p>
      </Transition>

      <BaseButton type="submit" :loading="loading" class="w-full login-btn" size="lg">
        {{ t('auth.login') }}
      </BaseButton>
    </form>

    <p class="hint">{{ t('auth.hint') }}</p>
  </div>
</template>

<style scoped>
.login-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 36px 32px;
  box-shadow:
    0 20px 50px -10px rgba(16, 25, 51, 0.25),
    0 0 0 1px rgba(255, 255, 255, 0.05);
}

.login-header {
  text-align: center;
  margin-bottom: 24px;
}

.login-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, var(--color-primary) 0%, #2B6BC0 100%);
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: white;
  margin-bottom: 14px;
  box-shadow: 0 4px 12px rgba(59, 125, 216, 0.3);
}

.login-header h2 {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-navy);
}

.login-desc {
  font-size: 13px;
  color: var(--color-text-muted);
  margin: 0;
}

.login-card .form-input {
  background: var(--color-bg);
  border-color: var(--color-border);
  transition: all 0.2s ease;
}

.login-card .form-input:focus {
  background: #ffffff;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(59, 125, 216, 0.12);
  transform: translateY(-1px);
}

.login-btn {
  margin-top: 4px;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.login-btn:active {
  transform: scale(0.98);
}

.error-text {
  color: var(--color-danger);
  font-size: 13px;
  margin-bottom: 12px;
  text-align: center;
  background: var(--color-danger-bg);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  animation: shakeX 0.4s ease-in-out;
}

.hint {
  text-align: center;
  font-size: 12px;
  color: var(--color-text-light);
  margin-top: 16px;
}

/* Shake animation for errors */
@keyframes shakeX {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-6px); }
  40% { transform: translateX(6px); }
  60% { transform: translateX(-4px); }
  80% { transform: translateX(4px); }
}

.shake-enter-active {
  animation: shakeX 0.4s ease-in-out;
}

.shake-leave-active {
  transition: opacity 0.2s ease;
}

.shake-leave-to {
  opacity: 0;
}
</style>
