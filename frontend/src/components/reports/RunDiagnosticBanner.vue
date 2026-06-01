<script setup lang="ts">
/**
 * Renders an actionable banner at the top of the ReportDetail view
 * when the backend's `detect_report_diagnostic` recognises a known
 * failure mode. Today the only code is `playwright_browser_missing`,
 * which suggests running `rfbrowser init` in the env's venv to
 * download the Chromium binaries Browser library expects.
 *
 * The button POSTs to the action endpoint the backend computed —
 * the frontend doesn't hard-code the URL so adding a new
 * diagnostic on the server side requires only a new locale entry
 * + a renderer hook here, not API surface changes.
 *
 * After a successful trigger, the banner flips to a "running"
 * state with a clear message that init can take a few minutes
 * and the page should be refreshed once finished. We deliberately
 * do NOT auto-poll the env status / re-fetch the report — the
 * banner's job is to TRIGGER, not to mirror the install progress
 * (the Environments view has the proper progress UI for that).
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import apiClient from '@/api/client'
import { extractErrorDetail } from '@/utils/errors'
import type { RunDiagnostic } from '@/types/domain.types'

const props = defineProps<{
  diagnostic: RunDiagnostic
}>()

const { t } = useI18n()

type Phase = 'idle' | 'triggering' | 'started' | 'failed'

const phase = ref<Phase>('idle')
const errorDetail = ref<string | null>(null)

const titleKey = computed(() => `reports.diagnostic.${props.diagnostic.code}.title`)
const descriptionKey = computed(() => `reports.diagnostic.${props.diagnostic.code}.description`)
const actionKey = computed(() => `reports.diagnostic.${props.diagnostic.code}.action`)

async function trigger() {
  if (phase.value === 'triggering' || phase.value === 'started') return
  phase.value = 'triggering'
  errorDetail.value = null
  try {
    // Backend tells us the exact endpoint to call — keeps the
    // frontend free of "which env, which verb" hardcoding.
    await apiClient.request({
      url: props.diagnostic.action.endpoint,
      method: props.diagnostic.action.method,
    })
    phase.value = 'started'
  } catch (err) {
    // `extractErrorDetail`'s second arg is the fallback when no
    // detail can be pulled off the error shape. Empty string =
    // "no extra info to render" — the template gates on the ref
    // being non-empty before appending it after the colon.
    errorDetail.value = extractErrorDetail(err, '') || null
    phase.value = 'failed'
  }
}
</script>

<template>
  <aside class="run-diagnostic-banner" role="status">
    <div class="run-diagnostic-banner__icon" aria-hidden="true">⚠</div>
    <div class="run-diagnostic-banner__body">
      <h4 class="run-diagnostic-banner__title">{{ t(titleKey) }}</h4>
      <p class="run-diagnostic-banner__description">{{ t(descriptionKey) }}</p>

      <!-- Status feedback after a click — the actual install
           progress is owned by the Environments view; the banner
           just confirms the trigger landed and points the user to
           refresh after a few minutes. -->
      <p v-if="phase === 'started'" class="run-diagnostic-banner__status run-diagnostic-banner__status--ok">
        {{ t('reports.diagnostic.startedMessage') }}
      </p>
      <p v-else-if="phase === 'failed'" class="run-diagnostic-banner__status run-diagnostic-banner__status--err">
        {{ t('reports.diagnostic.failedMessage') }}<span v-if="errorDetail">: {{ errorDetail }}</span>
      </p>
    </div>
    <div class="run-diagnostic-banner__action">
      <!-- Button is hidden ONLY in the "started" phase — for idle,
           triggering, and failed it stays visible so the user can
           click (idle / failed) or see the spinner (triggering).
           `:loading` flips the BaseButton into a spinner state
           while the request is in flight. -->
      <span
        v-if="phase === 'started'"
        class="run-diagnostic-banner__started-badge"
        data-testid="run-diagnostic-started"
      >
        ✓ {{ t('reports.diagnostic.startedBadge') }}
      </span>
      <BaseButton
        v-else
        size="sm"
        :loading="phase === 'triggering'"
        data-testid="run-diagnostic-trigger"
        @click="trigger"
      >
        {{ t(actionKey) }}
      </BaseButton>
    </div>
  </aside>
</template>

<style scoped>
.run-diagnostic-banner {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 16px;
  align-items: start;
  padding: 14px 18px;
  margin: 0 0 16px;
  background: var(--color-warning-bg, #fef3c7);
  border: 1px solid var(--color-warning-border, #f59e0b);
  border-radius: 6px;
  color: var(--color-warning-text, #92400e);
}

.run-diagnostic-banner__icon {
  font-size: 22px;
  line-height: 1;
  padding-top: 2px;
}

.run-diagnostic-banner__title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
}

.run-diagnostic-banner__description {
  margin: 0;
  font-size: 13px;
  line-height: 1.4;
}

.run-diagnostic-banner__status {
  margin: 8px 0 0;
  font-size: 12px;
  font-weight: 600;
}
.run-diagnostic-banner__status--ok {
  color: var(--color-success, #047857);
}
.run-diagnostic-banner__status--err {
  color: var(--color-danger, #b91c1c);
}

.run-diagnostic-banner__action {
  align-self: center;
}

.run-diagnostic-banner__started-badge {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-success, #047857);
}
</style>
