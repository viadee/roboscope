<script setup lang="ts">
/**
 * Story W.7 — Recorder v2 launcher view.
 *
 * Transport picker + Record CTA + repo selector. Once the session is
 * created the user is routed to /recordings/live/{session_id} (future
 * W.2/W.6 view) — the launcher itself only handles the pre-record
 * decisions.
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { createV2Session } from '@/api/recording-v2.api'
import { useReposStore } from '@/stores/repos.store'
import type { RecordingTransport } from '@/types/recorder.types'

const { t } = useI18n()
const router = useRouter()
const reposStore = useReposStore()

const transport = ref<RecordingTransport>('web_playwright')
const repoId = ref<number | null>(null)
const starting = ref(false)
const error = ref<string | null>(null)

const transports: { value: RecordingTransport; labelKey: string; disabled?: boolean }[] = [
  { value: 'web_playwright', labelKey: 'recorder.launcher.transport.web' },
  { value: 'desktop_windows', labelKey: 'recorder.launcher.transport.windows', disabled: true },
  { value: 'desktop_macos', labelKey: 'recorder.launcher.transport.macos', disabled: true },
]

const canStart = computed(() => transport.value && repoId.value !== null && !starting.value)

async function start() {
  if (!canStart.value) return
  starting.value = true
  error.value = null
  try {
    const session = await createV2Session(transport.value, repoId.value as number)
    router.push(`/recordings/live/${session.session_id}`)
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    error.value =
      typeof detail === 'string'
        ? detail
        : detail?.message ?? t('recorder.launcher.startFailed')
  } finally {
    starting.value = false
  }
}

onMounted(async () => {
  await reposStore.fetchRepos()
  if (reposStore.repos.length > 0 && repoId.value === null) {
    repoId.value = reposStore.repos[0].id
  }
})
</script>

<template>
  <section class="launcher">
    <h1>{{ t('recorder.launcher.heading') }}</h1>
    <p class="launcher__hint">{{ t('recorder.launcher.hint') }}</p>

    <div class="launcher__field">
      <label class="launcher__label" for="rec-repo">{{ t('recorder.launcher.repoLabel') }}</label>
      <select id="rec-repo" v-model.number="repoId" class="launcher__select">
        <option v-for="r in reposStore.repos" :key="r.id" :value="r.id">{{ r.name }}</option>
      </select>
    </div>

    <div class="launcher__field">
      <span class="launcher__label">{{ t('recorder.launcher.transportLabel') }}</span>
      <div class="launcher__radios">
        <label
          v-for="opt in transports"
          :key="opt.value"
          :class="['launcher__radio', { 'is-disabled': opt.disabled }]"
        >
          <input
            type="radio"
            :value="opt.value"
            v-model="transport"
            :disabled="opt.disabled"
          />
          <span>{{ t(opt.labelKey) }}</span>
          <small v-if="opt.disabled" class="launcher__soon">{{ t('recorder.launcher.comingSoon') }}</small>
        </label>
      </div>
    </div>

    <div v-if="error" class="launcher__error" role="alert">{{ error }}</div>

    <button
      type="button"
      class="launcher__cta"
      :disabled="!canStart"
      @click="start"
    >
      {{ starting ? t('recorder.launcher.starting') : t('recorder.launcher.record') }}
    </button>
  </section>
</template>

<style scoped>
.launcher {
  max-width: 560px;
  margin: 2rem auto;
  padding: 1.5rem;
}

.launcher__hint {
  color: var(--color-text-secondary, #555);
  margin-bottom: 1.5rem;
}

.launcher__field {
  margin: 1rem 0;
}

.launcher__label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.4rem;
}

.launcher__select {
  width: 100%;
  padding: 0.5rem 0.6rem;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 4px;
}

.launcher__radios {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.launcher__radio {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.launcher__radio.is-disabled {
  opacity: 0.5;
}

.launcher__soon {
  color: var(--color-text-secondary, #777);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-left: 0.3rem;
}

.launcher__error {
  padding: 0.6rem 0.8rem;
  margin: 1rem 0;
  background: #fee2e2;
  border: 1px solid #f87171;
  border-radius: 4px;
  color: #7f1d1d;
}

.launcher__cta {
  padding: 0.7rem 1.5rem;
  background: #c0392b;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
}

.launcher__cta:disabled {
  background: var(--color-border, #ccc);
  cursor: not-allowed;
}
</style>
