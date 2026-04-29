<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import type { Node, Edge } from '@vue-flow/core'
import { useI18n } from 'vue-i18n'

import KeywordNode from './flow/KeywordNode.vue'
import ControlNode from './flow/ControlNode.vue'
import ControlGroupNode from './flow/ControlGroupNode.vue'
import StartEndNode from './flow/StartEndNode.vue'
import KeywordPalette from './flow/KeywordPalette.vue'
import KeywordAutocompleteInput from './flow/KeywordAutocompleteInput.vue'
import KeywordDocModal from './flow/KeywordDocModal.vue'
import SelectorPicker from '@/components/recorder/SelectorPicker.vue'
import { type RecordedFlow } from '@/types/recorder.types'
import { useKeywordSignatures } from '@/composables/useKeywordSignatures'
import {
  getArgLabel,
  friendlyType,
  isVariableRef,
  readBoolValue,
  writeBoolValue,
  type FriendlyType,
} from '@/utils/robotKeywordSignatures'
import {
  applySelectorSwap,
  isCustomSelectorValue,
  isStepType,
  robotFormToFlow,
  robotKeywordsToFlow,
  updateStepFromNode,
  NODE_START_Y,
  NODE_X,
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
  /** Story EDITOR-1 — sidecar (`<file>.rbs.json`) carrying recorded
   *  selector candidates. Null if the file has none, the editor still
   *  works as before. Persistence is the parent's responsibility:
   *  FlowEditor only emits `update:sidecar` after a swap. */
  sidecar?: RecordedFlow | null
}>()

const emit = defineEmits<{
  (e: 'update:step', data: FlowNodeData): void
  (e: 'update:sidecar', sidecar: RecordedFlow): void
}>()

const { t } = useI18n()

const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])

const { fitView, project } = useVueFlow()

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

// Story EDITOR-2 — keyword signature map (lowercase keyword name → raw
// libdoc args). Reactive: rebuilds graph automatically when the
// explorer-store cache resolves after a repo open.
const { argsByName } = useKeywordSignatures()

function buildGraph() {
  const sc = props.sidecar ?? null
  const sig = argsByName.value
  if (activeSection.value === 'testcases') {
    const result = robotFormToFlow(props.form, sc, sig)
    nodes.value = result.nodes
    edges.value = result.edges
  } else {
    const result = robotKeywordsToFlow(props.form, sig)
    nodes.value = result.nodes
    edges.value = result.edges
  }
}

// Filter nodes/edges for active item only
const baseVisibleNodes = computed(() => {
  const prefix = activeSection.value === 'testcases'
    ? `tc${activeItemIndex.value}-`
    : `kw${activeItemIndex.value}-`
  return nodes.value.filter(n => n.id.startsWith(prefix))
})
// Inject drop indicator node when dragging
const visibleNodes = computed(() => {
  const base = baseVisibleNodes.value
  if (dropIndicatorIndex.value === null) return base
  const y = getDropIndicatorY(dropIndicatorIndex.value)
  const indicatorNode: Node = {
    id: '__drop-indicator__',
    type: 'drop-indicator',
    position: { x: NODE_X - 50, y: y - 2 },
    data: {},
    draggable: false,
    selectable: false,
  }
  return [...base, indicatorNode]
})
const visibleEdges = computed(() => {
  const prefix = activeSection.value === 'testcases'
    ? `tc${activeItemIndex.value}-`
    : `kw${activeItemIndex.value}-`
  return edges.value.filter(e => e.id.startsWith(prefix))
})

// Flag to suppress fitView during inline edits/reorder
let suppressFitView = false

// Rebuild graph when form, section, or sidecar identity changes.
// Note: sidecar mutations are NOT deep-watched here — `rebuildAndReselect()`
// is called explicitly from the swap handler so we don't double-render.
watch([() => props.form, activeSection], () => {
  // Story EDITOR-6 — `suppressFitView` originally short-circuited the
  // entire watcher to avoid double-rebuilds + re-fitting after an
  // internal step edit. The early return ALSO swallowed the rebuild
  // when a stuck flag got batched with a real file-switch mutation
  // (`form` mutates in place when RobotEditor re-parses), so the user
  // saw the old test case after switching files. Now we rebuild every
  // time and only the fitView call is conditional.
  const skipFit = suppressFitView
  suppressFitView = false
  if (!skipFit) {
    activeItemIndex.value = 0
    selectedNode.value = null
  }
  buildGraph()
  if (!skipFit) {
    nextTick(() => {
      fitView({ padding: 0.3 })
      setTimeout(() => fitView({ padding: 0.3 }), 100)
    })
  }
}, { deep: true })

// Sidecar identity change (file open / refresh) → rebuild without resetting tab/selection.
watch(() => props.sidecar, () => {
  buildGraph()
})

