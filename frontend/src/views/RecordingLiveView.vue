<script setup lang="ts">
/**
 * Story W.6 full — live recording view.
 *
 * Subscribes to the Story W.2 SSE stream, accumulates every incoming
 * RecordedCommand into a reactive list with the Story S.4 inline
 * selector picker, and offers a Stop-and-Save button that:
 *   1) aborts the session (closes the Chromium + ends the stream)
 *   2) prompts for a repo-relative path
 *   3) POSTs the collected flow to /recordings/save
 *   4) navigates to the saved file
 *
 * Deliberately minimal — the full Visual-Flow + Text editor remount
 * that the PRD describes can reuse the existing editor components
 * against the resulting .robot file; that's a follow-up story.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { abortV2Session, saveV2Flow, startV2Browser } from '@/api/recording-v2.api'
import type { RecordedCommand, RecordedFlow, RecordingTransport } from '@/types/recorder.types'
import { RECORDER_SCHEMA_VERSION } from '@/types/recorder.types'
import SelectorPicker from '@/components/recorder/SelectorPicker.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const sessionId = Number(route.params.sessionId)
const commands = ref<RecordedCommand[]>([])
const streamState = ref<'connecting' | 'live' | 'done' | 'error'>('connecting')
const errorMsg = ref<string | null>(null)
const saving = ref(false)
const savePathInput = ref('flows/recording')

let eventSource: EventSource | null = null

function handleCommand(ev: MessageEvent) {
  try {
    const cmd = JSON.parse(ev.data) as RecordedCommand
    commands.value.push(cmd)
    streamState.value = 'live'
  } catch (e) {
    // Malformed payload — log and continue; the capture layer is the
    // source of truth, not this consumer.
    // eslint-disable-next-line no-console
    console.warn('Unparseable command event', e)
  }
}

function handleEnd() {
  streamState.value = 'done'
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

function handleError() {
  if (streamState.value !== 'done') {
    streamState.value = 'error'
    errorMsg.value = t('recorder.live.streamError')
  }
}

async function ensureBrowserStarted() {
  try {
    await startV2Browser(sessionId)
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail ?? t('recorder.live.startFailed')
  }
}

function connectStream() {
  // EventSource cannot set Authorization headers — pass the access_token
  // as a query param. Backend's /commands endpoint accepts either the
  // `Authorization: Bearer …` header (programmatic clients) or this
  // `?token=` fallback (browser EventSource).
  const tok = localStorage.getItem('access_token') || ''
  const url = `/api/v1/recordings/sessions/${sessionId}/commands?token=${encodeURIComponent(tok)}`
  eventSource = new EventSource(url, { withCredentials: true })
  // Flip to 'live' as soon as the SSE handshake succeeds — otherwise
  // users with no captured events yet stay on 'connecting' forever,
  // which looks like a hang even though the stream is healthy.
  eventSource.addEventListener('open', () => {
    if (streamState.value === 'connecting') streamState.value = 'live'
  })
  eventSource.addEventListener('command', handleCommand as EventListener)
  eventSource.addEventListener('end', handleEnd as EventListener)
  eventSource.addEventListener('error', handleError as EventListener)
}

async function restartRecording() {
  // Clean the old session and route back to the launcher so the user
  // can pick transport + repo again.
  await abortV2Session(sessionId).catch(() => {
    /* already terminal — ignore */
  })
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  router.push('/recordings/new')
}

async function stopAndSave() {
  saving.value = true
  try {
    // Stop the session so Chromium tears down + the stream emits `end`.
    await abortV2Session(sessionId).catch(() => {
      /* already terminal → ignore */
    })
    const flow: RecordedFlow = {
      schema_version: RECORDER_SCHEMA_VERSION,
      transport: 'web_playwright' as RecordingTransport,
      session_id: String(sessionId),
      name: null,
      commands: commands.value,
    }
    // Repo id was picked on the launcher view and stashed in sessionStorage
    // so the live view doesn't re-prompt.
    const repoIdRaw = sessionStorage.getItem(`recorder.repo.${sessionId}`)
    const repoId = repoIdRaw ? Number(repoIdRaw) : NaN
    if (!repoId || Number.isNaN(repoId)) {
      errorMsg.value = t('recorder.live.repoMissing')
      saving.value = false
      return
    }
    const res = await saveV2Flow(flow, repoId, savePathInput.value)
    router.push(`/explorer/${repoId}?path=${encodeURIComponent(res.saved_path)}`)
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    errorMsg.value =
      typeof detail === 'string' ? detail : detail?.message ?? t('recorder.live.saveFailed')
  } finally {
    saving.value = false
  }
}

