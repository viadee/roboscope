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
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  createV2Session,
  getV2Capabilities,
  resetStuckSessions,
  type V2Capabilities,
} from '@/api/recording-v2.api'
import { useReposStore } from '@/stores/repos.store'
import { useToast } from '@/composables/useToast'
import type { RecordingTransport } from '@/types/recorder.types'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const reposStore = useReposStore()
const toast = useToast()

const transport = ref<RecordingTransport>('web_playwright')
const repoId = ref<number | null>(null)
// Optional URL the recorder will navigate to right after the browser
// opens. Only relevant for `web_playwright`; desktop transports
// ignore it. Empty/whitespace-only → recorder starts at about:blank
// and the user navigates manually. The same scheme guard the backend
// applies (`http(s)://` only) is mirrored here so users see an inline
// validation message instead of a 400 round-trip.
const targetUrl = ref<string>('')
const targetUrlError = computed<string | null>(() => {
  const v = targetUrl.value.trim()
  if (v === '') return null
  if (v.startsWith('http://') || v.startsWith('https://')) return null
  return t('recorder.launcher.targetUrlInvalid')
})
const starting = ref(false)
const error = ref<string | null>(null)
// RECORDER-RESET-1 — panic-button state for the "click here when
// something went wrong" affordance below the Record CTA.
const resetting = ref(false)

// Story DEPLOY-1 — capability probe. Defaults err on the side of
// "everything enabled" so a failed probe never locks the user out.
const capabilities = ref<V2Capabilities>({
  web_playwright_viable: true,
  desktop_windows_viable: true,
  desktop_macos_viable: false,
})

const transports = computed<{ value: RecordingTransport; labelKey: string; disabled: boolean }[]>(
  () => [
    {
      value: 'web_playwright',
      labelKey: 'recorder.launcher.transport.web',
      disabled: !capabilities.value.web_playwright_viable,
    },
    {
      value: 'desktop_windows',
      labelKey: 'recorder.launcher.transport.windows',
      disabled: !capabilities.value.desktop_windows_viable,
    },
    {
      value: 'desktop_macos',
      labelKey: 'recorder.launcher.transport.macos',
      disabled: !capabilities.value.desktop_macos_viable,
    },
  ],
)

const webNotViable = computed(() => !capabilities.value.web_playwright_viable)

const canStart = computed(
  () =>
    transport.value
    && repoId.value !== null
    && !starting.value
    && targetUrlError.value === null,
)

async function reset() {
  // No confirm dialog: the endpoint only touches the user's OWN stuck
  // sessions, and idempotent calls are zero-cost. A double-confirm
  // discourages the action exactly when the user needs it most
  // (recorder is already broken, they're trying to unstick it).
  if (resetting.value) return
  resetting.value = true
  error.value = null
  try {
    const out = await resetStuckSessions()
    if (out.aborted === 0) {
      toast.info(t('recorder.launcher.reset.noneFound'))
    } else {
      toast.success(
        t('recorder.launcher.reset.done'),
        t('recorder.launcher.reset.doneDetail', { count: out.aborted }),
      )
    }
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    error.value =
      typeof detail === 'string'
        ? detail
        : detail?.message ?? t('recorder.launcher.reset.failed')
  } finally {
    resetting.value = false
  }
}