// Story EDITOR-2 — re-render argSpecs once dynamic library signatures
// resolve (the backend fetch lags the first paint when a repo opens).
watch(argsByName, () => {
  buildGraph()
})

watch(activeItemIndex, () => {
  selectedNode.value = null
  // Wait for Vue Flow to render new nodes before fitting
  nextTick(() => {
    fitView({ padding: 0.3 })
    setTimeout(() => fitView({ padding: 0.3 }), 100)
  })
})

onMounted(() => {
  // Default to keywords section if no test cases
  if (!hasTestCases.value && hasKeywords.value) {
    activeSection.value = 'keywords'
  }
  buildGraph()
  // Multiple fitView attempts to ensure centering after Vue Flow renders
  setTimeout(() => fitView({ padding: 0.3 }), 200)
  setTimeout(() => fitView({ padding: 0.3 }), 500)
})

function onNodeClick(event: { node: Node }) {
  // EDITOR-13: terminal Start / End nodes carry only `{label}` in
  // their data — no `step` / `stepType` / `argSpecs`. The detail panel
  // template would dereference `stepType.toUpperCase()` and unmount on
  // the resulting TypeError ("blank page"). Skip them entirely; they
  // are never editable.
  if (event.node.type === 'start' || event.node.type === 'end') {
    selectedNode.value = null
    return
  }
  selectedNode.value = event.node
}
function onPaneClick() {
  selectedNode.value = null
}

// --- Editable step fields ---

// Optional `targetId` overrides the post-rebuild selection lookup.
// Reorder ops (moveStepUp/Down/drag-drop) move a step to a new array
// index, but node IDs are position-based — `tc0-step-N` for the step
// currently at index N — so the OLD id points to a DIFFERENT step
// after the rebuild. Callers that mutate positions must pass the new
// id explicitly so the selection follows the *step*, not the slot.
function rebuildAndReselect(targetId?: string) {
  const selectedId = targetId ?? selectedNode.value?.id
  suppressFitView = true
  buildGraph()
  if (selectedId) {
    nextTick(() => {
      const reselected = nodes.value.find(n => n.id === selectedId)
      selectedNode.value = reselected || null
    })
  }
}

// Helper: compose the position-based node id for a step at `realIdx`
// in the currently-active section/item. Mirrors the format used in
// `flowConverter.ts::stepsToFlow` (`${prefix}-step-${i}`).
function stepNodeIdAt(realIdx: number): string {
  const prefix = activeSection.value === 'testcases'
    ? `tc${activeItemIndex.value}`
    : `kw${activeItemIndex.value}`
  return `${prefix}-step-${realIdx}`
}

function onStepFieldChange() {
  if (!selectedNodeData.value) return
  updateStepFromNode(props.form, selectedNodeData.value)
  rebuildAndReselect()
  emit('update:step', selectedNodeData.value)
}

// --- Story EDITOR-1: selector candidate swap ---
//
// When the user picks a different selector candidate, we mutate args[0]
// + the sidecar's active_candidate_index in-memory and emit
// `update:sidecar` so the parent can fold both writes (`.robot` and
// `.rbs.json`) into one Save action. We never touch the disk here —
// that would re-introduce the silent-edit anti-pattern called out in
// CLAUDE.md (SH-2 invariant: never mutate `.robot` on disk at runtime).

function onSelectorPickerSwap(newIndex: number) {
  if (!selectedNodeData.value) return
  const cmd = selectedNodeData.value.recording
  if (!cmd) return
  const candidate = cmd.selector_candidates[newIndex]
  if (!candidate) return

  // If the user has typed a custom selector and is about to overwrite it,
  // confirm — otherwise the value disappears with no recovery path.
  if (isCustomSelectorValue(selectedNodeData.value.step, cmd)) {
    const ok = window.confirm(
      t('flowEditor.selector.replaceCustomConfirm', {
        current: selectedNodeData.value.step.args[0] ?? '',
        next: candidate.value,
      }),
    )
    if (!ok) return
  }

  if (!applySelectorSwap(selectedNodeData.value.step, cmd, newIndex)) return
  updateStepFromNode(props.form, selectedNodeData.value)
  rebuildAndReselect()
  emit('update:step', selectedNodeData.value)
  if (props.sidecar) emit('update:sidecar', props.sidecar)
}

/** True when the currently-selected step has at least one recorded
 *  selector candidate that the picker should expose. */
const selectorPickerVisible = computed(() => {
  const cmd = selectedNodeData.value?.recording
  return !!cmd && cmd.selector_candidates.length > 0
})

/** True when args[0] does not match any of the recorded candidates'
 *  values — the user has hand-edited the selector to a custom value. */
const selectorIsCustom = computed(() => {
  const data = selectedNodeData.value
  return data?.recording ? isCustomSelectorValue(data.step, data.recording) : false
})

