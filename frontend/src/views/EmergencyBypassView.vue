<script setup lang="ts">
/**
 * Story 5-2 — Admin view for the SSO emergency-bypass toggle.
 *
 * Shows current status + activate/deactivate controls. ADMIN-only
 * route (enforced by router meta + backend 403 as defense-in-depth).
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  activateBypass,
  deactivateBypass,
  getBypassStatus,
  type BypassStatus,
} from '@/api/emergencyBypass.api'

const { t } = useI18n()

const status = ref<BypassStatus | null>(null)
const loading = ref(false)
const errorMsg = ref<string | null>(null)
const duration = ref(1)

const remainingLabel = computed(() => {
  if (!status.value?.active || !status.value.expires_at) return null
  const expiresAt = new Date(status.value.expires_at).getTime()
  const diffMs = expiresAt - Date.now()
  if (diffMs <= 0) return t('bypass.expiringSoon')
  const minutes = Math.round(diffMs / 60000)
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return `${hours} h ${mins} min`
})

async function load() {
  loading.value = true
  errorMsg.value = null
  try {
    status.value = await getBypassStatus()
  } catch (e) {
    errorMsg.value = (e as Error).message ?? 'Error'
  } finally {
    loading.value = false
  }
}

async function onActivate() {
  loading.value = true
  errorMsg.value = null
  try {
    status.value = await activateBypass(duration.value)
  } catch (e) {
    errorMsg.value = (e as Error).message ?? 'Error'
  } finally {
    loading.value = false
  }
}

async function onDeactivate() {
  loading.value = true
  errorMsg.value = null
  try {
    status.value = await deactivateBypass()
  } catch (e) {
    errorMsg.value = (e as Error).message ?? 'Error'
  } finally {
    loading.value = false
  }
}

let tick: number | undefined
onMounted(() => {
  load()
  tick = window.setInterval(load, 30000)
})
onUnmounted(() => {
  if (tick) window.clearInterval(tick)
})
</script>

<template>
  <section class="bypass-admin">
    <h1>{{ t('bypass.heading') }}</h1>
    <p class="bypass-admin__hint">{{ t('bypass.hint') }}</p>

    <div v-if="errorMsg" class="bypass-admin__error" role="alert">{{ errorMsg }}</div>

    <div v-if="status" class="bypass-admin__status">
      <template v-if="status.active">
        <strong class="bypass-admin__active">{{ t('bypass.activeLabel') }}</strong>
        <span v-if="remainingLabel"> — {{ t('bypass.remaining', { time: remainingLabel }) }}</span>
      </template>
      <template v-else>
        <strong>{{ t('bypass.inactiveLabel') }}</strong>
      </template>
    </div>

    <div v-if="status && !status.active" class="bypass-admin__activate">
      <label for="bypass-duration">{{ t('bypass.durationLabel') }}</label>
      <select id="bypass-duration" v-model.number="duration">
        <option :value="1">1 h</option>
        <option :value="2">2 h</option>
        <option :value="4">4 h</option>
        <option :value="8">8 h</option>
        <option :value="12">12 h</option>
        <option :value="24">24 h</option>
      </select>
      <button
        type="button"
        class="bypass-admin__cta bypass-admin__cta--primary"
        :disabled="loading"
        @click="onActivate"
      >
        {{ t('bypass.activate') }}
      </button>
    </div>

    <div v-if="status && status.active" class="bypass-admin__deactivate">
      <button
        type="button"
        class="bypass-admin__cta bypass-admin__cta--danger"
        :disabled="loading"
        @click="onDeactivate"
      >
        {{ t('bypass.deactivate') }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.bypass-admin {
  max-width: 560px;
  padding: 1rem;
}

.bypass-admin__hint {
  color: var(--color-text-secondary, #555);
}

.bypass-admin__status {
  margin: 1rem 0;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 4px;
}

.bypass-admin__active {
  color: #b45309;
}

.bypass-admin__activate,
.bypass-admin__deactivate {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1rem;
}

.bypass-admin__cta {
  padding: 0.5rem 1rem;
  border: 1px solid var(--color-primary, #3B7DD8);
  border-radius: 4px;
  font: inherit;
  cursor: pointer;
}

.bypass-admin__cta--primary {
  background: var(--color-primary, #3B7DD8);
  color: white;
}

.bypass-admin__cta--danger {
  background: #b91c1c;
  border-color: #b91c1c;
  color: white;
}

.bypass-admin__error {
  padding: 0.5rem 0.75rem;
  background: #fee2e2;
  border: 1px solid #f87171;
  border-radius: 4px;
  color: #7f1d1d;
}
</style>
