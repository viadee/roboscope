<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import type { Node, Edge } from '@vue-flow/core'
import { useI18n } from 'vue-i18n'

import KeywordNode from './flow/KeywordNode.vue'
import ControlNode from './flow/ControlNode.vue'
import StartEndNode from './flow/StartEndNode.vue'
import KeywordPalette from './flow/KeywordPalette.vue'
import {
  robotFormToFlow,
  updateStepFromNode,
  type RobotForm,
  type RobotStep,
  type FlowNodeData,
} from './flow/flowConverter'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

const props = defineProps<{
  form: RobotForm
}>()

const emit = defineEmits<{
  (e: 'update:step', data: FlowNodeData): void
}>()

const { t } = useI18n()

const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])

const { fitView } = useVueFlow()

// Selected node for detail panel
const selectedNode = ref<Node | null>(null)

const selectedNodeData = computed<FlowNodeData | null>(() => {
  if (!selectedNode.value) return null
  return selectedNode.value.data as FlowNodeData
})

function buildGraph() {
  const result = robotFormToFlow(props.form)
  nodes.value = result.nodes
  edges.value = result.edges
}

// Rebuild graph when form changes
watch(() => props.form, () => {
  buildGraph()
  setTimeout(() => fitView({ padding: 0.2 }), 100)
}, { deep: true })

onMounted(() => {
  buildGraph()
  setTimeout(() => fitView({ padding: 0.2 }), 200)
})

function onNodeClick(event: { node: Node }) {
  selectedNode.value = event.node
}

function onPaneClick() {
  selectedNode.value = null
}

// Test case tabs
const activeTestCase = ref(0)
const testCaseNames = computed(() =>
  props.form.testCases.map((tc, i) => tc.name || `Test Case ${i + 1}`)
)

// Filter nodes/edges for active test case only
const visibleNodes = computed(() =>
  nodes.value.filter(n => n.id.startsWith(`tc${activeTestCase.value}-`))
)
const visibleEdges = computed(() =>
  edges.value.filter(e => e.id.startsWith(`tc${activeTestCase.value}-`))
)

// --- Add node from palette (click or drag & drop) ---

function addNodeFromPalette(step: RobotStep) {
  const tc = props.form.testCases[activeTestCase.value]
  if (!tc) return
  tc.steps.push(step)
  // Also add END for control structures
  if (['if', 'for', 'while', 'try'].includes(step.type)) {
    tc.steps.push({
      type: 'end', keyword: '', args: [], returnVars: [],
      condition: '', loopVar: '', loopFlavor: '', loopValues: [],
      exceptPattern: '', exceptVar: '', varScope: '', comment: '',
    })
  }
  emit('update:step', { step, testCaseIndex: activeTestCase.value, stepIndex: tc.steps.length - 1 } as FlowNodeData)
  buildGraph()
}

function onCanvasDrop(event: DragEvent) {
  const keyword = event.dataTransfer?.getData('application/rf-keyword')
  const control = event.dataTransfer?.getData('application/rf-control')
  if (keyword) {
    addNodeFromPalette({
      type: 'keyword', keyword, args: [], returnVars: [],
      condition: '', loopVar: '${item}', loopFlavor: 'IN', loopValues: [],
      exceptPattern: '', exceptVar: '', varScope: '', comment: '',
    })
  } else if (control) {
    addNodeFromPalette({
      type: control as any, keyword: '', args: [], returnVars: [],
      condition: control === 'if' || control === 'while' ? '${condition}' : '',
      loopVar: control === 'for' ? '${item}' : '',
      loopFlavor: control === 'for' ? 'IN' : '',
      loopValues: control === 'for' ? ['@{list}'] : [],
      exceptPattern: '', exceptVar: '', varScope: '', comment: '',
    })
  }
}

function onCanvasDragOver(event: DragEvent) {
  event.preventDefault()
  event.dataTransfer!.dropEffect = 'copy'
}
</script>

