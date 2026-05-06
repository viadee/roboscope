<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps<{
  // `data.label` is kept for backwards-compatibility with the
  // converter's old shape (it used to pass the test-case name as
  // the start label, which left the node visually empty for
  // unnamed test cases). Today the labels come from i18n —
  // "Start" / "End" — independent of the test case name (the
  // section tab strip already shows that). A non-empty label
  // here overrides the i18n default so a future caller can pin
  // a custom label without re-jiggering this component.
  data?: { label?: string }
  type: string
}>()

const { t } = useI18n()

const displayLabel = computed(() => {
  if (props.data?.label && props.data.label.trim()) return props.data.label
  return props.type === 'start'
    ? t('flowEditor.startNodeLabel')
    : t('flowEditor.endNodeLabel')
})
</script>

<template>
  <div :class="['flow-node-terminal', type === 'start' ? 'flow-node-start' : 'flow-node-end']">
    <Handle v-if="type === 'end'" type="target" :position="Position.Top" />
    <!-- Left handle on the Start node — target for the dashed edge
         coming from the [Documentation] side note (sits to the left
         of Start, edges in from its right). Hidden visually because
         we don't want a connection dot showing on every render. -->
    <Handle
      v-if="type === 'start'"
      type="target"
      :position="Position.Left"
      id="left"
      style="opacity: 0; pointer-events: none;"
    />
    <span class="flow-terminal-label">{{ displayLabel }}</span>
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
