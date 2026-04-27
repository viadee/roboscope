<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Handle, Position } from '@vue-flow/core'
import { activeSelector } from '@/types/recorder.types'
import { qualityBand } from '@/utils/selectorQuality'
import type { FlowNodeData } from './flowConverter'

const props = defineProps<{
  data: FlowNodeData
  reorderEnabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'reorder-drag-start', event: DragEvent): void
}>()

const { t } = useI18n()

function onHandleDragStart(event: DragEvent) {
  emit('reorder-drag-start', event)
}

// Story EDITOR-1 — selector-candidate badge for the first arg chip.
const candidateCount = computed(() => props.data.recording?.selector_candidates.length ?? 0)
const showCandidateBadge = computed(() => candidateCount.value > 0)
const candidateBand = computed(() => {
  const a = props.data.recording ? activeSelector(props.data.recording) : null
  return qualityBand(a?.quality_score ?? 0)
})
const candidateTooltip = computed(() =>
  t('flowEditor.selector.tooltipHasCandidates', { count: candidateCount.value }),
)
</script>

<template>
  <div class="flow-node flow-node-keyword">
    <Handle type="target" :position="Position.Top" />
    <div class="flow-node-header">
      <div
        v-if="reorderEnabled"
        class="flow-drag-handle"
        draggable="true"
        @mousedown.stop
        @dragstart.stop="onHandleDragStart"
      >&#x2630;</div>
      <span class="flow-node-icon">&#x2699;</span>
      <span class="flow-node-label">{{ data.step.keyword || 'Keyword' }}</span>
    </div>
    <div v-if="data.step.args.length" class="flow-node-args">
      <span
        v-for="(arg, i) in data.step.args"
        :key="i"
        class="flow-arg"
        :class="{ 'flow-arg--has-candidates': i === 0 && showCandidateBadge }"
      >
        <span
          v-if="i === 0 && showCandidateBadge"
          :class="['flow-arg-dot', `flow-arg-dot--${candidateBand}`]"
          :title="candidateTooltip"
          aria-hidden="true"
        />
        <span class="flow-arg-value">{{ arg }}</span>
        <span
          v-if="i === 0 && showCandidateBadge"
          class="flow-arg-count"
          :title="candidateTooltip"
          data-testid="selector-candidate-count"
        >{{ t('flowEditor.selector.candidatesBadge', { count: candidateCount }) }}</span>
      </span>
    </div>
    <div v-if="data.step.returnVars.length" class="flow-node-return">
      {{ data.step.returnVars.join(', ') }} =
    </div>
    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<style scoped>
.flow-node {
  padding: 8px 12px;
  border-radius: 8px;
  min-width: 180px;
  max-width: 320px;
  font-size: 13px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}
.flow-node-keyword {
  background: #fff;
  border: 2px solid var(--color-primary, #3B7DD8);
}
.flow-node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}
.flow-node-icon {
  font-size: 14px;
  opacity: 0.6;
}
.flow-node-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.flow-drag-handle {
  cursor: grab;
  color: var(--color-text-muted, #5A6380);
  font-size: 12px;
  line-height: 1;
  opacity: 0.4;
  padding: 2px;
  border-radius: 3px;
  user-select: none;
  flex-shrink: 0;
}
.flow-drag-handle:hover {
  opacity: 1;
  background: rgba(0, 0, 0, 0.06);
}
.flow-drag-handle:active {
  cursor: grabbing;
}
.flow-node-args {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.flow-arg {
  background: var(--color-bg, #F4F7FA);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: var(--color-text-muted, #5A6380);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.flow-arg--has-candidates {
  background: rgba(59, 125, 216, 0.10);
  border: 1px solid rgba(59, 125, 216, 0.30);
  padding: 0 6px;
}
.flow-arg-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.flow-arg-dot--good { background: #2c9846; }
.flow-arg-dot--ok   { background: #d4883e; }
.flow-arg-dot--poor { background: #c0392b; }
.flow-arg-value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}
.flow-arg-count {
  font-size: 10px;
  color: var(--color-primary, #3B7DD8);
  font-weight: 600;
}
.flow-node-return {
  margin-top: 4px;
  font-size: 11px;
  color: var(--color-accent, #D4883E);
  font-style: italic;
}
</style>
