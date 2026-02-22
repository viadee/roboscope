<script setup lang="ts">
import { ref, reactive, watch, computed, nextTick, onMounted, onUnmounted, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import { robotLanguage } from '@/utils/robotLanguage'
import { RF_KEYWORD_SIGNATURES } from '@/utils/robotKeywordSignatures'

// CodeMirror imports
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightSpecialChars } from '@codemirror/view'
import { EditorState } from '@codemirror/state'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { LanguageSupport } from '@codemirror/language'
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

// --- Step Types ---
type StepType = 'keyword' | 'assignment' | 'for' | 'end' | 'if' | 'else_if' | 'else'
  | 'while' | 'try' | 'except' | 'finally' | 'break' | 'continue' | 'return' | 'comment'

const STEP_TYPES: StepType[] = [
  'keyword', 'assignment', 'comment',
  'for', 'if', 'else_if', 'else', 'while',
  'try', 'except', 'finally',
  'end', 'break', 'continue', 'return',
]

const LOOP_FLAVORS = ['IN', 'IN RANGE', 'IN ENUMERATE', 'IN ZIP']

// --- Interfaces ---
interface RobotSettingEntry { key: string; value: string; args: string[] }
interface RobotVariable { name: string; value: string }

interface RobotStep {
  type: StepType
  keyword: string        // keyword/assignment: the keyword name
  args: string[]         // keyword/assignment/return: arguments
  returnVars: string[]   // assignment: ['${var1}', '${var2}']
  condition: string      // if/else_if/while: condition expression
  loopVar: string        // for: loop variable e.g. ${item}
  loopFlavor: string     // for: IN | IN RANGE | IN ENUMERATE | IN ZIP
  loopValues: string[]   // for: iteration values
  exceptPattern: string  // except: error pattern
  exceptVar: string      // except: AS ${var}
  comment: string        // comment: text
}

interface RobotTestCase {
  name: string; documentation: string; tags: string[]
  setup: string; teardown: string; timeout: string; template: string
  steps: RobotStep[]
}
interface RobotKeyword {
  name: string; documentation: string; arguments: string; tags: string[]
  setup: string; teardown: string; timeout: string; returnValue: string
  steps: RobotStep[]
}
interface RobotForm {
  settings: RobotSettingEntry[]
  variables: RobotVariable[]
  testCases: RobotTestCase[]
  keywords: RobotKeyword[]
  preambleLines: string[]
}

function makeStep(type: StepType = 'keyword'): RobotStep {
  return {
    type, keyword: '', args: [], returnVars: [],
    condition: '', loopVar: '${item}', loopFlavor: 'IN', loopValues: [],
    exceptPattern: '', exceptVar: '', comment: '',
  }
}

// --- State ---
const activeTab = ref<'visual' | 'code'>('visual')
const parseError = ref<string | null>(null)
const codeEditorContainer = ref<HTMLElement | null>(null)
const codeEditorView = shallowRef<EditorView | null>(null)
const internalCode = ref('')

// Collapsible state
const settingsCollapsed = ref(false)
const variablesCollapsed = ref(false)
const testCasesCollapsed = ref(false)
const keywordsCollapsed = ref(false)
const collapsedTestCases = ref<Set<number>>(new Set())
const collapsedKeywords = ref<Set<number>>(new Set())

// Keyword autocomplete state
const activeAutocompleteStep = ref<RobotStep | null>(null)
const keywordQuery = ref('')
const keywordDropdownIndex = ref(-1)
const keywordDropdownRef = ref<HTMLElement | null>(null)

// --- Form State ---
const form = reactive<RobotForm>({
  settings: [],
  variables: [],
  testCases: [],
  keywords: [],
  preambleLines: [],
})

// --- Computed ---
const isResource = computed(() => {
  return props.filePath?.toLowerCase().endsWith('.resource') ?? false
})

const testCaseCount = computed(() => form.testCases.length)
const keywordCount = computed(() => form.keywords.length)

// --- Step line parser ---
function parseStepLine(raw: string): RobotStep {
  const step = makeStep()
  const trimmed = raw.trim()
  if (!trimmed) return step

  // Comment
  if (trimmed.startsWith('#')) {
    step.type = 'comment'
    step.comment = trimmed
    return step
  }

  // Split into cells on 2+ spaces or tab
  const cells = trimmed.split(/  +|\t+/).filter(c => c !== '')
  if (cells.length === 0) return step

  const first = cells[0]

  // Control flow markers
  if (first === 'FOR') {
    step.type = 'for'
    step.loopVar = cells[1] || '${item}'
    // Find the flavor: cells[2] could be 'IN', 'IN RANGE', etc.
    // Since we split on 2+ spaces, 'IN RANGE' stays as one cell (single space)
    const flavor = cells[2] || 'IN'
    step.loopFlavor = LOOP_FLAVORS.includes(flavor) ? flavor : 'IN'
    step.loopValues = cells.slice(3)
    return step
  }
  if (first === 'END') { step.type = 'end'; return step }
  if (first === 'IF') {
    step.type = 'if'
    step.condition = cells.slice(1).join('    ')
    return step
  }
  if (first === 'ELSE IF') {
    step.type = 'else_if'
    step.condition = cells.slice(1).join('    ')
    return step
  }
  if (first === 'ELSE') { step.type = 'else'; return step }
  if (first === 'WHILE') {
    step.type = 'while'
    step.condition = cells.slice(1).join('    ')
    return step
  }
  if (first === 'TRY') { step.type = 'try'; return step }
  if (first === 'EXCEPT') {
    step.type = 'except'
    const asIdx = cells.indexOf('AS')
    if (asIdx > 1) {
      step.exceptPattern = cells.slice(1, asIdx).join('    ')
      step.exceptVar = cells[asIdx + 1] || ''
    } else {
      step.exceptPattern = cells.slice(1).join('    ')
    }
    return step
  }
  if (first === 'FINALLY') { step.type = 'finally'; return step }
  if (first === 'BREAK') { step.type = 'break'; return step }
  if (first === 'CONTINUE') { step.type = 'continue'; return step }
  if (first === 'RETURN') {
    step.type = 'return'
    step.args = cells.slice(1)
    return step
  }

  // Check for variable assignment: ${var}=  Keyword  args
  // or multi-assign: ${a}  ${b}=  Keyword  args
  const VAR_RE = /^[$@&%]\{[^}]+\}=?$/
  const returnVars: string[] = []
  let keywordIdx = 0
  for (let i = 0; i < cells.length; i++) {
    if (VAR_RE.test(cells[i])) {
      const varName = cells[i].replace(/=$/, '')
      returnVars.push(varName)
      if (cells[i].endsWith('=')) {
        keywordIdx = i + 1
        break
      }
    } else {
      keywordIdx = i
      break
    }
  }

  if (returnVars.length > 0 && keywordIdx < cells.length) {
    step.type = 'assignment'
    step.returnVars = returnVars
    step.keyword = cells[keywordIdx]
    step.args = cells.slice(keywordIdx + 1)
    return step
  }

  // Regular keyword call
  step.type = 'keyword'
  step.keyword = cells[0]
  step.args = cells.slice(1)
  return step
}

// --- Step serializer ---
const SEP = '    '

function serializeStep(step: RobotStep): string {
  switch (step.type) {
    case 'keyword':
      return [step.keyword, ...step.args].filter(Boolean).join(SEP)
    case 'assignment': {
      const vars = step.returnVars.map((v, i) =>
        i === step.returnVars.length - 1 ? v + '=' : v
      )
      return [...vars, step.keyword, ...step.args].filter(Boolean).join(SEP)
    }
    case 'for':
      return ['FOR', step.loopVar, step.loopFlavor, ...step.loopValues].filter(Boolean).join(SEP)
    case 'end': return 'END'
    case 'if':
      return ['IF', step.condition].filter(Boolean).join(SEP)
    case 'else_if':
      return ['ELSE IF', step.condition].filter(Boolean).join(SEP)
    case 'else': return 'ELSE'
    case 'while':
      return ['WHILE', step.condition].filter(Boolean).join(SEP)
    case 'try': return 'TRY'
    case 'except': {
      const parts = ['EXCEPT']
      if (step.exceptPattern) parts.push(step.exceptPattern)
      if (step.exceptVar) parts.push('AS', step.exceptVar)
      return parts.join(SEP)
    }
    case 'finally': return 'FINALLY'
    case 'break': return 'BREAK'
    case 'continue': return 'CONTINUE'
    case 'return':
      return ['RETURN', ...step.args].filter(Boolean).join(SEP)
    case 'comment':
      return step.comment || '# '
    default:
      return ''
  }
}

// --- Main Parser ---
const SECTION_HEADER_RE = /^\*{3}\s*(Settings?|Variables?|Test Cases?|Tasks?|Keywords?)\s*\*{0,3}/i

