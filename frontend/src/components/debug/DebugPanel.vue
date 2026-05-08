<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDebugStore } from '@/stores/debug.store'
import { extractErrorDetail } from '@/utils/errors'
import BaseButton from '@/components/ui/BaseButton.vue'

const props = defineProps<{
  /** Optional explicit run-id; when present the panel will start
   *  the session itself if the store doesn't already have one for
   *  this run. Without it the panel just renders the store. */
  runId?: number
}>()

const emit = defineEmits<{
  closed: []
}>()

const { t } = useI18n()
const debug = useDebugStore()

const error = ref<string | null>(null)

onMounted(async () => {
  if (props.runId !== undefined && !debug.isActive) {
    try {
      await debug.startFromRun(props.runId)
    } catch (e: unknown) {
      error.value = extractErrorDetail(e, t('debug.error.startFailed'))
    }
  }
})

onUnmounted(() => {
  // We deliberately do NOT call debug.stop() on unmount: closing the
  // panel without explicitly stopping is a "minimize" gesture, the
  // session keeps running. The Stop button is the explicit teardown.
})

const headerLabel = computed(() => {
  const at = debug.pausedAt
  if (!at.file && !at.keyword) return t('debug.panel.notPaused')
  const fileLine = at.line !== null ? `${at.file ?? ''}:${at.line}` : at.file ?? ''
  return at.keyword ? `${at.keyword}  —  ${fileLine}` : fileLine
})

async function onContinue() { await runCommand(() => debug.control('continue')) }
async function onNext()     { await runCommand(() => debug.control('next')) }
async function onStepIn()   { await runCommand(() => debug.control('stepIn')) }
async function onStepOut()  { await runCommand(() => debug.control('stepOut')) }
async function onStop() {
  try {
    await debug.stop()
  } finally {
    emit('closed')
  }
}

async function runCommand(fn: () => Promise<void>): Promise<void> {
  error.value = null
  try {
    await fn()
  } catch (e: unknown) {
    error.value = extractErrorDetail(e, t('debug.error.commandFailed'))
  }
}

const expandedScopes = ref<Set<string>>(new Set(['Local']))
function toggleScope(name: string): void {
  if (expandedScopes.value.has(name)) expandedScopes.value.delete(name)
  else expandedScopes.value.add(name)
  // Re-trigger reactivity on Set mutation.
  expandedScopes.value = new Set(expandedScopes.value)
}

function truncate(s: string, max = 200): string {
  if (s.length <= max) return s
  return s.slice(0, max) + '…'
}
</script>