<template>
  <div class="flow-editor">
    <!-- Test case selector (if multiple) -->
    <div v-if="testCaseNames.length > 1" class="flow-tc-tabs">
      <button
        v-for="(name, i) in testCaseNames"
        :key="i"
        :class="['flow-tc-tab', { active: activeTestCase === i }]"
        @click="activeTestCase = i"
      >
        {{ name }}
      </button>
    </div>

    <!-- Empty state -->
    <div v-if="!props.form.testCases.length" class="flow-empty">
      <p>{{ t('flowEditor.noTestCases') }}</p>
    </div>

    <!-- Vue Flow Canvas + Palette -->
    <div v-else class="flow-canvas-wrapper">
      <KeywordPalette @add-node="addNodeFromPalette" />
      <VueFlow
        @drop="onCanvasDrop"
        @dragover="onCanvasDragOver"
        :nodes="visibleNodes"
        :edges="visibleEdges"
        :default-viewport="{ zoom: 0.9, x: 0, y: 0 }"
        :min-zoom="0.2"
        :max-zoom="2"
        fit-view-on-init
        @node-click="onNodeClick"
        @pane-click="onPaneClick"
      >
        <!-- Custom node types -->
        <template #node-keyword="nodeProps">
          <KeywordNode v-bind="nodeProps" />
        </template>
        <template #node-assignment="nodeProps">
          <KeywordNode v-bind="nodeProps" />
        </template>
        <template #node-control="nodeProps">
          <ControlNode v-bind="nodeProps" />
        </template>
        <template #node-start="nodeProps">
          <StartEndNode v-bind="nodeProps" type="start" />
        </template>
        <template #node-end="nodeProps">
          <StartEndNode v-bind="nodeProps" type="end" />
        </template>
        <template #node-comment="nodeProps">
          <div class="flow-node-comment">
            <span>{{ nodeProps.data.label }}</span>
          </div>
        </template>
        <template #node-flow-control="nodeProps">
          <div class="flow-node-flowctrl">
            <span>{{ nodeProps.data.label }}</span>
          </div>
        </template>

        <Background />
        <Controls />
        <MiniMap />
      </VueFlow>

      <!-- Node detail panel -->
      <div v-if="selectedNodeData" class="flow-detail-panel">
        <h4>{{ selectedNodeData.step.type.toUpperCase().replace('_', ' ') }}</h4>
        <div class="flow-detail-row">
          <label>{{ t('flowEditor.keyword') }}</label>
          <span class="flow-detail-value">{{ selectedNodeData.step.keyword || '—' }}</span>
        </div>
        <div v-if="selectedNodeData.step.args.length" class="flow-detail-row">
          <label>{{ t('flowEditor.arguments') }}</label>
          <div class="flow-detail-args">
            <code v-for="(arg, i) in selectedNodeData.step.args" :key="i">{{ arg }}</code>
          </div>
        </div>
        <div v-if="selectedNodeData.step.condition" class="flow-detail-row">
          <label>{{ t('flowEditor.condition') }}</label>
          <code>{{ selectedNodeData.step.condition }}</code>
        </div>
        <div v-if="selectedNodeData.step.returnVars.length" class="flow-detail-row">
          <label>{{ t('flowEditor.returnVars') }}</label>
          <code>{{ selectedNodeData.step.returnVars.join(', ') }}</code>
        </div>
        <div v-if="selectedNodeData.step.comment" class="flow-detail-row">
          <label>{{ t('flowEditor.comment') }}</label>
          <span class="flow-detail-value">{{ selectedNodeData.step.comment }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.flow-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 500px;
}

.flow-tc-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border, #e2e8f0);
  background: var(--color-bg, #F4F7FA);
  overflow-x: auto;
}

.flow-tc-tab {
  padding: 4px 12px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 6px;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.flow-tc-tab.active {
  background: var(--color-primary, #3B7DD8);
  color: #fff;
  border-color: var(--color-primary, #3B7DD8);
}

.flow-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: var(--color-text-muted, #5A6380);
}

.flow-canvas-wrapper {
  flex: 1;
  position: relative;
  display: flex;
}

/* Detail panel */
.flow-detail-panel {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 280px;
  background: #fff;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 10;
  max-height: 400px;
  overflow-y: auto;
}
.flow-detail-panel h4 {
  margin: 0 0 12px 0;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-primary, #3B7DD8);
}
.flow-detail-row {
  margin-bottom: 8px;
}
.flow-detail-row label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--color-text-muted, #5A6380);
  margin-bottom: 2px;
}
.flow-detail-value {
  font-size: 13px;
}
.flow-detail-args {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.flow-detail-args code {
  background: var(--color-bg, #F4F7FA);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}
.flow-detail-row code {
  font-size: 12px;
  word-break: break-all;
}

/* Comment node inline style */
.flow-node-comment {
  padding: 6px 12px;
  border-radius: 6px;
  background: #f0f0f0;
  border: 1px dashed #ccc;
  font-size: 12px;
  color: #888;
  font-style: italic;
  max-width: 280px;
}
.flow-node-flowctrl {
  padding: 6px 12px;
  border-radius: 6px;
  background: #FFF5F5;
  border: 2px solid #E53E3E;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
</style>
