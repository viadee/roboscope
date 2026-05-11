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
import {
  abortV2Session,
  restartV2Browser,
  saveV2Flow,
  startV2Browser,
} from '@/api/recording-v2.api'
import { extractErrorDetail } from '@/utils/errors'
import { effectiveSelector } from '@/utils/effectiveSelector'
import type { RecordedCommand, RecordedFlow, RecordingTransport } from '@/types/recorder.types'
import { RECORDER_SCHEMA_VERSION } from '@/types/recorder.types'
import SelectorPicker from '@/components/recorder/SelectorPicker.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const sessionId = Number(route.params.sessionId)
const commands = ref<RecordedCommand[]>([])

/**
 * Story RECORDER-VIS-1 — richer state machine driven by both the SSE
 * transport state and the new `event: lifecycle` payloads from the
 * backend. `connecting` is the only transport-level state; everything
 * else mirrors a `LifecyclePhase` from `v2_command_queue.py`.
 */
type RecorderPhase =
  | 'connecting'
  | 'browser_starting'
  | 'browser_ready'
  | 'browser_restarting'
  | 'browser_crashed'
  | 'done'
  | 'error'

const phase = ref<RecorderPhase>('connecting')
const errorMsg = ref<string | null>(null)
const crashMessage = ref<string | null>(null)
const saving = ref(false)
const restarting = ref(false)
const savePathInput = ref('flows/recording')

// `browser_ready` timestamp from the backend's lifecycle event — used
// to drive the live uptime counter in the status card. `null` until
// the first `browser_ready` arrives. Reset on `browser_restarting` so
// the counter restarts from zero on the new browser.
const readyAtMs = ref<number | null>(null)
// `now` ticks each second once we're ready, so the template can render
// `formatUptime(now - readyAtMs)` reactively without re-rendering the
// rest of the view each tick.
const now = ref<number>(Date.now())
let uptimeInterval: ReturnType<typeof setInterval> | null = null

let eventSource: EventSource | null = null

function handleCommand(ev: MessageEvent) {
  try {
    const cmd = JSON.parse(ev.data) as RecordedCommand
    commands.value.push(cmd)
    // First command arriving without an explicit `browser_ready` is
    // still a strong signal that the browser is live. Catches the
    // edge case where lifecycle events were dropped (queue cleared,
    // network blip in the middle of the SSE handshake).
    if (phase.value === 'connecting' || phase.value === 'browser_starting') {
      _transitionTo('browser_ready')
    }
  } catch (e) {
    // Malformed payload — log and continue; the capture layer is the
    // source of truth, not this consumer.
    // eslint-disable-next-line no-console
    console.warn('Unparseable command event', e)
  }
}

interface LifecyclePayload {
  phase: 'browser_starting' | 'browser_ready' | 'browser_crashed' | 'browser_restarting'
  ts: number
  message?: string | null
}

function handleLifecycle(ev: MessageEvent) {
  try {
    const data = JSON.parse(ev.data) as LifecyclePayload
    _transitionTo(data.phase, data.message ?? null)
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('Unparseable lifecycle event', e)
  }
}

function _transitionTo(next: RecorderPhase, message: string | null = null): void {
  phase.value = next
  if (next === 'browser_ready') {
    readyAtMs.value = Date.now()
    crashMessage.value = null
    errorMsg.value = null
    if (uptimeInterval === null) {
      uptimeInterval = setInterval(() => { now.value = Date.now() }, 1000)
    }
  } else if (next === 'browser_restarting' || next === 'browser_starting') {
    readyAtMs.value = null
  } else if (next === 'browser_crashed') {
    crashMessage.value = message
    readyAtMs.value = null
    if (uptimeInterval !== null) {
      clearInterval(uptimeInterval)
      uptimeInterval = null
    }
  }
}

function handleEnd() {
  _transitionTo('done')
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  if (uptimeInterval !== null) {
    clearInterval(uptimeInterval)
    uptimeInterval = null
  }
}

function handleError() {
  if (phase.value !== 'done') {
    _transitionTo('error')
    errorMsg.value = t('recorder.live.streamError')
  }
}