<template>
  <div class="debug-panel" data-testid="debug-panel">
    <header class="debug-panel__header">
      <div class="debug-panel__title">
        <span class="debug-panel__icon" aria-hidden="true">🐞</span>
        <span class="debug-panel__paused-at">{{ headerLabel }}</span>
        <span v-if="debug.state.terminated" class="debug-panel__badge debug-panel__badge--terminated">
          {{ t('debug.panel.terminated') }}
        </span>
        <span v-else-if="debug.paused" class="debug-panel__badge debug-panel__badge--paused">
          {{ t('debug.panel.paused') }}
        </span>
      </div>
      <div class="debug-panel__toolbar">
        <BaseButton
          size="sm" variant="primary"
          :disabled="!debug.paused || debug.state.terminated"
          @click="onContinue"
        >▶ {{ t('debug.panel.toolbar.continue') }}</BaseButton>
        <BaseButton
          size="sm" variant="ghost"
          :disabled="!debug.paused || debug.state.terminated"
          @click="onNext"
        >⤼ {{ t('debug.panel.toolbar.stepOver') }}</BaseButton>
        <BaseButton
          size="sm" variant="ghost"
          :disabled="!debug.paused || debug.state.terminated"
          @click="onStepIn"
        >↳ {{ t('debug.panel.toolbar.stepIn') }}</BaseButton>
        <BaseButton
          size="sm" variant="ghost"
          :disabled="!debug.paused || debug.state.terminated"
          @click="onStepOut"
        >↰ {{ t('debug.panel.toolbar.stepOut') }}</BaseButton>
        <BaseButton size="sm" variant="danger" @click="onStop">
          ✕ {{ t('debug.panel.toolbar.stop') }}
        </BaseButton>
      </div>
    </header>

    <div v-if="error" class="debug-panel__error">{{ error }}</div>

    <div class="debug-panel__body">
      <aside class="debug-panel__stack">
        <h3>{{ t('debug.panel.callStack') }}</h3>
        <ul v-if="debug.callStack.length" class="debug-panel__stack-list">
          <li
            v-for="(frame, idx) in debug.callStack"
            :key="idx"
            :class="{ 'debug-panel__stack-item': true, 'is-top': idx === 0 }"
          >
            <span class="debug-panel__stack-name">{{ frame.name }}</span>
            <span v-if="frame.file" class="debug-panel__stack-file">
              {{ frame.file }}<span v-if="frame.line">:{{ frame.line }}</span>
            </span>
          </li>
        </ul>
        <p v-else class="debug-panel__empty">{{ t('debug.panel.callStackEmpty') }}</p>
      </aside>

      <section class="debug-panel__scopes">
        <h3>{{ t('debug.panel.scopes') }}</h3>
        <div v-if="!debug.scopes.length" class="debug-panel__empty">
          {{ t('debug.panel.scopesEmpty') }}
        </div>
        <div
          v-for="scope in debug.scopes"
          :key="scope.name"
          class="debug-panel__scope"
        >
          <button
            class="debug-panel__scope-header"
            :aria-expanded="expandedScopes.has(scope.name)"
            @click="toggleScope(scope.name)"
          >
            <span class="debug-panel__scope-chevron">
              {{ expandedScopes.has(scope.name) ? '▾' : '▸' }}
            </span>
            <span class="debug-panel__scope-name">{{ scope.name }}</span>
            <span class="debug-panel__scope-count">{{ scope.variables.length }}</span>
          </button>
          <div v-if="expandedScopes.has(scope.name)" class="debug-panel__scope-vars">
            <div v-if="!scope.variables.length" class="debug-panel__empty">
              {{ t('debug.panel.scopeEmpty') }}
            </div>
            <div
              v-for="v in scope.variables"
              :key="v.name"
              class="debug-panel__var"
            >
              <span class="debug-panel__var-name">{{ v.name }}</span>
              <span v-if="v.type" class="debug-panel__var-type">({{ v.type }})</span>
              <span class="debug-panel__var-value">{{ truncate(v.value) }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <footer class="debug-panel__output">
      <h3>{{ t('debug.panel.output') }}</h3>
      <div v-if="debug.outputLog.length === 0" class="debug-panel__empty">
        {{ t('debug.panel.outputEmpty') }}
      </div>
      <pre v-else class="debug-panel__output-log">{{ debug.outputLog.join('\n') }}</pre>
    </footer>
  </div>
</template>

<style scoped>
.debug-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  background: var(--color-bg-secondary, #f7f9fc);
  border: 1px solid var(--color-border, #d6dfeb);
  border-radius: 8px;
  font-size: 13px;
}
.debug-panel__header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.debug-panel__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.debug-panel__paused-at {
  font-family: var(--font-mono, ui-monospace, "Cascadia Code", monospace);
  font-size: 12px;
  color: var(--color-text-secondary, #4a5b75);
}
.debug-panel__badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.debug-panel__badge--paused {
  background: var(--color-warning-bg, #fef3c7);
  color: var(--color-warning, #92400e);
}
.debug-panel__badge--terminated {
  background: var(--color-bg-tertiary, #e5e7eb);
  color: var(--color-text-secondary, #4a5b75);
}
.debug-panel__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.debug-panel__error {
  padding: 8px 10px;
  background: var(--color-error-bg, #fee2e2);
  color: var(--color-error, #991b1b);
  border-radius: 6px;
}
.debug-panel__body {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 12px;
}
.debug-panel__stack h3,
.debug-panel__scopes h3,
.debug-panel__output h3 {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-tertiary, #6b7280);
  margin: 0 0 6px 0;
}
.debug-panel__stack-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.debug-panel__stack-item {
  padding: 4px 8px;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
}
.debug-panel__stack-item.is-top {
  background: var(--color-primary-bg, #dbeafe);
}
.debug-panel__stack-name {
  font-weight: 500;
}
.debug-panel__stack-file {
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 11px;
  color: var(--color-text-tertiary, #6b7280);
}
.debug-panel__scope {
  border: 1px solid var(--color-border, #d6dfeb);
  border-radius: 6px;
  margin-bottom: 6px;
  overflow: hidden;
}
.debug-panel__scope-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--color-bg, #ffffff);
  border: none;
  cursor: pointer;
  text-align: left;
  font-weight: 600;
}
.debug-panel__scope-name { flex: 1; }
.debug-panel__scope-count {
  background: var(--color-bg-tertiary, #e5e7eb);
  border-radius: 999px;
  padding: 0 6px;
  font-size: 11px;
}
.debug-panel__scope-vars {
  padding: 6px 10px;
  background: var(--color-bg-secondary, #f7f9fc);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.debug-panel__var {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 2px 0;
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 12px;
}
.debug-panel__var-name { font-weight: 600; color: var(--color-text-primary, #111827); }
.debug-panel__var-type { color: var(--color-text-tertiary, #6b7280); }
.debug-panel__var-value { color: var(--color-text-secondary, #4a5b75); word-break: break-all; }
.debug-panel__empty {
  font-size: 12px;
  color: var(--color-text-tertiary, #6b7280);
  font-style: italic;
}
.debug-panel__output-log {
  max-height: 200px;
  overflow-y: auto;
  background: var(--color-bg-tertiary, #1a2d50);
  color: var(--color-on-dark, #f5f7fa);
  padding: 8px;
  border-radius: 4px;
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
