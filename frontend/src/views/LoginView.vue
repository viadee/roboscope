<script setup lang="ts">
import { ref } from 'vue'
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

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (e: any) {
    error.value = e.response?.data?.detail || t('auth.loginFailed')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-card">
    <h2>{{ t('auth.login') }}</h2>
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
      <p v-if="error" class="error-text">{{ error }}</p>
      <BaseButton type="submit" :loading="loading" class="w-full" size="lg">
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
  box-shadow: 0 20px 50px -10px rgba(16, 25, 51, 0.25);
}

.login-card h2 {
  text-align: center;
  margin-bottom: 24px;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-navy);
}

.login-card .form-input {
  background: var(--color-bg);
  border-color: var(--color-border);
}

.login-card .form-input:focus {
  background: #ffffff;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(60, 181, 161, 0.15);
}

.error-text {
  color: var(--color-danger);
  font-size: 13px;
  margin-bottom: 12px;
  text-align: center;
  background: var(--color-danger-bg);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
}

.hint {
  text-align: center;
  font-size: 12px;
  color: var(--color-text-light);
  margin-top: 16px;
}
</style>
