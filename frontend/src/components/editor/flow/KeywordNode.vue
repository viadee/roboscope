<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import type { FlowNodeData } from './flowConverter'

const props = defineProps<{
  data: FlowNodeData
  reorderEnabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'reorder-drag-start', event: DragEvent): void
}>()

function onHandleDragStart(event: DragEvent) {
  emit('reorder-drag-start', event)
}
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
      <span v-for="(arg, i) in data.step.args" :key="i" class="flow-arg">{{ arg }}</span>
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
}
.flow-node-return {
  margin-top: 4px;
  font-size: 11px;
  color: var(--color-accent, #D4883E);
  font-style: italic;
}
</style>