async function start() {
  if (!canStart.value) return
  starting.value = true
  error.value = null
  try {
    const session = await createV2Session(transport.value, repoId.value as number)
    // Stash the repo id so the live view's save step can POST /save
    // without re-prompting the user.
    sessionStorage.setItem(`recorder.repo.${session.session_id}`, String(repoId.value))
    // Stash the target URL (if any) so the live view's
    // `startV2Browser(sessionId, targetUrl)` call carries it through
    // to the recorder. Trim + empty-check matches the backend's
    // normalisation in v2_start_browser.
    const trimmedUrl = targetUrl.value.trim()
    if (trimmedUrl) {
      sessionStorage.setItem(`recorder.url.${session.session_id}`, trimmedUrl)
    }
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

  // Story DEPLOY-1 — probe capabilities. Silent fallback on failure.
  try {
    capabilities.value = await getV2Capabilities()
  } catch {
    // Keep the optimistic defaults — the 501 guard on /start-browser
    // is the real enforcement point.
  }
  // If the default-selected transport turned out to be unviable,
  // switch to the first viable option so the user isn't stuck on a
  // disabled radio.
  const current = transports.value.find((t) => t.value === transport.value)
  if (current?.disabled) {
    const firstViable = transports.value.find((t) => !t.disabled)
    if (firstViable) transport.value = firstViable.value
  }

  if (reposStore.repos.length === 0) return
  // Story W.9 — deep-link from the Explorer: if the URL carries a
  // ?repoId=<N> query param and the repo is visible to the user, use
  // it. Otherwise fall back to the first repo.
  const qRaw = route.query.repoId
  const qNum = typeof qRaw === 'string' ? Number.parseInt(qRaw, 10) : NaN
  const match = Number.isFinite(qNum)
    ? reposStore.repos.find((r) => r.id === qNum)
    : undefined
  if (match) {
    repoId.value = match.id
  } else if (repoId.value === null) {
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

    <div v-if="transport === 'web_playwright'" class="launcher__field">
      <label class="launcher__label" for="rec-url">
        {{ t('recorder.launcher.targetUrlLabel') }}
      </label>
      <input
        id="rec-url"
        v-model="targetUrl"
        type="url"
        class="launcher__input"
        :placeholder="t('recorder.launcher.targetUrlPlaceholder')"
        :aria-invalid="targetUrlError !== null"
        autocomplete="url"
        spellcheck="false"
        data-testid="rec-target-url"
      />
      <small
        v-if="targetUrlError"
        class="launcher__field-error"
        role="alert"
        data-testid="rec-target-url-error"
      >{{ targetUrlError }}</small>
      <small v-else class="launcher__field-hint">
        {{ t('recorder.launcher.targetUrlHint') }}
      </small>
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

    <div v-if="webNotViable" class="launcher__headless-hint" role="status">
      <strong>{{ t('recorder.launcher.remote.heading') }}</strong>
      <p>{{ t('recorder.launcher.remote.body') }}</p>
      <p class="launcher__headless-hint-muted">{{ t('recorder.launcher.remote.override') }}</p>
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

    <!-- RECORDER-RESET-1 — panic button. Always visible so the user
         can find it when the recorder hangs. Visually subdued so it
         doesn't compete with the primary Record CTA above. -->
    <div class="launcher__reset" role="group">
      <p class="launcher__reset-hint">{{ t('recorder.launcher.reset.hint') }}</p>
      <button
        type="button"
        class="launcher__reset-btn"
        :disabled="resetting"
        data-testid="recorder-reset"
        @click="reset"
      >
        {{ resetting ? t('recorder.launcher.reset.busy') : t('recorder.launcher.reset.label') }}
      </button>
    </div>
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

.launcher__select,
.launcher__input {
  width: 100%;
  padding: 0.5rem 0.6rem;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 4px;
  box-sizing: border-box;
}

.launcher__input[aria-invalid="true"] {
  border-color: #c0392b;
}

.launcher__field-hint,
.launcher__field-error {
  display: block;
  margin-top: 0.35rem;
  font-size: 0.85rem;
}

.launcher__field-hint {
  color: var(--color-text-secondary, #666);
}

.launcher__field-error {
  color: #c0392b;
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

.launcher__headless-hint {
  padding: 0.7rem 0.9rem;
  margin: 1rem 0;
  background: #fff7e6;
  border: 1px solid #f6c86b;
  border-radius: 6px;
  color: #704500;
}

.launcher__headless-hint strong {
  display: block;
  margin-bottom: 0.3rem;
}

.launcher__headless-hint p {
  margin: 0.25rem 0;
  font-size: 0.9rem;
}

.launcher__headless-hint-muted {
  color: #8b5b00;
  font-size: 0.8rem !important;
  font-style: italic;
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

.launcher__reset {
  margin-top: 2.5rem;
  padding-top: 1rem;
  border-top: 1px dashed var(--color-border, #ddd);
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.launcher__reset-hint {
  margin: 0;
  font-size: 0.85rem;
  color: var(--color-text-secondary, #666);
}

.launcher__reset-btn {
  align-self: flex-start;
  padding: 0.4rem 0.9rem;
  background: transparent;
  color: var(--color-text-secondary, #666);
  border: 1px solid var(--color-border, #ccc);
  border-radius: 4px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background-color 0.15s, border-color 0.15s, color 0.15s;
}

.launcher__reset-btn:hover:not(:disabled) {
  background: rgba(192, 57, 43, 0.08);
  border-color: #c0392b;
  color: #c0392b;
}

.launcher__reset-btn:disabled {
  opacity: 0.6;
  cursor: progress;
}
</style>