function parseRobotToForm(content: string): boolean {
  try {
    const lines = content.split('\n')
    const newForm: RobotForm = {
      settings: [], variables: [], testCases: [], keywords: [], preambleLines: [],
    }

    let currentSection: 'none' | 'settings' | 'variables' | 'testcases' | 'keywords' = 'none'
    let currentItem: RobotTestCase | RobotKeyword | null = null
    let currentItemType: 'testcase' | 'keyword' | null = null

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      const trimmed = line.trimEnd()

      // Section header
      const headerMatch = trimmed.match(SECTION_HEADER_RE)
      if (headerMatch) {
        if (currentItem && currentItemType) {
          if (currentItemType === 'testcase') newForm.testCases.push(currentItem as RobotTestCase)
          else newForm.keywords.push(currentItem as RobotKeyword)
          currentItem = null
          currentItemType = null
        }
        const sectionName = headerMatch[1].toLowerCase()
        if (sectionName.startsWith('setting')) currentSection = 'settings'
        else if (sectionName.startsWith('variable')) currentSection = 'variables'
        else if (sectionName.startsWith('test') || sectionName.startsWith('task')) currentSection = 'testcases'
        else if (sectionName.startsWith('keyword')) currentSection = 'keywords'
        continue
      }

      if (currentSection === 'none') {
        newForm.preambleLines.push(trimmed)
        continue
      }

      if (currentSection === 'settings') {
        if (!trimmed || trimmed.startsWith('#')) {
          if (trimmed.startsWith('#')) {
            newForm.settings.push({ key: '#', value: trimmed, args: [] })
          }
          continue
        }
        const parts = trimmed.split(/  +|\t+/).filter(p => p !== '')
        if (parts.length >= 1) {
          newForm.settings.push({ key: parts[0], value: parts[1] || '', args: parts.slice(2) })
        }
        continue
      }

      if (currentSection === 'variables') {
        if (!trimmed || trimmed.startsWith('#')) {
          if (trimmed.startsWith('#')) {
            newForm.variables.push({ name: '#', value: trimmed })
          }
          continue
        }
        const parts = trimmed.split(/  +|\t+/).filter(p => p !== '')
        if (parts.length >= 1) {
          newForm.variables.push({ name: parts[0], value: parts.slice(1).join(SEP) })
        }
        continue
      }

      if (currentSection === 'testcases' || currentSection === 'keywords') {
        if (!trimmed) continue

        const isIndented = /^\s/.test(line) || line.startsWith('\t')

        if (!isIndented && trimmed) {
          if (currentItem && currentItemType) {
            if (currentItemType === 'testcase') newForm.testCases.push(currentItem as RobotTestCase)
            else newForm.keywords.push(currentItem as RobotKeyword)
          }
          if (currentSection === 'testcases') {
            currentItem = {
              name: trimmed, documentation: '', tags: [],
              setup: '', teardown: '', timeout: '', template: '', steps: [],
            }
            currentItemType = 'testcase'
          } else {
            currentItem = {
              name: trimmed, documentation: '', arguments: '', tags: [],
              setup: '', teardown: '', timeout: '', returnValue: '', steps: [],
            }
            currentItemType = 'keyword'
          }
          continue
        }

        if (currentItem && isIndented) {
          const bodyTrimmed = trimmed.trim()

          // Continuation line
          if (bodyTrimmed.startsWith('...')) {
            const contCells = bodyTrimmed.slice(3).trim().split(/  +|\t+/).filter(c => c !== '')
            if (currentItem.steps.length > 0) {
              const prev = currentItem.steps[currentItem.steps.length - 1]
              switch (prev.type) {
                case 'keyword':
                case 'assignment':
                case 'return':
                  prev.args.push(...contCells)
                  break
                case 'for':
                  prev.loopValues.push(...contCells)
                  break
                default:
                  // Append to condition or treat as extra text
                  if (prev.condition !== undefined && contCells.length) {
                    prev.condition += SEP + contCells.join(SEP)
                  }
              }
            } else if (currentItem.documentation) {
              currentItem.documentation += '\n' + contCells.join(' ')
            }
            continue
          }

          // Setting tags: [Documentation], [Tags], etc.
          const settingMatch = bodyTrimmed.match(/^\[(Documentation|Tags|Setup|Teardown|Timeout|Template|Arguments|Return)\]\s*(.*)/i)
          if (settingMatch) {
            const settingName = settingMatch[1].toLowerCase()
            const settingValue = settingMatch[2]?.trim() || ''
            switch (settingName) {
              case 'documentation': currentItem.documentation = settingValue; break
              case 'tags': currentItem.tags = settingValue ? settingValue.split(/  +|\t+/).map(t => t.trim()).filter(Boolean) : []; break
              case 'setup': currentItem.setup = settingValue; break
              case 'teardown': currentItem.teardown = settingValue; break
              case 'timeout': currentItem.timeout = settingValue; break
              case 'template':
                if ('template' in currentItem) (currentItem as RobotTestCase).template = settingValue
                break
              case 'arguments':
                if ('arguments' in currentItem) (currentItem as RobotKeyword).arguments = settingValue
                break
              case 'return':
                if ('returnValue' in currentItem) (currentItem as RobotKeyword).returnValue = settingValue
                break
            }
            continue
          }

          // Parse structured step
          currentItem.steps.push(parseStepLine(bodyTrimmed))
        }
        continue
      }
    }

    // Flush last item
    if (currentItem && currentItemType) {
      if (currentItemType === 'testcase') newForm.testCases.push(currentItem as RobotTestCase)
      else newForm.keywords.push(currentItem as RobotKeyword)
    }

    form.settings = newForm.settings
    form.variables = newForm.variables
    form.testCases = newForm.testCases
    form.keywords = newForm.keywords
    form.preambleLines = newForm.preambleLines
    parseError.value = null
    return true
  } catch (e: any) {
    parseError.value = e.message || 'Failed to parse Robot Framework file'
    return false
  }
}

// --- Main Serializer ---
function serializeFormToRobot(): string {
  const lines: string[] = []

  for (const pl of form.preambleLines) lines.push(pl)

  if (form.settings.length > 0) {
    if (lines.length > 0 && lines[lines.length - 1] !== '') lines.push('')
    lines.push('*** Settings ***')
    for (const s of form.settings) {
      if (s.key === '#') { lines.push(s.value); continue }
      let line = s.key
      if (s.value) line += SEP + s.value
      for (const a of s.args) line += SEP + a
      lines.push(line)
    }
  }

  if (form.variables.length > 0) {
    if (lines.length > 0 && lines[lines.length - 1] !== '') lines.push('')
    lines.push('*** Variables ***')
    for (const v of form.variables) {
      if (v.name === '#') { lines.push(v.value); continue }
      lines.push(v.value ? v.name + SEP + v.value : v.name)
    }
  }

  if (!isResource.value && form.testCases.length > 0) {
    if (lines.length > 0 && lines[lines.length - 1] !== '') lines.push('')
    lines.push('*** Test Cases ***')
    for (const tc of form.testCases) {
      lines.push(tc.name)
      if (tc.documentation) lines.push(SEP + '[Documentation]' + SEP + tc.documentation)
      if (tc.tags.length > 0) lines.push(SEP + '[Tags]' + SEP + tc.tags.join(SEP))
      if (tc.setup) lines.push(SEP + '[Setup]' + SEP + tc.setup)
      if (tc.teardown) lines.push(SEP + '[Teardown]' + SEP + tc.teardown)
      if (tc.timeout) lines.push(SEP + '[Timeout]' + SEP + tc.timeout)
      if (tc.template) lines.push(SEP + '[Template]' + SEP + tc.template)
      for (const step of tc.steps) lines.push(SEP + serializeStep(step))
      lines.push('')
    }
  }

  if (form.keywords.length > 0) {
    if (lines.length > 0 && lines[lines.length - 1] !== '') lines.push('')
    lines.push('*** Keywords ***')
    for (const kw of form.keywords) {
      lines.push(kw.name)
      if (kw.arguments) lines.push(SEP + '[Arguments]' + SEP + kw.arguments)
      if (kw.documentation) lines.push(SEP + '[Documentation]' + SEP + kw.documentation)
      if (kw.tags.length > 0) lines.push(SEP + '[Tags]' + SEP + kw.tags.join(SEP))
      if (kw.setup) lines.push(SEP + '[Setup]' + SEP + kw.setup)
      if (kw.teardown) lines.push(SEP + '[Teardown]' + SEP + kw.teardown)
      if (kw.timeout) lines.push(SEP + '[Timeout]' + SEP + kw.timeout)
      if (kw.returnValue) lines.push(SEP + '[Return]' + SEP + kw.returnValue)
      for (const step of kw.steps) lines.push(SEP + serializeStep(step))
      lines.push('')
    }
  }

  let result = lines.join('\n')
  result = result.replace(/\n{3,}/g, '\n\n')
  if (!result.endsWith('\n')) result += '\n'
  return result
}

// --- Tab Switching ---
function switchTab(tab: 'visual' | 'code') {
  if (tab === activeTab.value) return
  if (tab === 'code') {
    internalCode.value = serializeFormToRobot()
    activeTab.value = 'code'
    parseError.value = null
    nextTick(() => initCodeEditor())
  } else {
    const currentCode = getCodeEditorContent()
    if (parseRobotToForm(currentCode)) {
      activeTab.value = 'visual'
      destroyCodeEditor()
    }
  }
}

function getCodeEditorContent(): string {
  return codeEditorView.value?.state.doc.toString() ?? internalCode.value
}

