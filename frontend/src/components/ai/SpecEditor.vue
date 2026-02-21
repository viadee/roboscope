<script setup lang="ts">
import { ref, reactive, watch, computed, onMounted, nextTick, onUnmounted, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAiStore } from '@/stores/ai.store'
import { useEnvironmentsStore } from '@/stores/environments.store'
import { getInstalledPackages } from '@/api/environments.api'
import BaseButton from '@/components/ui/BaseButton.vue'
import * as yaml from 'js-yaml'

// CodeMirror imports
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightSpecialChars } from '@codemirror/view'
import { EditorState } from '@codemirror/state'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { StreamLanguage, LanguageSupport } from '@codemirror/language'
import { syntaxHighlighting, defaultHighlightStyle } from '@codemirror/language'

const props = defineProps<{
  content: string
  filePath: string
}>()

const emit = defineEmits<{
  save: [content: string]
  'update:content': [content: string]
}>()

const { t } = useI18n()
const aiStore = useAiStore()
const envsStore = useEnvironmentsStore()

// --- RF Library Constants ---
const RF_BUILTINS = ['BuiltIn', 'Collections', 'String', 'OperatingSystem', 'Process', 'DateTime', 'XML', 'Dialogs', 'Screenshot', 'Telnet', 'Remote']

const PYPI_TO_LIBRARY: Record<string, string> = {
  'robotframework-seleniumlibrary': 'SeleniumLibrary',
  'robotframework-browser': 'Browser',
  'robotframework-requests': 'RequestsLibrary',
  'robotframework-databaselibrary': 'DatabaseLibrary',
  'robotframework-sshlibrary': 'SSHLibrary',
  'robotframework-ftplibrary': 'FtpLibrary',
  'robotframework-appiumlibrary': 'AppiumLibrary',
  'robotframework-archivelibrary': 'ArchiveLibrary',
  'robotframework-jsonlibrary': 'JSONLibrary',
  'robotframework-excellibrary': 'ExcelLibrary',
  'robotframework-imaplibrary': 'ImapLibrary',
  'robotframework-pdflibrary': 'PdfLibrary',
  'robotframework-crypto': 'CryptoLibrary',
  'robotframework-datadriver': 'DataDriver',
  'robotframework-pabot': 'Pabot',
  'rpaframework': 'RPA',
  'restinstance': 'RESTinstance',
  'robotframework-selenium2library': 'Selenium2Library',
  'robotframework-whitelibrary': 'WhiteLibrary',
  'robotframework-sikulilibrary': 'SikuliLibrary',
  'robotframework-otp': 'OTPLibrary',
  'robotframework-debuglibrary': 'DebugLibrary',
}

// --- State ---
const activeTab = ref<'visual' | 'yaml'>('visual')
const validation = ref<{ valid: boolean; errors: string[]; test_count: number } | null>(null)
const validating = ref(false)
const parseError = ref<string | null>(null)
const yamlEditorContainer = ref<HTMLElement | null>(null)
const yamlEditorView = shallowRef<EditorView | null>(null)
const internalYaml = ref('')

// Collapsible state
const metadataCollapsed = ref(false)
const collapsedTestSets = ref<Set<number>>(new Set())
const collapsedTestCases = ref<Map<string, Set<number>>>(new Map())

// Environment & library autocomplete state
const installedPackages = ref<{ name: string; version: string }[]>([])
const showLibraryDropdown = ref(false)
const libraryDropdownIndex = ref(-1)
const libraryInputRef = ref<HTMLInputElement | null>(null)
const libraryDropdownRef = ref<HTMLElement | null>(null)

// --- Form State ---

// v2: structured step
interface StructuredStep {
  action: string
  data: string
  expected_result: string
}

type StepItem = string | StructuredStep

interface TestCase {
  name: string
  description: string
  priority: 'high' | 'medium' | 'low'
  steps: StepItem[]
  expected_result: string
  external_id: string
  preconditions: string[]
}

interface TestSet {
  name: string
  description: string
  tags: string[]
  setup: string
  teardown: string
  test_cases: TestCase[]
  external_id: string
  preconditions: string[]
}

interface SpecForm {
  version: string
  metadata: {
    title: string
    author: string
    created: string
    last_generated: string | null
    generation_hash: string | null
    target_file: string
    environment: string | null
    libraries: string[]
    external_id: string
  }
  test_sets: TestSet[]
}

const form = reactive<SpecForm>({
  version: '2',
  metadata: {
    title: '',
    author: '',
    created: '',
    last_generated: null,
    generation_hash: null,
    target_file: '',
    environment: null,
    libraries: [],
    external_id: '',
  },
  test_sets: [],
})

// New library input
const newLibrary = ref('')
// New tag inputs per test set
const newTagInputs = ref<Map<number, string>>(new Map())
// New precondition inputs per test set and test case
const newPreconditionInputs = ref<Map<string, string>>(new Map())

// --- Computed ---
const testCount = computed(() => {
  return form.test_sets.reduce((sum, ts) => sum + ts.test_cases.length, 0)
})

// --- Environment & Library Autocomplete ---
const selectedEnvId = computed(() => {
  if (!form.metadata.environment) return null
  const env = envsStore.environments.find(e => e.name === form.metadata.environment)
  return env?.id ?? null
})

interface LibrarySuggestion {
  name: string
  type: 'builtin' | 'installed'
}

const librarySuggestions = computed<LibrarySuggestion[]>(() => {
  const suggestions: LibrarySuggestion[] = RF_BUILTINS.map(name => ({ name, type: 'builtin' as const }))

  // Map installed pip packages to RF library names
  for (const pkg of installedPackages.value) {
    const pkgNameLower = pkg.name.toLowerCase()
    const knownLib = PYPI_TO_LIBRARY[pkgNameLower]
    if (knownLib) {
      if (!suggestions.some(s => s.name === knownLib)) {
        suggestions.push({ name: knownLib, type: 'installed' })
      }
    } else if (pkgNameLower.startsWith('robotframework-')) {
      // Heuristic: robotframework-excelreader → ExcelReader
      const suffix = pkg.name.substring('robotframework-'.length)
      const heuristicName = suffix.replace(/(^|-)(\w)/g, (_m: string, _p1: string, p2: string) => p2.toUpperCase())
      if (!suggestions.some(s => s.name === heuristicName)) {
        suggestions.push({ name: heuristicName, type: 'installed' })
      }
    }
  }

  return suggestions
})