async function ensureBrowserStarted() {
  try {
    // Optional target URL stashed by the launcher view in
    // sessionStorage. Empty/missing → undefined → recorder opens
    // about:blank (existing behavior). Validation is mirrored on
    // both sides — the launcher disables Start for malformed URLs,
    // and `v2_start_browser` returns 400 for any non-http(s) value
    // that somehow slipped through.
    const stashedUrl = sessionStorage.getItem(`recorder.url.${sessionId}`) ?? undefined
    await startV2Browser(sessionId, stashedUrl)
  } catch (e: unknown) {
    errorMsg.value = extractErrorDetail(e, t('recorder.live.startFailed'))
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
  // Old W.6 fallback — flip to a non-`connecting` phase as soon as
  // the SSE handshake succeeds, even if the backend hasn't emitted a
  // `browser_starting` lifecycle event yet. Catches the case where
  // the queue already had commands before the consumer subscribed
  // (restart, refresh, late-attach).
  eventSource.addEventListener('open', () => {
    if (phase.value === 'connecting') _transitionTo('browser_starting')
  })
  eventSource.addEventListener('command', handleCommand as EventListener)
  // Story RECORDER-VIS-1 — backend now emits lifecycle events on the
  // same SSE channel, marked with `event: lifecycle`. Handler routes
  // them through the same state machine as transport events.
  eventSource.addEventListener('lifecycle', handleLifecycle as EventListener)
  eventSource.addEventListener('end', handleEnd as EventListener)
  eventSource.addEventListener('error', handleError as EventListener)
}

async function onRestartBrowser(): Promise<void> {
  if (!canRestartBrowser.value) return
  restarting.value = true
  errorMsg.value = null
  try {
    await restartV2Browser(sessionId)
    // The backend emits `browser_restarting` → `browser_starting` →
    // `browser_ready` on the SSE stream. We don't transition locally
    // here so the user sees the canonical phase progression driven
    // by the backend, not an optimistic UI lie.
  } catch (e: unknown) {
    errorMsg.value = extractErrorDetail(e, t('recorder.live.restartFailed'))
  } finally {
    restarting.value = false
  }
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
  } catch (e: unknown) {
    errorMsg.value = extractErrorDetail(e, t('recorder.live.saveFailed'))
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
/** Wrapper so the template can call into the `@/utils/effectiveSelector`
 *  helper without exposing it as a setup-script binding by name. */
function effectivePreview(cmd: RecordedCommand): string {
  return effectiveSelector(cmd)
}

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
  if (uptimeInterval !== null) {
    clearInterval(uptimeInterval)
    uptimeInterval = null
  }
})

const isTerminal = computed(() => phase.value === 'done' || phase.value === 'error')

/** Restart is offered while we're either healthy (`browser_ready`) or
 * after a crash. During the transient `browser_starting` /
 * `browser_restarting` phases the previous task hasn't released its
 * slot yet — the backend would 409. */
const canRestartBrowser = computed(
  () => !restarting.value && (phase.value === 'browser_ready' || phase.value === 'browser_crashed'),
)

/** Uptime label since the latest `browser_ready` event, in mm:ss
 * form. Returns null until the browser is ready so the template
 * conditionally renders. */
const uptimeLabel = computed<string | null>(() => {
  const ready = readyAtMs.value
  if (ready === null) return null
  const elapsed = Math.max(0, Math.floor((now.value - ready) / 1000))
  const mm = String(Math.floor(elapsed / 60)).padStart(2, '0')
  const ss = String(elapsed % 60).padStart(2, '0')
  return `${mm}:${ss}`
})
</script>

