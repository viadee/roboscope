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

const colorMap: Record<string, string> = {
  if: '#E8A838',
  else_if: '#E8A838',
  else: '#E8A838',
  for: '#7B61FF',
  while: '#7B61FF',
  try: '#38B2AC',
  except: '#E53E3E',
  finally: '#38B2AC',
}

const iconMap: Record<string, string> = {
  if: '&#x2753;',      // ?
  else_if: '&#x2753;',
  else: '&#x2194;',    // ↔
  for: '&#x1F503;',    // 🔃
  while: '&#x1F503;',
  try: '&#x1F6E1;',    // 🛡
  except: '&#x26A0;',  // ⚠
  finally: '&#x2705;', // ✅
}
</script>

<template>
  <div
    class="flow-node flow-node-control"
    :style="{ borderColor: colorMap[data.stepType] || '#888' }"
  >
    <Handle type="target" :position="Position.Top" />
    <div class="flow-node-header">
      <div
        v-if="reorderEnabled"
        class="flow-drag-handle"
        draggable="true"
        @mousedown.stop
        @dragstart.stop="onHandleDragStart"
      >&#x2630;</div>
      <span class="flow-node-icon" v-html="iconMap[data.stepType] || '&#x25C6;'"></span>
      <span class="flow-node-type">{{ data.stepType.toUpperCase().replace('_', ' ') }}</span>
    </div>
    <div v-if="data.step.condition" class="flow-node-condition">
      {{ data.step.condition }}
    </div>
    <div v-if="data.stepType === 'for' || data.stepType === 'while'" class="flow-node-condition">
      {{ data.step.loopVar }} {{ data.step.loopFlavor }} {{ data.step.loopValues.join('  ') }}
    </div>
    <div v-if="data.step.exceptPattern" class="flow-node-condition">
      {{ data.step.exceptPattern }}
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
.flow-node-control {
  background: #FFFBF0;
  border: 2px solid #E8A838;
  border-style: dashed;
}
.flow-node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.flow-node-icon {
  font-size: 14px;
}
.flow-node-condition {
  margin-top: 4px;
  font-size: 12px;
  font-family: monospace;
  color: var(--color-text-muted, #5A6380);
  word-break: break-all;
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
</style>