function updateActiveIndex(cmdIndex: number, newActive: number) {
  const cmd = commands.value[cmdIndex]
  if (!cmd) return
  commands.value[cmdIndex] = { ...cmd, active_candidate_index: newActive }
}

/**
 * RECORDER-PRUNE-1 — local prune of an unwanted captured step.
 *
 * The deny-list at `_AD_IFRAME_HOST_SUBSTRINGS` filters known
 * ad/tracker iframes server-side, but it can never be exhaustive
 * (new ad networks, A/B-tested experimentation widgets, hover
 * interstitials a user accidentally hits, …). Per-step delete lets
 * the user remove a row before saving — purely client-side: the
 * sidecar uploaded on Save already excludes pruned rows because the
 * save POST sends `commands.value`, not the SSE-streamed history.
 *
 * No undo: the deletion is local-only and the user can always stop
 * + re-record if they over-prune. Adding undo would mean buffering
 * deleted commands and a UI toast — disproportionate for a path
 * that's by definition "I clearly don't want this row".
 */
function deleteCommand(cmdIndex: number): void {
  if (cmdIndex < 0 || cmdIndex >= commands.value.length) return
  commands.value.splice(cmdIndex, 1)
}

/**
 * RECORDER-FRAMES — short host label for the iframe badge.
 * Strips the protocol and any trailing path so the chip stays narrow
 * (`message-eu.sp-prod.net`, not the full URL with consent-id query).
 */
function frameHost(frameUrl: string | null | undefined): string {
  if (!frameUrl) return ''
  try {
    return new URL(frameUrl).host
  } catch {
    return frameUrl
  }
}

onMounted(async () => {
  await ensureBrowserStarted()
  connectStream()
})

onBeforeUnmount(() => {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
})

const isTerminal = computed(() => streamState.value === 'done' || streamState.value === 'error')
</script>