const filteredSuggestions = computed(() => {
  const query = newLibrary.value.trim().toLowerCase()
  const existing = new Set(form.metadata.libraries.map(l => l.toLowerCase()))
  return librarySuggestions.value
    .filter(s => !existing.has(s.name.toLowerCase()))
    .filter(s => !query || s.name.toLowerCase().includes(query))
})

async function loadInstalledPackages(envId: number) {
  try {
    installedPackages.value = await getInstalledPackages(envId)
  } catch {
    installedPackages.value = []
  }
}

function onEnvironmentChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  form.metadata.environment = value || null
  if (selectedEnvId.value) {
    loadInstalledPackages(selectedEnvId.value)
  } else {
    // Use default environment
    const defaultEnv = envsStore.environments.find(e => e.is_default) ?? envsStore.environments[0]
    if (defaultEnv) loadInstalledPackages(defaultEnv.id)
  }
}

function selectSuggestion(suggestion: LibrarySuggestion) {
  if (!form.metadata.libraries.includes(suggestion.name)) {
    form.metadata.libraries.push(suggestion.name)
  }
  newLibrary.value = ''
  showLibraryDropdown.value = false
  libraryDropdownIndex.value = -1
}

function onLibraryInputFocus() {
  showLibraryDropdown.value = true
  libraryDropdownIndex.value = -1
}

function onLibraryInputBlur(event: FocusEvent) {
  // Delay to allow click on dropdown item
  const related = event.relatedTarget as HTMLElement | null
  if (related && libraryDropdownRef.value?.contains(related)) return
  setTimeout(() => { showLibraryDropdown.value = false }, 150)
}

function onLibraryKeydown(event: KeyboardEvent) {
  const items = filteredSuggestions.value

  if (event.key === 'Enter') {
    event.preventDefault()
    if (libraryDropdownIndex.value >= 0 && libraryDropdownIndex.value < items.length) {
      selectSuggestion(items[libraryDropdownIndex.value])
    } else {
      addLibrary()
    }
    return
  }

  if (!items.length) return

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    showLibraryDropdown.value = true
    libraryDropdownIndex.value = Math.min(libraryDropdownIndex.value + 1, items.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    libraryDropdownIndex.value = Math.max(libraryDropdownIndex.value - 1, 0)
  } else if (event.key === 'Escape') {
    showLibraryDropdown.value = false
    libraryDropdownIndex.value = -1
  }
}

