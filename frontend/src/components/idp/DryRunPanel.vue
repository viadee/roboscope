<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import type {
  DryRunCheckRow,
  DryRunProbeResponse,
  DryRunStatus,
} from '@/types/domain.types'

const props = defineProps<{
  result: DryRunProbeResponse | null
  loading: boolean
  stale: boolean
}>()

const { t } = useI18n()

const KNOWN_CHECKS = [
  'issuer_reachable',
  'discovery_valid',
  'jwks_fetched',
] as const

type KnownCheck = (typeof KNOWN_CHECKS)[number]

const verdictKey = computed(() => {
  if (props.loading) return 'running'
  if (props.stale) return 'stale'
  if (!props.result) return 'idle'
  return props.result.overall_status
})

function checkFor(name: KnownCheck): DryRunCheckRow | null {
  const found = props.result?.checks.find((c) => c.check_name === name)
  return found ?? null
}

function statusIcon(status: DryRunStatus | 'running' | null): string {
  switch (status) {
    case 'passed': return '\u2705'
    case 'warning': return '\u26A0\uFE0F'
    case 'failed': return '\u274C'
    case 'running': return '\u23F3'
    default: return '\u2022'
  }
}

function badgeVariantForStatus(status: DryRunStatus | null): 'success' | 'warning' | 'danger' | 'default' {
  if (status === 'passed') return 'success'
  if (status === 'warning') return 'warning'
  if (status === 'failed') return 'danger'
  return 'default'
}

function verdictBadgeVariant(): 'success' | 'warning' | 'danger' | 'default' | 'info' {
  if (props.loading) return 'info'
  if (props.stale) return 'warning'
  if (!props.result) return 'default'
  return props.result.overall_status === 'passed' ? 'success' : 'danger'
}

// Announce progress to screen readers via aria-live
const a11yMessage = computed(() => {
  if (props.loading) return t('dryRunPanel.a11y.started')
  if (!props.result) return ''
  return props.result.overall_status === 'passed'
    ? t('dryRunPanel.a11y.finishedPassed')
    : t('dryRunPanel.a11y.finishedFailed')
})

// Re-emit on state transitions — ensures aria-live announces each change
const showAnnouncement = computed(() => props.loading || !!props.result)

watch(
  () => props.result,
  () => {
    // Vue reactive deps ensure the DOM mutation triggers aria-live.
  },
)
</script>

<template>
  <section class="card dry-run-panel" :class="{ stale, idle: !result && !loading }" data-testid="dry-run-panel">
    <header class="dry-run-header">
      <h3>{{ t('dryRunPanel.title') }}</h3>
      <BaseBadge :variant="verdictBadgeVariant()" role="status">
        {{ t(`dryRunPanel.status.${verdictKey}`) }}
      </BaseBadge>
    </header>

    <div
      v-if="stale"
      class="stale-banner"
      data-testid="dry-run-stale-banner"
    >
      <span class="stale-icon" aria-hidden="true">&#9888;</span>
      <span>{{ t('dryRunPanel.rerunNeeded') }}</span>
    </div>

    <ul v-if="loading || result" class="check-rows">
      <li
        v-for="name in KNOWN_CHECKS"
        :key="name"
        class="check-row"
        :data-testid="`check-row-${name}`"
      >
        <span class="check-icon" aria-hidden="true">
          {{ loading ? statusIcon('running') : statusIcon(checkFor(name)?.status ?? null) }}
        </span>
        <div class="check-body">
          <div class="check-name">{{ t(`dryRunPanel.checks.${name}`) }}</div>
          <div class="check-detail">
            <template v-if="loading">&nbsp;</template>
            <template v-else-if="checkFor(name)">{{ checkFor(name)!.detail }}</template>
            <template v-else>&mdash;</template>
          </div>
        </div>
        <BaseBadge
          v-if="!loading && checkFor(name)"
          :variant="badgeVariantForStatus(checkFor(name)!.status)"
        >
          {{ t(`dryRunPanel.status.${checkFor(name)!.status}`) }}
        </BaseBadge>
      </li>
    </ul>

    <footer v-if="result && !loading" class="dry-run-footer">
      {{ t('dryRunPanel.elapsed', { ms: result.elapsed_ms }) }}
    </footer>

    <div
      v-if="showAnnouncement"
      class="sr-only"
      aria-live="polite"
      role="status"
    >
      {{ a11yMessage }}
    </div>
  </section>
</template>

<style scoped>
.dry-run-panel {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dry-run-panel.stale {
  border: 1px solid var(--color-accent, #D4883E);
}

.dry-run-panel.idle {
  opacity: 0.8;
}

.dry-run-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dry-run-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-navy, #1A2D50);
}

.stale-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(212, 136, 62, 0.08);
  border-left: 3px solid var(--color-accent, #D4883E);
  border-radius: 4px;
  font-size: 13px;
  color: var(--color-text, #1A2D50);
}

.stale-icon {
  color: var(--color-accent, #D4883E);
  font-size: 16px;
}

.check-rows {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.check-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 12px;
  background: var(--color-bg, #F4F7FA);
  border-radius: 6px;
}

.check-icon {
  width: 24px;
  flex-shrink: 0;
  font-size: 18px;
  line-height: 1;
  text-align: center;
}

.check-body {
  flex: 1;
  min-width: 0;
}

.check-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-navy, #1A2D50);
}

.check-detail {
  font-size: 12px;
  color: var(--color-text-muted, #5C688C);
  margin-top: 2px;
  word-break: break-word;
}

.dry-run-footer {
  font-size: 12px;
  color: var(--color-text-muted, #5C688C);
  text-align: right;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
