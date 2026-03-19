<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'

const props = defineProps<{
  data: { label: string }
  type: string
}>()
</script>

<template>
  <div :class="['flow-node-terminal', type === 'start' ? 'flow-node-start' : 'flow-node-end']">
    <Handle v-if="type === 'end'" type="target" :position="Position.Top" />
    <span class="flow-terminal-label">{{ data.label }}</span>
    <Handle v-if="type === 'start'" type="source" :position="Position.Bottom" />
  </div>
</template>

<style scoped>
.flow-node-terminal {
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  text-align: center;
  min-width: 100px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
.flow-node-start {
  background: var(--color-navy, #1A2D50);
  color: #fff;
  border: 2px solid var(--color-navy-dark, #0F1A30);
}
.flow-node-end {
  background: var(--color-text-muted, #5A6380);
  color: #fff;
  border: 2px solid #444;
}
.flow-terminal-label {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}
</style>
