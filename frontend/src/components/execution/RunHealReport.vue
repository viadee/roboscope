<script setup lang="ts">
/**
 * Story SH-2 — runtime heal-report panel.
 *
 * Renders a summary of all selector heals that happened during a run,
 * cross-referenced with the test outcomes. `confirmed` heals (🩹)
 * offer a "Copy patch" button; `suspect` heals (⚠️) deliberately do
 * NOT — a heal that likely clicked the wrong element should not be
 * promoted into a one-click fix.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  applyHealPatch,
  getRunHealReport,
  type HealAuditEntry,
  type HealReport,
} from '@/api/execution.api'
import { useAuthStore } from '@/stores/auth.store'
import { extractErrorDetail } from '@/utils/errors'

const props = defineProps<{ runId: number; status: string }>()
const { t } = useI18n()
const auth = useAuthStore()

const report = ref<HealReport | null>(null)
const loading = ref(false)
const errored = ref(false)

// Story SH-4 — track which heals have been applied in this view so
// the button flips to ✅ without a full reload.
const appliedIndices = ref<Set<number>>(new Set())
const applyingIndices = ref<Set<number>>(new Set())
const applyErrors = ref<Map<number, string>>(new Map())

async function applyPatch(idx: number) {
  if (applyingIndices.value.has(idx) || appliedIndices.value.has(idx)) return
  applyingIndices.value.add(idx)
  applyErrors.value.delete(idx)
  try {
    const res = await applyHealPatch(props.runId, idx)
    if (res.applied || res.reason === 'already_patched') {
      appliedIndices.value.add(idx)
    }
  } catch (e: unknown) {
    applyErrors.value.set(
      idx,
      extractErrorDetail(e, t('execution.healReport.applyFailed')),
    )
  } finally {
    applyingIndices.value.delete(idx)
  }
}

const isTerminal = computed(() =>
  ['passed', 'failed', 'error', 'cancelled', 'timeout'].includes(props.status),
)

const visible = computed(() => (report.value?.total_heals ?? 0) > 0)

async function load() {
  if (!isTerminal.value) return
  loading.value = true
  errored.value = false
  try {
    report.value = await getRunHealReport(props.runId)
  } catch {
    errored.value = true
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.runId, props.status] as const,
  () => {
    report.value = null
    load()
  },
  { immediate: true },
)

function buildPatch(entry: HealAuditEntry): string {
  // Unified diff compatible with AI-2's "Copy patch" experience.
  // The path is unknown from the audit alone (heals don't carry the
  // source file), so we emit a "file_path=<test_name>" hint that the
  // user rewrites before applying.
  return [
    `--- a/${entry.test_name}.robot`,
    `+++ b/${entry.test_name}.robot`,
    `@@ selector healed at runtime @@`,
    `-    ${entry.keyword}    ${entry.original_selector}`,
    `+    ${entry.keyword}    ${entry.healed_selector}`,
    ``,
  ].join('\n')
}

async function copyPatch(entry: HealAuditEntry) {
  try {
    await navigator.clipboard.writeText(buildPatch(entry))
  } catch {
    /* no-op — patch is visible inline for manual copy */
  }
}

function outcomeIcon(entry: HealAuditEntry): string {
  switch (entry.outcome) {
    case 'confirmed': return '🩹'
    case 'suspect':   return '⚠️'
    case 'skipped':   return '·'
    default:          return '❔'
  }
}
</script>

<template>
  <section
    v-if="visible"
    class="heal-report"
    role="region"
    :aria-label="t('execution.healReport.heading')"
  >
    <header class="heal-report__head">
      <h3 class="heal-report__heading">
        🩹 {{ t('execution.healReport.heading') }}
      </h3>
      <div class="heal-report__counts">
        <span class="heal-report__count heal-report__count--confirmed">
          🩹 {{ report?.confirmed }} {{ t('execution.healReport.confirmed') }}
        </span>
        <span
          v-if="(report?.suspect ?? 0) > 0"
          class="heal-report__count heal-report__count--suspect"
        >
          ⚠️ {{ report?.suspect }} {{ t('execution.healReport.suspect') }}
        </span>
      </div>
    </header>

    <p class="heal-report__hint">
      {{ t('execution.healReport.hint') }}
    </p>

    <div
      v-for="(entry, idx) in report?.entries"
      :key="`${entry.test_name}-${idx}`"
      class="heal-entry"
      :class="{
        'heal-entry--confirmed': entry.outcome === 'confirmed',
        'heal-entry--suspect':   entry.outcome === 'suspect',
        'heal-entry--other':     entry.outcome !== 'confirmed' && entry.outcome !== 'suspect',
      }"
    >
      <div class="heal-entry__head">
        <span class="heal-entry__icon" :title="t(`execution.healReport.outcome.${entry.outcome}`)">
          {{ outcomeIcon(entry) }}
        </span>
        <code class="heal-entry__test">{{ entry.test_name }}</code>
        <span class="heal-entry__keyword">{{ entry.keyword }}</span>
      </div>

      <div class="heal-entry__swap">
        <code class="heal-entry__original">{{ entry.original_selector }}</code>
        <span class="heal-entry__arrow">→</span>
        <code class="heal-entry__healed">{{ entry.healed_selector }}</code>
      </div>

      <div class="heal-entry__meta">
        <span class="heal-entry__source" :data-source="entry.source">
          {{ entry.source }}
        </span>
        <span class="heal-entry__confidence">
          {{ (entry.confidence * 100).toFixed(0) }}%
        </span>
        <!-- RECORDER-IDMAP — show the recorded command id when the
             audit captured one. Lets the user grep the .robot for
             the matching `# rbs:<id>` comment to find the exact
             step the heal applied to. Null for legacy runs. -->
        <code
          v-if="entry.command_id"
          class="heal-entry__cmd-id"
          :title="t('execution.healReport.commandIdTitle')"
          data-testid="heal-command-id"
        >rbs:{{ entry.command_id }}</code>
        <template v-if="entry.outcome === 'confirmed'">
          <span v-if="appliedIndices.has(idx)" class="heal-entry__applied">
            ✅ {{ t('execution.healReport.applied') }}
          </span>
          <template v-else>
            <button
              type="button"
              class="heal-entry__copy"
              @click="copyPatch(entry)"
            >
              {{ t('execution.healReport.copyPatch') }}
            </button>
            <button
              v-if="auth.hasMinRole('editor')"
              type="button"
              class="heal-entry__apply"
              :disabled="applyingIndices.has(idx)"
              @click="applyPatch(idx)"
            >
              {{ applyingIndices.has(idx)
                  ? t('execution.healReport.applying')
                  : t('execution.healReport.applyPatch') }}
            </button>
          </template>
          <span
            v-if="applyErrors.get(idx)"
            class="heal-entry__apply-error"
            role="alert"
          >
            {{ applyErrors.get(idx) }}
          </span>
        </template>
        <span
          v-else-if="entry.outcome === 'suspect'"
          class="heal-entry__suspect-note"
        >
          {{ t('execution.healReport.suspectWarning') }}
        </span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.heal-report {
  margin: 1rem 0;
  padding: 0.85rem 1rem;
  background: #fdf4ff;
  border: 1px solid #d8b4fe;
  border-radius: 6px;
  color: #581c87;
}