<template>
  <section class="recording-live">
    <header class="recording-live__header">
      <h1>{{ t('recorder.live.heading') }}</h1>
      <!-- Story RECORDER-VIS-1 — phase pill is driven by the lifecycle
           events from the backend SSE channel; the live uptime + the
           Restart-Browser button render alongside it so the user can
           always tell whether Chromium is alive AND has an obvious
           recovery affordance. -->
      <div class="recording-live__phase-card" data-testid="recorder-phase-card">
        <span
          :class="['recording-live__status', `is-${phase}`]"
          data-testid="recorder-phase-pill"
        >
          {{ t(`recorder.live.lifecycle.${phase}`) }}
        </span>
        <span
          v-if="uptimeLabel !== null"
          class="recording-live__uptime"
          :title="t('recorder.live.uptimeTitle')"
          data-testid="recorder-uptime"
        >
          ⏱ {{ uptimeLabel }}
        </span>
        <button
          v-if="!isTerminal"
          type="button"
          class="recording-live__restart-browser"
          :disabled="!canRestartBrowser"
          :title="t('recorder.live.restartBrowserHint')"
          data-testid="recorder-restart-browser"
          @click="onRestartBrowser"
        >
          <span v-if="restarting" aria-hidden="true">⟳</span>
          {{ restarting
            ? t('recorder.live.restartingBrowser')
            : t('recorder.live.restartBrowser') }}
        </button>
      </div>
    </header>

    <div
      v-if="phase === 'browser_crashed' && crashMessage"
      class="recording-live__crash"
      role="alert"
      data-testid="recorder-crash-banner"
    >
      <strong>{{ t('recorder.live.crashTitle') }}</strong>
      <span>{{ crashMessage }}</span>
    </div>

    <div v-if="errorMsg" class="recording-live__error" role="alert">
      <span>{{ errorMsg }}</span>
      <button
        v-if="phase === 'error'"
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
        <!-- Story RECORDER-FRAMES-2 — preview of the COMPOSED line
             that the emitter will write into the .robot file. The
             picker above shows only the inner candidate; this preview
             also folds in the iframe wrapper chain and the defensive
             `>> nth=0` disambiguation, so what the user sees here is
             exactly what they'll save. Hidden for top-frame keyword-
             less commands (`Go To`, `Switch Page`) where the inner
             candidate IS the full line. -->
        <div
          v-if="cmd.selector_candidates.length"
          class="recording-live__effective"
          :title="t('recorder.live.effectiveTitle')"
          data-testid="recording-effective-selector"
        >
          <span class="recording-live__effective-label">.robot:</span>
          <code class="recording-live__effective-value">{{ effectivePreview(cmd) }}</code>
        </div>
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

    <p v-if="!commands.length && phase === 'browser_ready'" class="recording-live__hint">
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

.recording-live__status.is-connecting          { background: rgba(0, 0, 0, 0.08); }
.recording-live__status.is-browser_starting    { background: rgba(212, 136, 62, 0.15); color: #6e3d09; }
.recording-live__status.is-browser_ready       { background: rgba(44, 152, 70, 0.15); color: #1a5c2a; }
.recording-live__status.is-browser_restarting  { background: rgba(212, 136, 62, 0.2);  color: #6e3d09; }
.recording-live__status.is-browser_crashed     { background: #fee2e2; color: #7f1d1d; }
.recording-live__status.is-done                { background: rgba(59, 125, 216, 0.15); color: #1a3c7a; }
.recording-live__status.is-error               { background: #fee2e2; color: #7f1d1d; }

/* Story RECORDER-VIS-1 — phase card next to the heading. */
.recording-live__phase-card {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}
.recording-live__uptime {
  font-family: var(--font-mono, monospace);
  font-size: 0.8rem;
  color: var(--color-text-muted, #5A6380);
  user-select: none;
}
.recording-live__restart-browser {
  background: var(--color-bg, #fff);
  border: 1px solid var(--color-border, #d6dfeb);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 0.8rem;
  cursor: pointer;
  color: var(--color-text-muted, #5A6380);
}
.recording-live__restart-browser:hover:not(:disabled) {
  border-color: var(--color-primary, #3B7DD8);
  color: var(--color-primary, #3B7DD8);
}
.recording-live__restart-browser:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.recording-live__effective {
  flex-basis: 100%;
  margin-top: 0.15rem;
  font-size: 0.78rem;
  color: var(--color-text-muted, #5A6380);
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
}
.recording-live__effective-label {
  color: var(--color-text-tertiary, #94a3b8);
  font-variant: small-caps;
  letter-spacing: 0.04em;
}
.recording-live__effective-value {
  font-family: var(--font-mono, ui-monospace, "Cascadia Code", monospace);
  font-size: 0.78rem;
  color: var(--color-text-secondary, #4a5b75);
  background: var(--color-bg, #fff);
  padding: 1px 5px;
  border-radius: 3px;
  border: 1px solid var(--color-border, #e5e7eb);
  word-break: break-all;
  flex: 1;
  min-width: 0;
}
.recording-live__crash {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  background: #fee2e2;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.75rem;
  color: #7f1d1d;
  font-size: 0.85rem;
}

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