/**
 * Story EDITOR-9 — when a slot value starts with `name=`, find the
 * matching arg spec by name (Robot Framework named-arg form). Falls
 * back to positional lookup otherwise. Lets the detail panel label a
 * `namespace=${vars}` slot as `namespace:` even though it sits at a
 * positional index that would otherwise resolve to a different name.
 */
function specForSlot(index: number) {
  const data = selectedNodeData.value
  if (!data) return null
  const value = data.step.args[index] ?? ''
  const m = /^([A-Za-z_][\w]*)\s*=/.exec(value)
  if (m && data.argSpecs) {
    const named = data.argSpecs.find((s) => s.name === m[1])
    if (named) return { spec: named, viaName: true as const }
  }
  return data.argSpecs?.[index] ? { spec: data.argSpecs[index], viaName: false as const } : null
}

// Story EDITOR-2 — per-arg label + default placeholder for the detail panel.
function argLabelAt(index: number): string {
  const r = specForSlot(index)
  if (r?.viaName) return r.spec.name
  return getArgLabel(selectedNodeData.value?.argSpecs ?? null, index, t)
}

// Story EDITOR-4 — keyword input v-model glue for the autocomplete component.
function onKeywordValueChange(v: string) {
  if (!selectedNodeData.value) return
  selectedNodeData.value.step.keyword = v
}

// Story EDITOR-7 — keyword doc modal toggle.
const docModalOpen = ref(false)
const docModalKeyword = computed(() => selectedNodeData.value?.step.keyword ?? '')
const canShowDoc = computed(() => {
  const data = selectedNodeData.value
  if (!data) return false
  if (data.stepType !== 'keyword' && data.stepType !== 'assignment') return false
  return (data.step.keyword ?? '').trim().length > 0
})
function openDocModal() {
  if (!canShowDoc.value) return
  docModalOpen.value = true
}

function argPlaceholderAt(index: number): string {
  const r = specForSlot(index)
  // Prefer the bare default value as placeholder — terse, fits the
  // narrow input. The parameter-name label above carries the context.
  if (r?.spec.defaultValue != null && r.spec.defaultValue !== '') {
    return r.spec.defaultValue
  }
  return t('flowEditor.argLabels.fallback', { n: index + 1 })
}

// Story EDITOR-3 / EDITOR-9 — friendly type lookup. Resolves via
// `specForSlot` so a `name=value` slot uses the named spec's type,
// not the positional spec at the same index.
function argTypeAt(index: number): FriendlyType {
  const r = specForSlot(index)
  return friendlyType(r?.spec.type ?? null)
}

function argTooltipAt(index: number): string | undefined {
  const ft = argTypeAt(index)
  if (!ft.raw) return undefined
  return ft.raw + (ft.optional ? t('flowEditor.argTypes.optionalSuffix') : '')
}

/**
 * Story EDITOR-3 — when the user has a Robot Framework variable ref
 * (`${TRUE}`, `${SELECTED}`) in the slot, fall back to the plain text
 * input even for typed slots. A naive checkbox would read `${TRUE}` as
 * falsy and overwrite the variable reference with literal `False` on
 * the first toggle — silent data loss.
 */
function effectiveControl(index: number): FriendlyType['control'] {
  const ctrl = argTypeAt(index).control
  if (ctrl === 'text') return ctrl
  const v = selectedNodeData.value?.step.args[index]
  if (isVariableRef(v)) return 'text'
  return ctrl
}

// Bool control round-trip: value may be 'True', 'true', 'yes', 'on', '1'
// for truthy or anything else for falsy. We always write 'True' / 'False'.
function onBoolToggle(index: number, e: Event) {
  if (!selectedNodeData.value) return
  const checked = (e.target as HTMLInputElement).checked
  selectedNodeData.value.step.args[index] = writeBoolValue(checked)
  onStepFieldChange()
}
function isBoolChecked(index: number): boolean {
  const v = selectedNodeData.value?.step.args[index] ?? ''
  if (v) return readBoolValue(v)
  // Fall back to the default value when the user hasn't entered anything.
  const def = selectedNodeData.value?.argSpecs?.[index]?.defaultValue
  return readBoolValue(def ?? '')
}

function addArg() {
  if (!selectedNodeData.value) return
  selectedNodeData.value.step.args.push('')
  updateStepFromNode(props.form, selectedNodeData.value)
  rebuildAndReselect()
}

// --- Story EDITOR-9: named-parameter picker on "+ Add argument" -------

const addArgPickerOpen = ref(false)

interface AddArgOption {
  name: string
  defaultValue: string | null
  isNextPositional: boolean
}