<template>
  <section class="recording-live">
    <header class="recording-live__header">
      <h1>{{ t('recorder.live.heading') }}</h1>
      <span :class="['recording-live__status', `is-${streamState}`]">{{ t(`recorder.live.status.${streamState}`) }}</span>
    </header>

    <div v-if="errorMsg" class="recording-live__error" role="alert">
      <span>{{ errorMsg }}</span>
      <button
        v-if="streamState === 'error'"
        type="button"
        class="recording-live__retry"
        @click="restartRecording"
      >
        {{ t('recorder.live.restart') }}
      </button>
    </div>

    <ol class="recording-live__steps">
      <li v-for="(cmd, idx) in commands" :key="idx" class="recording-live__step">
        <span class="recording-live__keyword">{{ cmd.keyword }}</span>
        <!-- Story RECORDER-FRAMES — every iframe-originating command
             gets a small chip with the iframe host so the user can
             tell at a glance which clicks came from the consent
             banner / OAuth widget vs. the main page. Critical signal
             when the iframe was an ad they didn't intend to record —
             they can delete the row before saving. -->
        <span
          v-if="cmd.frame_url"
          class="recording-live__frame-badge"
          :title="cmd.frame_url"
          data-testid="recording-frame-badge"
        >
          ⇣ {{ frameHost(cmd.frame_url) }}
        </span>
        <SelectorPicker
          v-if="cmd.selector_candidates.length"
          :command="cmd"
          compact
          @update:activeIndex="updateActiveIndex(idx, $event)"
        />
        <span v-if="cmd.args && Object.keys(cmd.args).length" class="recording-live__args">
          {{ Object.values(cmd.args).join(' · ') }}
        </span>
        <!-- Story RECORDER-PRUNE-1 — per-step delete. Local-only;
             no undo (over-prune ⇒ stop and re-record). The button
             is visually subdued and right-aligned via flex so it
             doesn't compete with the keyword + selector picker. -->
        <button
          type="button"
          class="recording-live__step-delete"
          :title="t('recorder.live.deleteStep')"
          :aria-label="t('recorder.live.deleteStep')"
          :data-testid="`recording-step-delete-${idx}`"
          @click="deleteCommand(idx)"
        >
          ✕
        </button>
      </li>
    </ol>

    <p v-if="!commands.length && streamState === 'live'" class="recording-live__hint">
      {{ t('recorder.live.waiting') }}
    </p>

    <div class="recording-live__save">
      <label class="recording-live__label" for="save-path">
        {{ t('recorder.live.pathLabel') }}
      </label>
      <input
        id="save-path"
        v-model="savePathInput"
        class="recording-live__input"
        :placeholder="t('recorder.live.pathPlaceholder')"
      />
      <button
        type="button"
        class="recording-live__cta"
        :disabled="saving"
        @click="stopAndSave"
      >
        {{ isTerminal ? t('recorder.live.save') : t('recorder.live.stopAndSave') }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.recording-live {
  max-width: 720px;
  margin: 1.5rem auto;
  padding: 1rem 1.5rem;
}

.recording-live__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.recording-live__status {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.recording-live__status.is-connecting { background: rgba(0, 0, 0, 0.08); }
.recording-live__status.is-live       { background: rgba(44, 152, 70, 0.15); color: #1a5c2a; }
.recording-live__status.is-done       { background: rgba(59, 125, 216, 0.15); color: #1a3c7a; }
.recording-live__status.is-error      { background: #fee2e2; color: #7f1d1d; }

.recording-live__steps {
  list-style: decimal;
  padding-left: 1.5rem;
  margin: 0 0 1.5rem;
}

.recording-live__step {
  padding: 0.3rem 0;
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
}

.recording-live__keyword {
  font-weight: 600;
  color: var(--color-primary, #3B7DD8);
}

.recording-live__args {
  font-family: var(--font-mono, monospace);
  font-size: 0.8rem;
  color: var(--color-text-secondary, #555);
}

.recording-live__frame-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(212, 136, 62, 0.15);
  color: var(--color-accent, #D4883E);
  font-family: var(--font-mono, monospace);
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
  cursor: help;
}

.recording-live__step-delete {
  margin-left: auto;
  padding: 0 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--color-text-secondary, #888);
  font-size: 0.85rem;
  line-height: 1.6;
  cursor: pointer;
  border-radius: 3px;
  opacity: 0.4;
  transition: opacity 0.15s, color 0.15s, background-color 0.15s, border-color 0.15s;
}
.recording-live__step:hover .recording-live__step-delete {
  opacity: 1;
}
.recording-live__step-delete:hover {
  color: #c0392b;
  background: rgba(192, 57, 43, 0.10);
  border-color: rgba(192, 57, 43, 0.3);
}
.recording-live__step-delete:focus-visible {
  outline: 2px solid #c0392b;
  outline-offset: 1px;
  opacity: 1;
}

.recording-live__hint {
  color: var(--color-text-secondary, #555);
  font-style: italic;
  margin: 1rem 0;
}

.recording-live__save {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 1rem;
}

.recording-live__input {
  flex: 1 1 240px;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 4px;
}

.recording-live__cta {
  padding: 0.5rem 1.2rem;
  background: #c0392b;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.recording-live__cta:disabled {
  background: var(--color-border, #ccc);
  cursor: not-allowed;
}

.recording-live__error {
  padding: 0.5rem 0.75rem;
  margin: 0.5rem 0 1rem;
  background: #fee2e2;
  border: 1px solid #f87171;
  border-radius: 4px;
  color: #7f1d1d;
  display: flex;
  gap: 0.75rem;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
}

.recording-live__retry {
  padding: 0.35rem 0.9rem;
  background: white;
  color: #7f1d1d;
  border: 1px solid #7f1d1d;
  border-radius: 4px;
  cursor: pointer;
  font: inherit;
}
</style>
