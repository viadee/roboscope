<script setup lang="ts">
import { ref, watch, onMounted, computed, nextTick } from 'vue'
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
  robotKeywordsToFlow,
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
  repoId?: number
}>()

const emit = defineEmits<{
  (e: 'update:step', data: FlowNodeData): void
}>()

const { t } = useI18n()

const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])

const { fitView } = useVueFlow()

// --- Section tabs: Test Cases vs Keywords ---
const activeSection = ref<'testcases' | 'keywords'>('testcases')

// Active item within section
const activeItemIndex = ref(0)

const testCaseNames = computed(() =>
  props.form.testCases.map((tc, i) => tc.name || `Test Case ${i + 1}`)
)
const keywordNames = computed(() =>
  props.form.keywords.map((kw, i) => kw.name || `Keyword ${i + 1}`)
)

const hasTestCases = computed(() => props.form.testCases.length > 0)
const hasKeywords = computed(() => props.form.keywords.length > 0)
const hasContent = computed(() => hasTestCases.value || hasKeywords.value)

// Selected node for editable detail panel
const selectedNode = ref<Node | null>(null)
const selectedNodeData = computed<FlowNodeData | null>(() => {
  if (!selectedNode.value) return null
  return selectedNode.value.data as FlowNodeData
})

function buildGraph() {
  if (activeSection.value === 'testcases') {
    const result = robotFormToFlow(props.form)
    nodes.value = result.nodes
    edges.value = result.edges
  } else {
    const result = robotKeywordsToFlow(props.form)
    nodes.value = result.nodes
    edges.value = result.edges
  }
}

// Filter nodes/edges for active item only
const visibleNodes = computed(() => {
  const prefix = activeSection.value === 'testcases'
    ? `tc${activeItemIndex.value}-`
    : `kw${activeItemIndex.value}-`
  return nodes.value.filter(n => n.id.startsWith(prefix))
})
const visibleEdges = computed(() => {
  const prefix = activeSection.value === 'testcases'
    ? `tc${activeItemIndex.value}-`
    : `kw${activeItemIndex.value}-`
  return edges.value.filter(e => e.id.startsWith(prefix))
})

// Flag to suppress fitView during inline edits/reorder
let suppressFitView = false

// Rebuild graph when form or section changes
watch([() => props.form, activeSection], () => {
  if (suppressFitView) {
    suppressFitView = false
    return
  }
  activeItemIndex.value = 0
  selectedNode.value = null
  buildGraph()
  nextTick(() => fitView({ padding: 0.2 }))
}, { deep: true })

watch(activeItemIndex, () => {
  selectedNode.value = null
  nextTick(() => fitView({ padding: 0.2 }))
})

onMounted(() => {
  // Default to keywords section if no test cases
  if (!hasTestCases.value && hasKeywords.value) {
    activeSection.value = 'keywords'
  }
  buildGraph()
  setTimeout(() => fitView({ padding: 0.2 }), 200)
})

function onNodeClick(event: { node: Node }) {
  selectedNode.value = event.node
}
function onPaneClick() {
  selectedNode.value = null
}

// --- Editable step fields ---

function rebuildAndReselect() {
  const selectedId = selectedNode.value?.id
  suppressFitView = true
  buildGraph()
  if (selectedId) {
    nextTick(() => {
      const reselected = nodes.value.find(n => n.id === selectedId)
      selectedNode.value = reselected || null
    })
  }
}

function onStepFieldChange() {
  if (!selectedNodeData.value) return
  updateStepFromNode(props.form, selectedNodeData.value)
  rebuildAndReselect()
  emit('update:step', selectedNodeData.value)
}

function addArg() {
  if (!selectedNodeData.value) return
  selectedNodeData.value.step.args.push('')
  updateStepFromNode(props.form, selectedNodeData.value)
  rebuildAndReselect()
}
function removeArg(index: number) {
  if (!selectedNodeData.value) return
  selectedNodeData.value.step.args.splice(index, 1)
  updateStepFromNode(props.form, selectedNodeData.value)
  rebuildAndReselect()
}
function addReturnVar() {
  if (!selectedNodeData.value) return
  selectedNodeData.value.step.returnVars.push('${var}')
  updateStepFromNode(props.form, selectedNodeData.value)
  rebuildAndReselect()
}
function removeReturnVar(index: number) {
  if (!selectedNodeData.value) return
  selectedNodeData.value.step.returnVars.splice(index, 1)
  updateStepFromNode(props.form, selectedNodeData.value)
  rebuildAndReselect()
}
function addLoopValue() {
  if (!selectedNodeData.value) return
  selectedNodeData.value.step.loopValues.push('')
  updateStepFromNode(props.form, selectedNodeData.value)
  rebuildAndReselect()
}
function removeLoopValue(index: number) {
  if (!selectedNodeData.value) return
  selectedNodeData.value.step.loopValues.splice(index, 1)
  updateStepFromNode(props.form, selectedNodeData.value)
  rebuildAndReselect()
}