/**
 * Build the picker option list from the keyword's signature minus the
 * names already filled (positionally OR via `name=` form). `*args` /
 * `**kwargs` slots are excluded — power users reach them via the
 * "Custom value" fallback (story AC9).
 */
const addArgOptions = computed<AddArgOption[]>(() => {
  const data = selectedNodeData.value
  if (!data?.argSpecs) return []
  const args = data.step.args
  const usedNames = new Set<string>()
  for (let i = 0; i < args.length; i++) {
    const v = args[i]
    const m = /^([A-Za-z_][\w]*)\s*=/.exec(v)
    if (m) {
      usedNames.add(m[1])
    } else {
      const positional = data.argSpecs[i]
      if (positional && (positional.kind === 'positional' || positional.kind === 'optional')) {
        usedNames.add(positional.name)
      }
    }
  }
  const out: AddArgOption[] = []
  for (let i = 0; i < data.argSpecs.length; i++) {
    const s = data.argSpecs[i]
    if (s.kind !== 'positional' && s.kind !== 'optional') continue
    if (!s.name || usedNames.has(s.name)) continue
    out.push({
      name: s.name,
      defaultValue: s.defaultValue,
      isNextPositional: i === args.length,
    })
  }
  return out
})

function toggleAddArgPicker() {
  addArgPickerOpen.value = !addArgPickerOpen.value
}

function pickAddArg(opt: AddArgOption) {
  if (!selectedNodeData.value) return
  // Next positional → bare value (RF reads positionally, label resolves
  // by index). Otherwise write a named arg `name=` so RF doesn't depend
  // on order, and `specForSlot` will pick up the spec by name.
  const value = opt.isNextPositional ? '' : `${opt.name}=`
  selectedNodeData.value.step.args.push(value)
  updateStepFromNode(props.form, selectedNodeData.value)
  rebuildAndReselect()
  addArgPickerOpen.value = false
}

function pickCustomArg() {
  addArg()
  addArgPickerOpen.value = false
}

let addArgDocListenerBound = false
function onAddArgDocClick(e: MouseEvent) {
  const t = e.target
  if (!(t instanceof Element)) return
  if (t.closest('.flow-add-arg-wrap')) return
  addArgPickerOpen.value = false
}
function bindAddArgDocClick() {
  if (addArgDocListenerBound) return
  document.addEventListener('click', onAddArgDocClick)
  addArgDocListenerBound = true
}
function unbindAddArgDocClick() {
  if (!addArgDocListenerBound) return
  document.removeEventListener('click', onAddArgDocClick)
  addArgDocListenerBound = false
}
watch(addArgPickerOpen, (open) => {
  if (open) bindAddArgDocClick()
  else unbindAddArgDocClick()
})
onUnmounted(unbindAddArgDocClick)
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
  // Pin selection to the moved step's NEW position id so a user can
  // press Up repeatedly to walk a step to the top of the list.
  rebuildAndReselect(stepNodeIdAt(idx - 1))
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
  rebuildAndReselect(stepNodeIdAt(idx + 1))
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

// --- Drop zone indicator for drag-to-position ---

const dropIndicatorIndex = ref<number | null>(null)
const canvasRef = ref<HTMLElement | null>(null)

/** Get sorted step nodes for current view (excluding start/end) */
function getStepNodes(): Node[] {
  return baseVisibleNodes.value
    .filter(n => n.type !== 'start' && n.type !== 'end')
    .sort((a, b) => a.position.y - b.position.y)
}

/** Find insertion index from a flow-coordinate Y position */
function findInsertIndex(flowY: number): number {
  const stepNodes = getStepNodes()
  if (stepNodes.length === 0) return 0

  for (let i = 0; i < stepNodes.length; i++) {
    const nodeY = stepNodes[i].position.y
    if (flowY < nodeY) return i
  }
  return stepNodes.length
}

/** Convert mouse event to flow Y coordinate */
function eventToFlowY(event: DragEvent): number {
  const el = canvasRef.value
  if (!el) return 0
  const rect = el.getBoundingClientRect()
  const pos = project({ x: event.clientX - rect.left, y: event.clientY - rect.top })
  return pos.y
}

/** Get the Y position for the drop indicator line */
function getDropIndicatorY(index: number): number {
  const stepNodes = getStepNodes()
  if (stepNodes.length === 0) return NODE_START_Y
  if (index <= 0) return stepNodes[0].position.y - 25
  if (index >= stepNodes.length) return stepNodes[stepNodes.length - 1].position.y + 60
  return (stepNodes[index - 1].position.y + stepNodes[index].position.y) / 2
}