// --- YAML Language for CodeMirror ---
function yamlLanguage() {
  return StreamLanguage.define({
    startState() {
      return { inBlock: false }
    },
    token(stream, _state: { inBlock: boolean }) {
      // Comments
      if (stream.match(/^#.*/)) return 'comment'
      // Keys at start of line or after indent
      if (stream.sol() && stream.match(/^[\w][\w\s]*(?=:)/)) return 'attributeName'
      if (stream.sol() && stream.match(/^\s+[\w][\w\s]*(?=:)/)) return 'attributeName'
      // List marker
      if (stream.match(/^- /)) return 'punctuation'
      // Colon separator
      if (stream.match(/^:\s*/)) return 'punctuation'
      // Quoted strings
      if (stream.match(/^"(?:[^"\\]|\\.)*"/)) return 'string'
      if (stream.match(/^'(?:[^'\\]|\\.)*'/)) return 'string'
      // Booleans and null
      if (stream.match(/^(true|false|null|~)\b/)) return 'keyword'
      // Numbers
      if (stream.match(/^-?\d+(\.\d+)?/)) return 'number'
      // Pipe/block scalar indicators
      if (stream.match(/^[|>][+-]?\s*$/)) return 'keyword'
      stream.next()
      return null
    },
  })
}

// --- Step helpers ---
function isStructuredStep(step: StepItem): step is StructuredStep {
  return typeof step === 'object' && step !== null && 'action' in step
}

function getStepAction(step: StepItem): string {
  return isStructuredStep(step) ? step.action : step
}

function toggleStepType(tsIndex: number, tcIndex: number, stepIdx: number) {
  const step = form.test_sets[tsIndex].test_cases[tcIndex].steps[stepIdx]
  if (isStructuredStep(step)) {
    // Convert to simple string
    form.test_sets[tsIndex].test_cases[tcIndex].steps[stepIdx] = step.action
  } else {
    // Convert to structured
    form.test_sets[tsIndex].test_cases[tcIndex].steps[stepIdx] = {
      action: step,
      data: '',
      expected_result: '',
    }
  }
}

// --- Parse/Serialize ---
function parseYamlToForm(yamlContent: string): boolean {
  try {
    const parsed = yaml.load(yamlContent) as any
    if (!parsed || typeof parsed !== 'object') {
      form.version = '2'
      form.metadata = { title: '', author: '', created: '', last_generated: null, generation_hash: null, target_file: '', environment: null, libraries: [], external_id: '' }
      form.test_sets = []
      parseError.value = null
      return true
    }

    form.version = String(parsed.version || '2')
    const m = parsed.metadata || {}
    form.metadata.title = m.title || ''
    form.metadata.author = m.author || ''
    form.metadata.created = m.created || ''
    form.metadata.last_generated = m.last_generated || null
    form.metadata.generation_hash = m.generation_hash || null
    form.metadata.target_file = m.target_file || ''
    form.metadata.environment = m.environment || null
    form.metadata.libraries = Array.isArray(m.libraries) ? [...m.libraries] : []
    form.metadata.external_id = m.external_id || ''

    form.test_sets = Array.isArray(parsed.test_sets) ? parsed.test_sets.map((ts: any) => ({
      name: ts.name || '',
      description: ts.description || '',
      tags: Array.isArray(ts.tags) ? [...ts.tags] : [],
      setup: ts.setup || '',
      teardown: ts.teardown || '',
      external_id: ts.external_id || '',
      preconditions: Array.isArray(ts.preconditions) ? [...ts.preconditions] : [],
      test_cases: Array.isArray(ts.test_cases) ? ts.test_cases.map((tc: any) => ({
        name: tc.name || '',
        description: tc.description || '',
        priority: ['high', 'medium', 'low'].includes(tc.priority) ? tc.priority : 'medium',
        steps: Array.isArray(tc.steps) ? tc.steps.map((step: any) => {
          if (typeof step === 'string') return step
          if (typeof step === 'object' && step !== null && 'action' in step) {
            return {
              action: step.action || '',
              data: step.data || '',
              expected_result: step.expected_result || '',
            }
          }
          return String(step)
        }) : [],
        expected_result: tc.expected_result || '',
        external_id: tc.external_id || '',
        preconditions: Array.isArray(tc.preconditions) ? [...tc.preconditions] : [],
      })) : [],
    })) : []

    parseError.value = null
    return true
  } catch (e: any) {
    parseError.value = e.message || 'Failed to parse YAML'
    return false
  }
}

function serializeFormToYaml(): string {
  const obj: any = {
    version: form.version,
    metadata: {
      title: form.metadata.title || undefined,
      author: form.metadata.author || undefined,
      created: form.metadata.created || undefined,
      last_generated: form.metadata.last_generated || null,
      generation_hash: form.metadata.generation_hash || null,
      target_file: form.metadata.target_file || undefined,
      environment: form.metadata.environment || undefined,
      libraries: form.metadata.libraries.length ? form.metadata.libraries : undefined,
    },
  }

  // v2: external_id at metadata level
  if (form.metadata.external_id) {
    obj.metadata.external_id = form.metadata.external_id
  }

  // Clean metadata: remove undefined/null keys for cleanliness
  if (!obj.metadata.last_generated) delete obj.metadata.last_generated
  if (!obj.metadata.generation_hash) delete obj.metadata.generation_hash
  if (!obj.metadata.created) delete obj.metadata.created
  if (!obj.metadata.author) delete obj.metadata.author

  if (form.test_sets.length) {
    obj.test_sets = form.test_sets.map(ts => {
      const tsObj: any = { name: ts.name }
      if (ts.description) tsObj.description = ts.description
      if (ts.tags.length) tsObj.tags = [...ts.tags]
      if (ts.setup) tsObj.setup = ts.setup
      if (ts.teardown) tsObj.teardown = ts.teardown
      if (ts.external_id) tsObj.external_id = ts.external_id
      if (ts.preconditions.length) tsObj.preconditions = [...ts.preconditions]
      if (ts.test_cases.length) {
        tsObj.test_cases = ts.test_cases.map(tc => {
          const tcObj: any = { name: tc.name }
          if (tc.description) tcObj.description = tc.description
          if (tc.priority && tc.priority !== 'medium') tcObj.priority = tc.priority
          if (tc.external_id) tcObj.external_id = tc.external_id
          if (tc.preconditions.length) tcObj.preconditions = [...tc.preconditions]
          if (tc.steps.length) {
            tcObj.steps = tc.steps.map(step => {
              if (typeof step === 'string') return step
              const stepObj: any = { action: step.action }
              if (step.data) stepObj.data = step.data
              if (step.expected_result) stepObj.expected_result = step.expected_result
              return stepObj
            })
          }
          if (tc.expected_result) tcObj.expected_result = tc.expected_result
          return tcObj
        })
      }
      return tsObj
    })
  }

  return yaml.dump(obj, { lineWidth: -1, noRefs: true, sortKeys: false })
}

// --- Tab Switching ---
function switchTab(tab: 'visual' | 'yaml') {
  if (tab === activeTab.value) return

  if (tab === 'yaml') {
    // Visual → YAML: always succeeds
    const yamlStr = serializeFormToYaml()
    internalYaml.value = yamlStr
    activeTab.value = 'yaml'
    parseError.value = null
    nextTick(() => initYamlEditor())
  } else {
    // YAML → Visual: may fail
    const currentYaml = getYamlEditorContent()
    if (parseYamlToForm(currentYaml)) {
      activeTab.value = 'visual'
      destroyYamlEditor()
    }
    // If parse failed, parseError is set and we stay on yaml tab
  }
}

function getYamlEditorContent(): string {
  if (yamlEditorView.value) {
    return yamlEditorView.value.state.doc.toString()
  }
  return internalYaml.value
}

// --- YAML CodeMirror ---
function initYamlEditor() {
  destroyYamlEditor()
  if (!yamlEditorContainer.value) return

  const state = EditorState.create({
    doc: internalYaml.value,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      highlightSpecialChars(),
      history(),
      keymap.of([...defaultKeymap, ...historyKeymap]),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      new LanguageSupport(yamlLanguage()),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          const content = update.state.doc.toString()
          internalYaml.value = content
          emitContent(content)
        }
      }),
      EditorView.theme({
        '&': { height: '100%', fontSize: '13px' },
        '.cm-content': { fontFamily: "'Fira Code', 'Consolas', 'Monaco', monospace", padding: '8px 0' },
        '.cm-gutters': { background: '#f8f9fa', borderRight: '1px solid #e0e0e0', color: '#999' },
        '.cm-activeLine': { background: 'rgba(60, 181, 161, 0.06)' },
        '.cm-activeLineGutter': { background: 'rgba(60, 181, 161, 0.1)' },
      }),
    ],
  })

  yamlEditorView.value = new EditorView({
    state,
    parent: yamlEditorContainer.value,
  })
}

function destroyYamlEditor() {
  if (yamlEditorView.value) {
    yamlEditorView.value.destroy()
    yamlEditorView.value = null
  }
}

// --- Content sync ---
function emitContent(content: string) {
  emit('update:content', content)
}

function emitFormContent() {
  const yamlStr = serializeFormToYaml()
  emitContent(yamlStr)
}

