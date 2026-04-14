<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRecorderStore } from '@/stores/recorder.store'
import BaseButton from '@/components/ui/BaseButton.vue'

const { t } = useI18n()
const recorder = useRecorderStore()

const eventsContainer = ref<HTMLElement | null>(null)

// Auto-scroll events list when new events arrive
watch(
  () => recorder.liveEvents.length,
  async () => {
    await nextTick()
    if (eventsContainer.value) {
      eventsContainer.value.scrollTop = eventsContainer.value.scrollHeight
    }
  },
)

function formatEvent(event: any): string {
  const type = event.event_type || 'unknown'
  const selector = event.selector || ''
  const value = event.value || ''
  const url = event.url || ''

  switch (type) {
    case 'navigate':
      return `Navigate  ${url}`
    case 'click':
      return `Click  ${selector}`
    case 'input':
      return `Fill Text  ${selector}  ${value}`
    case 'password':
      return `Fill Secret  ${selector}  ***`
    case 'select':
      return `Select  ${selector}  ${value}`
    case 'checkbox':
      return `Check  ${selector}`
    default:
      return `${type}  ${selector}  ${value}`.trim()
  }
}

function eventIcon(type: string): string {
  switch (type) {
    case 'navigate': return '>'
    case 'click': return '#'
    case 'input': return 'T'
    case 'password': return '*'
    case 'select': return 'v'
    case 'checkbox': return 'x'
    default: return '-'
  }
}

async function handleStop() {
  await recorder.stopSession(true)
}

async function handleCancel() {
  await recorder.cancelSession()
}

function handleClose() {
  recorder.closePanel()
}

function handleReset() {
  recorder.reset()
}
</script>

<template>
  <div v-if="recorder.panelOpen" class="recorder-panel">
    <div class="recorder-header">
      <div class="recorder-title">
        <span
          class="recorder-status-dot"
          :class="recorder.activeSession?.status"
        ></span>
        <strong>{{ t('recorder.title') }}</strong>
      </div>
      <button class="recorder-close" @click="handleClose">&times;</button>
    </div>

    <!-- Recording controls -->
    <div class="recorder-controls">
      <template v-if="recorder.isRecording">
        <BaseButton size="sm" variant="danger" @click="handleStop" :disabled="recorder.loading">
          {{ t('recorder.stop') }}
        </BaseButton>
        <BaseButton size="sm" variant="secondary" @click="handleCancel" :disabled="recorder.loading">
          {{ t('common.cancel') }}
        </BaseButton>
        <span class="event-count">{{ recorder.liveEvents.length }} {{ t('recorder.events') }}</span>
      </template>

      <template v-else-if="recorder.isProcessing">
        <span class="processing-label">{{ t('recorder.generating') }}</span>
      </template>

      <template v-else-if="recorder.isCompleted">
        <BaseButton size="sm" @click="handleReset">
          {{ t('recorder.newRecording') }}
        </BaseButton>
      </template>

      <template v-else-if="recorder.activeSession?.status === 'failed'">
        <span class="error-label">{{ recorder.activeSession?.error_message || t('recorder.failedMsg') }}</span>
        <BaseButton size="sm" @click="handleReset">
          {{ t('recorder.tryAgain') }}
        </BaseButton>
      </template>

      <template v-else-if="recorder.activeSession?.status === 'cancelled'">
        <span class="cancelled-label">{{ t('recorder.cancelled') }}</span>
        <BaseButton size="sm" @click="handleReset">
          {{ t('recorder.newRecording') }}
        </BaseButton>
      </template>
    </div>

    <!-- Live events stream -->
    <div
      v-if="recorder.liveEvents.length > 0"
      ref="eventsContainer"
      class="recorder-events"
    >
      <div
        v-for="(event, index) in recorder.liveEvents"
        :key="index"
        class="event-line"
      >
        <span class="event-index">{{ index + 1 }}</span>
        <span class="event-icon" :class="event.event_type">{{ eventIcon(event.event_type) }}</span>
        <span class="event-text">{{ formatEvent(event) }}</span>
      </div>
    </div>
    <div v-else-if="recorder.isRecording" class="recorder-empty">
      {{ t('recorder.waitingForEvents') }}
    </div>

    <!-- Generated .robot preview -->
    <div v-if="recorder.generatedRobot" class="recorder-output">
      <div class="output-header">
        <strong>{{ t('recorder.generatedFile') }}</strong>
      </div>
      <pre class="output-code"><code>{{ recorder.generatedRobot }}</code></pre>
    </div>
  </div>
</template>

<style scoped>
.recorder-panel {
  border-top: 2px solid var(--color-primary, #3B7DD8);
  background: var(--color-bg-card, #fff);
  display: flex;
  flex-direction: column;
  max-height: 400px;
  overflow: hidden;
}

.recorder-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
  background: var(--color-bg, #f4f7fa);
}

.recorder-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.recorder-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #9ca3af;
}
.recorder-status-dot.recording {
  background: #ef4444;
  animation: pulse 1.5s infinite;
}
.recorder-status-dot.processing {
  background: #f59e0b;
  animation: pulse 1s infinite;
}
.recorder-status-dot.completed {
  background: #22c55e;
}
.recorder-status-dot.failed {
  background: #ef4444;
}
.recorder-status-dot.cancelled {
  background: #9ca3af;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.recorder-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: var(--color-text-muted, #5a6380);
  padding: 0 4px;
  line-height: 1;
}
.recorder-close:hover {
  color: var(--color-text, #1a1d2e);
}

.recorder-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
}

.event-count {
  font-size: 12px;
  color: var(--color-text-muted, #5a6380);
  margin-left: auto;
}

.processing-label {
  font-size: 12px;
  color: #f59e0b;
  font-weight: 500;
}

.error-label {
  font-size: 12px;
  color: #ef4444;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cancelled-label {
  font-size: 12px;
  color: var(--color-text-muted, #5a6380);
}

.recorder-events {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  min-height: 80px;
  max-height: 200px;
}

.event-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 2px 12px;
  line-height: 1.6;
}
.event-line:hover {
  background: var(--color-bg, #f4f7fa);
}

.event-index {
  color: var(--color-text-muted, #9ca3af);
  width: 24px;
  text-align: right;
  flex-shrink: 0;
  font-size: 11px;
}

.event-icon {
  width: 16px;
  text-align: center;
  flex-shrink: 0;
  font-weight: 600;
  font-size: 11px;
  color: var(--color-primary, #3B7DD8);
}
.event-icon.navigate { color: #7c3aed; }
.event-icon.click { color: #3B7DD8; }
.event-icon.input { color: #059669; }
.event-icon.password { color: #d97706; }
.event-icon.select { color: #0891b2; }

.event-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text, #1a1d2e);
}

.recorder-empty {
  padding: 24px 12px;
  text-align: center;
  color: var(--color-text-muted, #9ca3af);
  font-size: 13px;
  font-style: italic;
}

.recorder-output {
  border-top: 1px solid var(--color-border, #e5e7eb);
  max-height: 200px;
  overflow-y: auto;
}

.output-header {
  padding: 6px 12px;
  font-size: 12px;
  background: var(--color-bg, #f4f7fa);
  border-bottom: 1px solid var(--color-border, #e5e7eb);
}

.output-code {
  margin: 0;
  padding: 8px 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
  line-height: 1.5;
  background: #1e1e2e;
  color: #cdd6f4;
  overflow-x: auto;
  white-space: pre;
}
</style>