function makeStepFromDrag(event: DragEvent): RobotStep | null {
  const keyword = event.dataTransfer?.getData('application/rf-keyword')
  const control = event.dataTransfer?.getData('application/rf-control')
  if (keyword) {
    return {
      type: 'keyword', keyword, args: [], returnVars: [],
      condition: '', loopVar: '${item}', loopFlavor: 'IN', loopValues: [],
      exceptPattern: '', exceptVar: '', varScope: '', comment: '',
    }
  }
  if (control && isStepType(control)) {
    return {
      type: control, keyword: '', args: [], returnVars: [],
      condition: control === 'if' || control === 'while' ? '${condition}' : '',
      loopVar: control === 'for' ? '${item}' : '',
      loopFlavor: control === 'for' ? 'IN' : '',
      loopValues: control === 'for' ? ['@{list}'] : [],
      exceptPattern: '', exceptVar: '', varScope: '', comment: '',
    }
  }
  return null
}

function insertStepAt(step: RobotStep, index: number) {
  const list = getActiveSteps()
  if (!list) return
  // Clamp index — skip 'end' type steps when counting
  let realIndex = 0
  let counted = 0
  for (let i = 0; i < list.length; i++) {
    if (list[i].type === 'end') { realIndex++; continue }
    if (counted === index) break
    counted++
    realIndex++
  }
  list.splice(realIndex, 0, step)
  if (['if', 'for', 'while', 'try'].includes(step.type)) {
    list.splice(realIndex + 1, 0, {
      type: 'end', keyword: '', args: [], returnVars: [],
      condition: '', loopVar: '', loopFlavor: '', loopValues: [],
      exceptPattern: '', exceptVar: '', varScope: '', comment: '',
    })
  }
  suppressFitView = true
  buildGraph()
}

function onCanvasDrop(event: DragEvent) {
  event.preventDefault()
  dropIndicatorIndex.value = null

  // Check for node reorder drop
  const reorderIdx = event.dataTransfer?.getData('application/rf-reorder')
  if (reorderIdx !== undefined && reorderIdx !== '') {
    const fromIdx = parseInt(reorderIdx, 10)
    const flowY = eventToFlowY(event)
    const toIdx = findInsertIndex(flowY)
    reorderStep(fromIdx, toIdx)
    return
  }

  const step = makeStepFromDrag(event)
  if (!step) return

  const flowY = eventToFlowY(event)
  const idx = findInsertIndex(flowY)
  insertStepAt(step, idx)
}

function onCanvasDragOver(event: DragEvent) {
  event.preventDefault()
  event.dataTransfer!.dropEffect = 'copy'
  const flowY = eventToFlowY(event)
  dropIndicatorIndex.value = findInsertIndex(flowY)
}

function onCanvasDragLeave() {
  dropIndicatorIndex.value = null
}

// --- Node reorder via drag handle ---

function onNodeReorderDragStart(event: DragEvent, node: Node) {
  const data = node.data as FlowNodeData
  // Map visual step index (excluding 'end' nodes) to real index
  const steps = getActiveSteps()
  if (!steps) return
  let visualIdx = 0
  for (let i = 0; i < steps.length; i++) {
    if (steps[i].type === 'end') continue
    if (i === data.stepIndex) break
    visualIdx++
  }
  event.dataTransfer?.setData('application/rf-reorder', String(visualIdx))
  event.dataTransfer!.effectAllowed = 'move'
}

function reorderStep(fromVisualIdx: number, toVisualIdx: number) {
  const steps = getActiveSteps()
  if (!steps) return

  // Map visual indices to real indices (skipping 'end' steps)
  const realIndices: number[] = []
  for (let i = 0; i < steps.length; i++) {
    if (steps[i].type !== 'end') realIndices.push(i)
  }

  if (fromVisualIdx < 0 || fromVisualIdx >= realIndices.length) return
  const fromReal = realIndices[fromVisualIdx]

  // Adjust toVisualIdx if moving down (account for removed element)
  let toReal: number
  if (toVisualIdx >= realIndices.length) {
    toReal = steps.length
  } else if (toVisualIdx <= fromVisualIdx) {
    toReal = realIndices[toVisualIdx]
  } else {
    // Moving down — the target shifts by 1 because we remove first
    toReal = realIndices[toVisualIdx]
  }

  if (fromReal === toReal || fromReal + 1 === toReal) return

  // Check if this step has an accompanying 'end' step
  const step = steps[fromReal]
  const hasEnd = ['if', 'for', 'while', 'try'].includes(step.type) && fromReal + 1 < steps.length && steps[fromReal + 1].type === 'end'

  // Remove
  const removed = hasEnd ? steps.splice(fromReal, 2) : steps.splice(fromReal, 1)

  // Recalculate insertion point after removal
  let insertAt: number
  if (toReal > fromReal) {
    insertAt = toReal - removed.length
  } else {
    insertAt = toReal
  }
  insertAt = Math.max(0, Math.min(insertAt, steps.length))

  steps.splice(insertAt, 0, ...removed)
  suppressFitView = true
  buildGraph()
}