// --- Validation ---
async function handleValidate() {
  validating.value = true
  try {
    const content = activeTab.value === 'yaml' ? getYamlEditorContent() : serializeFormToYaml()
    validation.value = await aiStore.validateSpec(content)
  } catch {
    validation.value = { valid: false, errors: ['Validation request failed'], test_count: 0 }
  } finally {
    validating.value = false
  }
}

// --- Form watchers (emit on change) ---
watch(() => form.metadata, () => {
  if (activeTab.value === 'visual') emitFormContent()
}, { deep: true })

watch(() => form.test_sets, () => {
  if (activeTab.value === 'visual') emitFormContent()
}, { deep: true })

watch(() => form.version, () => {
  if (activeTab.value === 'visual') emitFormContent()
})

// Reset validation on content change
watch(() => props.content, () => {
  validation.value = null
})

// --- Libraries ---
function addLibrary() {
  // If dropdown has a selected item, use that instead
  const items = filteredSuggestions.value
  if (libraryDropdownIndex.value >= 0 && libraryDropdownIndex.value < items.length) {
    selectSuggestion(items[libraryDropdownIndex.value])
    return
  }
  const lib = newLibrary.value.trim()
  if (lib && !form.metadata.libraries.includes(lib)) {
    form.metadata.libraries.push(lib)
  }
  newLibrary.value = ''
  showLibraryDropdown.value = false
  libraryDropdownIndex.value = -1
}

function removeLibrary(index: number) {
  form.metadata.libraries.splice(index, 1)
}

// --- Tags ---
function addTag(tsIndex: number) {
  const tag = (newTagInputs.value.get(tsIndex) || '').trim()
  if (tag && !form.test_sets[tsIndex].tags.includes(tag)) {
    form.test_sets[tsIndex].tags.push(tag)
  }
  newTagInputs.value.set(tsIndex, '')
}

function removeTag(tsIndex: number, tagIndex: number) {
  form.test_sets[tsIndex].tags.splice(tagIndex, 1)
}

// --- Preconditions ---
function addPrecondition(key: string, target: string[]) {
  const text = (newPreconditionInputs.value.get(key) || '').trim()
  if (text && !target.includes(text)) {
    target.push(text)
  }
  newPreconditionInputs.value.set(key, '')
}

function removePrecondition(arr: string[], index: number) {
  arr.splice(index, 1)
}

// --- Test Sets ---
function addTestSet() {
  form.test_sets.push({
    name: '',
    description: '',
    tags: [],
    setup: '',
    teardown: '',
    test_cases: [],
    external_id: '',
    preconditions: [],
  })
}

function removeTestSet(index: number) {
  form.test_sets.splice(index, 1)
  collapsedTestSets.value.delete(index)
}

function toggleTestSet(index: number) {
  if (collapsedTestSets.value.has(index)) {
    collapsedTestSets.value.delete(index)
  } else {
    collapsedTestSets.value.add(index)
  }
}

// --- Test Cases ---
function addTestCase(tsIndex: number) {
  form.test_sets[tsIndex].test_cases.push({
    name: '',
    description: '',
    priority: 'medium',
    steps: [],
    expected_result: '',
    external_id: '',
    preconditions: [],
  })
}

function removeTestCase(tsIndex: number, tcIndex: number) {
  form.test_sets[tsIndex].test_cases.splice(tcIndex, 1)
}

function toggleTestCase(tsIndex: number, tcIndex: number) {
  const key = `${tsIndex}`
  if (!collapsedTestCases.value.has(key)) {
    collapsedTestCases.value.set(key, new Set())
  }
  const set = collapsedTestCases.value.get(key)!
  if (set.has(tcIndex)) {
    set.delete(tcIndex)
  } else {
    set.add(tcIndex)
  }
}

function isTestCaseCollapsed(tsIndex: number, tcIndex: number): boolean {
  return collapsedTestCases.value.get(`${tsIndex}`)?.has(tcIndex) || false
}

// --- Steps ---
function addStep(tsIndex: number, tcIndex: number) {
  form.test_sets[tsIndex].test_cases[tcIndex].steps.push('')
}

function removeStep(tsIndex: number, tcIndex: number, stepIndex: number) {
  form.test_sets[tsIndex].test_cases[tcIndex].steps.splice(stepIndex, 1)
}

function moveStep(tsIndex: number, tcIndex: number, stepIndex: number, direction: -1 | 1) {
  const steps = form.test_sets[tsIndex].test_cases[tcIndex].steps
  const newIndex = stepIndex + direction
  if (newIndex < 0 || newIndex >= steps.length) return
  const temp = steps[stepIndex]
  steps[stepIndex] = steps[newIndex]
  steps[newIndex] = temp
}

function updateSimpleStep(tsIndex: number, tcIndex: number, stepIdx: number, value: string) {
  form.test_sets[tsIndex].test_cases[tcIndex].steps[stepIdx] = value
}

function updateStructuredStep(tsIndex: number, tcIndex: number, stepIdx: number, field: 'action' | 'data' | 'expected_result', value: string) {
  const step = form.test_sets[tsIndex].test_cases[tcIndex].steps[stepIdx]
  if (isStructuredStep(step)) {
    (step as any)[field] = value
  }
}

// --- Initialize ---
onMounted(async () => {
  parseYamlToForm(props.content)
  internalYaml.value = props.content

  // Fetch environments for the dropdown
  if (!envsStore.environments.length) {
    await envsStore.fetchEnvironments()
  }

  // Load installed packages for the selected or default environment
  const envName = form.metadata.environment
  let targetEnv = envName
    ? envsStore.environments.find(e => e.name === envName)
    : null
  if (!targetEnv) {
    targetEnv = envsStore.environments.find(e => e.is_default) ?? envsStore.environments[0] ?? null
  }
  if (targetEnv) {
    loadInstalledPackages(targetEnv.id)
  }
})

onUnmounted(() => {
  destroyYamlEditor()
})

