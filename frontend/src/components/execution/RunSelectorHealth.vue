<script setup lang="ts">
/**
 * Story SH-1 — selector-health diagnosis.
 *
 * Rendered inside RunDetailPanel for terminal runs (failed / error /
 * timeout). Fetches /runs/{id}/selector-health once and, if a sidecar
 * was present AND at least one failing locator was detected, lists
 * the ranked alternative candidates next to each failure.
 *
 * Stays silent on passing runs, missing sidecars, or zero matches —
 * no empty panel.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getRunSelectorHealth, type SelectorHealth } from '@/api/execution.api'

const props = defineProps<{ runId: number; status: string }>()
const { t } = useI18n()

const health = ref<SelectorHealth | null>(null)
const loading = ref(false)
const errored = ref(false)

const isTerminalFailure = computed(() =>
  ['failed', 'error', 'timeout'].includes(props.status),
)

const hasContent = computed(
  () =>
    !!health.value?.has_sidecar &&
    (health.value?.failed_locators?.length ?? 0) > 0,
)

async function copyToClipboard(value: string) {
  try {
    await navigator.clipboard.writeText(value)
  } catch {
    // Clipboard may be restricted; silently ignore — user can still read+manually copy.
  }
}

async function load() {
  if (!isTerminalFailure.value) return
  loading.value = true
  errored.value = false
  try {
    health.value = await getRunSelectorHealth(props.runId)
  } catch {
    errored.value = true
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.runId, props.status] as const,
  () => {
    health.value = null
    load()
  },
  { immediate: true },
)
</script>

<template>
  <section
    v-if="hasContent"
    class="selector-health"
    role="region"
    :aria-label="t('execution.selectorHealth.heading')"
  >
    <h3 class="selector-health__heading">
      🔎 {{ t('execution.selectorHealth.heading') }}
    </h3>
    <p class="selector-health__hint">
      {{ t('execution.selectorHealth.hint', { path: health?.sidecar_path }) }}
    </p>

    <div
      v-for="hit in health?.failed_locators"
      :key="hit.raw_locator"
      class="selector-health__hit"
    >
      <div class="selector-health__hit-head">
        <span class="selector-health__label">{{ t('execution.selectorHealth.failedLocator') }}</span>
        <code class="selector-health__locator">{{ hit.raw_locator }}</code>
      </div>

      <div v-if="hit.candidates.length" class="selector-health__candidates">
        <p class="selector-health__candidates-label">
          {{ t('execution.selectorHealth.tryInstead') }}
        </p>
        <ul class="selector-health__candidate-list">
          <li
            v-for="c in hit.candidates"
            :key="c.value"
            class="selector-health__candidate"
          >
            <span class="selector-health__strategy" :data-strategy="c.strategy">{{ c.strategy }}</span>
            <code class="selector-health__candidate-value">{{ c.value }}</code>
            <span
              v-if="c.quality_score != null"
              class="selector-health__quality"
              :title="t('execution.selectorHealth.qualityTitle')"
            >
              {{ (c.quality_score * 100).toFixed(0) }}%
            </span>
            <button
              type="button"
              class="selector-health__copy"
              @click="copyToClipboard(c.value)"
            >
              {{ t('execution.selectorHealth.copy') }}
            </button>
          </li>
        </ul>
      </div>
      <p v-else class="selector-health__no-alt">
        {{ t('execution.selectorHealth.noAlternatives') }}
      </p>
    </div>
  </section>
</template>

<style scoped>
.selector-health {
  margin: 1rem 0;
  padding: 0.85rem 1rem;
  background: #f0f9ff;
  border: 1px solid #7dd3fc;
  border-radius: 6px;
  color: #075985;
}

.selector-health__heading {
  margin: 0 0 0.4rem;
  font-size: 0.95rem;
}

.selector-health__hint {
  margin: 0 0 0.8rem;
  font-size: 0.8rem;
  color: #0c4a6e;
  font-style: italic;
}

.selector-health__hit {
  padding: 0.5rem 0;
  border-top: 1px dashed rgba(7, 89, 133, 0.3);
}
.selector-health__hit:first-of-type { border-top: none; padding-top: 0; }

.selector-health__hit-head {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  margin-bottom: 0.3rem;
}

.selector-health__label {
  font-size: 0.8rem;
  color: #0c4a6e;
  font-weight: 600;
}

.selector-health__locator {
  background: rgba(7, 89, 133, 0.08);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: var(--font-mono, monospace);
  font-size: 0.85rem;
}

.selector-health__candidates-label {
  margin: 0.2rem 0;
  font-size: 0.8rem;
}

.selector-health__candidate-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.selector-health__candidate {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.selector-health__strategy {
  font-size: 0.7rem;
  text-transform: uppercase;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 2px 6px;
  border-radius: 3px;
  background: #cffafe;
  color: #155e75;
}
.selector-health__strategy[data-strategy="testid"],
.selector-health__strategy[data-strategy="aria"],
.selector-health__strategy[data-strategy="pw_locator"] {
  background: #bbf7d0;
  color: #14532d;
}
.selector-health__strategy[data-strategy="text"],
.selector-health__strategy[data-strategy="css"] {
  background: #fef3c7;
  color: #854d0e;
}
.selector-health__strategy[data-strategy="xpath"] {
  background: #fee2e2;
  color: #7f1d1d;
}

.selector-health__candidate-value {
  background: white;
  border: 1px solid rgba(7, 89, 133, 0.2);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: var(--font-mono, monospace);
  font-size: 0.82rem;
  flex: 1 1 280px;
  overflow-wrap: anywhere;
}

.selector-health__quality {
  font-size: 0.75rem;
  color: #0c4a6e;
  font-variant-numeric: tabular-nums;
}

.selector-health__copy {
  padding: 3px 8px;
  background: white;
  border: 1px solid #7dd3fc;
  border-radius: 3px;
  cursor: pointer;
  color: #075985;
  font-size: 0.78rem;
}
.selector-health__copy:hover {
  background: #7dd3fc;
  color: white;
}

.selector-health__no-alt {
  margin: 0;
  font-size: 0.8rem;
  color: #0c4a6e;
  font-style: italic;
}
</style>
