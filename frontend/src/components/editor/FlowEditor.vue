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
  estimateNodeHeight,
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
  /** Repo-relative path of the currently open file. Forwarded to
   *  `KeywordPalette` so it can re-collapse all categories whenever
   *  the user switches to a different test file. */
  filePath?: string
  /** Story EDITOR-1 — sidecar (`<file>.rbs.json`) carrying recorded
   *  selector candidates. Null if the file has none, the editor still
   *  works as before. Persistence is the parent's responsibility:
   *  FlowEditor only emits `update:sidecar` after a swap. */
  sidecar?: RecordedFlow | null
}>()

const emit = defineEmits<{
  (e: 'update:step', data: FlowNodeData): void
  (e: 'update:sidecar', sidecar: RecordedFlow): void
  /** Request the parent (RobotEditor) to push a new empty test case
   *  onto `form.testCases`. The parent owns the form, FlowEditor only
   *  triggers and then jumps the selection to the new item. */
  (e: 'add-test-case'): void
  /** Same as `add-test-case` but for the keywords list. */
  (e: 'add-keyword'): void
  /** Library / Resource import was added or removed. RobotEditor
   *  hooks this to invalidate the keyword cache and re-fetch the
   *  palette so the new library's keywords show up immediately.
   *  `addedLibrary` carries the name of the library just added so
   *  the parent can verify post-refresh that the env actually
   *  picked it up — and surface a hint when not (lib not pip-
   *  installed in the env, the file-side import alone won't make
   *  it visible). Undefined for removals or the input-panel path
   *  where verification isn't useful. */
  (e: 'libraries-changed', addedLibrary?: string): void
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

/**
 * Which section, if any, is currently empty. Drives the contextual
 * empty-state CTA: a file with only keywords still lets the user
 * click the Test Cases tab and see "No test cases yet — add one"
 * with the right button. Without this, the empty state would only
 * fire when both lists were empty, leaving keyword-only files in a
 * dead-end blank canvas if the user wanted to add a test case.
 */
const emptySection = computed<'testcases' | 'keywords' | null>(() => {
  if (activeSection.value === 'testcases' && !hasTestCases.value) return 'testcases'
  if (activeSection.value === 'keywords' && !hasKeywords.value) return 'keywords'
  return null
})

// --- Library management ---
//
// `form.settings` carries Library / Resource imports as
// `{ key: 'Library', value: 'Browser', args: [...] }` entries.
// FlowEditor lets the user add / remove these without leaving the
// flow tab; RobotEditor's settings watcher picks up the mutation,
// re-emits the `.robot` text, and re-fetches the keyword cache so
// the palette updates with whatever keywords the new library
// exposes (or drops keywords from a removed library).

const librariesPanelOpen = ref(false)
const libraryInputValue = ref('')

interface LibraryEntry {
  idx: number          // index into form.settings (so removeLibrary can splice cleanly)
  kind: 'library' | 'resource'
  value: string        // library name or resource path
}

const libraryEntries = computed<LibraryEntry[]>(() => {
  const out: LibraryEntry[] = []
  props.form.settings.forEach((s, idx) => {
    const keyLower = s.key.toLowerCase()
    if (keyLower === 'library') {
      out.push({ idx, kind: 'library', value: s.value })
    } else if (keyLower === 'resource') {
      out.push({ idx, kind: 'resource', value: s.value })
    }
  })
  return out
})

/** Lower-cased set of imported library names. Always includes
 *  `'builtin'` because RF auto-imports BuiltIn. Drives the
 *  KeywordPalette dimming + auto-import logic.
 */
const importedLibraryNames = computed<Set<string>>(() => {
  const s = new Set<string>(['builtin'])
  for (const e of libraryEntries.value) {
    if (e.kind === 'library') s.add(e.value.toLowerCase())
  }
  return s
})

// Static suggestion list — same set the Visual Editor uses. Filtered
// by the user's current input + already-imported libraries.
const RF_LIBRARY_SUGGESTIONS = [
  'BuiltIn', 'Collections', 'String', 'OperatingSystem', 'Process',
  'DateTime', 'XML', 'Dialogs', 'Screenshot', 'Telnet', 'Remote',
  'SeleniumLibrary', 'Browser', 'RequestsLibrary', 'DatabaseLibrary',
  'SSHLibrary', 'FTPLibrary', 'ExcelLibrary', 'JSONLibrary',
  'AppiumLibrary', 'SwingLibrary', 'SikuliLibrary', 'ImapLibrary',
  'ArchiveLibrary', 'CryptoLibrary', 'RESTinstance',
]

const librarySuggestions = computed<string[]>(() => {
  const q = libraryInputValue.value.trim().toLowerCase()
  const already = new Set(
    libraryEntries.value
      .filter(e => e.kind === 'library')
      .map(e => e.value.toLowerCase()),
  )
  return RF_LIBRARY_SUGGESTIONS.filter(name => {
    if (already.has(name.toLowerCase())) return false
    if (!q) return true
    return name.toLowerCase().includes(q)
  }).slice(0, 8)
})

// Libs shipped with `robotframework` itself — `Library    X` is enough,
// no pip install. Skip the install-dialog branch for these.
const _RF_BUNDLED = new Set([
  'collections', 'string', 'datetime', 'operatingsystem', 'process', 'xml',
  'dialogs', 'screenshot', 'telnet', 'remote',
])

/** Push a Library entry onto form.settings unless an identical one
 *  already exists. Names containing a `/` or ending in `.resource`
 *  are treated as Resource imports instead. Emits
 *  `libraries-changed` so the parent can refresh the keyword
 *  cache. */
function addLibrary(rawName: string): void {
  const name = rawName.trim()
  if (!name) return
  const isResource = name.toLowerCase().endsWith('.resource') || name.includes('/')
  const key = isResource ? 'Resource' : 'Library'
  // Dedupe — RF accepts duplicate Library imports but they're noise.
  const existing = props.form.settings.find(
    s => s.key.toLowerCase() === key.toLowerCase()
      && s.value.trim().toLowerCase() === name.toLowerCase(),
  )
  if (existing) return
  props.form.settings.push({ key, value: name, args: [] })
  libraryInputValue.value = ''
  // Only third-party Library imports trigger the env-introspection
  // check. Resource imports point at .resource files, and RF-bundled
  // libs (Collections, XML, …) don't need pip install.
  const skipInstallCheck = isResource || _RF_BUNDLED.has(name.toLowerCase())
  emit('libraries-changed', skipInstallCheck ? undefined : name)
}

function confirmAddLibrary(): void {
  addLibrary(libraryInputValue.value)
}

/** Remove the settings entry at `idx`. Index comes straight from
 *  the `LibraryEntry` so the splice targets the right row even when
 *  multiple Library imports are interleaved with other settings
 *  (Documentation, Suite Setup, …). */
function removeLibrary(idx: number): void {
  if (idx < 0 || idx >= props.form.settings.length) return
  props.form.settings.splice(idx, 1)
  emit('libraries-changed')
}

/**
 * Emit `add-test-case` and, after the parent has pushed onto
 * `form.testCases`, switch to the test-cases section and select the
 * newly-appended item. The new index is `length - 1` AFTER the push,
 * which we observe via `nextTick` (Vue propagates the prop change in
 * the next microtask).
 */
async function handleAddTestCase(): Promise<void> {
  emit('add-test-case')
  await nextTick()
  if (props.form.testCases.length > 0) {
    activeSection.value = 'testcases'
    activeItemIndex.value = props.form.testCases.length - 1
  }
}

/** Mirror of `handleAddTestCase` for the keywords list. */
async function handleAddKeyword(): Promise<void> {
  emit('add-keyword')
  await nextTick()
  if (props.form.keywords.length > 0) {
    activeSection.value = 'keywords'
    activeItemIndex.value = props.form.keywords.length - 1
  }
}

// Selected node for editable detail panel
const selectedNode = ref<Node | null>(null)
const selectedNodeData = computed<FlowNodeData | null>(() => {
  if (!selectedNode.value) return null
  // Doc-meta nodes carry a different data shape (`{label, text,
  // section, sectionIndex}`) — they're handled by `selectedDocMeta`
  // below. Returning null here keeps the step-detail-panel template
  // from dereferencing missing `stepType` / `step` fields and
  // crashing.
  if (selectedNode.value.type === 'doc-meta') return null
  return selectedNode.value.data as FlowNodeData
})

/** Truthy when the user clicked a `[Documentation]` side-note node.
 *  Drives a separate detail-panel branch with a textarea bound to
 *  the underlying test case / keyword's `documentation` field. */
const selectedDocMeta = computed<{
  text: string
  section: 'testcase' | 'keyword'
  sectionIndex: number
} | null>(() => {
  if (!selectedNode.value || selectedNode.value.type !== 'doc-meta') return null
  const d = selectedNode.value.data as {
    text: string
    section: 'testcase' | 'keyword'
    sectionIndex: number
  }
  return { text: d.text, section: d.section, sectionIndex: d.sectionIndex }
})

/** Two-way bound model for the doc-meta textarea. Reads / writes
 *  the underlying form's documentation field directly so changes
 *  flow through the existing `update:step`-style watcher chain. */
const docMetaModel = computed<string>({
  get(): string {
    if (!selectedDocMeta.value) return ''
    const { section, sectionIndex } = selectedDocMeta.value
    if (section === 'testcase') {
      return props.form.testCases[sectionIndex]?.documentation ?? ''
    }
    return props.form.keywords[sectionIndex]?.documentation ?? ''
  },
  set(value: string) {
    if (!selectedDocMeta.value) return
    const { section, sectionIndex } = selectedDocMeta.value
    const target = section === 'testcase'
      ? props.form.testCases[sectionIndex]
      : props.form.keywords[sectionIndex]
    if (target) target.documentation = value
  },
})

function deleteDocMeta() {
  if (!selectedDocMeta.value) return
  docMetaModel.value = ''
  selectedNode.value = null
  rebuildAndReselect()
}

/** True when the active test case / keyword has no documentation
 *  yet — drives the "+ [Documentation]" affordance in the tab
 *  strip. Once a doc is added, the side node makes the affordance
 *  redundant so it hides. */
const canAddDocMeta = computed<boolean>(() => {
  const target = activeSection.value === 'testcases'
    ? props.form.testCases[activeItemIndex.value]
    : props.form.keywords[activeItemIndex.value]
  return !!target && !target.documentation
})

function addDocMeta() {
  const target = activeSection.value === 'testcases'
    ? props.form.testCases[activeItemIndex.value]
    : props.form.keywords[activeItemIndex.value]
  if (!target) return
  // Seed with a single space so the side node renders + the
  // detail panel auto-selects on the user's first interaction.
  // The first keystroke replaces it.
  target.documentation = ' '
  rebuildAndReselect()
  // Auto-select the freshly-added doc-meta side node so the user
  // lands directly in the textarea.
  nextTick(() => {
    const prefix = activeSection.value === 'testcases'
      ? `tc${activeItemIndex.value}`
      : `kw${activeItemIndex.value}`
    const docNode = nodes.value.find((n) => n.id === `${prefix}-doc`)
    if (docNode) selectedNode.value = docNode
  })
}

// User-resizable detail-panel width — drag the handle on the left
// edge to widen / narrow. Lives in component-local state so the
// chosen width survives selection changes inside this Explorer
// session, and resets when the user navigates away (component
// unmounts). Hard caps prevent the user dragging it off-screen.
const PANEL_MIN_WIDTH = 240
const PANEL_MAX_WIDTH = 720
const detailPanelWidth = ref(300)
const isResizingPanel = ref(false)

function onPanelResizeStart(ev: PointerEvent) {
  ev.preventDefault()
  isResizingPanel.value = true
  const startX = ev.clientX
  const startWidth = detailPanelWidth.value
  function onMove(e: PointerEvent) {
    // Drag handle is on the LEFT edge — moving the pointer left
    // grows the panel, moving right shrinks it.
    const delta = startX - e.clientX
    const next = Math.min(PANEL_MAX_WIDTH, Math.max(PANEL_MIN_WIDTH, startWidth + delta))
    detailPanelWidth.value = next
  }
  function onUp() {
    isResizingPanel.value = false
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    window.removeEventListener('pointercancel', onUp)
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
  window.addEventListener('pointercancel', onUp)
}

// Story EDITOR-2 — keyword signature map (lowercase keyword name → raw
// libdoc args). Reactive: rebuilds graph automatically when the
// explorer-store cache resolves after a repo open.
const { argsByName, getKeywordInfo } = useKeywordSignatures()

// Library usage histogram for the currently-open file. Walks every
// keyword / assignment step in test cases AND keyword definitions
// and tallies which library each step.keyword resolves to. The
// palette uses this to sort library categories descending so the
// libs the user is actually working with bubble to the top.
const libraryUsageCounts = computed<Map<string, number>>(() => {
  const counts = new Map<string, number>()
  const tally = (steps: RobotStep[]) => {
    for (const step of steps) {
      if (step.type !== 'keyword' && step.type !== 'assignment') continue
      if (!step.keyword) continue
      const info = getKeywordInfo(step.keyword)
      const lib = info?.library
      if (!lib) continue
      counts.set(lib, (counts.get(lib) ?? 0) + 1)
    }
  }
  for (const tc of props.form.testCases) tally(tc.steps)
  for (const kw of props.form.keywords) tally(kw.steps)
  return counts
})

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

// Backspace / Delete on a selected node deletes it, mirroring the
// "x" button on the detail panel. Skip when focus is in any text
// input — the detail panel inputs (args, condition, loopVar, …) all
// rely on Backspace to delete characters, and the library autocomplete
// uses Backspace to retreat through suggestions. `contenteditable`
// is treated the same way.
function onWindowKeydown(e: KeyboardEvent) {
  if (e.key !== 'Backspace' && e.key !== 'Delete') return
  if (!selectedNode.value || !selectedNodeData.value) return
  const tgt = e.target as HTMLElement | null
  if (tgt) {
    const tag = tgt.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
    if (tgt.isContentEditable) return
  }
  e.preventDefault()
  deleteStep()
}

onMounted(() => {
  // Default to keywords section if no test cases
  if (!hasTestCases.value && hasKeywords.value) {
    activeSection.value = 'keywords'
  }
  buildGraph()
  // Multiple fitView attempts to ensure centering after Vue Flow renders
  setTimeout(() => fitView({ padding: 0.3 }), 200)
  setTimeout(() => fitView({ padding: 0.3 }), 500)
  window.addEventListener('keydown', onWindowKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onWindowKeydown)
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

// Per-slot user override that forces the text input even when the
// inferred control would be checkbox / select / number. Cleared when
// the selected node changes (different step → different intent).
// Keyed by `${nodeId}#${slotIndex}` so two slots on different nodes
// don't share state.
const textModeOverrides = ref<Set<string>>(new Set())
function _slotKey(index: number): string {
  return `${selectedNode.value?.id ?? '?'}#${index}`
}
function isTextModeOverridden(index: number): boolean {
  return textModeOverrides.value.has(_slotKey(index))
}
function toggleTextMode(index: number): void {
  const key = _slotKey(index)
  const next = new Set(textModeOverrides.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  textModeOverrides.value = next
}
// Reset the per-slot text-mode overrides when the selection changes
// — overrides are intent-bound to a specific step, not the panel.
watch(selectedNode, () => {
  textModeOverrides.value = new Set()
})

/**
 * Story EDITOR-3 — when the user has a Robot Framework variable ref
 * (`${TRUE}`, `${SELECTED}`) in the slot, fall back to the plain text
 * input even for typed slots. A naive checkbox would read `${TRUE}` as
 * falsy and overwrite the variable reference with literal `False` on
 * the first toggle — silent data loss.
 *
 * Three layers of "render as text instead of typed control":
 *   1. The arg-type itself is `text` (no friendly typing known).
 *   2. The slot value (or the value-half of a `name=value` slot, like
 *      `headless=${HEADLESS}`) is a Robot Framework variable
 *      reference. The detection has to peek INSIDE the named-arg form
 *      so the recorder's `headless=${HEADLESS}` doesn't get rendered
 *      as a checkbox that would overwrite the var ref on toggle.
 *   3. The user explicitly flipped text mode on for this slot via the
 *      `{}` toggle button (e.g. they want to enter `${HEADLESS}` into
 *      a slot currently holding `False`).
 */
function effectiveControl(index: number): FriendlyType['control'] {
  if (isTextModeOverridden(index)) return 'text'
  const ctrl = argTypeAt(index).control
  if (ctrl === 'text') return ctrl
  const raw = selectedNodeData.value?.step.args[index] ?? ''
  // Strip a leading `name=` so `headless=${HEADLESS}` is recognised
  // as a variable-bearing slot. Without this, `isVariableRef` only
  // matches bare `${...}` and the recorder's `headless=${HEADLESS}`
  // gets rendered as a checkbox.
  const m = /^([A-Za-z_][\w]*)\s*=(.*)$/.exec(raw)
  const valueHalf = m ? m[2] : raw
  if (isVariableRef(valueHalf)) return 'text'
  return ctrl
}

// Bool control round-trip: value may be 'True', 'true', 'yes', 'on', '1'
// for truthy or anything else for falsy. We always write 'True' / 'False'.
//
// Both helpers must respect the `name=value` form (e.g. `force=True`).
// Without that:
//   - `isBoolChecked` would `readBoolValue('force=True')` → false, so a
//     value the user explicitly set to True renders unchecked.
//   - `onBoolToggle` would overwrite `force=True` with bare `True`,
//     dropping the `name=` prefix. After re-render `specForSlot` no
//     longer finds the spec by name and falls back to the positional
//     spec at the same index — usually a different, non-bool spec —
//     so the checkbox disappears and a text input takes its place
//     mid-edit. Both bugs reported by the user, both fixed here.
const _NAMED_ARG_RE = /^([A-Za-z_][\w]*)\s*=(.*)$/
function onBoolToggle(index: number, e: Event) {
  if (!selectedNodeData.value) return
  const checked = (e.target as HTMLInputElement).checked
  const raw = selectedNodeData.value.step.args[index] ?? ''
  const m = _NAMED_ARG_RE.exec(raw)
  selectedNodeData.value.step.args[index] = m
    ? `${m[1]}=${writeBoolValue(checked)}`
    : writeBoolValue(checked)
  onStepFieldChange()
}
function isBoolChecked(index: number): boolean {
  const raw = selectedNodeData.value?.step.args[index] ?? ''
  // Strip a leading `name=` so a named-arg slot is read against its
  // value half rather than the literal slot string.
  const m = _NAMED_ARG_RE.exec(raw)
  const v = m ? m[2] : raw
  if (v) return readBoolValue(v)
  // Fall back to the keyword's signature default — covers both bare
  // empty positional slots and `name=` (no value yet) named slots,
  // so the checkbox initial state mirrors RF's runtime behaviour.
  // `specForSlot` resolves named-arg slots by name; falls back to
  // positional otherwise.
  const def = specForSlot(index)?.spec.defaultValue
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

// Trigger ref + computed popover position. Story EDITOR-9 originally
// rendered the picker as a regular descendant of the detail panel,
// but that panel has `overflow-y: auto`, which clips the popover so
// the user has to scroll inside the panel just to read the options.
// We Teleport the popover to <body> and pin it to the trigger button
// via getBoundingClientRect() so it floats over the canvas instead.
const addArgTriggerRef = ref<HTMLElement | null>(null)
const addArgPickerStyle = ref<{ top: string; left: string; minWidth: string }>({
  top: '0px',
  left: '0px',
  minWidth: '200px',
})

function recomputeAddArgPickerPosition() {
  const trigger = addArgTriggerRef.value
  if (!trigger) return
  const rect = trigger.getBoundingClientRect()
  addArgPickerStyle.value = {
    top: `${rect.bottom + 4}px`,
    left: `${rect.left}px`,
    minWidth: `${Math.max(rect.width, 200)}px`,
  }
}

function toggleAddArgPicker() {
  addArgPickerOpen.value = !addArgPickerOpen.value
  if (addArgPickerOpen.value) {
    // Position before the popover paints so it never flashes at (0,0).
    nextTick(recomputeAddArgPickerPosition)
  }
}

function pickAddArg(opt: AddArgOption) {
  if (!selectedNodeData.value) return
  // Next positional → bare value (RF reads positionally, label resolves
  // by index). Otherwise write a named arg `name=<default>` so RF
  // doesn't depend on order AND the slot is valid the moment it's
  // added — `name=` on its own would be syntactically invalid in
  // `.robot` source, plus a bool checkbox would read it as unchecked
  // even when the keyword's signature default is True.
  let value: string
  if (opt.isNextPositional) {
    value = ''
  } else if (opt.defaultValue != null && opt.defaultValue !== '') {
    value = `${opt.name}=${opt.defaultValue}`
  } else {
    value = `${opt.name}=`
  }
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
  // The popover is Teleported to <body>, so a "click inside the
  // wrapper" check no longer covers option clicks. Allow either the
  // wrapper (the trigger) OR the popover itself — both are part of
  // the picker UX, just no longer the same DOM subtree.
  if (t.closest('.flow-add-arg-wrap, .flow-add-arg-popover')) return
  addArgPickerOpen.value = false
}
// Keep the popover pinned to the trigger when the surrounding scroll
// container or window changes shape. Without this the user would see
// the popover detach from the button as soon as they scroll.
function onAddArgRecomputeEvent() {
  if (!addArgPickerOpen.value) return
  recomputeAddArgPickerPosition()
}
function bindAddArgDocClick() {
  if (addArgDocListenerBound) return
  document.addEventListener('click', onAddArgDocClick)
  // `capture: true` so we catch scrolls inside the detail panel
  // (which has `overflow-y: auto`) — those bubble through capture
  // phase but not the bubble phase.
  window.addEventListener('scroll', onAddArgRecomputeEvent, true)
  window.addEventListener('resize', onAddArgRecomputeEvent)
  addArgDocListenerBound = true
}
function unbindAddArgDocClick() {
  if (!addArgDocListenerBound) return
  document.removeEventListener('click', onAddArgDocClick)
  window.removeEventListener('scroll', onAddArgRecomputeEvent, true)
  window.removeEventListener('resize', onAddArgRecomputeEvent)
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
// Adding the first return-variable to a plain keyword step flips its
// type to 'assignment' so the serializer emits `${var}=  Keyword`
// instead of just `Keyword`. Removing the last var flips it back —
// keeps the FlowEditor surface "any keyword can return a value"
// rather than asking the user to pick the right node type up front.
function addReturnVar() {
  if (!selectedNodeData.value) return
  const step = selectedNodeData.value.step
  step.returnVars.push('${var}')
  if (step.type === 'keyword') step.type = 'assignment'
  updateStepFromNode(props.form, selectedNodeData.value)
  rebuildAndReselect()
}
function removeReturnVar(index: number) {
  if (!selectedNodeData.value) return
  const step = selectedNodeData.value.step
  step.returnVars.splice(index, 1)
  if (step.returnVars.length === 0 && step.type === 'assignment') {
    step.type = 'keyword'
  }
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

function addNodeFromPalette(step: RobotStep, library?: string) {
  // Auto-import: when the keyword came from a library that isn't in
  // form.settings yet, prepend a `Library    X` row so RF can
  // resolve the keyword at runtime. `addLibrary` already dedupes
  // and emits `libraries-changed` (which refreshes the palette
  // signatures cache).
  if (library) {
    const lower = library.toLowerCase()
    const already = importedLibraryNames.value.has(lower)
    if (!already) addLibrary(library)
  }

  const list = activeSection.value === 'testcases'
    ? props.form.testCases[activeItemIndex.value]?.steps
    : props.form.keywords[activeItemIndex.value]?.steps
  if (!list) return
  // When a node is selected, splice the new step in directly after
  // it — the user's mental model is "extend from where I am" rather
  // than "always append at the bottom". With no selection, fall
  // back to the original push-to-end behavior.
  const insertAt = selectedNodeData.value
    ? selectedNodeData.value.stepIndex + 1
    : list.length
  list.splice(insertAt, 0, step)
  if (['if', 'for', 'while', 'try'].includes(step.type)) {
    list.splice(insertAt + 1, 0, {
      type: 'end', keyword: '', args: [], returnVars: [],
      condition: '', loopVar: '', loopFlavor: '', loopValues: [],
      exceptPattern: '', exceptVar: '', varScope: '', comment: '',
    })
  }
  // Move selection to the freshly-inserted node so the user can
  // edit args / chain another insert without a second click.
  rebuildAndReselect(stepNodeIdAt(insertAt))
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

/** Find insertion index from a flow-coordinate Y position.
 *
 * Compares `flowY` against each step node's MIDPOINT (top + height/2)
 * rather than its top edge. The previous "fixed offset" feel was the
 * top-edge comparison: anywhere inside a node body resolved to "after
 * this node", so dropping near the bottom of node N inserted at N+1
 * — but so did dropping in the upper half of N+1. Whether you wanted
 * "before this step" or "after the previous step", the cursor had to
 * be in the narrow gap above the next node's top, which felt like
 * the indicator only snapped on a fixed grid.
 *
 * Heights vary because keyword nodes grow with arg count (one chip
 * per row, per `estimateNodeHeight`). The midpoint comparison keeps
 * the indicator anchored to where the user expects.
 */
function findInsertIndex(flowY: number): number {
  const stepNodes = getStepNodes()
  if (stepNodes.length === 0) return 0

  for (let i = 0; i < stepNodes.length; i++) {
    const top = stepNodes[i].position.y
    const data = stepNodes[i].data as FlowNodeData
    const midpoint = top + estimateNodeHeight(data.step) / 2
    if (flowY < midpoint) return i
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

/** Get the Y position for the drop indicator line.
 *
 * Renders the indicator inside the actual gap between nodes. Without
 * factoring in `estimateNodeHeight`, the average of two `position.y`
 * values (TOP edges) is biased toward the previous node — the
 * indicator visually overlapped the lower part of the previous node
 * body whenever it had args, instead of sitting in the gap. Using
 * `prev.bottom + (gap / 2)` puts the line in the geometric middle of
 * the actual whitespace.
 */
function getDropIndicatorY(index: number): number {
  const stepNodes = getStepNodes()
  if (stepNodes.length === 0) return NODE_START_Y
  if (index <= 0) return stepNodes[0].position.y - 25
  if (index >= stepNodes.length) {
    const last = stepNodes[stepNodes.length - 1]
    const lastData = last.data as FlowNodeData
    return last.position.y + estimateNodeHeight(lastData.step) + 25
  }
  const prev = stepNodes[index - 1]
  const next = stepNodes[index]
  const prevBottom = prev.position.y + estimateNodeHeight((prev.data as FlowNodeData).step)
  return (prevBottom + next.position.y) / 2
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

  // Auto-import: KeywordPalette stamps the source library on the
  // drag in `application/rf-library`. If the user dragged a keyword
  // from a not-yet-imported library, prepend the Library row before
  // inserting the step.
  const sourceLib = event.dataTransfer?.getData('application/rf-library') || ''
  if (sourceLib && !importedLibraryNames.value.has(sourceLib.toLowerCase())) {
    addLibrary(sourceLib)
  }

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
    <!-- Section tabs: Test Cases | Keywords. Both tabs are ALWAYS
         visible (even when one side is empty) so the user can
         create a test case in a keyword-only file and vice versa
         via the "+ ..." button below. Previously these were
         hidden behind v-if="hasTestCases" / v-if="hasKeywords",
         which dead-ended files that started life with only one
         section type. -->
    <div class="flow-section-bar">
      <div class="flow-section-tabs">
        <button
          :class="['flow-section-tab', { active: activeSection === 'testcases' }]"
          @click="activeSection = 'testcases'"
        >
          {{ t('robotEditor.testCasesSection') }} ({{ props.form.testCases.length }})
        </button>
        <button
          :class="['flow-section-tab', { active: activeSection === 'keywords' }]"
          @click="activeSection = 'keywords'"
        >
          {{ t('robotEditor.keywordsSection') }} ({{ props.form.keywords.length }})
        </button>
      </div>

      <!-- Library quick-manage: chevron toggles an inline panel
           below the section bar. Add / remove imports without
           leaving the Flow tab. The keyword palette + signatures
           refresh automatically (RobotEditor watches `form.settings`
           Library entries and re-fetches the cache). -->
      <button
        type="button"
        :class="['flow-libs-toggle', { active: librariesPanelOpen }]"
        :title="t('flowEditor.librariesTitle')"
        data-testid="flow-libraries-toggle"
        @click="librariesPanelOpen = !librariesPanelOpen"
      >
        📚 {{ t('flowEditor.libraries') }} ({{ libraryEntries.length }})
        <span aria-hidden="true">{{ librariesPanelOpen ? '▴' : '▾' }}</span>
      </button>

      <!-- Item tabs within section -->
      <div class="flow-item-tabs">
        <template v-if="activeSection === 'testcases'">
          <button
            v-for="(name, i) in testCaseNames" :key="'tc'+i"
            :class="['flow-item-tab', { active: activeItemIndex === i }]"
            @click="activeItemIndex = i"
          >{{ name }}</button>
          <button
            type="button"
            class="flow-item-tab flow-item-tab--add"
            :title="t('flowEditor.addTestCaseTitle')"
            data-testid="flow-add-test-case"
            @click="handleAddTestCase"
          >+ {{ t('flowEditor.addTestCase') }}</button>
        </template>
        <template v-else>
          <button
            v-for="(name, i) in keywordNames" :key="'kw'+i"
            :class="['flow-item-tab', { active: activeItemIndex === i }]"
            @click="activeItemIndex = i"
          >{{ name }}</button>
          <button
            type="button"
            class="flow-item-tab flow-item-tab--add"
            :title="t('flowEditor.addKeywordTitle')"
            data-testid="flow-add-keyword"
            @click="handleAddKeyword"
          >+ {{ t('flowEditor.addKeyword') }}</button>
        </template>
        <!-- Add a `[Documentation]` side note to the active item if
             it doesn't have one yet. The button only renders when
             the doc is currently empty so the affordance disappears
             once a doc-meta side node is on the canvas. -->
        <button
          v-if="canAddDocMeta"
          type="button"
          class="flow-item-tab flow-item-tab--add-doc"
          :title="t('flowEditor.docMeta.addTitle')"
          data-testid="flow-add-doc-meta"
          @click="addDocMeta"
        >+ [Documentation]</button>
      </div>
    </div>

    <!-- Library management panel (toggled by the section-bar
         button above). Shows the file's current Library / Resource
         imports as removable chips, plus an autocomplete-input to
         add new ones. Each mutation rewrites `form.settings` and
         RobotEditor's settings-watcher refreshes the keyword cache
         + palette automatically. -->
    <div v-if="librariesPanelOpen" class="flow-libraries">
      <div class="flow-libraries__chips">
        <span v-if="libraryEntries.length === 0" class="flow-libraries__empty">
          {{ t('flowEditor.librariesNone') }}
        </span>
        <span
          v-for="entry in libraryEntries"
          :key="entry.idx"
          class="flow-libraries__chip"
          :class="{ 'flow-libraries__chip--resource': entry.kind === 'resource' }"
        >
          <span class="flow-libraries__chip-kind">{{ entry.kind === 'resource' ? 'R' : 'L' }}</span>
          <span class="flow-libraries__chip-name">{{ entry.value }}</span>
          <button
            type="button"
            class="flow-libraries__chip-remove"
            :title="t('flowEditor.libraryRemoveTitle', { name: entry.value })"
            @click="removeLibrary(entry.idx)"
            data-testid="flow-library-remove"
          >×</button>
        </span>
      </div>
      <div class="flow-libraries__input-row">
        <input
          v-model="libraryInputValue"
          type="text"
          class="flow-libraries__input"
          :placeholder="t('flowEditor.libraryInputPlaceholder')"
          autocomplete="off"
          spellcheck="false"
          data-testid="flow-library-input"
          @keydown.enter.prevent="confirmAddLibrary"
        />
        <button
          type="button"
          class="flow-libraries__add"
          :disabled="!libraryInputValue.trim()"
          data-testid="flow-library-add"
          @click="confirmAddLibrary"
        >+ {{ t('flowEditor.libraryAdd') }}</button>
      </div>
      <div v-if="librarySuggestions.length" class="flow-libraries__suggestions">
        <button
          v-for="suggestion in librarySuggestions"
          :key="suggestion"
          type="button"
          class="flow-libraries__suggestion"
          @click="addLibrary(suggestion)"
        >{{ suggestion }}</button>
      </div>
    </div>

    <!-- Empty state — fires when the active section is empty,
         independent of whether the OTHER section has content.
         A keyword-only file that switches to the Test Cases tab
         lands here with the right contextual CTA. -->
    <div v-if="emptySection" class="flow-empty">
      <p>
        {{ emptySection === 'testcases'
          ? t('flowEditor.noTestCasesYet')
          : t('flowEditor.noKeywordsYet')
        }}
      </p>
      <div class="flow-empty__actions">
        <button
          v-if="emptySection === 'testcases'"
          type="button"
          class="flow-empty__cta"
          data-testid="flow-empty-add-test-case"
          @click="handleAddTestCase"
        >+ {{ t('flowEditor.addTestCase') }}</button>
        <button
          v-if="emptySection === 'keywords'"
          type="button"
          class="flow-empty__cta"
          data-testid="flow-empty-add-keyword"
          @click="handleAddKeyword"
        >+ {{ t('flowEditor.addKeyword') }}</button>
      </div>
    </div>

    <!-- Vue Flow Canvas + Palette -->
    <div v-else class="flow-canvas-wrapper">
      <KeywordPalette
        :repo-id="props.repoId"
        :file-path="props.filePath"
        :imported-libraries="importedLibraryNames"
        :usage-counts="libraryUsageCounts"
        @add-node="addNodeFromPalette"
      />

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
            <KeywordNode v-bind="nodeProps" :reorder-enabled="true" :selected="selectedNode?.id === nodeProps.id" @reorder-drag-start="onNodeDragHandleStart($event, nodeProps.id)" />
          </template>
          <template #node-assignment="nodeProps">
            <KeywordNode v-bind="nodeProps" :reorder-enabled="true" :selected="selectedNode?.id === nodeProps.id" @reorder-drag-start="onNodeDragHandleStart($event, nodeProps.id)" />
          </template>
          <template #node-control="nodeProps">
            <ControlNode v-bind="nodeProps" :reorder-enabled="true" :selected="selectedNode?.id === nodeProps.id" @reorder-drag-start="onNodeDragHandleStart($event, nodeProps.id)" />
          </template>
          <template #node-control-frame="nodeProps">
            <ControlGroupNode v-bind="nodeProps" />
          </template>
          <template #node-start="nodeProps"><StartEndNode v-bind="nodeProps" type="start" /></template>
          <template #node-end="nodeProps"><StartEndNode v-bind="nodeProps" type="end" /></template>
          <template #node-doc-meta="nodeProps">
            <div
              class="flow-node-doc-meta"
              :class="{ 'flow-node--selected': selectedNode?.id === nodeProps.id }"
            >
              <span class="flow-node-doc-meta__bracket" aria-hidden="true">[</span>
              <div class="flow-node-doc-meta__body">
                <span class="flow-node-doc-meta__label">{{ nodeProps.data.label }}</span>
                <p class="flow-node-doc-meta__text">{{ nodeProps.data.text }}</p>
              </div>
              <span class="flow-node-doc-meta__bracket" aria-hidden="true">]</span>
            </div>
          </template>
          <template #node-comment="nodeProps">
            <div class="flow-node-comment" :class="{ 'flow-node--selected': selectedNode?.id === nodeProps.id }">
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
            <div class="flow-node-flowctrl" :class="{ 'flow-node--selected': selectedNode?.id === nodeProps.id }">
              <div
                class="flow-drag-handle"
                draggable="true"
                @mousedown.stop
                @dragstart.stop="onNodeDragHandleStart($event, nodeProps.id)"
              >&#x2630;</div>
              <span>{{ nodeProps.data.label }}</span>
            </div>
          </template>
          <template #node-return="nodeProps">
            <div class="flow-node-return-block" :class="{ 'flow-node--selected': selectedNode?.id === nodeProps.id }">
              <div
                class="flow-drag-handle"
                draggable="true"
                @mousedown.stop
                @dragstart.stop="onNodeDragHandleStart($event, nodeProps.id)"
              >&#x2630;</div>
              <span class="flow-node-return-label">↵ RETURN</span>
              <div
                v-if="nodeProps.data.step?.args?.length"
                class="flow-node-return-values"
              >
                <span
                  v-for="(arg, i) in nodeProps.data.step.args"
                  :key="i"
                  class="flow-node-return-value"
                >{{ arg }}</span>
              </div>
              <span v-else class="flow-node-return-empty">{{ t('flowEditor.returnNoValue') }}</span>
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

      <!-- Editable Node Detail Panel.
           Drop handlers are mirrored from the canvas so a drag
           that crosses the panel (it's `position: absolute` over
           the canvas's top-right) doesn't get rejected with a
           "no-drop" cursor. Without these, the user couldn't
           drag a keyword from the palette into the canvas while
           a step was selected — the panel intercepted the
           dragover but had no preventDefault. -->
      <div
        v-if="selectedDocMeta"
        class="flow-detail-panel"
        :class="{ 'flow-detail-panel--resizing': isResizingPanel }"
        :style="{ width: detailPanelWidth + 'px' }"
      >
        <div
          class="flow-detail-resizer"
          role="separator"
          aria-orientation="vertical"
          :title="t('flowEditor.resizePanelHint')"
          @pointerdown="onPanelResizeStart"
        ></div>
        <div class="flow-detail-header">
          <h4>[Documentation]</h4>
          <div class="flow-detail-actions">
            <button class="flow-action-btn flow-action-delete" @click="deleteDocMeta" :title="t('flowEditor.docMeta.removeTitle')">&times;</button>
          </div>
        </div>
        <div class="flow-detail-row">
          <label>{{ t('flowEditor.docMeta.label') }}</label>
          <textarea
            v-model="docMetaModel"
            class="flow-input flow-textarea"
            rows="8"
            :placeholder="t('flowEditor.docMeta.placeholder')"
            @blur="rebuildAndReselect()"
          ></textarea>
        </div>
        <p class="flow-detail-hint">{{ t('flowEditor.docMeta.hint') }}</p>
      </div>

      <div
        v-else-if="selectedNodeData"
        class="flow-detail-panel"
        :class="{ 'flow-detail-panel--resizing': isResizingPanel }"
        :style="{ width: detailPanelWidth + 'px' }"
        @drop.stop="onCanvasDrop"
        @dragover.stop.prevent="onCanvasDragOver"
        @dragleave.stop="onCanvasDragLeave"
      >
        <div
          class="flow-detail-resizer"
          role="separator"
          aria-orientation="vertical"
          :title="t('flowEditor.resizePanelHint')"
          @pointerdown="onPanelResizeStart"
        ></div>
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
              <!-- Story EDITOR-VAR-1 — escape hatch from the typed
                   control to a free-text input so the user can enter
                   a Robot Framework variable reference (`${HEADLESS}`)
                   on a slot whose underlying type is bool/select/number.
                   Hidden when the underlying type is already plain text
                   (nothing to toggle to). The button text flips when
                   the override is active so the user can switch back. -->
              <button
                v-if="argTypeAt(i).control !== 'text'"
                type="button"
                class="flow-input-toggle"
                :title="isTextModeOverridden(i)
                  ? t('flowEditor.argTypes.toggleBackToTyped')
                  : t('flowEditor.argTypes.toggleToText')"
                :data-testid="`arg-text-toggle-${i}`"
                @click="toggleTextMode(i)"
              >{{ isTextModeOverridden(i) ? '⌨' : '{}' }}</button>
            </template>
            <button class="flow-btn-remove" @click="removeArg(i)">&times;</button>
          </div>
          <!-- Story EDITOR-9: "+ Add argument" → small picker of unused
               named parameters; "Custom value" appends an empty positional
               slot for keywords with no signature.
               The popover is Teleported to <body> with computed fixed
               positioning so the detail panel's `overflow-y: auto` can't
               clip it (it would otherwise force the user to scroll
               inside the panel just to read the options). -->
          <div ref="addArgTriggerRef" class="flow-add-arg-wrap">
            <button class="flow-btn-add" type="button" @click="toggleAddArgPicker">
              + {{ t('flowEditor.addArg') }}
              <span v-if="addArgOptions.length > 0" class="flow-add-arg-caret">▾</span>
            </button>
            <Teleport to="body">
            <div
              v-if="addArgPickerOpen"
              class="flow-add-arg-popover"
              role="listbox"
              data-testid="add-arg-popover"
              :style="addArgPickerStyle"
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
            </Teleport>
          </div>
        </div>

        <!-- Return variables (any keyword call can be promoted to an
             assignment by adding a return-variable here). -->
        <div
          v-if="['keyword', 'assignment'].includes(selectedNodeData.stepType)"
          class="flow-detail-row"
        >
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
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
  border-bottom: 1px solid var(--color-border, #e2e8f0);
  background: var(--color-bg, #F4F7FA);
  padding: 6px 12px 0;
}
.flow-section-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 6px;
}
.flow-libs-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  padding: 4px 10px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 4px;
  background: #fff;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary, #555);
  cursor: pointer;
}
.flow-libs-toggle:hover {
  border-color: var(--color-primary, #3B7DD8);
  color: var(--color-primary, #3B7DD8);
}
.flow-libs-toggle.active {
  background: var(--color-primary, #3B7DD8);
  color: #fff;
  border-color: var(--color-primary, #3B7DD8);
}

/* Library management panel — opens below the section bar. */
.flow-libraries {
  border-bottom: 1px solid var(--color-border, #e2e8f0);
  background: #fff;
  padding: 10px 12px;
}
.flow-libraries__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.flow-libraries__empty {
  color: var(--color-text-muted, #5A6380);
  font-size: 12px;
  font-style: italic;
}
.flow-libraries__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px 2px 0;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 4px;
  background: rgba(59, 125, 216, 0.08);
  font-size: 12px;
}
.flow-libraries__chip--resource {
  background: rgba(212, 136, 62, 0.10);
  border-color: var(--color-accent, #D4883E);
}
.flow-libraries__chip-kind {
  display: inline-block;
  width: 18px;
  text-align: center;
  font-size: 10px;
  font-weight: 700;
  color: var(--color-primary, #3B7DD8);
  background: rgba(59, 125, 216, 0.15);
  border-right: 1px solid var(--color-border, #e2e8f0);
  border-radius: 4px 0 0 4px;
  padding: 2px 0;
}
.flow-libraries__chip--resource .flow-libraries__chip-kind {
  color: var(--color-accent, #D4883E);
  background: rgba(212, 136, 62, 0.18);
}
.flow-libraries__chip-name {
  padding: 0 4px;
  font-family: var(--font-mono, monospace);
}
.flow-libraries__chip-remove {
  border: none;
  background: transparent;
  color: var(--color-text-muted, #5A6380);
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  padding: 0 4px;
}
.flow-libraries__chip-remove:hover {
  color: #c0392b;
}
.flow-libraries__input-row {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
}
.flow-libraries__input {
  flex: 1;
  padding: 4px 8px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 4px;
  font-size: 12px;
  font-family: var(--font-mono, monospace);
}
.flow-libraries__input:focus {
  outline: none;
  border-color: var(--color-primary, #3B7DD8);
}
.flow-libraries__add {
  padding: 4px 12px;
  border: 1px solid var(--color-primary, #3B7DD8);
  border-radius: 4px;
  background: var(--color-primary, #3B7DD8);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.flow-libraries__add:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.flow-libraries__suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.flow-libraries__suggestion {
  padding: 2px 8px;
  border: 1px dashed var(--color-border, #e2e8f0);
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-secondary, #555);
  font-size: 11px;
  cursor: pointer;
}
.flow-libraries__suggestion:hover {
  border-color: var(--color-primary, #3B7DD8);
  color: var(--color-primary, #3B7DD8);
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
.flow-item-tab--add {
  border-style: dashed;
  color: var(--color-text-muted, #5A6380);
  font-weight: 500;
}
.flow-item-tab--add:hover {
  border-color: var(--color-primary, #3B7DD8);
  color: var(--color-primary, #3B7DD8);
}

.flow-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 1rem;
  color: var(--color-text-muted, #5A6380);
}
.flow-empty__actions {
  display: flex;
  gap: 0.5rem;
}
.flow-empty__cta {
  padding: 0.4rem 0.9rem;
  border: 1px solid var(--color-primary, #3B7DD8);
  border-radius: 4px;
  background: var(--color-primary, #3B7DD8);
  color: #fff;
  font-size: 0.85rem;
  cursor: pointer;
}
.flow-empty__cta:hover {
  filter: brightness(1.05);
}
.flow-empty__cta--secondary {
  background: #fff;
  color: var(--color-primary, #3B7DD8);
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

/* Editable detail panel — pinned to the right of the canvas, full
   height minus a 12px gutter top/bottom so the user can see the
   full form without an inner scrollbar that competed with the
   browser scroll. The previous max-height: 80% capped it at ~4/5
   of the canvas which forced internal scrolling on tall forms. */
.flow-detail-panel {
  position: absolute;
  top: 12px;
  right: 12px;
  bottom: 12px;
  /* width is set inline via :style — defaults to 300px from
     `detailPanelWidth` and is updated by the left-edge resizer. */
  background: #fff;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 10;
  overflow-y: auto;
}
/* Disable the smooth pointer-events / cursor flicker while the
   user is actively dragging the resizer. */
.flow-detail-panel--resizing,
.flow-detail-panel--resizing * {
  user-select: none;
  cursor: ew-resize !important;
}
.flow-detail-resizer {
  position: absolute;
  left: -3px;
  top: 0;
  bottom: 0;
  width: 8px;
  cursor: ew-resize;
  z-index: 11;
  background: transparent;
  /* Larger invisible hit target than the visible accent below.
     The accent itself is rendered via ::after so the user has a
     visual cue of where the resize edge lives. */
}
.flow-detail-resizer::after {
  content: '';
  position: absolute;
  left: 3px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--color-border, #e2e8f0);
  border-radius: 1px;
  transition: background 0.15s;
}
.flow-detail-resizer:hover::after,
.flow-detail-panel--resizing .flow-detail-resizer::after {
  background: var(--color-primary, #3B7DD8);
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
.flow-textarea {
  font-family: var(--font-sans, sans-serif);
  resize: vertical;
  line-height: 1.45;
}
.flow-detail-hint {
  margin: 8px 0 0;
  font-size: 11px;
  color: var(--color-text-muted, #5A6380);
  font-style: italic;
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
/* Story EDITOR-VAR-1 — toggle between typed control and plain text.
   Lets the user enter a Robot Framework variable reference on a slot
   whose inferred type is bool / select / number. */
.flow-input-toggle {
  border: 1px solid var(--color-border, #e2e8f0);
  background: #fff;
  border-radius: 4px;
  padding: 1px 6px;
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  line-height: 1.4;
  color: var(--color-text-muted, #5A6380);
  cursor: pointer;
  flex-shrink: 0;
}
.flow-input-toggle:hover {
  background: rgba(59, 125, 216, 0.10);
  color: var(--color-primary, #3B7DD8);
  border-color: var(--color-primary, #3B7DD8);
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
  /* Teleported to <body> and pinned to the trigger via inline
     `top` / `left` (set in the script). Positioned `fixed` so the
     detail panel's `overflow-y: auto` can't clip it.
     `min-width` is also set inline to mirror the trigger width. */
  position: fixed;
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

/* `[Documentation]` side-note attached to a test case / keyword
   header. Two oversized brackets bracket the doc body, framing it
   visually as an annotation rather than a step. The connecting
   edge from this node to the Start node is dashed (set in
   flowConverter.ts) so the user reads it as "linked metadata".
   Click to edit in the detail panel. */
.flow-node-doc-meta {
  display: inline-flex;
  align-items: stretch;
  gap: 6px;
  padding: 8px 4px;
  background: color-mix(in srgb, var(--color-text-muted, #5A6380) 6%, var(--color-bg-card, #fff));
  border: 1px dashed var(--color-border, #e2e8f0);
  border-radius: 6px;
  font-size: 12px;
  max-width: 240px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.flow-node-doc-meta:hover {
  border-color: var(--color-primary, #3B7DD8);
  background: color-mix(in srgb, var(--color-primary, #3B7DD8) 6%, var(--color-bg-card, #fff));
}
.flow-node-doc-meta__bracket {
  font-size: 36px;
  font-weight: 300;
  line-height: 0.85;
  color: var(--color-text-muted, #5A6380);
  font-family: 'Times New Roman', Georgia, serif;
  align-self: stretch;
  display: flex;
  align-items: center;
}
.flow-node-doc-meta__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.flow-node-doc-meta__label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted, #5A6380);
}
.flow-node-doc-meta__text {
  margin: 0;
  font-size: 12px;
  line-height: 1.4;
  color: var(--color-text, #1A2D50);
  font-style: italic;
  /* Cap to 4 visible lines so a long doc doesn't dominate the
     side margin; the full text is still readable in the detail
     panel after a click. */
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
  white-space: pre-wrap;
}
.flow-node-doc-meta.flow-node--selected {
  outline: 3px solid var(--color-primary, #3B7DD8);
  outline-offset: 2px;
  border-color: var(--color-primary, #3B7DD8);
  background: color-mix(in srgb, var(--color-primary, #3B7DD8) 10%, var(--color-bg-card, #fff));
}

/* RETURN node — distinct from BREAK / CONTINUE because it carries
   payload (the keyword's return values) and reads as the public
   "result" of a *** Keywords *** definition rather than a control-
   flow break. Green-tinted background, leading ↵ glyph, each
   return value rendered as its own value chip so the user can scan
   them at a glance. */
.flow-node-return-block {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 8px;
  background: #F0FDF4;
  border: 2px solid #22C55E;
  font-size: 13px;
  min-width: 200px;
  max-width: 420px;
  flex-wrap: wrap;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}
.flow-node-return-label {
  font-weight: 700;
  color: #166534;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 12px;
}
.flow-node-return-values {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.flow-node-return-value {
  display: inline-block;
  padding: 2px 8px;
  background: #fff;
  border: 1px solid #BBF7D0;
  border-radius: 4px;
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  color: #166534;
  word-break: break-word;
}
.flow-node-return-empty {
  font-size: 11px;
  color: #166534;
  font-style: italic;
  opacity: 0.7;
}

/* Selected-node highlight — applied on the inline comment / flow-
   control / return templates as well as bound through the `selected`
   prop on KeywordNode / ControlNode (their scoped styles mirror
   this rule). Thicker outline + slight primary-color tint so the
   active node reads at a glance against the canvas. */
.flow-node-comment.flow-node--selected,
.flow-node-flowctrl.flow-node--selected,
.flow-node-return-block.flow-node--selected {
  outline: 3px solid var(--color-primary, #3B7DD8);
  outline-offset: 2px;
  background: color-mix(in srgb, var(--color-primary, #3B7DD8) 10%, var(--color-bg-card, #fff));
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--color-primary, #3B7DD8) 18%, transparent);
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