// Watch for external content changes (e.g. file reload)
watch(() => props.content, (newContent) => {
  if (activeTab.value === 'visual') {
    parseYamlToForm(newContent)
  } else {
    internalYaml.value = newContent
    if (yamlEditorView.value) {
      const currentDoc = yamlEditorView.value.state.doc.toString()
      if (currentDoc !== newContent) {
        yamlEditorView.value.dispatch({
          changes: { from: 0, to: currentDoc.length, insert: newContent },
        })
      }
    }
  }
})
</script>

<template>
  <div class="spec-editor">
    <!-- Tab Bar -->
    <div class="spec-tabs">
      <div class="tab-buttons">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'visual' }"
          @click="switchTab('visual')"
        >
          {{ t('ai.specEditor.visualTab') }}
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'yaml' }"
          @click="switchTab('yaml')"
        >
          YAML
        </button>
      </div>
      <div class="tab-toolbar">
        <span class="badge badge-spec">.roboscope</span>
        <span v-if="testCount > 0" class="badge badge-info">
          {{ testCount }} {{ t('ai.tests') }}
        </span>
        <span v-if="validation?.valid" class="badge badge-success">
          {{ t('ai.valid') }} ({{ validation.test_count }} {{ t('ai.tests') }})
        </span>
        <span v-else-if="validation && !validation.valid" class="badge badge-danger">
          {{ t('ai.invalid') }}
        </span>
        <BaseButton size="sm" variant="secondary" :loading="validating" @click="handleValidate">
          {{ t('ai.validate') }}
        </BaseButton>
      </div>
    </div>

    <!-- Parse Error Banner -->
    <div v-if="parseError" class="parse-error-banner">
      <span>{{ t('ai.specEditor.parseError') }}:</span> {{ parseError }}
    </div>

    <!-- Validation Errors -->
    <div v-if="validation && !validation.valid" class="validation-errors">
      <ul>
        <li v-for="(err, i) in validation.errors" :key="i">{{ err }}</li>
      </ul>
    </div>

    <!-- Visual Tab -->
    <div v-show="activeTab === 'visual'" class="visual-editor">
      <!-- Metadata Section -->
      <div class="editor-section">
        <div class="section-header" @click="metadataCollapsed = !metadataCollapsed">
          <span class="collapse-icon">{{ metadataCollapsed ? '▶' : '▼' }}</span>
          <h3>{{ t('ai.specEditor.metadata') }}</h3>
        </div>
        <div v-show="!metadataCollapsed" class="section-body">
          <div class="form-row">
            <div class="form-group flex-1">
              <label class="form-label">{{ t('ai.specEditor.title') }} <span class="required">*</span></label>
              <input v-model="form.metadata.title" class="form-input" :placeholder="t('ai.specEditor.titlePlaceholder')" required />
            </div>
            <div class="form-group flex-1">
              <label class="form-label">{{ t('ai.specEditor.author') }}</label>
              <input v-model="form.metadata.author" class="form-input" :placeholder="t('ai.specEditor.authorPlaceholder')" />
            </div>
            <div class="form-group" style="width: 80px">
              <label class="form-label">Version</label>
              <input v-model="form.version" class="form-input" placeholder="2" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group flex-1">
              <label class="form-label">{{ t('ai.specEditor.targetFile') }} <span class="required">*</span></label>
              <input v-model="form.metadata.target_file" class="form-input" placeholder="tests/my_tests.robot" required />
            </div>
            <div class="form-group" style="min-width: 200px">
              <label class="form-label">{{ t('ai.specEditor.environment') }}</label>
              <select
                class="form-input"
                :value="form.metadata.environment || ''"
                @change="onEnvironmentChange"
              >
                <option value="">{{ t('ai.specEditor.selectEnvironment') }}</option>
                <option
                  v-for="env in envsStore.environments"
                  :key="env.id"
                  :value="env.name"
                >
                  {{ env.name }}{{ env.is_default ? ` (${t('ai.specEditor.defaultEnvironment')})` : '' }}
                </option>
              </select>
            </div>
          </div>
          <!-- v2: External ID -->
          <div class="form-row">
            <div class="form-group flex-1">
              <label class="form-label">{{ t('ai.specEditor.externalId') }}</label>
              <input v-model="form.metadata.external_id" class="form-input" :placeholder="t('ai.specEditor.externalIdPlaceholder')" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">{{ t('ai.specEditor.libraries') }}</label>
            <div class="chips-container">
              <span v-for="(lib, i) in form.metadata.libraries" :key="i" class="chip">
                {{ lib }}
                <button class="chip-remove" @click="removeLibrary(i)">&times;</button>
              </span>
              <div class="library-autocomplete-wrapper">
                <div class="chip-input-wrapper">
                  <input
                    ref="libraryInputRef"
                    v-model="newLibrary"
                    class="chip-input"
                    :placeholder="t('ai.specEditor.addLibrary')"
                    @keydown="onLibraryKeydown"
                    @focus="onLibraryInputFocus"
                    @blur="onLibraryInputBlur"
                  />
                  <button v-if="newLibrary.trim()" class="chip-add-btn" @click="addLibrary">+</button>
                </div>
                <div
                  v-if="showLibraryDropdown && filteredSuggestions.length > 0"
                  ref="libraryDropdownRef"
                  class="library-dropdown"
                >
                  <div
                    v-for="(suggestion, idx) in filteredSuggestions"
                    :key="suggestion.name"
                    class="library-dropdown-item"
                    :class="{ active: idx === libraryDropdownIndex }"
                    @mousedown.prevent="selectSuggestion(suggestion)"
                  >
                    <span class="library-name">{{ suggestion.name }}</span>
                    <span class="library-type-badge" :class="'type-' + suggestion.type">
                      {{ suggestion.type === 'builtin' ? t('ai.specEditor.builtinLibraries') : t('ai.specEditor.installedLibraries') }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Test Sets Section -->
      <div class="editor-section">
        <div class="section-header">
          <h3>{{ t('ai.specEditor.testSets') }}</h3>
          <BaseButton size="sm" variant="secondary" @click="addTestSet">
            + {{ t('ai.specEditor.addTestSet') }}
          </BaseButton>
        </div>

        <div v-if="!form.test_sets.length" class="empty-hint">
          {{ t('ai.specEditor.noTestSets') }}
        </div>

        <div v-for="(ts, tsIndex) in form.test_sets" :key="tsIndex" class="test-set-card">
          <div class="test-set-header" @click="toggleTestSet(tsIndex)">
            <span class="collapse-icon">{{ collapsedTestSets.has(tsIndex) ? '▶' : '▼' }}</span>
            <span class="test-set-title">
              {{ ts.name || t('ai.specEditor.unnamedTestSet') }}
            </span>
            <span class="test-set-count">{{ ts.test_cases.length }} {{ t('ai.specEditor.cases') }}</span>
            <button class="remove-btn" @click.stop="removeTestSet(tsIndex)" :title="t('common.delete')">🗑</button>
          </div>

          <div v-show="!collapsedTestSets.has(tsIndex)" class="test-set-body">
            <div class="form-row">
              <div class="form-group flex-1">
                <label class="form-label">{{ t('ai.specEditor.name') }} <span class="required">*</span></label>
                <input v-model="ts.name" class="form-input" :placeholder="t('ai.specEditor.testSetNamePlaceholder')" />
              </div>
              <div class="form-group" style="width: 180px">
                <label class="form-label">{{ t('ai.specEditor.externalId') }}</label>
                <input v-model="ts.external_id" class="form-input" :placeholder="t('ai.specEditor.externalIdPlaceholder')" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">{{ t('ai.specEditor.description') }}</label>
              <textarea v-model="ts.description" class="form-input form-textarea" rows="2" :placeholder="t('ai.specEditor.descriptionPlaceholder')"></textarea>
            </div>

            <!-- Tags -->
            <div class="form-group">
              <label class="form-label">{{ t('ai.specEditor.tags') }}</label>
              <div class="chips-container">
                <span v-for="(tag, tagIdx) in ts.tags" :key="tagIdx" class="chip chip-tag">
                  {{ tag }}
                  <button class="chip-remove" @click="removeTag(tsIndex, tagIdx)">&times;</button>
                </span>
                <div class="chip-input-wrapper">
                  <input
                    :value="newTagInputs.get(tsIndex) || ''"
                    @input="newTagInputs.set(tsIndex, ($event.target as HTMLInputElement).value)"
                    class="chip-input"
                    :placeholder="t('ai.specEditor.addTag')"
                    @keydown.enter.prevent="addTag(tsIndex)"
                  />
                  <button v-if="(newTagInputs.get(tsIndex) || '').trim()" class="chip-add-btn" @click="addTag(tsIndex)">+</button>
                </div>
              </div>
            </div>

            <!-- v2: Preconditions -->
            <div class="form-group">
              <label class="form-label">{{ t('ai.specEditor.preconditions') }}</label>
              <div class="chips-container">
                <span v-for="(pre, preIdx) in ts.preconditions" :key="preIdx" class="chip chip-precondition">
                  {{ pre }}
                  <button class="chip-remove" @click="removePrecondition(ts.preconditions, preIdx)">&times;</button>
                </span>
                <div class="chip-input-wrapper">
                  <input
                    :value="newPreconditionInputs.get(`ts-${tsIndex}`) || ''"
                    @input="newPreconditionInputs.set(`ts-${tsIndex}`, ($event.target as HTMLInputElement).value)"
                    class="chip-input"
                    :placeholder="t('ai.specEditor.addPrecondition')"
                    @keydown.enter.prevent="addPrecondition(`ts-${tsIndex}`, ts.preconditions)"
                  />
                  <button v-if="(newPreconditionInputs.get(`ts-${tsIndex}`) || '').trim()" class="chip-add-btn" @click="addPrecondition(`ts-${tsIndex}`, ts.preconditions)">+</button>
                </div>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group flex-1">
                <label class="form-label">{{ t('ai.specEditor.setup') }}</label>
                <input v-model="ts.setup" class="form-input" :placeholder="t('ai.specEditor.setupPlaceholder')" />
              </div>
              <div class="form-group flex-1">
                <label class="form-label">{{ t('ai.specEditor.teardown') }}</label>
                <input v-model="ts.teardown" class="form-input" :placeholder="t('ai.specEditor.teardownPlaceholder')" />
              </div>
            </div>

            <!-- Test Cases -->
            <div class="test-cases-section">
              <div class="test-cases-header">
                <h4>{{ t('ai.specEditor.testCases') }}</h4>
                <BaseButton size="sm" variant="secondary" @click="addTestCase(tsIndex)">
                  + {{ t('ai.specEditor.addTestCase') }}
                </BaseButton>
              </div>

              <div v-if="!ts.test_cases.length" class="empty-hint">
                {{ t('ai.specEditor.noTestCases') }}
              </div>

              <div v-for="(tc, tcIndex) in ts.test_cases" :key="tcIndex" class="test-case-card">
                <div class="test-case-header" @click="toggleTestCase(tsIndex, tcIndex)">
                  <span class="collapse-icon">{{ isTestCaseCollapsed(tsIndex, tcIndex) ? '▶' : '▼' }}</span>
                  <span class="test-case-title">
                    {{ tc.name || t('ai.specEditor.unnamedTestCase') }}
                  </span>
                  <span v-if="tc.priority !== 'medium'" class="priority-badge" :class="'priority-' + tc.priority">
                    {{ tc.priority }}
                  </span>
                  <button class="remove-btn" @click.stop="removeTestCase(tsIndex, tcIndex)" :title="t('common.delete')">🗑</button>
                </div>

                <div v-show="!isTestCaseCollapsed(tsIndex, tcIndex)" class="test-case-body">
                  <div class="form-row">
                    <div class="form-group flex-1">
                      <label class="form-label">{{ t('ai.specEditor.name') }} <span class="required">*</span></label>
                      <input v-model="tc.name" class="form-input" :placeholder="t('ai.specEditor.testCaseNamePlaceholder')" />
                    </div>
                    <div class="form-group" style="width: 140px">
                      <label class="form-label">{{ t('ai.specEditor.priority') }}</label>
                      <select v-model="tc.priority" class="form-input">
                        <option value="high">{{ t('ai.specEditor.priorityHigh') }}</option>
                        <option value="medium">{{ t('ai.specEditor.priorityMedium') }}</option>
                        <option value="low">{{ t('ai.specEditor.priorityLow') }}</option>
                      </select>
                    </div>
                    <div class="form-group" style="width: 180px">
                      <label class="form-label">{{ t('ai.specEditor.externalId') }}</label>
                      <input v-model="tc.external_id" class="form-input" :placeholder="t('ai.specEditor.externalIdPlaceholder')" />
                    </div>
                  </div>
                  <div class="form-group">
                    <label class="form-label">{{ t('ai.specEditor.description') }}</label>
                    <textarea v-model="tc.description" class="form-input form-textarea" rows="2" :placeholder="t('ai.specEditor.descriptionPlaceholder')"></textarea>
                  </div>

                  <!-- v2: Test case preconditions -->
                  <div class="form-group">
                    <label class="form-label">{{ t('ai.specEditor.preconditions') }}</label>
                    <div class="chips-container">
                      <span v-for="(pre, preIdx) in tc.preconditions" :key="preIdx" class="chip chip-precondition">
                        {{ pre }}
                        <button class="chip-remove" @click="removePrecondition(tc.preconditions, preIdx)">&times;</button>
                      </span>
                      <div class="chip-input-wrapper">
                        <input
                          :value="newPreconditionInputs.get(`tc-${tsIndex}-${tcIndex}`) || ''"
                          @input="newPreconditionInputs.set(`tc-${tsIndex}-${tcIndex}`, ($event.target as HTMLInputElement).value)"
                          class="chip-input"
                          :placeholder="t('ai.specEditor.addPrecondition')"
                          @keydown.enter.prevent="addPrecondition(`tc-${tsIndex}-${tcIndex}`, tc.preconditions)"
                        />
                        <button v-if="(newPreconditionInputs.get(`tc-${tsIndex}-${tcIndex}`) || '').trim()" class="chip-add-btn" @click="addPrecondition(`tc-${tsIndex}-${tcIndex}`, tc.preconditions)">+</button>
                      </div>
                    </div>
                  </div>

                  <!-- Steps (v2: mixed string + structured) -->
                  <div class="form-group">
                    <label class="form-label">{{ t('ai.specEditor.steps') }}</label>
                    <div class="steps-list">
                      <div v-for="(step, stepIdx) in tc.steps" :key="stepIdx" class="step-row-wrapper">
                        <div class="step-row">
                          <span class="step-number">{{ stepIdx + 1 }}.</span>
                          <template v-if="!isStructuredStep(step)">
                            <input
                              :value="step as string"
                              @input="updateSimpleStep(tsIndex, tcIndex, stepIdx, ($event.target as HTMLInputElement).value)"
                              class="form-input flex-1"
                              :placeholder="t('ai.specEditor.stepPlaceholder')"
                            />
                          </template>
                          <template v-else>
                            <input
                              :value="(step as StructuredStep).action"
                              @input="updateStructuredStep(tsIndex, tcIndex, stepIdx, 'action', ($event.target as HTMLInputElement).value)"
                              class="form-input flex-1"
                              :placeholder="t('ai.specEditor.stepActionPlaceholder')"
                            />
                          </template>
                          <button
                            class="step-btn"
                            :class="{ active: isStructuredStep(step) }"
                            @click="toggleStepType(tsIndex, tcIndex, stepIdx)"
                            :title="t('ai.specEditor.toggleStructured')"
                          >
                            &#9776;
                          </button>
                          <button class="step-btn" @click="moveStep(tsIndex, tcIndex, stepIdx, -1)" :disabled="stepIdx === 0" title="Move up">↑</button>
                          <button class="step-btn" @click="moveStep(tsIndex, tcIndex, stepIdx, 1)" :disabled="stepIdx === tc.steps.length - 1" title="Move down">↓</button>
                          <button class="step-btn danger" @click="removeStep(tsIndex, tcIndex, stepIdx)" :title="t('common.delete')">&times;</button>
                        </div>
                        <!-- Structured step extra fields -->
                        <div v-if="isStructuredStep(step)" class="structured-step-fields">
                          <div class="form-group flex-1">
                            <label class="form-label-sm">{{ t('ai.specEditor.stepData') }}</label>
                            <input
                              :value="(step as StructuredStep).data"
                              @input="updateStructuredStep(tsIndex, tcIndex, stepIdx, 'data', ($event.target as HTMLInputElement).value)"
                              class="form-input"
                              :placeholder="t('ai.specEditor.stepDataPlaceholder')"
                            />
                          </div>
                          <div class="form-group flex-1">
                            <label class="form-label-sm">{{ t('ai.specEditor.stepExpectedResult') }}</label>
                            <input
                              :value="(step as StructuredStep).expected_result"
                              @input="updateStructuredStep(tsIndex, tcIndex, stepIdx, 'expected_result', ($event.target as HTMLInputElement).value)"
                              class="form-input"
                              :placeholder="t('ai.specEditor.stepExpectedResultPlaceholder')"
                            />
                          </div>
                        </div>
                      </div>
                      <button class="add-step-btn" @click="addStep(tsIndex, tcIndex)">
                        + {{ t('ai.specEditor.addStep') }}
                      </button>
                    </div>
                  </div>

                  <div class="form-group">
                    <label class="form-label">{{ t('ai.specEditor.expectedResult') }}</label>
                    <textarea v-model="tc.expected_result" class="form-input form-textarea" rows="2" :placeholder="t('ai.specEditor.expectedResultPlaceholder')"></textarea>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- YAML Tab -->
    <div v-show="activeTab === 'yaml'" class="yaml-editor" ref="yamlEditorContainer"></div>
  </div>
</template>

<style scoped>
.spec-editor {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* Tab Bar */
.spec-tabs {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.tab-buttons {
  display: flex;
  gap: 0;
}

.tab-btn {
  padding: 8px 16px;
  border: none;
  background: transparent;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.15s ease;
}

.tab-btn:hover {
  color: var(--color-text);
  background: rgba(59, 125, 216, 0.05);
}

.tab-btn.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.tab-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

/* Badges */
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge-spec {
  background: #f0e6ff;
  color: #7c3aed;
}

.badge-info {
  background: #e8f0fe;
  color: var(--color-primary);
}

.badge-success {
  background: #e8f5e9;
  color: var(--color-success);
}

.badge-danger {
  background: #fce4e4;
  color: var(--color-danger);
}

/* Error banners */
.parse-error-banner {
  padding: 8px 12px;
  background: #fff3cd;
  border-bottom: 1px solid #ffc107;
  font-size: 13px;
  color: #856404;
  flex-shrink: 0;
}

.parse-error-banner span {
  font-weight: 600;
}

.validation-errors {
  padding: 8px 12px;
  background: #fce4e4;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.validation-errors ul {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  color: var(--color-danger);
}

/* Visual Editor */
.visual-editor {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.editor-section {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: visible;
  flex-shrink: 0;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  user-select: none;
}

.section-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.section-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.collapse-icon {
  font-size: 10px;
  margin-right: 8px;
  color: var(--color-text-muted);
}

/* Form Elements */
.form-row {
  display: flex;
  gap: 12px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.flex-1 {
  flex: 1;
}

.form-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-muted);
}

.form-label-sm {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-muted);
}

.required {
  color: var(--color-danger);
}

.form-input {
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 13px;
  background: var(--color-bg-card);
  color: var(--color-text);
  transition: border-color 0.15s;
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(59, 125, 216, 0.15);
}

.form-textarea {
  resize: vertical;
  min-height: 40px;
  font-family: inherit;
}

/* Chips/Tags */
.chips-container {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  background: #e8f0fe;
  color: var(--color-primary);
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.chip-tag {
  background: #f0e6ff;
  color: #7c3aed;
}

.chip-precondition {
  background: #fff3e0;
  color: #e65100;
}

.chip-remove {
  border: none;
  background: none;
  color: inherit;
  font-size: 14px;
  cursor: pointer;
  padding: 0 2px;
  opacity: 0.7;
  line-height: 1;
}

.chip-remove:hover {
  opacity: 1;
}

.chip-input-wrapper {
  display: flex;
  align-items: center;
  gap: 4px;
}

.chip-input {
  border: 1px dashed var(--color-border);
  border-radius: 12px;
  padding: 3px 10px;
  font-size: 12px;
  background: transparent;
  color: var(--color-text);
  width: 140px;
  outline: none;
}

.chip-input:focus {
  border-color: var(--color-primary);
}

.chip-add-btn {
  border: none;
  background: var(--color-primary);
  color: white;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

/* Test Set Cards */
.test-set-card {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin: 8px 14px;
  overflow: hidden;
}

.test-set-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  user-select: none;
}

.test-set-title {
  flex: 1;
  font-weight: 500;
  font-size: 13px;
}

.test-set-count {
  font-size: 11px;
  color: var(--color-text-muted);
  padding: 1px 8px;
  background: rgba(59, 125, 216, 0.1);
  border-radius: 8px;
}

.test-set-body {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.remove-btn {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 14px;
  padding: 2px 4px;
  opacity: 0.5;
  transition: opacity 0.15s;
}

.remove-btn:hover {
  opacity: 1;
}

/* Test Cases */
.test-cases-section {
  border-top: 1px solid var(--color-border);
  padding-top: 10px;
}

.test-cases-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.test-cases-header h4 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-muted);
}

.test-case-card {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  margin-bottom: 8px;
  overflow: hidden;
}

.test-case-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  user-select: none;
}

.test-case-title {
  flex: 1;
  font-size: 13px;
  font-weight: 450;
}

.priority-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 8px;
  text-transform: uppercase;
}