.heal-report__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.3rem;
}

.heal-report__heading {
  margin: 0;
  font-size: 0.95rem;
}

.heal-report__counts {
  display: flex;
  gap: 0.6rem;
  font-size: 0.85rem;
}

.heal-report__count--confirmed {
  color: #166534;
  font-weight: 600;
}

.heal-report__count--suspect {
  color: #991b1b;
  font-weight: 600;
}

.heal-report__hint {
  margin: 0 0 0.75rem;
  font-size: 0.8rem;
  color: #6b21a8;
  font-style: italic;
}

.heal-entry {
  padding: 0.55rem 0.7rem;
  margin-bottom: 0.5rem;
  border-left: 3px solid transparent;
  border-radius: 4px;
  background: white;
}
.heal-entry:last-of-type { margin-bottom: 0; }

.heal-entry--confirmed { border-left-color: #16a34a; }
.heal-entry--suspect   { border-left-color: #dc2626; background: #fef2f2; }
.heal-entry--other     { border-left-color: #94a3b8; opacity: 0.8; }

.heal-entry__head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.3rem;
}

.heal-entry__icon { font-size: 1rem; }

.heal-entry__test {
  font-family: var(--font-mono, monospace);
  font-size: 0.8rem;
  color: #334155;
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 3px;
}

.heal-entry__keyword {
  font-size: 0.78rem;
  color: #7e22ce;
  font-weight: 600;
  margin-left: auto;
}

.heal-entry__swap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin-bottom: 0.3rem;
}

.heal-entry__original {
  background: #fee2e2;
  color: #7f1d1d;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: var(--font-mono, monospace);
  font-size: 0.82rem;
  text-decoration: line-through;
}

.heal-entry__healed {
  background: #dcfce7;
  color: #14532d;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: var(--font-mono, monospace);
  font-size: 0.82rem;
}

.heal-entry__arrow {
  color: #94a3b8;
  font-weight: 700;
}

.heal-entry__meta {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
  font-size: 0.75rem;
}

.heal-entry__source {
  text-transform: uppercase;
  font-weight: 700;
  letter-spacing: 0.04em;
  background: #ede9fe;
  color: #5b21b6;
  padding: 2px 6px;
  border-radius: 3px;
}
.heal-entry__source[data-source="sidecar"] {
  background: #bbf7d0; color: #14532d;
}

.heal-entry__confidence {
  color: #581c87;
  font-variant-numeric: tabular-nums;
}

.heal-entry__cmd-id {
  font-family: var(--font-mono, monospace);
  font-size: 0.7rem;
  color: var(--color-text-secondary, #6b7280);
  background: rgba(107, 114, 128, 0.10);
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

.heal-entry__copy {
  margin-left: auto;
  padding: 3px 10px;
  background: white;
  border: 1px solid #a855f7;
  color: #6b21a8;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.78rem;
}
.heal-entry__copy:hover {
  background: #6b21a8;
  color: white;
}

.heal-entry__apply {
  padding: 3px 10px;
  background: #6b21a8;
  border: 1px solid #6b21a8;
  color: white;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 600;
}
.heal-entry__apply:hover:not(:disabled) {
  background: #581c87;
  border-color: #581c87;
}
.heal-entry__apply:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.heal-entry__applied {
  margin-left: auto;
  padding: 3px 10px;
  background: #dcfce7;
  color: #166534;
  border-radius: 3px;
  font-size: 0.78rem;
  font-weight: 700;
}

.heal-entry__apply-error {
  flex-basis: 100%;
  color: #7f1d1d;
  font-size: 0.75rem;
  font-style: italic;
  margin-top: 0.2rem;
}

.heal-entry__suspect-note {
  margin-left: auto;
  color: #991b1b;
  font-style: italic;
}
</style>