// --- Add node from palette ---

function addNodeFromPalette(step: RobotStep) {
  const list = activeSection.value === 'testcases'
    ? props.form.testCases[activeItemIndex.value]?.steps
    : props.form.keywords[activeItemIndex.value]?.steps
  if (!list) return
  list.push(step)
  if (['if', 'for', 'while', 'try'].includes(step.type)) {
    list.push({
      type: 'end', keyword: '', args: [], returnVars: [],
      condition: '', loopVar: '', loopFlavor: '', loopValues: [],
      exceptPattern: '', exceptVar: '', varScope: '', comment: '',
    })
  }
  buildGraph()
}

// --- Move step up/down ---

function getActiveSteps(): RobotStep[] | null {
  return activeSection.value === 'testcases'
    ? props.form.testCases[activeItemIndex.value]?.steps ?? null
    : props.form.keywords[activeItemIndex.value]?.steps ?? null
}

function moveStepUp() {
  if (!selectedNodeData.value) return
  const steps = getActiveSteps()
  if (!steps) return
  const idx = selectedNodeData.value.stepIndex
  if (idx <= 0) return
  const temp = steps[idx]
  steps[idx] = steps[idx - 1]
  steps[idx - 1] = temp
  selectedNodeData.value.stepIndex = idx - 1
  rebuildAndReselect()
  emit('update:step', selectedNodeData.value)
}

function moveStepDown() {
  if (!selectedNodeData.value) return
  const steps = getActiveSteps()
  if (!steps) return
  const idx = selectedNodeData.value.stepIndex
  if (idx >= steps.length - 1) return
  const temp = steps[idx]
  steps[idx] = steps[idx + 1]
  steps[idx + 1] = temp
  selectedNodeData.value.stepIndex = idx + 1
  rebuildAndReselect()
  emit('update:step', selectedNodeData.value)
}

function deleteStep() {
  if (!selectedNodeData.value) return
  const steps = getActiveSteps()
  if (!steps) return
  steps.splice(selectedNodeData.value.stepIndex, 1)
  selectedNode.value = null
  suppressFitView = true
  buildGraph()
}