.priority-high {
  background: #fce4e4;
  color: var(--color-danger);
}

.priority-low {
  background: #e8f5e9;
  color: var(--color-success);
}

.test-case-body {
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Steps */
.steps-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.step-row-wrapper {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.step-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.step-number {
  font-size: 12px;
  color: var(--color-text-muted);
  width: 20px;
  text-align: right;
  flex-shrink: 0;
}

.step-btn {
  border: 1px solid var(--color-border);
  background: var(--color-bg-card);
  color: var(--color-text-muted);
  width: 26px;
  height: 26px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-btn:hover:not(:disabled) {
  background: var(--color-bg);
  color: var(--color-text);
}

.step-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.step-btn.danger:hover {
  color: var(--color-danger);
  border-color: var(--color-danger);
}

.step-btn.active {
  background: rgba(59, 125, 216, 0.1);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.structured-step-fields {
  display: flex;
  gap: 8px;
  margin-left: 26px;
  padding: 6px 8px;
  background: var(--color-bg);
  border-radius: 6px;
  border: 1px dashed var(--color-border);
}

.add-step-btn {
  border: 1px dashed var(--color-border);
  background: transparent;
  color: var(--color-text-muted);
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  text-align: left;
}

.add-step-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

/* Empty hints */
.empty-hint {
  padding: 16px;
  text-align: center;
  color: var(--color-text-muted);
  font-size: 13px;
  font-style: italic;
}

/* Library Autocomplete */
.library-autocomplete-wrapper {
  position: relative;
}

.library-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 50;
  min-width: 240px;
  max-height: 220px;
  overflow-y: auto;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  margin-top: 4px;
}

.library-dropdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.1s;
}

.library-dropdown-item:hover,
.library-dropdown-item.active {
  background: rgba(59, 125, 216, 0.08);
}

.library-name {
  font-weight: 500;
  color: var(--color-text);
}

.library-type-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 8px;
  text-transform: uppercase;
  flex-shrink: 0;
  margin-left: 8px;
}

.library-type-badge.type-builtin {
  background: #e8f5e9;
  color: var(--color-success, #2e7d32);
}

.library-type-badge.type-installed {
  background: #e8f0fe;
  color: var(--color-primary);
}

/* YAML Editor */
.yaml-editor {
  flex: 1;
  overflow: hidden;
}

.yaml-editor :deep(.cm-editor) {
  height: 100%;
}
</style>