// Expose reorder drag start for node components
function onNodeDragHandleStart(event: DragEvent, nodeId: string) {
  const node = baseVisibleNodes.value.find(n => n.id === nodeId)
  if (!node) return
  onNodeReorderDragStart(event, node)
}

// Provide drag handle start to child nodes via provide/inject would be complex,
// so we expose it as a data attribute approach
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

      <div ref="canvasRef" class="flow-canvas">
        <VueFlow
          @drop="onCanvasDrop"
          @dragover="onCanvasDragOver"
          @dragleave="onCanvasDragLeave"
          :nodes="visibleNodes"
          :edges="visibleEdges"
          :default-viewport="{ zoom: 0.9, x: 0, y: 0 }"
          :min-zoom="0.2"
          :max-zoom="2"
          :nodes-draggable="false"
          fit-view-on-init
          @node-click="onNodeClick"
          @pane-click="onPaneClick"
        >
          <template #node-keyword="nodeProps">
            <KeywordNode v-bind="nodeProps" :reorder-enabled="true" @reorder-drag-start="onNodeDragHandleStart($event, nodeProps.id)" />
          </template>
          <template #node-assignment="nodeProps">
            <KeywordNode v-bind="nodeProps" :reorder-enabled="true" @reorder-drag-start="onNodeDragHandleStart($event, nodeProps.id)" />
          </template>
          <template #node-control="nodeProps">
            <ControlNode v-bind="nodeProps" :reorder-enabled="true" @reorder-drag-start="onNodeDragHandleStart($event, nodeProps.id)" />
          </template>
          <template #node-control-frame="nodeProps">
            <ControlGroupNode v-bind="nodeProps" />
          </template>
          <template #node-start="nodeProps"><StartEndNode v-bind="nodeProps" type="start" /></template>
          <template #node-end="nodeProps"><StartEndNode v-bind="nodeProps" type="end" /></template>
          <template #node-comment="nodeProps">
            <div class="flow-node-comment">
              <div
                class="flow-drag-handle"
                draggable="true"
                @mousedown.stop
                @dragstart.stop="onNodeDragHandleStart($event, nodeProps.id)"
              >&#x2630;</div>
              <span>{{ nodeProps.data.label }}</span>
            </div>
          </template>
          <template #node-flow-control="nodeProps">
            <div class="flow-node-flowctrl">
              <div
                class="flow-drag-handle"
                draggable="true"
                @mousedown.stop
                @dragstart.stop="onNodeDragHandleStart($event, nodeProps.id)"
              >&#x2630;</div>
              <span>{{ nodeProps.data.label }}</span>
            </div>
          </template>
          <template #node-drop-indicator>
            <div class="flow-drop-indicator">
              <div class="flow-drop-dot" />
              <div class="flow-drop-line" />
              <div class="flow-drop-dot" />
            </div>
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
            <!-- Story EDITOR-7: keyword documentation popup -->
            <button
              v-if="canShowDoc"
              class="flow-action-btn flow-action-info"
              :title="t('flowEditor.docModal.button')"
              data-testid="kw-doc-info-btn"
              @click="openDocModal"
            >&#9432;</button>
            <button class="flow-action-btn flow-action-delete" @click="deleteStep" title="Delete">&times;</button>
          </div>
        </div>

        <!-- Keyword name (Story EDITOR-4: autocompleted from useKeywordSignatures) -->
        <div v-if="['keyword', 'assignment'].includes(selectedNodeData.stepType)" class="flow-detail-row">
          <label>{{ t('flowEditor.keyword') }}</label>
          <KeywordAutocompleteInput
            :value="selectedNodeData.step.keyword"
            @update:value="onKeywordValueChange"
            @select="onStepFieldChange"
          />
        </div>

        <!-- Arguments -->
        <div v-if="['keyword', 'assignment'].includes(selectedNodeData.stepType)" class="flow-detail-row">
          <label>{{ t('flowEditor.arguments') }}</label>
          <div v-for="(arg, i) in selectedNodeData.step.args" :key="i" class="flow-arg-row">
            <!-- Story EDITOR-2: per-arg name label inline with the input,
                 matches the row layout used by condition / loopVar / etc. -->
            <span
              class="flow-arg-name-inline"
              :title="selectedNodeData.argSpecs?.[i]?.type ?? undefined"
            >{{ argLabelAt(i) }}:</span>
            <!-- Story EDITOR-3: friendly type chip (icon + localised label),
                 raw type in tooltip. Hidden whenever the SelectorPicker
                 actually replaces the input for this slot, AND hidden
                 (Story EDITOR-10) when the type bucket is the generic
                 "unknown" — that chip shows "? Value" which is noise,
                 not information. The parameter-name label still carries
                 the title-attribute tooltip with the raw type if any. -->
            <span
              v-if="!(i === 0 && selectorPickerVisible && selectedNodeData.recording)
                    && argTypeAt(i).labelKey !== 'flowEditor.argTypes.unknown'"
              class="flow-arg-type-chip"
              :title="argTooltipAt(i)"
              data-testid="arg-type-chip"
            >
              <span class="flow-arg-type-icon">{{ argTypeAt(i).icon }}</span>
              <span class="flow-arg-type-label">{{ t(argTypeAt(i).labelKey) }}</span>
              <span v-if="argTypeAt(i).optional" class="flow-arg-type-opt">?</span>
            </span>
            <!-- Story EDITOR-1: SelectorPicker for args[0] when we have recorded candidates -->
            <template v-if="i === 0 && selectorPickerVisible && selectedNodeData.recording">
              <div class="flow-selector-picker-wrap">
                <SelectorPicker
                  :command="selectedNodeData.recording"
                  @update:active-index="onSelectorPickerSwap"
                />
                <span v-if="selectorIsCustom" class="flow-selector-custom-hint">
                  {{ t('flowEditor.selector.customValueHint') }}
                </span>
              </div>
            </template>
            <!-- Story EDITOR-3: typed input control by friendlyType().control,
                 with `effectiveControl(i)` falling back to `text` for RF
                 variable refs to preserve `${VAR}` round-tripping. -->
            <template v-else>
              <input
                v-if="effectiveControl(i) === 'checkbox'"
                type="checkbox"
                class="flow-input-checkbox"
                :checked="isBoolChecked(i)"
                @change="onBoolToggle(i, $event)"
                :data-testid="`arg-bool-${i}`"
              />
              <select
                v-else-if="effectiveControl(i) === 'select'"
                v-model="selectedNodeData.step.args[i]"
                class="flow-input flow-input-sm"
                :data-testid="`arg-select-${i}`"
                @change="onStepFieldChange"
              >
                <!-- Pre-existing custom value the user typed before
                     EDITOR-3 landed (or any value not in the choice
                     list). Render it as an option so it stays visible
                     and isn't silently overwritten on next pick. -->
                <option
                  v-if="selectedNodeData.step.args[i] && !(argTypeAt(i).choices ?? []).includes(selectedNodeData.step.args[i])"
                  :value="selectedNodeData.step.args[i]"
                >{{ selectedNodeData.step.args[i] }} ({{ t('flowEditor.argTypes.customValue') }})</option>
                <option value="" disabled hidden>{{ argPlaceholderAt(i) }}</option>
                <option
                  v-for="choice in (argTypeAt(i).choices ?? [])"
                  :key="choice"
                  :value="choice"
                >{{ choice }}</option>
              </select>
              <input
                v-else-if="effectiveControl(i) === 'integer' || effectiveControl(i) === 'number'"
                v-model="selectedNodeData.step.args[i]"
                type="number"
                :step="effectiveControl(i) === 'integer' ? '1' : 'any'"
                inputmode="decimal"
                class="flow-input flow-input-sm"
                :placeholder="argPlaceholderAt(i)"
                @change="onStepFieldChange"
              />
              <input
                v-else-if="effectiveControl(i) === 'duration'"
                v-model="selectedNodeData.step.args[i]"
                class="flow-input flow-input-sm"
                :placeholder="argPlaceholderAt(i) || t('flowEditor.argTypes.durationHint')"
                :title="t('flowEditor.argTypes.durationHint')"
                @change="onStepFieldChange"
              />
              <input
                v-else
                v-model="selectedNodeData.step.args[i]"
                class="flow-input flow-input-sm"
                :placeholder="argPlaceholderAt(i)"
                @change="onStepFieldChange"
              />
            </template>
            <button class="flow-btn-remove" @click="removeArg(i)">&times;</button>
          </div>
          <!-- Story EDITOR-9: "+ Add argument" → small picker of unused
               named parameters; "Custom value" appends an empty positional
               slot for keywords with no signature. -->
          <div class="flow-add-arg-wrap">
            <button class="flow-btn-add" type="button" @click="toggleAddArgPicker">
              + {{ t('flowEditor.addArg') }}
              <span v-if="addArgOptions.length > 0" class="flow-add-arg-caret">▾</span>
            </button>
            <div
              v-if="addArgPickerOpen"
              class="flow-add-arg-popover"
              role="listbox"
              data-testid="add-arg-popover"
            >
              <div v-if="addArgOptions.length === 0" class="flow-add-arg-empty">
                {{ t('flowEditor.addArgPicker.noUnused') }}
              </div>
              <button
                v-for="opt in addArgOptions"
                :key="opt.name"
                type="button"
                class="flow-add-arg-option"
                :data-testid="`add-arg-option-${opt.name}`"
                @click="pickAddArg(opt)"
              >
                <span class="flow-add-arg-option-name">{{ opt.name }}</span>
                <span v-if="opt.defaultValue !== null" class="flow-add-arg-option-default">
                  = {{ opt.defaultValue }}
                </span>
                <span v-if="!opt.isNextPositional" class="flow-add-arg-option-named">
                  {{ t('flowEditor.addArgPicker.namedHint') }}
                </span>
              </button>
              <button
                type="button"
                class="flow-add-arg-option flow-add-arg-option--custom"
                data-testid="add-arg-custom"
                @click="pickCustomArg"
              >
                {{ t('flowEditor.addArgPicker.custom') }}
              </button>
            </div>
          </div>
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
    <!-- Story EDITOR-7: keyword documentation modal (teleported to body by BaseModal) -->
    <KeywordDocModal
      v-model="docModalOpen"
      :keyword="docModalKeyword"
      :repo-id="props.repoId"
    />
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
.flow-action-info {
  color: var(--color-primary, #3B7DD8);
  border-color: rgba(59, 125, 216, 0.4);
  font-style: italic;
  font-weight: 700;
}
.flow-action-info:hover {
  background: rgba(59, 125, 216, 0.08);
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
.flow-arg-name-inline {
  font-size: 10px;
  font-weight: 600;
  color: var(--color-text-muted, #5A6380);
  cursor: default;
  flex-shrink: 0;
  min-width: 60px;
  max-width: 96px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.flow-arg-type-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 5px;
  background: var(--color-bg, #F4F7FA);
  border-radius: 9px;
  font-size: 9px;
  color: var(--color-text-muted, #5A6380);
  flex-shrink: 0;
  cursor: default;
  user-select: none;
}
.flow-arg-type-icon {
  color: var(--color-primary, #3B7DD8);
  font-weight: 700;
  font-size: 9px;
  font-family: var(--font-mono, monospace);
}
.flow-arg-type-label {
  font-size: 9px;
}
.flow-arg-type-opt {
  font-weight: 700;
  color: var(--color-accent, #D4883E);
}
.flow-input-checkbox {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  cursor: pointer;
  accent-color: var(--color-primary, #3B7DD8);
}
/* Story EDITOR-9 — named-arg picker popover */
.flow-add-arg-wrap {
  position: relative;
  display: inline-block;
  margin-top: 2px;
}
.flow-add-arg-caret {
  font-size: 10px;
  margin-left: 2px;
  opacity: 0.7;
}
.flow-add-arg-popover {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 200px;
  max-width: 280px;
  background: #fff;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 6px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.10);
  padding: 4px 0;
  z-index: 1000;
  max-height: 240px;
  overflow-y: auto;
}
.flow-add-arg-option {
  display: flex;
  align-items: baseline;
  gap: 6px;
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  padding: 5px 10px;
  font-size: 12px;
  font-family: monospace;
  color: var(--color-text, #1A2D50);
  cursor: pointer;
}
.flow-add-arg-option:hover {
  background: var(--color-bg, #F4F7FA);
}
.flow-add-arg-option-name {
  flex: 0 0 auto;
  font-weight: 600;
}
.flow-add-arg-option-default {
  flex: 1;
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  color: var(--color-text-muted, #5A6380);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.flow-add-arg-option-named {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-accent, #D4883E);
  font-family: var(--font-sans, sans-serif);
  flex-shrink: 0;
}
.flow-add-arg-option--custom {
  border-top: 1px solid var(--color-border, #e2e8f0);
  margin-top: 2px;
  font-style: italic;
  color: var(--color-text-muted, #5A6380);
  font-family: var(--font-sans, sans-serif);
  font-size: 11px;
}
.flow-add-arg-empty {
  padding: 6px 10px;
  font-size: 11px;
  font-style: italic;
  color: var(--color-text-muted, #5A6380);
}
.flow-selector-picker-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.flow-selector-custom-hint {
  font-size: 10px;
  color: var(--color-accent, #D4883E);
  font-style: italic;
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
  display: flex;
  align-items: center;
  gap: 6px;
}
.flow-node-flowctrl {
  padding: 6px 12px;
  border-radius: 6px;
  background: #FFF5F5;
  border: 2px solid #E53E3E;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Drag handle on nodes */
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

/* Drop indicator */
.flow-drop-indicator {
  display: flex;
  align-items: center;
  gap: 0;
  width: 280px;
  pointer-events: none;
}
.flow-drop-line {
  flex: 1;
  height: 3px;
  background: var(--color-primary, #3B7DD8);
  border-radius: 2px;
}
.flow-drop-dot {
  width: 10px;
  height: 10px;
  background: var(--color-primary, #3B7DD8);
  border-radius: 50%;
  flex-shrink: 0;
}
</style>
