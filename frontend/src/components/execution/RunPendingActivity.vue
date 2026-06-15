<script setup lang="ts">
/**
 * Story EXEC-1 — Pending-run activity surface.
 *
 * Rendered inside RunDetailPanel when the run is in the `pending`
 * state. Polls /runs/{id}/pending-activity every ~3s to derive:
 *   - queue position (how many earlier runs are still in-flight), or
 *   - active Docker image build (name + live log tail)
 * and falls back to a generic waiting line if neither applies.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getRunPendingActivity, type PendingActivity } from '@/api/execution.api'

const props = defineProps<{ runId: number; status: string }>()

const { t } = useI18n()

const activity = ref<PendingActivity | null>(null)
const loading = ref(false)
const errored = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

const isPending = computed(() => props.status === 'pending')

async function refresh() {
  if (!isPending.value) return
  loading.value = true
  errored.value = false
  try {
    activity.value = await getRunPendingActivity(props.runId)
  } catch {
    errored.value = true
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  refresh()
  // 3 s keeps the queue-position responsive without DoSing the backend
  // — the heavier build log reads the already-persisted env column, so
  // polling cost is low.
  timer = setInterval(refresh, 3000)
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

watch(
  () => [props.runId, props.status] as const,
  ([, status]) => {
    if (status === 'pending') startPolling()
    else stopPolling()
  },
  { immediate: true },
)

onBeforeUnmount(stopPolling)

const headline = computed(() => {
  const a = activity.value
  if (!a) return t('execution.pending.starting')
  if (a.active_build) {
    return t('execution.pending.waitingForBuild', {
      env: a.active_build.environment_name,
    })
  }
  if (a.ahead_count > 0) {
    return t('execution.pending.queuedBehind', { count: a.ahead_count })
  }
  return t('execution.pending.starting')
})
</script>

<template>
  <div v-if="isPending" class="pending-activity" role="status" aria-live="polite">
    <div class="pending-activity__headline">
      <span class="pending-activity__spinner" aria-hidden="true"></span>
      <span>{{ headline }}</span>
    </div>

    <div
      v-if="activity?.active_build"
      class="pending-activity__build"
    >
      <div class="pending-activity__build-meta">
        <strong>{{ activity.active_build.environment_name }}</strong>
        <router-link
          class="pending-activity__link"
          :to="'/environments'"
        >{{ t('execution.pending.viewFullLog') }}</router-link>
      </div>
      <pre
        v-if="activity.active_build.log_tail"
        class="pending-activity__log"
      >{{ activity.active_build.log_tail }}</pre>
      <p v-else class="pending-activity__hint">
        {{ t('execution.pending.buildLogEmpty') }}
      </p>
    </div>

    <p
      v-else-if="activity && activity.queue_position && activity.ahead_count > 0"
      class="pending-activity__hint"
    >
      {{ t('execution.pending.queuedPositionHint', {
        position: activity.queue_position,
        total: activity.queue_position,
      }) }}
    </p>

    <p v-if="errored" class="pending-activity__error" role="alert">
      {{ t('execution.pending.loadError') }}
    </p>
  </div>
</template>

<style scoped>
.pending-activity {
  margin: 0.75rem 0;
  padding: 0.75rem 1rem;
  background: #fff7e6;
  border: 1px solid #f6c86b;
  border-radius: 6px;
  color: #704500;
  font-size: 0.9rem;
}

.pending-activity__headline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
}

.pending-activity__spinner {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid #f6c86b;
  border-top-color: transparent;
  animation: pending-spin 0.9s linear infinite;
}

@keyframes pending-spin {
  to { transform: rotate(360deg); }
}

.pending-activity__build {
  margin-top: 0.6rem;
  padding-top: 0.6rem;
  border-top: 1px dashed rgba(112, 69, 0, 0.3);
}

.pending-activity__build-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.6rem;
  margin-bottom: 0.4rem;
}

.pending-activity__link {
  color: var(--color-primary, #2D63B0);
  text-decoration: none;
  font-size: 0.85rem;
}
.pending-activity__link:hover { text-decoration: underline; }

.pending-activity__log {
  max-height: 240px;
  overflow: auto;
  background: #1b1b1b;
  color: #d6d6d6;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  font-family: var(--font-mono, monospace);
  font-size: 0.78rem;
  line-height: 1.35;
  white-space: pre-wrap;
  margin: 0;
}

.pending-activity__hint {
  margin: 0.3rem 0 0 0;
  font-size: 0.85rem;
  color: #8b5b00;
}

.pending-activity__error {
  margin-top: 0.4rem;
  color: #7f1d1d;
  font-size: 0.85rem;
}
</style>