// --- Code CodeMirror ---
function initCodeEditor() {
  destroyCodeEditor()
  if (!codeEditorContainer.value) return

  const state = EditorState.create({
    doc: internalCode.value,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      highlightSpecialChars(),
      history(),
      keymap.of([...defaultKeymap, ...historyKeymap]),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      new LanguageSupport(robotLanguage()),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          const content = update.state.doc.toString()
          internalCode.value = content
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

  codeEditorView.value = new EditorView({ state, parent: codeEditorContainer.value })
}

function destroyCodeEditor() {
  if (codeEditorView.value) { codeEditorView.value.destroy(); codeEditorView.value = null }
}

// --- Content sync ---
let lastEmittedContent = ''
function emitContent(content: string) { emit('update:content', content) }
function emitFormContent() {
  const code = serializeFormToRobot()
  lastEmittedContent = code
  emitContent(code)
}

// --- Form watchers ---
watch(() => form.settings, () => { if (activeTab.value === 'visual') emitFormContent() }, { deep: true })
watch(() => form.variables, () => { if (activeTab.value === 'visual') emitFormContent() }, { deep: true })
watch(() => form.testCases, () => { if (activeTab.value === 'visual') emitFormContent() }, { deep: true })
watch(() => form.keywords, () => { if (activeTab.value === 'visual') emitFormContent() }, { deep: true })

// --- Known RF Libraries (for Library setting autocomplete) ---
const RF_LIBRARIES = [
  'BuiltIn', 'Collections', 'String', 'OperatingSystem', 'Process',
  'DateTime', 'XML', 'Dialogs', 'Screenshot', 'Telnet', 'Remote',
  'SeleniumLibrary', 'Browser', 'RequestsLibrary', 'DatabaseLibrary',
  'SSHLibrary', 'FTPLibrary', 'ExcelLibrary', 'JSONLibrary',
  'AppiumLibrary', 'SwingLibrary', 'SikuliLibrary', 'ImapLibrary',
  'ArchiveLibrary', 'CryptoLibrary', 'RESTinstance',
]

// Library autocomplete state for settings
const activeLibrarySettingIdx = ref<number | null>(null)
const librarySettingQuery = ref('')
const librarySettingDropdownIndex = ref(-1)
const librarySettingDropdownRef = ref<HTMLElement | null>(null)

const filteredLibrarySuggestions = computed(() => {
  const query = librarySettingQuery.value.toLowerCase().trim()
  return RF_LIBRARIES
    .filter(l => !query || l.toLowerCase().includes(query))
    .slice(0, 15)
})

function onLibrarySettingFocus(sIdx: number) {
  activeLibrarySettingIdx.value = sIdx
  librarySettingQuery.value = form.settings[sIdx].value
  librarySettingDropdownIndex.value = -1
}

function onLibrarySettingBlur(event: FocusEvent) {
  const related = event.relatedTarget as HTMLElement | null
  if (related && librarySettingDropdownRef.value?.contains(related)) return
  setTimeout(() => { activeLibrarySettingIdx.value = null }, 150)
}

function onLibrarySettingInput(sIdx: number) {
  librarySettingQuery.value = form.settings[sIdx].value
  librarySettingDropdownIndex.value = -1
  activeLibrarySettingIdx.value = sIdx
}

function onLibrarySettingKeydown(event: KeyboardEvent, sIdx: number) {
  const items = filteredLibrarySuggestions.value
  if (event.key === 'Enter') {
    event.preventDefault()
    if (librarySettingDropdownIndex.value >= 0 && librarySettingDropdownIndex.value < items.length) {
      selectLibrarySuggestion(sIdx, items[librarySettingDropdownIndex.value])
    }
    return
  }
  if (!items.length) return
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeLibrarySettingIdx.value = sIdx
    librarySettingDropdownIndex.value = Math.min(librarySettingDropdownIndex.value + 1, items.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    librarySettingDropdownIndex.value = Math.max(librarySettingDropdownIndex.value - 1, 0)
  } else if (event.key === 'Escape') {
    activeLibrarySettingIdx.value = null
    librarySettingDropdownIndex.value = -1
  }
}

function selectLibrarySuggestion(sIdx: number, name: string) {
  form.settings[sIdx].value = name
  activeLibrarySettingIdx.value = null
  librarySettingDropdownIndex.value = -1
  librarySettingQuery.value = ''
}

// --- Settings helpers ---
const SETTING_TYPES = [
  'Documentation', 'Library', 'Resource', 'Variables',
  'Suite Setup', 'Suite Teardown',
  'Test Setup', 'Test Teardown',
  'Test Template', 'Test Timeout',
  'Force Tags', 'Default Tags', 'Metadata',
]
function addSetting() { form.settings.push({ key: 'Library', value: '', args: [] }) }
function removeSetting(i: number) { form.settings.splice(i, 1) }
function addSettingArg(i: number) { form.settings[i].args.push('') }
function removeSettingArg(si: number, ai: number) { form.settings[si].args.splice(ai, 1) }

// --- Variable helpers ---
function addVariable() { form.variables.push({ name: '${NEW_VAR}', value: '' }) }
function removeVariable(i: number) { form.variables.splice(i, 1) }

// --- Generic step helpers ---
function addStep(steps: RobotStep[], type: StepType = 'keyword') {
  steps.push(makeStep(type))
}

function addBlock(steps: RobotStep[], blockType: 'for' | 'if' | 'while' | 'try') {
  const block = makeStep(blockType)
  steps.push(block)
  // Add a placeholder keyword step inside the block
  steps.push(makeStep('keyword'))
  // Add closing END
  steps.push(makeStep('end'))
}

function removeStep(steps: RobotStep[], i: number) { steps.splice(i, 1) }

function moveStep(steps: RobotStep[], i: number, dir: -1 | 1) {
  const j = i + dir
  if (j < 0 || j >= steps.length) return
  const tmp = steps[i]; steps[i] = steps[j]; steps[j] = tmp
}

function addStepArg(step: RobotStep) { step.args.push('') }
function removeStepArg(step: RobotStep, i: number) { step.args.splice(i, 1) }
function addReturnVar(step: RobotStep) { step.returnVars.push('${var}') }
function removeReturnVar(step: RobotStep, i: number) { step.returnVars.splice(i, 1) }
function addLoopValue(step: RobotStep) { step.loopValues.push('') }
function removeLoopValue(step: RobotStep, i: number) { step.loopValues.splice(i, 1) }

// When step type changes, reset irrelevant fields
function onStepTypeChange(step: RobotStep) {
  // Preserve keyword/args when switching between keyword and assignment
  if (step.type === 'keyword') {
    step.returnVars = []
  } else if (step.type === 'assignment') {
    if (step.returnVars.length === 0) step.returnVars = ['${result}']
  } else if (step.type === 'for') {
    if (!step.loopVar) step.loopVar = '${item}'
    if (!step.loopFlavor) step.loopFlavor = 'IN'
  } else if (step.type === 'comment') {
    if (!step.comment) step.comment = '# '
  }
}

// Step type display helpers
function stepTypeLabel(type: StepType): string {
  return t('robotEditor.stepType.' + type)
}

function stepTypeColor(type: StepType): string {
  switch (type) {
    case 'keyword': return 'type-keyword'
    case 'assignment': return 'type-assign'
    case 'for': case 'while': return 'type-loop'
    case 'if': case 'else_if': case 'else': return 'type-condition'
    case 'try': case 'except': case 'finally': return 'type-error'
    case 'end': case 'break': case 'continue': case 'return': return 'type-flow'
    case 'comment': return 'type-comment'
    default: return ''
  }
}

// Is this step type a "block opener" that indents the next lines visually?
function isBlockOpener(type: StepType): boolean {
  return ['for', 'if', 'else_if', 'else', 'while', 'try', 'except', 'finally'].includes(type)
}

function isBlockCloser(type: StepType): boolean {
  return type === 'end'
}

// Calculate visual indent level for a step based on preceding steps
function stepIndent(steps: RobotStep[], index: number): number {
  let level = 0
  for (let i = 0; i < index; i++) {
    if (isBlockOpener(steps[i].type)) level++
    if (isBlockCloser(steps[i].type)) level = Math.max(0, level - 1)
  }
  // END itself reduces indent
  if (isBlockCloser(steps[index].type)) level = Math.max(0, level - 1)
  // ELSE / ELSE IF / EXCEPT / FINALLY are at same level as IF / TRY
  if (['else', 'else_if', 'except', 'finally'].includes(steps[index].type)) {
    level = Math.max(0, level - 1)
  }
  return level
}

// --- Keyword Autocomplete ---
interface KeywordSuggestion { name: string; source: 'builtin' | 'local' }

// Build title-cased display names for RF built-in keywords
const rfBuiltinSuggestions = computed<KeywordSuggestion[]>(() => {
  const result: KeywordSuggestion[] = []
  for (const key of RF_KEYWORD_SIGNATURES.keys()) {
    const titleCase = key.replace(/\b\w/g, c => c.toUpperCase())
    result.push({ name: titleCase, source: 'builtin' })
  }
  return result
})

const filteredKeywordSuggestions = computed<KeywordSuggestion[]>(() => {
  const query = keywordQuery.value.toLowerCase().trim()
  const suggestions: KeywordSuggestion[] = [...rfBuiltinSuggestions.value]
  // Add local keywords from the file
  for (const kw of form.keywords) {
    if (kw.name && !suggestions.some(s => s.name.toLowerCase() === kw.name.toLowerCase())) {
      suggestions.push({ name: kw.name, source: 'local' })
    }
  }
  return suggestions
    .filter(s => !query || s.name.toLowerCase().includes(query))
    .slice(0, 15)
})

function onKeywordInputFocus(step: RobotStep) {
  activeAutocompleteStep.value = step
  keywordQuery.value = step.keyword
  keywordDropdownIndex.value = -1
}

function onKeywordInputBlur(event: FocusEvent) {
  const related = event.relatedTarget as HTMLElement | null
  if (related && keywordDropdownRef.value?.contains(related)) return
  setTimeout(() => { activeAutocompleteStep.value = null }, 150)
}

function onKeywordInput(step: RobotStep) {
  keywordQuery.value = step.keyword
  keywordDropdownIndex.value = -1
  activeAutocompleteStep.value = step
}

function onKeywordKeydown(event: KeyboardEvent, step: RobotStep) {
  const items = filteredKeywordSuggestions.value
  if (event.key === 'Enter') {
    event.preventDefault()
    if (keywordDropdownIndex.value >= 0 && keywordDropdownIndex.value < items.length) {
      selectKeywordSuggestion(step, items[keywordDropdownIndex.value])
    }
    return
  }
  if (!items.length) return
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeAutocompleteStep.value = step
    keywordDropdownIndex.value = Math.min(keywordDropdownIndex.value + 1, items.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    keywordDropdownIndex.value = Math.max(keywordDropdownIndex.value - 1, 0)
  } else if (event.key === 'Escape') {
    activeAutocompleteStep.value = null
    keywordDropdownIndex.value = -1
  }
}

function selectKeywordSuggestion(step: RobotStep, suggestion: KeywordSuggestion) {
  step.keyword = suggestion.name
  activeAutocompleteStep.value = null
  keywordDropdownIndex.value = -1
  keywordQuery.value = ''
  // Auto-populate arg slots from signature
  const sig = getKeywordArgNames(step)
  const requiredCount = sig.filter(a => !a.includes('=') && !a.startsWith('*')).length
  while (step.args.length < requiredCount) {
    step.args.push('')
  }
}

// --- Argument Name Labels ---
function getKeywordArgNames(step: RobotStep): string[] {
  const kw = step.keyword.toLowerCase().trim()
  const builtin = RF_KEYWORD_SIGNATURES.get(kw)
  if (builtin) return builtin
  const localKw = form.keywords.find(k => k.name.toLowerCase() === kw)
  if (localKw?.arguments) {
    return localKw.arguments.split(/  +|\t+/)
      .filter(Boolean)
      .map(a => a.replace(/^[$@&%]\{([^}]+)\}$/, '$1'))
  }
  return []
}

// --- Test Case helpers ---
function addTestCase() {
  form.testCases.push({
    name: '', documentation: '', tags: [],
    setup: '', teardown: '', timeout: '', template: '', steps: [],
  })
}
function removeTestCase(i: number) { form.testCases.splice(i, 1); collapsedTestCases.value.delete(i) }
function toggleTestCase(i: number) {
  if (collapsedTestCases.value.has(i)) collapsedTestCases.value.delete(i)
  else collapsedTestCases.value.add(i)
}

// Test case tag helpers
const newTestCaseTagInputs = ref<Map<number, string>>(new Map())
function addTestCaseTag(tcIndex: number, tag: string) {
  if (tag.trim() && !form.testCases[tcIndex].tags.includes(tag.trim()))
    form.testCases[tcIndex].tags.push(tag.trim())
}
function removeTestCaseTag(tcIndex: number, tagIdx: number) { form.testCases[tcIndex].tags.splice(tagIdx, 1) }
function handleAddTestCaseTag(tcIndex: number) {
  addTestCaseTag(tcIndex, newTestCaseTagInputs.value.get(tcIndex) || '')
  newTestCaseTagInputs.value.set(tcIndex, '')
}

// --- Keyword helpers ---
function addKeyword() {
  form.keywords.push({
    name: '', documentation: '', arguments: '', tags: [],
    setup: '', teardown: '', timeout: '', returnValue: '', steps: [],
  })
}
function removeKeyword(i: number) { form.keywords.splice(i, 1); collapsedKeywords.value.delete(i) }
function toggleKeyword(i: number) {
  if (collapsedKeywords.value.has(i)) collapsedKeywords.value.delete(i)
  else collapsedKeywords.value.add(i)
}

// Keyword tag helpers
const newKeywordTagInputs = ref<Map<number, string>>(new Map())
function addKeywordTag(kwIndex: number, tag: string) {
  if (tag.trim() && !form.keywords[kwIndex].tags.includes(tag.trim()))
    form.keywords[kwIndex].tags.push(tag.trim())
}
function removeKeywordTag(kwIndex: number, tagIdx: number) { form.keywords[kwIndex].tags.splice(tagIdx, 1) }
function handleAddKeywordTag(kwIndex: number) {
  addKeywordTag(kwIndex, newKeywordTagInputs.value.get(kwIndex) || '')
  newKeywordTagInputs.value.set(kwIndex, '')
}

// --- Initialize ---
onMounted(() => { parseRobotToForm(props.content); internalCode.value = props.content })
onUnmounted(() => { destroyCodeEditor() })

watch(() => props.content, (newContent) => {
  // Skip re-parsing if this is our own emitted content (prevents reactive watch cycle
  // that would lose items with empty names during round-trip serialize→parse)
  if (newContent === lastEmittedContent) return

  if (activeTab.value === 'visual') {
    parseRobotToForm(newContent)
  } else {
    internalCode.value = newContent
    if (codeEditorView.value) {
      const currentDoc = codeEditorView.value.state.doc.toString()
      if (currentDoc !== newContent) {
        codeEditorView.value.dispatch({ changes: { from: 0, to: currentDoc.length, insert: newContent } })
      }
    }
  }
})
</script>

<template>
  <div class="robot-editor">
    <!-- Tab Bar -->
    <div class="spec-tabs">
      <div class="tab-buttons">
        <button class="tab-btn" :class="{ active: activeTab === 'visual' }" @click="switchTab('visual')">
          {{ t('robotEditor.visualTab') }}
        </button>
        <button class="tab-btn" :class="{ active: activeTab === 'code' }" @click="switchTab('code')">
          {{ t('robotEditor.codeTab') }}
        </button>
      </div>
      <div class="tab-toolbar">
        <span class="badge badge-robot">{{ isResource ? '.resource' : '.robot' }}</span>
        <span v-if="!isResource && testCaseCount > 0" class="badge badge-info">{{ testCaseCount }} {{ t('robotEditor.tests') }}</span>
        <span v-if="keywordCount > 0" class="badge badge-info">{{ keywordCount }} {{ t('robotEditor.keywordsCount') }}</span>
      </div>
    </div>

    <!-- Parse Error Banner -->
    <div v-if="parseError" class="parse-error-banner">
      <span>{{ t('robotEditor.parseError') }}:</span> {{ parseError }}
    </div>

    <!-- Visual Tab -->
    <div v-show="activeTab === 'visual'" class="visual-editor">

      <!-- *** Settings *** -->
      <div class="editor-section">
        <div class="section-header" @click="settingsCollapsed = !settingsCollapsed">
          <span class="collapse-icon">{{ settingsCollapsed ? '\u25B6' : '\u25BC' }}</span>
          <h3>{{ t('robotEditor.settingsSection') }}</h3>
          <span class="section-count">{{ form.settings.filter(s => s.key !== '#').length }}</span>
          <BaseButton size="sm" variant="secondary" @click.stop="addSetting">+ {{ t('robotEditor.addSetting') }}</BaseButton>
        </div>
        <div v-show="!settingsCollapsed" class="section-body">
          <div v-if="form.settings.length === 0" class="empty-hint">{{ t('robotEditor.noSettings') }}</div>
          <div v-for="(s, sIdx) in form.settings" :key="sIdx" class="setting-row">
            <template v-if="s.key === '#'">
              <input v-model="s.value" class="form-input flex-1" placeholder="# Comment" />
              <button class="step-btn danger" @click="removeSetting(sIdx)" :title="t('common.delete')">&times;</button>
            </template>
            <template v-else>
              <select v-model="s.key" class="form-input setting-type-select">
                <option v-for="st in SETTING_TYPES" :key="st" :value="st">{{ t('robotEditor.settingType.' + st.replace(/ /g, '')) }}</option>
              </select>
              <div v-if="s.key === 'Library'" class="keyword-autocomplete-wrapper flex-1">
                <input v-model="s.value" class="form-input setting-library-input"
                  :placeholder="t('robotEditor.settingValuePlaceholder')"
                  @focus="onLibrarySettingFocus(sIdx)"
                  @blur="onLibrarySettingBlur"
                  @keydown="onLibrarySettingKeydown($event, sIdx)"
                  @input="onLibrarySettingInput(sIdx)" />
                <div v-if="activeLibrarySettingIdx === sIdx && filteredLibrarySuggestions.length > 0"
                  ref="librarySettingDropdownRef" class="keyword-dropdown">
                  <div v-for="(lib, idx) in filteredLibrarySuggestions" :key="lib"
                    class="keyword-dropdown-item" :class="{ active: idx === librarySettingDropdownIndex }"
                    @mousedown.prevent="selectLibrarySuggestion(sIdx, lib)">
                    <span class="kw-suggestion-name">{{ lib }}</span>
                  </div>
                </div>
              </div>
              <input v-else v-model="s.value" class="form-input flex-1" :placeholder="t('robotEditor.settingValuePlaceholder')" />
              <div v-if="s.args.length > 0" class="setting-args">
                <span v-for="(arg, aIdx) in s.args" :key="aIdx" class="chip">
                  <input v-model="s.args[aIdx]" class="chip-edit-input" :placeholder="t('robotEditor.argPlaceholder')" />
                  <button class="chip-remove" @click="removeSettingArg(sIdx, aIdx)">&times;</button>
                </span>
              </div>
              <button class="step-btn" @click="addSettingArg(sIdx)" title="Add argument">+</button>
              <button class="step-btn danger" @click="removeSetting(sIdx)" :title="t('common.delete')">&times;</button>
            </template>
          </div>
        </div>
      </div>

      <!-- *** Variables *** -->
      <div class="editor-section">
        <div class="section-header" @click="variablesCollapsed = !variablesCollapsed">
          <span class="collapse-icon">{{ variablesCollapsed ? '\u25B6' : '\u25BC' }}</span>
          <h3>{{ t('robotEditor.variablesSection') }}</h3>
          <span class="section-count">{{ form.variables.filter(v => v.name !== '#').length }}</span>
          <BaseButton size="sm" variant="secondary" @click.stop="addVariable">+ {{ t('robotEditor.addVariable') }}</BaseButton>
        </div>
        <div v-show="!variablesCollapsed" class="section-body">
          <div v-if="form.variables.length === 0" class="empty-hint">{{ t('robotEditor.noVariables') }}</div>
          <div v-for="(v, vIdx) in form.variables" :key="vIdx" class="variable-row">
            <template v-if="v.name === '#'">
              <input v-model="v.value" class="form-input flex-1" placeholder="# Comment" />
              <button class="step-btn danger" @click="removeVariable(vIdx)" :title="t('common.delete')">&times;</button>
            </template>
            <template v-else>
              <input v-model="v.name" class="form-input var-name-input" :placeholder="t('robotEditor.variableNamePlaceholder')" />
              <input v-model="v.value" class="form-input flex-1" :placeholder="t('robotEditor.variableValuePlaceholder')" />
              <button class="step-btn danger" @click="removeVariable(vIdx)" :title="t('common.delete')">&times;</button>
            </template>
          </div>
        </div>
      </div>

      <!-- *** Test Cases *** (hidden for .resource) -->
      <div v-if="!isResource" class="editor-section">
        <div class="section-header" @click="testCasesCollapsed = !testCasesCollapsed">
          <span class="collapse-icon">{{ testCasesCollapsed ? '\u25B6' : '\u25BC' }}</span>
          <h3>{{ t('robotEditor.testCasesSection') }}</h3>
          <span class="section-count">{{ form.testCases.length }}</span>
          <BaseButton size="sm" variant="secondary" @click.stop="addTestCase">+ {{ t('robotEditor.addTestCase') }}</BaseButton>
        </div>
        <div v-show="!testCasesCollapsed" class="section-body">
          <div v-if="form.testCases.length === 0" class="empty-hint">{{ t('robotEditor.noTestCases') }}</div>

          <div v-for="(tc, tcIdx) in form.testCases" :key="tcIdx" class="item-card">
            <div class="item-header" @click="toggleTestCase(tcIdx)">
              <span class="collapse-icon">{{ collapsedTestCases.has(tcIdx) ? '\u25B6' : '\u25BC' }}</span>
              <span class="item-title">{{ tc.name || t('robotEditor.unnamedTestCase') }}</span>
              <span class="item-count">{{ tc.steps.length }} {{ t('robotEditor.steps') }}</span>
              <button class="remove-btn" @click.stop="removeTestCase(tcIdx)" :title="t('common.delete')">&#128465;</button>
            </div>

            <div v-show="!collapsedTestCases.has(tcIdx)" class="item-body">
              <div class="form-group">
                <label class="form-label">{{ t('robotEditor.testCaseName') }} <span class="required">*</span></label>
                <input v-model="tc.name" class="form-input" :placeholder="t('robotEditor.testCaseNamePlaceholder')" />
              </div>
              <div class="form-group">
                <label class="form-label">{{ t('robotEditor.documentation') }}</label>
                <textarea v-model="tc.documentation" class="form-input form-textarea" rows="2" :placeholder="t('robotEditor.documentationPlaceholder')"></textarea>
              </div>
              <div class="form-group">
                <label class="form-label">{{ t('robotEditor.tags') }}</label>
                <div class="chips-container">
                  <span v-for="(tag, tagIdx) in tc.tags" :key="tagIdx" class="chip chip-tag">
                    {{ tag }}
                    <button class="chip-remove" @click="removeTestCaseTag(tcIdx, tagIdx)">&times;</button>
                  </span>
                  <div class="chip-input-wrapper">
                    <input
                      :value="newTestCaseTagInputs.get(tcIdx) || ''"
                      @input="newTestCaseTagInputs.set(tcIdx, ($event.target as HTMLInputElement).value)"
                      class="chip-input" :placeholder="t('robotEditor.addTag')"
                      @keydown.enter.prevent="handleAddTestCaseTag(tcIdx)"
                    />
                    <button v-if="(newTestCaseTagInputs.get(tcIdx) || '').trim()" class="chip-add-btn" @click="handleAddTestCaseTag(tcIdx)">+</button>
                  </div>
                </div>
              </div>
              <div class="form-row">
                <div class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.setup') }}</label>
                  <input v-model="tc.setup" class="form-input" :placeholder="t('robotEditor.setupPlaceholder')" />
                </div>
                <div class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.teardown') }}</label>
                  <input v-model="tc.teardown" class="form-input" :placeholder="t('robotEditor.teardownPlaceholder')" />
                </div>
              </div>
              <div class="form-row">
                <div class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.timeout') }}</label>
                  <input v-model="tc.timeout" class="form-input" :placeholder="t('robotEditor.timeoutPlaceholder')" />
                </div>
                <div class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.template') }}</label>
                  <input v-model="tc.template" class="form-input" :placeholder="t('robotEditor.templatePlaceholder')" />
                </div>
              </div>

              <!-- Steps -->
              <div class="form-group">
                <label class="form-label">{{ t('robotEditor.steps') }}</label>
                <div class="steps-list">
                  <div v-for="(step, sIdx) in tc.steps" :key="sIdx"
                    class="step-row" :style="{ paddingLeft: stepIndent(tc.steps, sIdx) * 24 + 'px' }">
                    <span class="step-number">{{ sIdx + 1 }}.</span>

                    <!-- Type selector -->
                    <select v-model="step.type" class="step-type-select" :class="stepTypeColor(step.type)"
                      @change="onStepTypeChange(step)">
                      <option v-for="st in STEP_TYPES" :key="st" :value="st">{{ stepTypeLabel(st) }}</option>
                    </select>

                    <!-- Keyword type -->
                    <template v-if="step.type === 'keyword'">
                      <div class="keyword-autocomplete-wrapper">
                        <input v-model="step.keyword" class="form-input step-keyword-input"
                          :placeholder="t('robotEditor.keywordPlaceholder')"
                          @focus="onKeywordInputFocus(step)"
                          @blur="onKeywordInputBlur"
                          @keydown="onKeywordKeydown($event, step)"
                          @input="onKeywordInput(step)" />
                        <div v-if="activeAutocompleteStep === step && filteredKeywordSuggestions.length > 0"
                          ref="keywordDropdownRef" class="keyword-dropdown">
                          <div v-for="(s, idx) in filteredKeywordSuggestions" :key="s.name"
                            class="keyword-dropdown-item" :class="{ active: idx === keywordDropdownIndex }"
                            @mousedown.prevent="selectKeywordSuggestion(step, s)">
                            <span class="kw-suggestion-name">{{ s.name }}</span>
                            <span class="kw-suggestion-source" :class="'source-' + s.source">{{ s.source === 'builtin' ? t('robotEditor.builtinKeyword') : t('robotEditor.localKeyword') }}</span>
                          </div>
                        </div>
                      </div>
                      <span v-for="(arg, aIdx) in step.args" :key="aIdx" class="step-arg-chip">
                        <span v-if="getKeywordArgNames(step)[aIdx]" class="arg-label">{{ getKeywordArgNames(step)[aIdx] }}</span>
                        <input v-model="step.args[aIdx]" class="step-arg-input"
                          :placeholder="getKeywordArgNames(step)[aIdx] || t('robotEditor.argPlaceholder')" />
                        <button class="chip-remove" @click="removeStepArg(step, aIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-arg" @click="addStepArg(step)" :title="t('robotEditor.addArg')">+</button>
                    </template>

                    <!-- Assignment type -->
                    <template v-else-if="step.type === 'assignment'">
                      <span v-for="(rv, rvIdx) in step.returnVars" :key="rvIdx" class="step-var-chip">
                        <input v-model="step.returnVars[rvIdx]" class="step-var-input" placeholder="${var}" />
                        <button class="chip-remove" @click="removeReturnVar(step, rvIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-var" @click="addReturnVar(step)" title="+var">+v</button>
                      <span class="step-assign-eq">=</span>
                      <div class="keyword-autocomplete-wrapper">
                        <input v-model="step.keyword" class="form-input step-keyword-input"
                          :placeholder="t('robotEditor.keywordPlaceholder')"
                          @focus="onKeywordInputFocus(step)"
                          @blur="onKeywordInputBlur"
                          @keydown="onKeywordKeydown($event, step)"
                          @input="onKeywordInput(step)" />
                        <div v-if="activeAutocompleteStep === step && filteredKeywordSuggestions.length > 0"
                          ref="keywordDropdownRef" class="keyword-dropdown">
                          <div v-for="(s, idx) in filteredKeywordSuggestions" :key="s.name"
                            class="keyword-dropdown-item" :class="{ active: idx === keywordDropdownIndex }"
                            @mousedown.prevent="selectKeywordSuggestion(step, s)">
                            <span class="kw-suggestion-name">{{ s.name }}</span>
                            <span class="kw-suggestion-source" :class="'source-' + s.source">{{ s.source === 'builtin' ? t('robotEditor.builtinKeyword') : t('robotEditor.localKeyword') }}</span>
                          </div>
                        </div>
                      </div>
                      <span v-for="(arg, aIdx) in step.args" :key="aIdx" class="step-arg-chip">
                        <span v-if="getKeywordArgNames(step)[aIdx]" class="arg-label">{{ getKeywordArgNames(step)[aIdx] }}</span>
                        <input v-model="step.args[aIdx]" class="step-arg-input"
                          :placeholder="getKeywordArgNames(step)[aIdx] || t('robotEditor.argPlaceholder')" />
                        <button class="chip-remove" @click="removeStepArg(step, aIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-arg" @click="addStepArg(step)" :title="t('robotEditor.addArg')">+</button>
                    </template>

                    <!-- FOR type -->
                    <template v-else-if="step.type === 'for'">
                      <input v-model="step.loopVar" class="form-input step-var-input-inline" placeholder="${item}" />
                      <select v-model="step.loopFlavor" class="step-flavor-select">
                        <option v-for="f in LOOP_FLAVORS" :key="f" :value="f">{{ f }}</option>
                      </select>
                      <span v-for="(lv, lvIdx) in step.loopValues" :key="lvIdx" class="step-arg-chip">
                        <input v-model="step.loopValues[lvIdx]" class="step-arg-input" :placeholder="t('robotEditor.valuePlaceholder')" />
                        <button class="chip-remove" @click="removeLoopValue(step, lvIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-arg" @click="addLoopValue(step)" :title="t('robotEditor.addValue')">+</button>
                    </template>

                    <!-- IF / ELSE IF / WHILE -->
                    <template v-else-if="step.type === 'if' || step.type === 'else_if' || step.type === 'while'">
                      <input v-model="step.condition" class="form-input flex-1" :placeholder="t('robotEditor.conditionPlaceholder')" />
                    </template>

                    <!-- EXCEPT -->
                    <template v-else-if="step.type === 'except'">
                      <input v-model="step.exceptPattern" class="form-input step-keyword-input" :placeholder="t('robotEditor.exceptPatternPlaceholder')" />
                      <span v-if="step.exceptVar || step.exceptPattern" class="step-as-label">AS</span>
                      <input v-if="step.exceptVar || step.exceptPattern" v-model="step.exceptVar" class="form-input step-var-input-inline" placeholder="${error}" />
                    </template>

                    <!-- RETURN with values -->
                    <template v-else-if="step.type === 'return'">
                      <span v-for="(arg, aIdx) in step.args" :key="aIdx" class="step-arg-chip">
                        <input v-model="step.args[aIdx]" class="step-arg-input" :placeholder="t('robotEditor.valuePlaceholder')" />
                        <button class="chip-remove" @click="removeStepArg(step, aIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-arg" @click="addStepArg(step)" :title="t('robotEditor.addValue')">+</button>
                    </template>

                    <!-- Comment -->
                    <template v-else-if="step.type === 'comment'">
                      <input v-model="step.comment" class="form-input flex-1 step-comment-input" placeholder="# ..." />
                    </template>

                    <!-- END / ELSE / TRY / FINALLY / BREAK / CONTINUE: no extra fields -->

                    <!-- Action buttons -->
                    <div class="step-actions">
                      <button class="step-btn" @click="moveStep(tc.steps, sIdx, -1)" :disabled="sIdx === 0">&uarr;</button>
                      <button class="step-btn" @click="moveStep(tc.steps, sIdx, 1)" :disabled="sIdx === tc.steps.length - 1">&darr;</button>
                      <button class="step-btn danger" @click="removeStep(tc.steps, sIdx)" :title="t('common.delete')">&times;</button>
                    </div>
                  </div>

                  <!-- Add step buttons -->
                  <div class="add-step-bar">
                    <button class="add-step-btn" @click="addStep(tc.steps)">+ {{ t('robotEditor.addStep') }}</button>
                    <button class="add-step-btn add-block" @click="addBlock(tc.steps, 'for')">+ FOR</button>
                    <button class="add-step-btn add-block" @click="addBlock(tc.steps, 'if')">+ IF</button>
                    <button class="add-step-btn add-block" @click="addBlock(tc.steps, 'while')">+ WHILE</button>
                    <button class="add-step-btn add-block" @click="addBlock(tc.steps, 'try')">+ TRY</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- *** Keywords *** -->
      <div class="editor-section">
        <div class="section-header" @click="keywordsCollapsed = !keywordsCollapsed">
          <span class="collapse-icon">{{ keywordsCollapsed ? '\u25B6' : '\u25BC' }}</span>
          <h3>{{ t('robotEditor.keywordsSection') }}</h3>
          <span class="section-count">{{ form.keywords.length }}</span>
          <BaseButton size="sm" variant="secondary" @click.stop="addKeyword">+ {{ t('robotEditor.addKeyword') }}</BaseButton>
        </div>
        <div v-show="!keywordsCollapsed" class="section-body">
          <div v-if="form.keywords.length === 0" class="empty-hint">{{ t('robotEditor.noKeywords') }}</div>

          <div v-for="(kw, kwIdx) in form.keywords" :key="kwIdx" class="item-card">
            <div class="item-header" @click="toggleKeyword(kwIdx)">
              <span class="collapse-icon">{{ collapsedKeywords.has(kwIdx) ? '\u25B6' : '\u25BC' }}</span>
              <span class="item-title">{{ kw.name || t('robotEditor.unnamedKeyword') }}</span>
              <span class="item-count">{{ kw.steps.length }} {{ t('robotEditor.steps') }}</span>
              <button class="remove-btn" @click.stop="removeKeyword(kwIdx)" :title="t('common.delete')">&#128465;</button>
            </div>

            <div v-show="!collapsedKeywords.has(kwIdx)" class="item-body">
              <div class="form-group">
                <label class="form-label">{{ t('robotEditor.keywordName') }} <span class="required">*</span></label>
                <input v-model="kw.name" class="form-input" :placeholder="t('robotEditor.keywordNamePlaceholder')" />
              </div>
              <div class="form-group">
                <label class="form-label">{{ t('robotEditor.arguments') }}</label>
                <input v-model="kw.arguments" class="form-input" :placeholder="t('robotEditor.argumentsPlaceholder')" />
              </div>
              <div class="form-group">
                <label class="form-label">{{ t('robotEditor.documentation') }}</label>
                <textarea v-model="kw.documentation" class="form-input form-textarea" rows="2" :placeholder="t('robotEditor.documentationPlaceholder')"></textarea>
              </div>
              <div class="form-group">
                <label class="form-label">{{ t('robotEditor.tags') }}</label>
                <div class="chips-container">
                  <span v-for="(tag, tagIdx) in kw.tags" :key="tagIdx" class="chip chip-tag">
                    {{ tag }}
                    <button class="chip-remove" @click="removeKeywordTag(kwIdx, tagIdx)">&times;</button>
                  </span>
                  <div class="chip-input-wrapper">
                    <input
                      :value="newKeywordTagInputs.get(kwIdx) || ''"
                      @input="newKeywordTagInputs.set(kwIdx, ($event.target as HTMLInputElement).value)"
                      class="chip-input" :placeholder="t('robotEditor.addTag')"
                      @keydown.enter.prevent="handleAddKeywordTag(kwIdx)"
                    />
                    <button v-if="(newKeywordTagInputs.get(kwIdx) || '').trim()" class="chip-add-btn" @click="handleAddKeywordTag(kwIdx)">+</button>
                  </div>
                </div>
              </div>
              <div class="form-row">
                <div class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.setup') }}</label>
                  <input v-model="kw.setup" class="form-input" :placeholder="t('robotEditor.setupPlaceholder')" />
                </div>
                <div class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.teardown') }}</label>
                  <input v-model="kw.teardown" class="form-input" :placeholder="t('robotEditor.teardownPlaceholder')" />
                </div>
              </div>
              <div class="form-row">
                <div class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.timeout') }}</label>
                  <input v-model="kw.timeout" class="form-input" :placeholder="t('robotEditor.timeoutPlaceholder')" />
                </div>
                <div class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.returnValue') }}</label>
                  <input v-model="kw.returnValue" class="form-input" :placeholder="t('robotEditor.returnValuePlaceholder')" />
                </div>
              </div>

              <!-- Steps -->
              <div class="form-group">
                <label class="form-label">{{ t('robotEditor.steps') }}</label>
                <div class="steps-list">
                  <div v-for="(step, sIdx) in kw.steps" :key="sIdx"
                    class="step-row" :style="{ paddingLeft: stepIndent(kw.steps, sIdx) * 24 + 'px' }">
                    <span class="step-number">{{ sIdx + 1 }}.</span>

                    <select v-model="step.type" class="step-type-select" :class="stepTypeColor(step.type)"
                      @change="onStepTypeChange(step)">
                      <option v-for="st in STEP_TYPES" :key="st" :value="st">{{ stepTypeLabel(st) }}</option>
                    </select>

                    <!-- Keyword -->
                    <template v-if="step.type === 'keyword'">
                      <div class="keyword-autocomplete-wrapper">
                        <input v-model="step.keyword" class="form-input step-keyword-input"
                          :placeholder="t('robotEditor.keywordPlaceholder')"
                          @focus="onKeywordInputFocus(step)"
                          @blur="onKeywordInputBlur"
                          @keydown="onKeywordKeydown($event, step)"
                          @input="onKeywordInput(step)" />
                        <div v-if="activeAutocompleteStep === step && filteredKeywordSuggestions.length > 0"
                          ref="keywordDropdownRef" class="keyword-dropdown">
                          <div v-for="(s, idx) in filteredKeywordSuggestions" :key="s.name"
                            class="keyword-dropdown-item" :class="{ active: idx === keywordDropdownIndex }"
                            @mousedown.prevent="selectKeywordSuggestion(step, s)">
                            <span class="kw-suggestion-name">{{ s.name }}</span>
                            <span class="kw-suggestion-source" :class="'source-' + s.source">{{ s.source === 'builtin' ? t('robotEditor.builtinKeyword') : t('robotEditor.localKeyword') }}</span>
                          </div>
                        </div>
                      </div>
                      <span v-for="(arg, aIdx) in step.args" :key="aIdx" class="step-arg-chip">
                        <span v-if="getKeywordArgNames(step)[aIdx]" class="arg-label">{{ getKeywordArgNames(step)[aIdx] }}</span>
                        <input v-model="step.args[aIdx]" class="step-arg-input"
                          :placeholder="getKeywordArgNames(step)[aIdx] || t('robotEditor.argPlaceholder')" />
                        <button class="chip-remove" @click="removeStepArg(step, aIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-arg" @click="addStepArg(step)" :title="t('robotEditor.addArg')">+</button>
                    </template>

                    <!-- Assignment -->
                    <template v-else-if="step.type === 'assignment'">
                      <span v-for="(rv, rvIdx) in step.returnVars" :key="rvIdx" class="step-var-chip">
                        <input v-model="step.returnVars[rvIdx]" class="step-var-input" placeholder="${var}" />
                        <button class="chip-remove" @click="removeReturnVar(step, rvIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-var" @click="addReturnVar(step)" title="+var">+v</button>
                      <span class="step-assign-eq">=</span>
                      <div class="keyword-autocomplete-wrapper">
                        <input v-model="step.keyword" class="form-input step-keyword-input"
                          :placeholder="t('robotEditor.keywordPlaceholder')"
                          @focus="onKeywordInputFocus(step)"
                          @blur="onKeywordInputBlur"
                          @keydown="onKeywordKeydown($event, step)"
                          @input="onKeywordInput(step)" />
                        <div v-if="activeAutocompleteStep === step && filteredKeywordSuggestions.length > 0"
                          ref="keywordDropdownRef" class="keyword-dropdown">
                          <div v-for="(s, idx) in filteredKeywordSuggestions" :key="s.name"
                            class="keyword-dropdown-item" :class="{ active: idx === keywordDropdownIndex }"
                            @mousedown.prevent="selectKeywordSuggestion(step, s)">
                            <span class="kw-suggestion-name">{{ s.name }}</span>
                            <span class="kw-suggestion-source" :class="'source-' + s.source">{{ s.source === 'builtin' ? t('robotEditor.builtinKeyword') : t('robotEditor.localKeyword') }}</span>
                          </div>
                        </div>
                      </div>
                      <span v-for="(arg, aIdx) in step.args" :key="aIdx" class="step-arg-chip">
                        <span v-if="getKeywordArgNames(step)[aIdx]" class="arg-label">{{ getKeywordArgNames(step)[aIdx] }}</span>
                        <input v-model="step.args[aIdx]" class="step-arg-input"
                          :placeholder="getKeywordArgNames(step)[aIdx] || t('robotEditor.argPlaceholder')" />
                        <button class="chip-remove" @click="removeStepArg(step, aIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-arg" @click="addStepArg(step)" :title="t('robotEditor.addArg')">+</button>
                    </template>

                    <!-- FOR -->
                    <template v-else-if="step.type === 'for'">
                      <input v-model="step.loopVar" class="form-input step-var-input-inline" placeholder="${item}" />
                      <select v-model="step.loopFlavor" class="step-flavor-select">
                        <option v-for="f in LOOP_FLAVORS" :key="f" :value="f">{{ f }}</option>
                      </select>
                      <span v-for="(lv, lvIdx) in step.loopValues" :key="lvIdx" class="step-arg-chip">
                        <input v-model="step.loopValues[lvIdx]" class="step-arg-input" :placeholder="t('robotEditor.valuePlaceholder')" />
                        <button class="chip-remove" @click="removeLoopValue(step, lvIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-arg" @click="addLoopValue(step)" :title="t('robotEditor.addValue')">+</button>
                    </template>

                    <!-- IF / ELSE IF / WHILE -->
                    <template v-else-if="step.type === 'if' || step.type === 'else_if' || step.type === 'while'">
                      <input v-model="step.condition" class="form-input flex-1" :placeholder="t('robotEditor.conditionPlaceholder')" />
                    </template>

                    <!-- EXCEPT -->
                    <template v-else-if="step.type === 'except'">
                      <input v-model="step.exceptPattern" class="form-input step-keyword-input" :placeholder="t('robotEditor.exceptPatternPlaceholder')" />
                      <span v-if="step.exceptVar || step.exceptPattern" class="step-as-label">AS</span>
                      <input v-if="step.exceptVar || step.exceptPattern" v-model="step.exceptVar" class="form-input step-var-input-inline" placeholder="${error}" />
                    </template>

                    <!-- RETURN -->
                    <template v-else-if="step.type === 'return'">
                      <span v-for="(arg, aIdx) in step.args" :key="aIdx" class="step-arg-chip">
                        <input v-model="step.args[aIdx]" class="step-arg-input" :placeholder="t('robotEditor.valuePlaceholder')" />
                        <button class="chip-remove" @click="removeStepArg(step, aIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-arg" @click="addStepArg(step)" :title="t('robotEditor.addValue')">+</button>
                    </template>

                    <!-- Comment -->
                    <template v-else-if="step.type === 'comment'">
                      <input v-model="step.comment" class="form-input flex-1 step-comment-input" placeholder="# ..." />
                    </template>

                    <div class="step-actions">
                      <button class="step-btn" @click="moveStep(kw.steps, sIdx, -1)" :disabled="sIdx === 0">&uarr;</button>
                      <button class="step-btn" @click="moveStep(kw.steps, sIdx, 1)" :disabled="sIdx === kw.steps.length - 1">&darr;</button>
                      <button class="step-btn danger" @click="removeStep(kw.steps, sIdx)" :title="t('common.delete')">&times;</button>
                    </div>
                  </div>

                  <div class="add-step-bar">
                    <button class="add-step-btn" @click="addStep(kw.steps)">+ {{ t('robotEditor.addStep') }}</button>
                    <button class="add-step-btn add-block" @click="addBlock(kw.steps, 'for')">+ FOR</button>
                    <button class="add-step-btn add-block" @click="addBlock(kw.steps, 'if')">+ IF</button>
                    <button class="add-step-btn add-block" @click="addBlock(kw.steps, 'while')">+ WHILE</button>
                    <button class="add-step-btn add-block" @click="addBlock(kw.steps, 'try')">+ TRY</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Code Tab -->
    <div v-show="activeTab === 'code'" class="code-editor" ref="codeEditorContainer"></div>
  </div>
</template>

<style scoped>
.robot-editor {
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
.tab-buttons { display: flex; gap: 0; }
.tab-btn {
  padding: 8px 16px; border: none; background: transparent; font-size: 13px;
  font-weight: 500; color: var(--color-text-muted); cursor: pointer;
  border-bottom: 2px solid transparent; transition: all 0.15s ease;
}
.tab-btn:hover { color: var(--color-text); background: rgba(59, 125, 216, 0.05); }
.tab-btn.active { color: var(--color-primary); border-bottom-color: var(--color-primary); }
.tab-toolbar { display: flex; align-items: center; gap: 8px; padding: 6px 0; }

/* Badges */
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
.badge-robot { background: #e8f5e9; color: #2e7d32; }
.badge-info { background: #e8f0fe; color: var(--color-primary); }

/* Parse Error */
.parse-error-banner { padding: 8px 12px; background: #fff3cd; border-bottom: 1px solid #ffc107; font-size: 13px; color: #856404; flex-shrink: 0; }
.parse-error-banner span { font-weight: 600; }

/* Visual Editor */
.visual-editor { flex: 1; min-height: 0; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; }
.editor-section { background: var(--color-bg-card); border: 1px solid var(--color-border); border-radius: 8px; overflow: visible; flex-shrink: 0; }
.section-header { display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: var(--color-bg); border-bottom: 1px solid var(--color-border); cursor: pointer; user-select: none; }
.section-header h3 { margin: 0; font-size: 14px; font-weight: 600; flex: 1; }
.section-count { font-size: 11px; color: var(--color-text-muted); padding: 1px 8px; background: rgba(59, 125, 216, 0.1); border-radius: 8px; }
.section-body { padding: 14px; display: flex; flex-direction: column; gap: 8px; }
.collapse-icon { font-size: 10px; color: var(--color-text-muted); width: 14px; flex-shrink: 0; }

/* Setting/Variable rows */
.setting-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.setting-type-select { width: 160px; flex-shrink: 0; }
.setting-args { display: flex; gap: 4px; flex-wrap: wrap; }
.chip-edit-input { border: none; background: transparent; color: inherit; font-size: 12px; width: 80px; outline: none; }
.variable-row { display: flex; align-items: center; gap: 8px; }
.var-name-input { width: 200px; flex-shrink: 0; font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; }

/* Item cards */
.item-card { border: 1px solid var(--color-border); border-radius: 8px; overflow: hidden; }
.item-header { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: var(--color-bg); border-bottom: 1px solid var(--color-border); cursor: pointer; user-select: none; }
.item-title { flex: 1; font-weight: 500; font-size: 13px; }
.item-count { font-size: 11px; color: var(--color-text-muted); padding: 1px 8px; background: rgba(59, 125, 216, 0.1); border-radius: 8px; }
.item-body { padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.remove-btn { border: none; background: none; cursor: pointer; font-size: 14px; padding: 2px 4px; opacity: 0.5; transition: opacity 0.15s; }
.remove-btn:hover { opacity: 1; }

/* Form Elements */
.form-row { display: flex; gap: 12px; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.flex-1 { flex: 1; }
.form-label { font-size: 12px; font-weight: 500; color: var(--color-text-muted); }
.required { color: var(--color-danger); }
.form-input { padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 13px; background: var(--color-bg-card); color: var(--color-text); transition: border-color 0.15s; }
.form-input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 2px rgba(59, 125, 216, 0.15); }
.form-textarea { resize: vertical; min-height: 40px; font-family: inherit; }

/* Chips/Tags */
.chips-container { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; background: #e8f0fe; color: var(--color-primary); border-radius: 12px; font-size: 12px; font-weight: 500; }
.chip-tag { background: #f0e6ff; color: #7c3aed; }
.chip-remove { border: none; background: none; color: inherit; font-size: 14px; cursor: pointer; padding: 0 2px; opacity: 0.7; line-height: 1; }
.chip-remove:hover { opacity: 1; }
.chip-input-wrapper { display: flex; align-items: center; gap: 4px; }
.chip-input { border: 1px dashed var(--color-border); border-radius: 12px; padding: 3px 10px; font-size: 12px; background: transparent; color: var(--color-text); width: 140px; outline: none; }
.chip-input:focus { border-color: var(--color-primary); }
.chip-add-btn { border: none; background: var(--color-primary); color: white; width: 22px; height: 22px; border-radius: 50%; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; line-height: 1; }

/* Steps */
.steps-list { display: flex; flex-direction: column; gap: 4px; }
.step-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-height: 32px; transition: padding-left 0.15s; }
.step-number { font-size: 11px; color: var(--color-text-muted); width: 22px; text-align: right; flex-shrink: 0; }

/* Step type selector */
.step-type-select {
  width: auto; min-width: 90px; padding: 3px 6px; border-radius: 4px;
  font-size: 11px; font-weight: 600; text-transform: uppercase; cursor: pointer;
  border: 1px solid var(--color-border); background: var(--color-bg); color: var(--color-text);
  flex-shrink: 0;
}
.step-type-select.type-keyword { background: #f0f7ff; color: #1a5fb4; border-color: #b8d4f0; }
.step-type-select.type-assign { background: #f5f0ff; color: #7c3aed; border-color: #d4c4f0; }
.step-type-select.type-loop { background: #fff8e1; color: #e65100; border-color: #ffe0b2; }
.step-type-select.type-condition { background: #e8f5e9; color: #2e7d32; border-color: #a5d6a7; }
.step-type-select.type-error { background: #fce4ec; color: #c62828; border-color: #ef9a9a; }
.step-type-select.type-flow { background: #eceff1; color: #455a64; border-color: #b0bec5; }
.step-type-select.type-comment { background: #f5f5f5; color: #757575; border-color: #ccc; }

/* Step inline fields */
.step-keyword-input { min-width: 160px; max-width: 260px; font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; padding: 4px 8px; }
.step-var-input-inline { width: 110px; font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; padding: 4px 8px; flex-shrink: 0; }
.step-flavor-select { padding: 3px 6px; font-size: 12px; font-weight: 600; border: 1px solid #ffe0b2; background: #fff8e1; color: #e65100; border-radius: 4px; cursor: pointer; flex-shrink: 0; }
.step-comment-input { font-style: italic; color: var(--color-text-muted); font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; }

/* Step arg chips */
.step-arg-chip {
  display: inline-flex; align-items: center; gap: 2px;
  padding: 2px 6px; background: var(--color-bg); border: 1px solid var(--color-border);
  border-radius: 4px; flex-shrink: 0;
}
.step-arg-input { border: none; background: transparent; color: var(--color-text); font-size: 12px; font-family: 'Fira Code', 'Consolas', monospace; width: 90px; outline: none; padding: 0; }
.step-arg-input::placeholder { color: var(--color-text-muted); opacity: 0.5; }

/* Step variable chips (for assignment) */
.step-var-chip {
  display: inline-flex; align-items: center; gap: 2px;
  padding: 2px 6px; background: #f5f0ff; border: 1px solid #d4c4f0;
  border-radius: 4px; flex-shrink: 0;
}
.step-var-input { border: none; background: transparent; color: #7c3aed; font-size: 12px; font-family: 'Fira Code', 'Consolas', monospace; width: 80px; outline: none; padding: 0; font-weight: 500; }

.step-assign-eq { font-weight: 700; color: #7c3aed; font-size: 14px; margin: 0 2px; flex-shrink: 0; }
.step-as-label { font-weight: 600; color: var(--color-text-muted); font-size: 11px; text-transform: uppercase; flex-shrink: 0; }

.step-add-arg { font-size: 14px !important; width: 22px !important; height: 22px !important; }
.step-add-var { font-size: 10px !important; width: 22px !important; height: 22px !important; }

.step-actions { display: flex; gap: 2px; flex-shrink: 0; margin-left: auto; }

.step-btn { border: 1px solid var(--color-border); background: var(--color-bg-card); color: var(--color-text-muted); width: 26px; height: 26px; border-radius: 4px; font-size: 12px; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.step-btn:hover:not(:disabled) { background: var(--color-bg); color: var(--color-text); }
.step-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.step-btn.danger:hover { color: var(--color-danger); border-color: var(--color-danger); }

/* Add step bar */
.add-step-bar { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px; }
.add-step-btn { border: 1px dashed var(--color-border); background: transparent; color: var(--color-text-muted); padding: 4px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; text-align: left; }
.add-step-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }
.add-step-btn.add-block { font-weight: 600; font-size: 11px; }
.add-step-btn.add-block:hover { border-color: #e65100; color: #e65100; }

/* Empty hints */
.empty-hint { padding: 16px; text-align: center; color: var(--color-text-muted); font-size: 13px; font-style: italic; }

/* Code Editor */
.code-editor { flex: 1; overflow: hidden; }
.code-editor :deep(.cm-editor) { height: 100%; }

/* Keyword autocomplete dropdown */
.keyword-autocomplete-wrapper { position: relative; display: inline-flex; }
.keyword-dropdown {
  position: absolute; top: 100%; left: 0; z-index: 50;
  min-width: 280px; max-height: 220px; overflow-y: auto;
  background: var(--color-bg-card); border: 1px solid var(--color-border);
  border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-top: 2px;
}
.keyword-dropdown-item { padding: 6px 10px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.keyword-dropdown-item:hover, .keyword-dropdown-item.active { background: rgba(59,125,216,0.08); }
.kw-suggestion-name { font-family: 'Fira Code', monospace; font-size: 12px; }
.kw-suggestion-source { font-size: 10px; padding: 1px 6px; border-radius: 8px; font-weight: 600; text-transform: uppercase; }
.source-builtin { background: #e8f5e9; color: #2e7d32; }
.source-local { background: #f0e6ff; color: #7c3aed; }

/* Argument labels */
.arg-label { font-size: 10px; color: var(--color-text-muted); font-weight: 500; margin-right: 2px; white-space: nowrap; }

/* Setting library input */
.setting-library-input { width: 100%; font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; }
</style>