function insertStepBefore(step: RobotStep) {
  if (!selectedNodeData.value) return
  const steps = getActiveSteps()
  if (!steps) return
  const idx = selectedNodeData.value.stepIndex
  steps.splice(idx, 0, step)
  if (['if', 'for', 'while', 'try'].includes(step.type)) {
    steps.splice(idx + 1, 0, {
      type: 'end', keyword: '', args: [], returnVars: [],
      condition: '', loopVar: '', loopFlavor: '', loopValues: [],
      exceptPattern: '', exceptVar: '', varScope: '', comment: '',
    })
  }
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
    <!-- Section tabs: Test Cases | Keywords -->
    <div class="flow-section-bar">
      <div class="flow-section-tabs">
        <button
          v-if="hasTestCases"
          :class="['flow-section-tab', { active: activeSection === 'testcases' }]"
          @click="activeSection = 'testcases'"
        >
          {{ t('robotEditor.testCasesSection') }} ({{ props.form.testCases.length }})
        </button>
        <button
          v-if="hasKeywords"
          :class="['flow-section-tab', { active: activeSection === 'keywords' }]"
          @click="activeSection = 'keywords'"
        >
          {{ t('robotEditor.keywordsSection') }} ({{ props.form.keywords.length }})
        </button>
      </div>

      <!-- Item tabs within section -->
      <div class="flow-item-tabs">
        <template v-if="activeSection === 'testcases'">
          <button
            v-for="(name, i) in testCaseNames" :key="'tc'+i"
            :class="['flow-item-tab', { active: activeItemIndex === i }]"
            @click="activeItemIndex = i"
          >{{ name }}</button>
        </template>
        <template v-else>
          <button
            v-for="(name, i) in keywordNames" :key="'kw'+i"
            :class="['flow-item-tab', { active: activeItemIndex === i }]"
            @click="activeItemIndex = i"
          >{{ name }}</button>
        </template>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="!hasContent" class="flow-empty">
      <p>{{ t('flowEditor.noTestCases') }}</p>
    </div>

    <!-- Vue Flow Canvas + Palette -->
    <div v-else class="flow-canvas-wrapper">
      <KeywordPalette :repo-id="props.repoId" @add-node="addNodeFromPalette" />

      <div class="flow-canvas">
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
          <template #node-keyword="nodeProps"><KeywordNode v-bind="nodeProps" /></template>
          <template #node-assignment="nodeProps"><KeywordNode v-bind="nodeProps" /></template>
          <template #node-control="nodeProps"><ControlNode v-bind="nodeProps" /></template>
          <template #node-start="nodeProps"><StartEndNode v-bind="nodeProps" type="start" /></template>
          <template #node-end="nodeProps"><StartEndNode v-bind="nodeProps" type="end" /></template>
          <template #node-comment="nodeProps">
            <div class="flow-node-comment"><span>{{ nodeProps.data.label }}</span></div>
          </template>
          <template #node-flow-control="nodeProps">
            <div class="flow-node-flowctrl"><span>{{ nodeProps.data.label }}</span></div>
          </template>

          <Background />
          <Controls />
          <MiniMap />
        </VueFlow>
      </div>

      <!-- Editable Node Detail Panel -->
      <div v-if="selectedNodeData" class="flow-detail-panel">
        <div class="flow-detail-header">
          <h4>{{ selectedNodeData.stepType.toUpperCase().replace('_', ' ') }}</h4>
          <div class="flow-detail-actions">
            <button class="flow-action-btn" @click="moveStepUp" title="Move up">&#x2191;</button>
            <button class="flow-action-btn" @click="moveStepDown" title="Move down">&#x2193;</button>
            <button class="flow-action-btn flow-action-delete" @click="deleteStep" title="Delete">&times;</button>
          </div>
        </div>

        <!-- Keyword name -->
        <div v-if="['keyword', 'assignment'].includes(selectedNodeData.stepType)" class="flow-detail-row">
          <label>{{ t('flowEditor.keyword') }}</label>
          <input
            v-model="selectedNodeData.step.keyword"
            class="flow-input"
            @change="onStepFieldChange"
          />
        </div>

        <!-- Arguments -->
        <div v-if="['keyword', 'assignment'].includes(selectedNodeData.stepType)" class="flow-detail-row">
          <label>{{ t('flowEditor.arguments') }}</label>
          <div v-for="(arg, i) in selectedNodeData.step.args" :key="i" class="flow-arg-row">
            <input
              v-model="selectedNodeData.step.args[i]"
              class="flow-input flow-input-sm"
              :placeholder="'arg ' + (i+1)"
              @change="onStepFieldChange"
            />
            <button class="flow-btn-remove" @click="removeArg(i)">&times;</button>
          </div>
          <button class="flow-btn-add" @click="addArg">+ {{ t('flowEditor.addArg') }}</button>
        </div>

        <!-- Return variables (assignment) -->
        <div v-if="selectedNodeData.stepType === 'assignment'" class="flow-detail-row">
          <label>{{ t('flowEditor.returnVars') }}</label>
          <div v-for="(rv, i) in selectedNodeData.step.returnVars" :key="i" class="flow-arg-row">
            <input
              v-model="selectedNodeData.step.returnVars[i]"
              class="flow-input flow-input-sm"
              @change="onStepFieldChange"
            />
            <button class="flow-btn-remove" @click="removeReturnVar(i)">&times;</button>
          </div>
          <button class="flow-btn-add" @click="addReturnVar">+ {{ t('flowEditor.addVar') }}</button>
        </div>

        <!-- Condition (IF/ELSE IF/WHILE) -->
        <div v-if="['if', 'else_if', 'while'].includes(selectedNodeData.stepType)" class="flow-detail-row">
          <label>{{ t('flowEditor.condition') }}</label>
          <input
            v-model="selectedNodeData.step.condition"
            class="flow-input"
            @change="onStepFieldChange"
          />
        </div>

        <!-- FOR loop -->
        <div v-if="selectedNodeData.stepType === 'for'" class="flow-detail-row">
          <label>{{ t('flowEditor.loopVar') }}</label>
          <input v-model="selectedNodeData.step.loopVar" class="flow-input" @change="onStepFieldChange" />
        </div>
        <div v-if="selectedNodeData.stepType === 'for'" class="flow-detail-row">
          <label>{{ t('flowEditor.loopFlavor') }}</label>
          <select v-model="selectedNodeData.step.loopFlavor" class="flow-input" @change="onStepFieldChange">
            <option>IN</option>
            <option>IN RANGE</option>
            <option>IN ENUMERATE</option>
            <option>IN ZIP</option>
          </select>
        </div>
        <div v-if="selectedNodeData.stepType === 'for'" class="flow-detail-row">
          <label>{{ t('flowEditor.loopValues') }}</label>
          <div v-for="(val, i) in selectedNodeData.step.loopValues" :key="i" class="flow-arg-row">
            <input v-model="selectedNodeData.step.loopValues[i]" class="flow-input flow-input-sm" @change="onStepFieldChange" />
            <button class="flow-btn-remove" @click="removeLoopValue(i)">&times;</button>
          </div>
          <button class="flow-btn-add" @click="addLoopValue">+ {{ t('flowEditor.addValue') }}</button>
        </div>

        <!-- EXCEPT -->
        <div v-if="selectedNodeData.stepType === 'except'" class="flow-detail-row">
          <label>{{ t('flowEditor.exceptPattern') }}</label>
          <input v-model="selectedNodeData.step.exceptPattern" class="flow-input" @change="onStepFieldChange" />
        </div>
        <div v-if="selectedNodeData.stepType === 'except'" class="flow-detail-row">
          <label>{{ t('flowEditor.exceptVar') }}</label>
          <input v-model="selectedNodeData.step.exceptVar" class="flow-input" placeholder="AS ${error}" @change="onStepFieldChange" />
        </div>

        <!-- VAR -->
        <div v-if="selectedNodeData.stepType === 'var'" class="flow-detail-row">
          <label>{{ t('flowEditor.varName') }}</label>
          <input v-model="selectedNodeData.step.keyword" class="flow-input" @change="onStepFieldChange" />
        </div>
        <div v-if="selectedNodeData.stepType === 'var'" class="flow-detail-row">
          <label>{{ t('flowEditor.varScope') }}</label>
          <select v-model="selectedNodeData.step.varScope" class="flow-input" @change="onStepFieldChange">
            <option value="">default</option>
            <option>LOCAL</option><option>TEST</option><option>TASK</option>
            <option>SUITE</option><option>GLOBAL</option>
          </select>
        </div>

        <!-- Comment -->
        <div v-if="selectedNodeData.stepType === 'comment'" class="flow-detail-row">
          <label>{{ t('flowEditor.comment') }}</label>
          <input v-model="selectedNodeData.step.comment" class="flow-input" @change="onStepFieldChange" />
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

/* Section bar: Test Cases | Keywords + item tabs */
.flow-section-bar {
  border-bottom: 1px solid var(--color-border, #e2e8f0);
  background: var(--color-bg, #F4F7FA);
  padding: 6px 12px 0;
}
.flow-section-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 6px;
}
.flow-section-tab {
  padding: 5px 14px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-bottom: none;
  border-radius: 6px 6px 0 0;
  background: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.flow-section-tab.active {
  background: var(--color-primary, #3B7DD8);
  color: #fff;
  border-color: var(--color-primary, #3B7DD8);
}
.flow-item-tabs {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  padding-bottom: 6px;
}
.flow-item-tab {
  padding: 3px 10px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 4px;
  background: #fff;
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;
}
.flow-item-tab.active {
  background: var(--color-navy, #1A2D50);
  color: #fff;
  border-color: var(--color-navy, #1A2D50);
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
  overflow: hidden;
}
.flow-canvas {
  flex: 1;
  position: relative;
}

/* Editable detail panel */
.flow-detail-panel {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 300px;
  background: #fff;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 10;
  max-height: 80%;
  overflow-y: auto;
}
.flow-detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.flow-detail-panel h4 {
  margin: 0;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-primary, #3B7DD8);
}
.flow-detail-actions {
  display: flex;
  gap: 2px;
}
.flow-action-btn {
  width: 26px;
  height: 26px;
  border: 1px solid var(--color-border, #e2e8f0);
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.flow-action-btn:hover {
  background: var(--color-bg, #F4F7FA);
}
.flow-action-delete {
  color: #c33;
  border-color: #fcc;
}
.flow-action-delete:hover {
  background: #fee;
}
.flow-detail-row {
  margin-bottom: 10px;
}
.flow-detail-row label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--color-text-muted, #5A6380);
  margin-bottom: 3px;
}
.flow-input {
  width: 100%;
  padding: 5px 8px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 5px;
  font-size: 12px;
  font-family: monospace;
  outline: none;
  box-sizing: border-box;
}
.flow-input:focus {
  border-color: var(--color-primary, #3B7DD8);
}
.flow-input-sm {
  flex: 1;
}
.flow-arg-row {
  display: flex;
  gap: 4px;
  margin-bottom: 4px;
  align-items: center;
}
.flow-btn-remove {
  width: 22px;
  height: 22px;
  border: none;
  background: #fee;
  color: #c33;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  flex-shrink: 0;
}
.flow-btn-add {
  font-size: 11px;
  color: var(--color-primary, #3B7DD8);
  background: none;
  border: 1px dashed var(--color-primary, #3B7DD8);
  border-radius: 4px;
  padding: 3px 8px;
  cursor: pointer;
  margin-top: 2px;
}

/* Comment/flow-control inline nodes */
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
