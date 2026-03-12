<script setup lang="ts">
import { ref, reactive, watch, computed, nextTick, onMounted, onUnmounted, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import { robotLanguage } from '@/utils/robotLanguage'
import { RF_KEYWORD_SIGNATURES } from '@/utils/robotKeywordSignatures'
import { searchKeywords, type RfKeywordResult } from '@/api/ai.api'

// CodeMirror imports
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightSpecialChars } from '@codemirror/view'
import { EditorState } from '@codemirror/state'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { LanguageSupport } from '@codemirror/language'
import { syntaxHighlighting, defaultHighlightStyle } from '@codemirror/language'

const props = defineProps<{
  content: string
  filePath: string
  repoId?: number
}>()

const emit = defineEmits<{
  save: [content: string]
  'update:content': [content: string]
}>()

const { t } = useI18n()

// --- Step Types ---
type StepType = 'keyword' | 'assignment' | 'var' | 'for' | 'end' | 'if' | 'else_if' | 'else'
  | 'while' | 'try' | 'except' | 'finally' | 'break' | 'continue' | 'return' | 'comment'

const STEP_TYPES: StepType[] = [
  'keyword', 'assignment', 'var', 'comment',
  'for', 'if', 'else_if', 'else', 'while',
  'try', 'except', 'finally',
  'end', 'break', 'continue', 'return',
]

const VAR_SCOPES = ['LOCAL', 'TEST', 'TASK', 'SUITE', 'GLOBAL'] as const

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
  varScope: string       // var: scope (LOCAL|TEST|TASK|SUITE|GLOBAL)
  comment: string        // comment: text
}

interface RobotTestCase {
  name: string; documentation: string; tags: string[]
  setup: string; teardown: string; timeout: string; template: string
  steps: RobotStep[]
}
interface RobotKeyword {
  name: string; documentation: string; arguments: string[]; tags: string[]
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
    exceptPattern: '', exceptVar: '', varScope: '', comment: '',
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

function expandAllSections() {
  settingsCollapsed.value = false
  variablesCollapsed.value = false
  testCasesCollapsed.value = false
  keywordsCollapsed.value = false
  collapsedTestCases.value.clear()
  collapsedKeywords.value.clear()
}

function collapseAllSections() {
  settingsCollapsed.value = true
  variablesCollapsed.value = true
  testCasesCollapsed.value = true
  keywordsCollapsed.value = true
  for (let i = 0; i < form.testCases.length; i++) collapsedTestCases.value.add(i)
  for (let i = 0; i < form.keywords.length; i++) collapsedKeywords.value.add(i)
}

// Track which meta fields are expanded per test case / keyword (key: "tc-0-setup", "kw-1-teardown", etc.)
const expandedMeta = ref<Set<string>>(new Set())
function isMetaVisible(prefix: string, idx: number, field: string, value: string): boolean {
  return !!value || expandedMeta.value.has(`${prefix}-${idx}-${field}`)
}
function toggleMeta(prefix: string, idx: number, field: string) {
  const key = `${prefix}-${idx}-${field}`
  if (expandedMeta.value.has(key)) expandedMeta.value.delete(key)
  else expandedMeta.value.add(key)
}

// Keyword autocomplete state
const activeAutocompleteStep = ref<RobotStep | null>(null)
const keywordQuery = ref('')
const keywordDropdownIndex = ref(-1)
const keywordDropdownRef = ref<HTMLElement | null>(null)
const keywordSuggestions = ref<RfKeywordResult[]>([])
const knownKeywordArgs = reactive(new Map<string, string[]>())
let keywordSearchTimer: ReturnType<typeof setTimeout> | null = null

// Arg variable autocomplete state
const argAutocompleteItems = ref<string[]>([])
const argAutocompleteIndex = ref(-1)
const argAutocompleteKey = ref<string | null>(null) // "kwIdx-sIdx-aIdx" or "tcIdx-sIdx-aIdx"

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
  if (first === 'VAR') {
    step.type = 'var'
    step.returnVars = cells[1] ? [cells[1]] : ['${var}']
    // Remaining cells are values, but check for scope= at the end
    const rest = cells.slice(2)
    const scopeIdx = rest.findIndex(c => /^scope=/i.test(c))
    if (scopeIdx >= 0) {
      step.varScope = rest[scopeIdx].replace(/^scope=/i, '')
      step.args = rest.slice(0, scopeIdx)
    } else {
      step.args = rest
    }
    return step
  }

  // Check for variable assignment: ${var}=  Keyword  args
  // or multi-assign: ${a}  ${b}=  Keyword  args
  // Also handles: ${var} =  Keyword (space before =) and = as separate cell
  const VAR_RE = /^[$@&%]\{[^}]+\}\s*=?$/
  const returnVars: string[] = []
  let keywordIdx = 0
  for (let i = 0; i < cells.length; i++) {
    const cell = cells[i].trim()
    if (VAR_RE.test(cell)) {
      const varName = cell.replace(/\s*=$/, '')
      returnVars.push(varName)
      if (cell.endsWith('=')) {
        keywordIdx = i + 1
        break
      }
      // Check if next cell is just '=' (standalone equals sign)
      if (i + 1 < cells.length && cells[i + 1].trim() === '=') {
        keywordIdx = i + 2
        break
      }
    } else if (cell === '=' && returnVars.length > 0) {
      // Standalone = after variables
      keywordIdx = i + 1
      break
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
    case 'var': {
      const parts = ['VAR', step.returnVars[0] || '${var}', ...step.args]
      if (step.varScope) parts.push('scope=' + step.varScope)
      return parts.filter(Boolean).join(SEP)
    }
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
              name: trimmed, documentation: '', arguments: [], tags: [],
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
                if ('arguments' in currentItem) {
                  (currentItem as RobotKeyword).arguments = settingValue
                    ? settingValue.split(/  +|\t+/).filter(Boolean)
                    : []
                }
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

// --- Lazy-load keyword arg names on parse ---
function collectStepKeywords(steps: RobotStep[], out: Set<string>) {
  for (const step of steps) {
    if ((step.type === 'keyword' || step.type === 'assignment') && step.keyword.trim()) {
      out.add(step.keyword.trim())
    }
  }
}

async function lazyLoadKeywordArgs() {
  // Collect all unique keyword names from all steps
  const names = new Set<string>()
  for (const tc of form.testCases) collectStepKeywords(tc.steps, names)
  for (const kw of form.keywords) collectStepKeywords(kw.steps, names)

  // Filter out already-known keywords (builtins, locals, cached)
  const unknown: string[] = []
  for (const name of names) {
    const lower = name.toLowerCase().trim()
    const bare = lower.includes('.') ? lower.substring(lower.indexOf('.') + 1).trim() : lower
    if (RF_KEYWORD_SIGNATURES.has(lower) || RF_KEYWORD_SIGNATURES.has(bare)) continue
    if (form.keywords.some(k => k.name.toLowerCase() === lower || k.name.toLowerCase() === bare)) continue
    if (knownKeywordArgs.has(lower) || knownKeywordArgs.has(bare)) continue
    unknown.push(name)
  }

  if (unknown.length === 0) return

  // Search each unknown keyword (deduplicated, limited batch)
  const searched = new Set<string>()
  for (const name of unknown) {
    const lower = name.toLowerCase().trim()
    if (searched.has(lower)) continue
    searched.add(lower)
    try {
      const response = await searchKeywords(name, props.repoId)
      for (const kw of response.results) {
        if (kw.args?.length) {
          const full = kw.name.toLowerCase().trim()
          knownKeywordArgs.set(full, kw.args)
          if (full.includes('.')) {
            knownKeywordArgs.set(full.substring(full.indexOf('.') + 1).trim(), kw.args)
          }
        }
      }
    } catch {
      // keyword search may not be available — silently skip
    }
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
      if (kw.arguments.length) lines.push(SEP + '[Arguments]' + SEP + kw.arguments.join(SEP))
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

// Get label for next expected arg on the + button
function nextArgHint(step: RobotStep): string {
  const sig = getKeywordArgNames(step)
  if (sig.length === 0) return '+'
  const nextIdx = step.args.length
  if (nextIdx < sig.length) {
    return '+ ' + sig[nextIdx]
  }
  // Past defined args — check if varargs
  const last = sig[sig.length - 1]
  if (last?.startsWith('*') && !last.startsWith('**')) return '+ ...'
  return '+'
}
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
  } else if (step.type === 'var') {
    if (step.returnVars.length === 0) step.returnVars = ['${var}']
    if (step.args.length === 0) step.args = ['']
  } else if (step.type === 'comment') {
    if (!step.comment) step.comment = '# '
  }
}

// Step type display helpers
function stepTypeLabel(type: StepType): string {
  return t('robotEditor.stepType.' + type)
}

function settingTypeColor(key: string): string {
  switch (key) {
    case 'Library': return 'stype-library'
    case 'Resource': return 'stype-resource'
    case 'Variables': return 'stype-variables'
    case 'Documentation': return 'stype-doc'
    case 'Suite Setup': case 'Test Setup': return 'stype-setup'
    case 'Suite Teardown': case 'Test Teardown': return 'stype-teardown'
    case 'Test Template': case 'Test Timeout': return 'stype-config'
    case 'Force Tags': case 'Default Tags': return 'stype-tags'
    case 'Metadata': return 'stype-meta'
    default: return ''
  }
}

function stepTypeColor(type: StepType): string {
  switch (type) {
    case 'keyword': return 'type-keyword'
    case 'assignment': return 'type-assign'
    case 'var': return 'type-var'
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
interface KeywordSuggestion { name: string; source: string; args?: string[] }

// Build title-cased display names for RF built-in keywords
const rfBuiltinSuggestions = computed<KeywordSuggestion[]>(() => {
  const result: KeywordSuggestion[] = []
  for (const key of RF_KEYWORD_SIGNATURES.keys()) {
    const titleCase = key.replace(/\b\w/g, c => c.toUpperCase())
    result.push({ name: titleCase, source: 'builtin', args: RF_KEYWORD_SIGNATURES.get(key) })
  }
  return result
})

const filteredKeywordSuggestions = computed<KeywordSuggestion[]>(() => {
  const query = keywordQuery.value.toLowerCase().trim()
  const seen = new Set<string>()
  const suggestions: KeywordSuggestion[] = []

  // 1. Project + library keywords from backend search
  for (const kw of keywordSuggestions.value) {
    const key = kw.name.toLowerCase()
    if (!seen.has(key)) {
      seen.add(key)
      const src = kw.library || 'project'
      suggestions.push({ name: kw.name, source: src, args: kw.args })
      // Add resource-prefixed variant: "resource.Keyword Name"
      if (src && src !== 'project' && src !== 'local' && src !== 'builtin' && !src.includes('Library')) {
        const prefixed = src + '.' + kw.name
        const pKey = prefixed.toLowerCase()
        if (!seen.has(pKey)) {
          seen.add(pKey)
          suggestions.push({ name: prefixed, source: src, args: kw.args })
        }
      }
    }
  }

  // 2. Local keywords from the current file
  for (const kw of form.keywords) {
    const key = kw.name.toLowerCase()
    if (kw.name && !seen.has(key)) {
      seen.add(key)
      suggestions.push({ name: kw.name, source: 'local', args: kw.arguments })
    }
  }

  // 3. Built-in RF keyword signatures (fallback)
  for (const s of rfBuiltinSuggestions.value) {
    const key = s.name.toLowerCase()
    if (!seen.has(key)) {
      seen.add(key)
      suggestions.push(s)
    }
  }

  return suggestions
    .filter(s => {
      if (!query) return true
      const lower = s.name.toLowerCase()
      // Match on full name or bare name after resource prefix
      const bare = lower.includes('.') ? lower.substring(lower.indexOf('.') + 1) : lower
      return lower.includes(query) || bare.includes(query)
    })
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
  debouncedKeywordSearch(step.keyword)
}

function debouncedKeywordSearch(query: string) {
  if (keywordSearchTimer) clearTimeout(keywordSearchTimer)
  if (query.trim().length < 2) {
    keywordSuggestions.value = []
    return
  }
  keywordSearchTimer = setTimeout(async () => {
    try {
      const response = await searchKeywords(query.trim(), props.repoId)
      keywordSuggestions.value = response.results.slice(0, 15)
      // Cache args for later use in getKeywordArgNames
      for (const kw of keywordSuggestions.value) {
        if (kw.args?.length) {
          knownKeywordArgs.set(kw.name.toLowerCase().trim(), kw.args)
        }
      }
    } catch {
      keywordSuggestions.value = []
    }
  }, 300)
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
  // Store args from suggestion for later lookup (both full and bare name)
  if (suggestion.args?.length) {
    const full = suggestion.name.toLowerCase().trim()
    knownKeywordArgs.set(full, suggestion.args)
    if (full.includes('.')) {
      knownKeywordArgs.set(full.substring(full.indexOf('.') + 1).trim(), suggestion.args)
    }
  }
  activeAutocompleteStep.value = null
  keywordDropdownIndex.value = -1
  keywordQuery.value = ''
  // Auto-populate arg slots from signature (required = no '?' suffix, not varargs/kwargs)
  const sig = getKeywordArgNames(step)
  const requiredCount = sig.filter(a => !a.endsWith('?') && !a.startsWith('*')).length
  while (step.args.length < requiredCount) {
    step.args.push('')
  }
}

// --- Arg Variable Autocomplete ---
function collectAvailableVars(): string[] {
  const vars: string[] = []
  for (const v of form.variables) if (v.name) vars.push(v.name)
  for (const kw of form.keywords) {
    for (const a of kw.arguments) {
      if (a) vars.push(a.replace(/=.*$/, ''))
    }
  }
  return vars
}

function onArgInput(value: string, key: string) {
  argAutocompleteKey.value = key
  if (!value.includes('$')) {
    argAutocompleteItems.value = []
    return
  }
  const m = value.match(/[$@&%]\{([^}]*)$/)
  if (!m) { argAutocompleteItems.value = []; return }
  const partial = m[1].toLowerCase()
  const all = collectAvailableVars()
  argAutocompleteItems.value = all.filter(v => v.toLowerCase().includes(partial)).slice(0, 8)
  argAutocompleteIndex.value = -1
}

function selectArgVar(step: RobotStep, aIdx: number, varName: string) {
  const current = step.args[aIdx] || ''
  // Replace the partial ${... with the full variable
  const replaced = current.replace(/[$@&%]\{[^}]*$/, varName + '}')
  step.args[aIdx] = replaced.includes('}') ? replaced : varName
  argAutocompleteItems.value = []
  argAutocompleteKey.value = null
}

function onArgKeydown(event: KeyboardEvent, step: RobotStep, aIdx: number) {
  if (!argAutocompleteItems.value.length) return
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    argAutocompleteIndex.value = Math.min(argAutocompleteIndex.value + 1, argAutocompleteItems.value.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    argAutocompleteIndex.value = Math.max(argAutocompleteIndex.value - 1, 0)
  } else if (event.key === 'Enter' && argAutocompleteIndex.value >= 0) {
    event.preventDefault()
    selectArgVar(step, aIdx, argAutocompleteItems.value[argAutocompleteIndex.value])
  } else if (event.key === 'Escape') {
    argAutocompleteItems.value = []
    argAutocompleteKey.value = null
  }
}

function onArgBlur() {
  setTimeout(() => { argAutocompleteItems.value = []; argAutocompleteKey.value = null }, 200)
}

// --- Arg input helpers ---
function hasVariable(val: string): boolean {
  return /[$@&%]\{[^}]+\}/.test(val)
}

function highlightVariables(val: string): string {
  if (!val) return ''
  // Escape HTML, then wrap ${}, @{}, &{}, %{} references in colored spans
  const escaped = val.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return escaped.replace(/([$@&])\{([^}]+)\}/g, '<span class="hl-var">$1{$2}</span>')
    .replace(/%\{([^}]+)\}/g, '<span class="hl-env">%{$1}</span>')
}

function syncOverlayScroll(e: Event) {
  const input = e.target as HTMLInputElement
  const overlay = input.parentElement?.querySelector('.arg-highlight-overlay, .form-hl-overlay') as HTMLElement
  if (overlay) overlay.scrollLeft = input.scrollLeft
}

function argInputWidth(val: string): string {
  const len = Math.max((val || '').length, 6)
  return Math.min(len, 30) + 'ch'
}

function ensureArgSyntax(kw: { arguments: string[] }, idx: number) {
  let v = kw.arguments[idx]
  if (!v) return
  v = v.trim()
  if (!v) return
  // Skip the bare @{} separator (named-only marker)
  if (v === '@{}') return
  // Already has correct RF variable syntax — validate closing brace
  if (/^[$@&]\{[^}]*\}(=.*)?$/.test(v)) return

  // Determine correct prefix based on current arg type
  const prefix = v.startsWith('@{') ? '@{' : v.startsWith('&{') ? '&{' : '${'

  // Strip any partial/wrong RF syntax the user may have typed
  let name = v.replace(/^[$@&%]\{/, '').replace(/\}(=.*)?$/, '')
  // Extract default value if present
  let defaultVal = ''
  const origMatch = v.match(/\}=(.*)$/)
  if (origMatch) {
    defaultVal = '=' + origMatch[1]
  } else {
    // Check if bare name has = (e.g. user typed "name=default" without ${})
    const eqIdx = name.indexOf('=')
    if (eqIdx > 0) {
      defaultVal = name.substring(eqIdx)
      name = name.substring(0, eqIdx)
    }
  }
  // Clean the name: remove any leftover braces or sigils
  name = name.replace(/[$@&%{}]/g, '').trim()
  if (!name) return
  kw.arguments[idx] = prefix + name + '}' + defaultVal
}

// Auto-repair variable name syntax on blur: ensure ${name} / @{name} / &{name} format
function ensureVarSyntax(v: RobotVariable) {
  if (!v.name || v.name === '#') return
  let name = v.name.trim()
  if (!name) return
  // Already valid RF variable syntax
  if (/^[$@&%]\{[^}]+\}$/.test(name)) return
  // Determine prefix — preserve @{} or &{} if user typed it, default to ${}
  let prefix = '${'
  if (name.startsWith('@')) prefix = '@{'
  else if (name.startsWith('&')) prefix = '&{'
  else if (name.startsWith('%')) prefix = '%{'
  // Strip any partial syntax
  name = name.replace(/^[$@&%]\{?/, '').replace(/\}$/, '').replace(/[$@&%{}]/g, '').trim()
  if (!name) return
  v.name = prefix + name + '}'
}

// Auto-repair return variable syntax on blur
function ensureReturnVarSyntax(step: RobotStep, idx: number) {
  let name = step.returnVars[idx]
  if (!name) return
  name = name.trim()
  if (!name) return
  if (/^[$@&%]\{[^}]+\}$/.test(name)) return
  let prefix = '${'
  if (name.startsWith('@')) prefix = '@{'
  else if (name.startsWith('&')) prefix = '&{'
  else if (name.startsWith('%')) prefix = '%{'
  name = name.replace(/^[$@&%]\{?/, '').replace(/\}$/, '').replace(/[$@&%{}]/g, '').trim()
  if (!name) return
  step.returnVars[idx] = prefix + name + '}'
}

// --- Argument Name Labels ---
function formatArgLabel(arg: string): string {
  // @{args} → *args, &{kwargs} → **kwargs, ${name}=default → name?, ${name} → name
  if (arg.startsWith('@{')) return '*' + arg.replace(/^@\{([^}]*)\}.*$/, '$1')
  if (arg.startsWith('&{')) return '**' + arg.replace(/^&\{([^}]*)\}.*$/, '$1')
  const name = arg.replace(/^[$@&%]\{([^}]+)\}.*$/, '$1').replace(/=.*$/, '')
  const hasDefault = arg.includes('=')
  return hasDefault ? name + '?' : name
}

function getKeywordArgNames(step: RobotStep): string[] {
  const kw = step.keyword.toLowerCase().trim()
  // Strip resource prefix: "account.Account Speichern" → "account speichern"
  const bare = kw.includes('.') ? kw.substring(kw.indexOf('.') + 1).trim() : kw
  for (const lookup of [kw, bare]) {
    const builtin = RF_KEYWORD_SIGNATURES.get(lookup)
    if (builtin) return builtin
    const localKw = form.keywords.find(k => k.name.toLowerCase() === lookup)
    if (localKw?.arguments?.length) {
      return localKw.arguments.filter(a => a !== '@{}').map(formatArgLabel)
    }
    const cached = knownKeywordArgs.get(lookup)
    if (cached?.length) {
      return cached.filter(a => a !== '@{}').map(formatArgLabel)
    }
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
    name: '', documentation: '', arguments: [], tags: [],
    setup: '', teardown: '', timeout: '', returnValue: '', steps: [],
  })
}
function removeKeyword(i: number) { form.keywords.splice(i, 1); collapsedKeywords.value.delete(i) }
function toggleKeyword(i: number) {
  if (collapsedKeywords.value.has(i)) collapsedKeywords.value.delete(i)
  else collapsedKeywords.value.add(i)
}

// Keyword argument helpers
const newKeywordArgInputs = ref<Map<number, string>>(new Map())
function addKeywordArg(kwIndex: number, arg: string) {
  if (arg.trim()) form.keywords[kwIndex].arguments.push(arg.trim())
}
function removeKeywordArg(kwIndex: number, argIdx: number) { form.keywords[kwIndex].arguments.splice(argIdx, 1) }
function handleAddKeywordArg(kwIndex: number) {
  addKeywordArg(kwIndex, newKeywordArgInputs.value.get(kwIndex) || '')
  newKeywordArgInputs.value.set(kwIndex, '')
}

// Typed argument add helpers — user doesn't need to know RF syntax
function addTypedArg(kwIndex: number, type: 'positional' | 'optional' | 'varargs' | 'kwargs' | 'named-only') {
  const kw = form.keywords[kwIndex]
  switch (type) {
    case 'positional':
      kw.arguments.push('${arg}')
      break
    case 'optional':
      kw.arguments.push('${arg}=')
      break
    case 'varargs':
      // Only one @{} allowed
      if (!kw.arguments.some(a => a.startsWith('@{'))) {
        kw.arguments.push('@{args}')
      }
      break
    case 'kwargs':
      // Only one &{} allowed, must be last
      if (!kw.arguments.some(a => a.startsWith('&{'))) {
        kw.arguments.push('&{kwargs}')
      }
      break
    case 'named-only':
      // Named-only args go after @{} or after bare @{} marker
      // If no varargs present, insert @{} first as separator
      if (!kw.arguments.some(a => a.startsWith('@{'))) {
        kw.arguments.push('@{}')
      }
      kw.arguments.push('${arg}=')
      break
  }
}

// Detect argument type from RF syntax for display
function argType(arg: string): 'positional' | 'optional' | 'varargs' | 'kwargs' | 'named-only-sep' | 'named-only' {
  if (arg === '@{}') return 'named-only-sep'
  if (arg.startsWith('@{')) return 'varargs'
  if (arg.startsWith('&{')) return 'kwargs'
  // Check if this arg is after @{} or @{varargs} → named-only
  // (handled in template via computed)
  if (arg.includes('=')) return 'optional'
  return 'positional'
}

// Get human-readable name from RF arg syntax: ${name}=default → name, @{args} → args
function argDisplayName(arg: string): string {
  return arg.replace(/^[$@&%]\{([^}]*)\}.*$/, '$1')
}

// Get default value from arg: ${name}=default → default
function argDefaultValue(arg: string): string {
  const m = arg.match(/\}=(.*)$/)
  return m ? m[1] : ''
}

// Set just the name part, preserving type prefix and default
function setArgName(kw: RobotKeyword, idx: number, newName: string) {
  const arg = kw.arguments[idx]
  const prefix = arg.match(/^([$@&%]\{)/)?.[1] || '${'
  const suffix = arg.match(/(\}=?.*)$/)?.[1] || '}'
  // Strip any RF syntax the user might paste/type into the bare name field
  const cleanName = newName.replace(/[$@&%{}]/g, '')
  kw.arguments[idx] = prefix + cleanName + suffix
}

// Set just the default value
function setArgDefault(kw: RobotKeyword, idx: number, newDefault: string) {
  const arg = kw.arguments[idx]
  const base = arg.replace(/\}=.*$/, '}')
  kw.arguments[idx] = base + '=' + newDefault
}

// Check if an argument at given index is after varargs (named-only)
function isNamedOnly(kw: RobotKeyword, idx: number): boolean {
  for (let i = 0; i < idx; i++) {
    if (kw.arguments[i].startsWith('@{')) return true
  }
  return false
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
// --- Step row overflow detection → vertical args layout ---
const visualEditorRef = ref<HTMLElement | null>(null)
let stepRowObserver: MutationObserver | null = null
let stepRowResizeObserver: ResizeObserver | null = null

function checkStepRowOverflow() {
  if (!visualEditorRef.value) return
  const rows = visualEditorRef.value.querySelectorAll('.step-row')
  for (const row of rows) {
    const el = row as HTMLElement
    // A single-line step-row is ~32px; if it's taller, args have wrapped
    const isWrapped = el.scrollHeight > 40
    el.classList.toggle('args-vertical', isWrapped)
  }
}

function setupStepRowObserver() {
  if (!visualEditorRef.value) return
  // Re-check on DOM mutations (args added/removed) and on resize
  stepRowObserver = new MutationObserver(() => nextTick(checkStepRowOverflow))
  stepRowObserver.observe(visualEditorRef.value, { childList: true, subtree: true })
  stepRowResizeObserver = new ResizeObserver(() => checkStepRowOverflow())
  stepRowResizeObserver.observe(visualEditorRef.value)
  nextTick(checkStepRowOverflow)
}

function teardownStepRowObserver() {
  stepRowObserver?.disconnect()
  stepRowResizeObserver?.disconnect()
  stepRowObserver = null
  stepRowResizeObserver = null
}

onMounted(() => {
  parseRobotToForm(props.content)
  internalCode.value = props.content
  lazyLoadKeywordArgs()
  nextTick(setupStepRowObserver)
})
onUnmounted(() => { destroyCodeEditor(); teardownStepRowObserver() })

watch(() => props.content, (newContent) => {
  // Skip re-parsing if this is our own emitted content (prevents reactive watch cycle
  // that would lose items with empty names during round-trip serialize→parse)
  if (newContent === lastEmittedContent) return

  if (activeTab.value === 'visual') {
    parseRobotToForm(newContent)
    lazyLoadKeywordArgs()
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
        <button v-if="activeTab === 'visual'" class="icon-btn" @click="expandAllSections" :title="t('robotEditor.expandAll')">&#x229E;</button>
        <button v-if="activeTab === 'visual'" class="icon-btn" @click="collapseAllSections" :title="t('robotEditor.collapseAll')">&#x229F;</button>
      </div>
    </div>

    <!-- Parse Error Banner -->
    <div v-if="parseError" class="parse-error-banner">
      <span>{{ t('robotEditor.parseError') }}:</span> {{ parseError }}
    </div>

    <!-- Visual Tab -->
    <div v-show="activeTab === 'visual'" ref="visualEditorRef" class="visual-editor">

      <!-- *** Settings *** -->
      <div class="editor-section section-settings">
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
              <select v-model="s.key" class="form-input setting-type-select" :class="settingTypeColor(s.key)">
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
              <span v-else class="form-hl-wrap flex-1">
                <span class="form-hl-overlay" v-html="highlightVariables(s.value)"></span>
                <input v-model="s.value" class="form-input" style="width: 100%" :placeholder="t('robotEditor.settingValuePlaceholder')" spellcheck="false" />
              </span>
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
      <div class="editor-section section-variables">
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
              <span class="form-hl-wrap hl-var-name">
                <span class="form-hl-overlay hl-mono" v-html="highlightVariables(v.name)"></span>
                <input v-model="v.name" class="form-input var-name-input" :placeholder="t('robotEditor.variableNamePlaceholder')" @blur="ensureVarSyntax(v)" spellcheck="false" />
              </span>
              <span class="form-hl-wrap flex-1">
                <span class="form-hl-overlay" v-html="highlightVariables(v.value)"></span>
                <input v-model="v.value" class="form-input" style="width: 100%" :placeholder="t('robotEditor.variableValuePlaceholder')" spellcheck="false" />
              </span>
              <button class="step-btn danger" @click="removeVariable(vIdx)" :title="t('common.delete')">&times;</button>
            </template>
          </div>
        </div>
      </div>

      <!-- *** Test Cases *** (hidden for .resource) -->
      <div v-if="!isResource" class="editor-section section-testcases">
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
              <div v-if="isMetaVisible('tc', tcIdx, 'tags', tc.tags.length ? 'x' : '')" class="form-group">
                <label class="form-label">{{ t('robotEditor.tags') }} <button class="meta-close-btn" v-if="!tc.tags.length" @click="toggleMeta('tc', tcIdx, 'tags')">&times;</button></label>
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
              <div class="meta-toggles">
                <button v-if="!isMetaVisible('tc', tcIdx, 'tags', tc.tags.length ? 'x' : '')" class="meta-toggle-btn mt-tags" @click="toggleMeta('tc', tcIdx, 'tags')">+ Tags</button>
                <button v-if="!isMetaVisible('tc', tcIdx, 'setup', tc.setup)" class="meta-toggle-btn mt-setup" @click="toggleMeta('tc', tcIdx, 'setup')">+ Setup</button>
                <button v-if="!isMetaVisible('tc', tcIdx, 'teardown', tc.teardown)" class="meta-toggle-btn mt-teardown" @click="toggleMeta('tc', tcIdx, 'teardown')">+ Teardown</button>
                <button v-if="!isMetaVisible('tc', tcIdx, 'timeout', tc.timeout)" class="meta-toggle-btn mt-config" @click="toggleMeta('tc', tcIdx, 'timeout')">+ Timeout</button>
                <button v-if="!isMetaVisible('tc', tcIdx, 'template', tc.template)" class="meta-toggle-btn mt-config" @click="toggleMeta('tc', tcIdx, 'template')">+ Template</button>
              </div>
              <div v-if="isMetaVisible('tc', tcIdx, 'setup', tc.setup) || isMetaVisible('tc', tcIdx, 'teardown', tc.teardown)" class="form-row">
                <div v-if="isMetaVisible('tc', tcIdx, 'setup', tc.setup)" class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.setup') }} <button class="meta-close-btn" v-if="!tc.setup" @click="toggleMeta('tc', tcIdx, 'setup')">&times;</button></label>
                  <span class="form-hl-wrap">
                    <span class="form-hl-overlay" v-html="highlightVariables(tc.setup)"></span>
                    <input v-model="tc.setup" class="form-input" style="width: 100%" :placeholder="t('robotEditor.setupPlaceholder')" spellcheck="false" />
                  </span>
                </div>
                <div v-if="isMetaVisible('tc', tcIdx, 'teardown', tc.teardown)" class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.teardown') }} <button class="meta-close-btn" v-if="!tc.teardown" @click="toggleMeta('tc', tcIdx, 'teardown')">&times;</button></label>
                  <span class="form-hl-wrap">
                    <span class="form-hl-overlay" v-html="highlightVariables(tc.teardown)"></span>
                    <input v-model="tc.teardown" class="form-input" style="width: 100%" :placeholder="t('robotEditor.teardownPlaceholder')" spellcheck="false" />
                  </span>
                </div>
              </div>
              <div v-if="isMetaVisible('tc', tcIdx, 'timeout', tc.timeout) || isMetaVisible('tc', tcIdx, 'template', tc.template)" class="form-row">
                <div v-if="isMetaVisible('tc', tcIdx, 'timeout', tc.timeout)" class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.timeout') }} <button class="meta-close-btn" v-if="!tc.timeout" @click="toggleMeta('tc', tcIdx, 'timeout')">&times;</button></label>
                  <span class="form-hl-wrap">
                    <span class="form-hl-overlay" v-html="highlightVariables(tc.timeout)"></span>
                    <input v-model="tc.timeout" class="form-input" style="width: 100%" :placeholder="t('robotEditor.timeoutPlaceholder')" spellcheck="false" />
                  </span>
                </div>
                <div v-if="isMetaVisible('tc', tcIdx, 'template', tc.template)" class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.template') }} <button class="meta-close-btn" v-if="!tc.template" @click="toggleMeta('tc', tcIdx, 'template')">&times;</button></label>
                  <span class="form-hl-wrap">
                    <span class="form-hl-overlay" v-html="highlightVariables(tc.template)"></span>
                    <input v-model="tc.template" class="form-input" style="width: 100%" :placeholder="t('robotEditor.templatePlaceholder')" spellcheck="false" />
                  </span>
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
                        <input v-model="step.keyword" class="form-input step-keyword-input" spellcheck="false"
                          :style="{ width: Math.max(18, Math.min((step.keyword || '').length + 5, 60)) + 'ch' }"
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
                            <span v-if="s.args?.length" class="kw-suggestion-args">{{ s.args.map(a => a.replace(/^[$@&%]\{([^}]+)\}.*$/, '$1')).join(', ') }}</span>
                            <span class="kw-suggestion-source" :class="'source-' + (s.source === 'builtin' ? 'builtin' : s.source === 'local' || s.source === 'project' ? 'local' : 'library')">{{ s.source === 'builtin' ? t('robotEditor.builtinKeyword') : s.source === 'local' || s.source === 'project' ? t('robotEditor.localKeyword') : s.source }}</span>
                          </div>
                        </div>
                      </div>
                      <div v-if="step.args.length" class="step-args-group">
                        <span v-for="(arg, aIdx) in step.args" :key="aIdx" class="step-arg-chip arg-ac-wrapper">
                          <span v-if="getKeywordArgNames(step)[aIdx]" class="arg-label">{{ getKeywordArgNames(step)[aIdx] }}</span>
                          <span class="arg-highlight-wrap" :style="{ width: argInputWidth(step.args[aIdx]) }">
                            <span class="arg-highlight-overlay" v-html="highlightVariables(step.args[aIdx])"></span>
                            <input v-model="step.args[aIdx]" class="step-arg-input" spellcheck="false"
                              @scroll="syncOverlayScroll" :style="{ width: '100%' }"
                              :placeholder="getKeywordArgNames(step)[aIdx] || t('robotEditor.argPlaceholder')"
                              @input="onArgInput(($event.target as HTMLInputElement).value, `${sIdx}-${aIdx}`)"
                              @keydown="onArgKeydown($event, step, aIdx)"
                              @blur="onArgBlur" autocomplete="off" />
                          </span>
                          <div v-if="argAutocompleteKey === `${sIdx}-${aIdx}` && argAutocompleteItems.length" class="arg-ac-dropdown">
                            <div v-for="(v, vi) in argAutocompleteItems" :key="v"
                              class="arg-ac-item" :class="{ active: vi === argAutocompleteIndex }"
                              @mousedown.prevent="selectArgVar(step, aIdx, v)">{{ v }}</div>
                          </div>
                          <button class="chip-remove" @click="removeStepArg(step, aIdx)">&times;</button>
                        </span>
                      </div>
                      <button class="step-btn step-add-arg" :class="{ 'has-hint': nextArgHint(step) !== '+' }" @click="addStepArg(step)" :title="t('robotEditor.addArg')">{{ nextArgHint(step) }}</button>
                    </template>

                    <!-- Assignment type -->
                    <template v-else-if="step.type === 'assignment'">
                      <span v-for="(rv, rvIdx) in step.returnVars" :key="rvIdx" class="step-var-chip">
                        <input v-model="step.returnVars[rvIdx]" class="step-var-input" spellcheck="false" placeholder="${var}" @blur="ensureReturnVarSyntax(step, rvIdx)" />
                        <button class="chip-remove" @click="removeReturnVar(step, rvIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-var" @click="addReturnVar(step)" title="+var">+v</button>
                      <span class="step-assign-eq">=</span>
                      <div class="keyword-autocomplete-wrapper">
                        <input v-model="step.keyword" class="form-input step-keyword-input" spellcheck="false"
                          :style="{ width: Math.max(18, Math.min((step.keyword || '').length + 5, 60)) + 'ch' }"
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
                            <span v-if="s.args?.length" class="kw-suggestion-args">{{ s.args.map(a => a.replace(/^[$@&%]\{([^}]+)\}.*$/, '$1')).join(', ') }}</span>
                            <span class="kw-suggestion-source" :class="'source-' + (s.source === 'builtin' ? 'builtin' : s.source === 'local' || s.source === 'project' ? 'local' : 'library')">{{ s.source === 'builtin' ? t('robotEditor.builtinKeyword') : s.source === 'local' || s.source === 'project' ? t('robotEditor.localKeyword') : s.source }}</span>
                          </div>
                        </div>
                      </div>
                      <div v-if="step.args.length" class="step-args-group">
                        <span v-for="(arg, aIdx) in step.args" :key="aIdx" class="step-arg-chip arg-ac-wrapper">
                          <span v-if="getKeywordArgNames(step)[aIdx]" class="arg-label">{{ getKeywordArgNames(step)[aIdx] }}</span>
                          <span class="arg-highlight-wrap" :style="{ width: argInputWidth(step.args[aIdx]) }">
                            <span class="arg-highlight-overlay" v-html="highlightVariables(step.args[aIdx])"></span>
                            <input v-model="step.args[aIdx]" class="step-arg-input" spellcheck="false"
                              @scroll="syncOverlayScroll" :style="{ width: '100%' }"
                              :placeholder="getKeywordArgNames(step)[aIdx] || t('robotEditor.argPlaceholder')"
                              @input="onArgInput(($event.target as HTMLInputElement).value, `${sIdx}-${aIdx}`)"
                              @keydown="onArgKeydown($event, step, aIdx)"
                              @blur="onArgBlur" autocomplete="off" />
                          </span>
                          <div v-if="argAutocompleteKey === `${sIdx}-${aIdx}` && argAutocompleteItems.length" class="arg-ac-dropdown">
                            <div v-for="(v, vi) in argAutocompleteItems" :key="v"
                              class="arg-ac-item" :class="{ active: vi === argAutocompleteIndex }"
                              @mousedown.prevent="selectArgVar(step, aIdx, v)">{{ v }}</div>
                          </div>
                          <button class="chip-remove" @click="removeStepArg(step, aIdx)">&times;</button>
                        </span>
                      </div>
                      <button class="step-btn step-add-arg" :class="{ 'has-hint': nextArgHint(step) !== '+' }" @click="addStepArg(step)" :title="t('robotEditor.addArg')">{{ nextArgHint(step) }}</button>
                    </template>

                    <!-- VAR type -->
                    <template v-else-if="step.type === 'var'">
                      <span class="step-var-chip">
                        <input v-model="step.returnVars[0]" class="step-var-input" spellcheck="false" placeholder="${var}" @blur="ensureReturnVarSyntax(step, 0)" />
                      </span>
                      <span class="step-assign-eq">=</span>
                      <span v-for="(arg, aIdx) in step.args" :key="aIdx" class="step-arg-chip">
                        <span class="arg-highlight-wrap" :style="{ width: argInputWidth(step.args[aIdx]) }">
                          <span class="arg-highlight-overlay" v-html="highlightVariables(step.args[aIdx])"></span>
                          <input v-model="step.args[aIdx]" class="step-arg-input" spellcheck="false"
                            @scroll="syncOverlayScroll" :style="{ width: '100%' }"
                            :placeholder="t('robotEditor.valuePlaceholder')" />
                        </span>
                        <button class="chip-remove" @click="removeStepArg(step, aIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-arg" @click="addStepArg(step)" :title="t('robotEditor.addValue')">+</button>
                      <select v-model="step.varScope" class="step-scope-select">
                        <option value="">scope</option>
                        <option v-for="s in VAR_SCOPES" :key="s" :value="s">{{ s }}</option>
                      </select>
                    </template>

                    <!-- FOR type -->
                    <template v-else-if="step.type === 'for'">
                      <span class="form-hl-wrap hl-var-inline">
                        <span class="form-hl-overlay hl-mono" v-html="highlightVariables(step.loopVar)"></span>
                        <input v-model="step.loopVar" class="form-input step-var-input-inline" spellcheck="false" style="width: 100%" placeholder="${item}" />
                      </span>
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
                      <span class="form-hl-wrap flex-1 hl-condition-wrap">
                        <span class="form-hl-overlay hl-condition" v-html="highlightVariables(step.condition)"></span>
                        <input v-model="step.condition" class="form-input step-condition-input" style="width: 100%" :placeholder="t('robotEditor.conditionPlaceholder')" spellcheck="false" />
                      </span>
                    </template>

                    <!-- EXCEPT -->
                    <template v-else-if="step.type === 'except'">
                      <input v-model="step.exceptPattern" class="form-input step-keyword-input" spellcheck="false" :placeholder="t('robotEditor.exceptPatternPlaceholder')" />
                      <span v-if="step.exceptVar || step.exceptPattern" class="step-as-label">AS</span>
                      <span v-if="step.exceptVar || step.exceptPattern" class="form-hl-wrap hl-var-inline">
                        <span class="form-hl-overlay hl-mono" v-html="highlightVariables(step.exceptVar)"></span>
                        <input v-model="step.exceptVar" class="form-input step-var-input-inline" spellcheck="false" style="width: 100%" placeholder="${error}" />
                      </span>
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
                      <input v-model="step.comment" class="form-input flex-1 step-comment-input" spellcheck="false" placeholder="# ..." />
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
                    <button class="add-step-btn add-keyword" @click="addStep(tc.steps)">+ {{ t('robotEditor.addStep') }}</button>
                    <button class="add-step-btn add-block add-var" @click="addStep(tc.steps, 'var')">+ VAR</button>
                    <button class="add-step-btn add-block add-loop" @click="addBlock(tc.steps, 'for')">+ FOR</button>
                    <button class="add-step-btn add-block add-condition" @click="addBlock(tc.steps, 'if')">+ IF</button>
                    <button class="add-step-btn add-block add-loop" @click="addBlock(tc.steps, 'while')">+ WHILE</button>
                    <button class="add-step-btn add-block add-error" @click="addBlock(tc.steps, 'try')">+ TRY</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- *** Keywords *** -->
      <div class="editor-section section-keywords">
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
                <div class="kw-args-list">
                  <div v-for="(arg, argIdx) in kw.arguments" :key="argIdx" class="kw-arg-row"
                    :class="'kw-arg-' + (arg === '@{}' ? 'sep' : isNamedOnly(kw, argIdx) ? 'named' : argType(arg))">
                    <!-- Named-only separator -->
                    <template v-if="arg === '@{}'">
                      <span class="kw-arg-sep-line"></span>
                      <span class="kw-arg-sep-label">{{ t('robotEditor.argTypes.namedOnlyBelow') }}</span>
                      <span class="kw-arg-sep-line"></span>
                    </template>
                    <!-- Varargs @{} -->
                    <template v-else-if="arg.startsWith('@{')">
                      <span class="kw-arg-type-badge badge-varargs">*{{ t('robotEditor.argTypes.varargs') }}</span>
                      <input class="kw-arg-name-input" spellcheck="false" :value="argDisplayName(arg)"
                        @input="setArgName(kw, argIdx, ($event.target as HTMLInputElement).value)"
                        @blur="ensureArgSyntax(kw, argIdx)" placeholder="args" />
                    </template>
                    <!-- Kwargs &{} -->
                    <template v-else-if="arg.startsWith('&{')">
                      <span class="kw-arg-type-badge badge-kwargs">**{{ t('robotEditor.argTypes.kwargs') }}</span>
                      <input class="kw-arg-name-input" spellcheck="false" :value="argDisplayName(arg)"
                        @input="setArgName(kw, argIdx, ($event.target as HTMLInputElement).value)"
                        @blur="ensureArgSyntax(kw, argIdx)" placeholder="kwargs" />
                    </template>
                    <!-- Positional or optional (with/without default) -->
                    <template v-else>
                      <span v-if="isNamedOnly(kw, argIdx)" class="kw-arg-type-badge badge-named">{{ t('robotEditor.argTypes.namedOnly') }}</span>
                      <span v-else-if="arg.includes('=')" class="kw-arg-type-badge badge-optional">{{ t('robotEditor.argTypes.optional') }}</span>
                      <span v-else class="kw-arg-type-badge badge-required">{{ t('robotEditor.argTypes.required') }}</span>
                      <input class="kw-arg-name-input" spellcheck="false" :value="argDisplayName(arg)"
                        @input="setArgName(kw, argIdx, ($event.target as HTMLInputElement).value)"
                        @blur="ensureArgSyntax(kw, argIdx)" :placeholder="t('robotEditor.argTypes.namePlaceholder')" />
                      <template v-if="arg.includes('=')">
                        <span class="kw-arg-eq">=</span>
                        <span class="form-hl-wrap kw-default-wrap">
                          <span class="form-hl-overlay hl-kw-default" v-html="highlightVariables(argDefaultValue(arg))"></span>
                          <input class="kw-arg-default-input" spellcheck="false" :value="argDefaultValue(arg)"
                            @input="setArgDefault(kw, argIdx, ($event.target as HTMLInputElement).value)"
                            :placeholder="t('robotEditor.argTypes.defaultPlaceholder')" />
                        </span>
                      </template>
                      <!-- Toggle default value -->
                      <button v-if="!arg.includes('=')" class="kw-arg-opt-btn" @click="kw.arguments[argIdx] = arg + '='"
                        :title="t('robotEditor.argTypes.addDefault')">= ?</button>
                    </template>
                    <button class="chip-remove" @click="removeKeywordArg(kwIdx, argIdx)">&times;</button>
                  </div>
                </div>
                <div class="kw-arg-add-buttons">
                  <button class="kw-arg-add-btn" @click="addTypedArg(kwIdx, 'positional')">+ {{ t('robotEditor.argTypes.required') }}</button>
                  <button class="kw-arg-add-btn" @click="addTypedArg(kwIdx, 'optional')">+ {{ t('robotEditor.argTypes.optional') }}</button>
                  <button class="kw-arg-add-btn" :disabled="kw.arguments.some(a => a.startsWith('@{'))"
                    @click="addTypedArg(kwIdx, 'varargs')">+ {{ t('robotEditor.argTypes.varargs') }}</button>
                  <button class="kw-arg-add-btn" :disabled="kw.arguments.some(a => a.startsWith('&{'))"
                    @click="addTypedArg(kwIdx, 'kwargs')">+ {{ t('robotEditor.argTypes.kwargs') }}</button>
                  <button class="kw-arg-add-btn" @click="addTypedArg(kwIdx, 'named-only')">+ {{ t('robotEditor.argTypes.namedOnly') }}</button>
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">{{ t('robotEditor.documentation') }}</label>
                <textarea v-model="kw.documentation" class="form-input form-textarea" rows="2" :placeholder="t('robotEditor.documentationPlaceholder')"></textarea>
              </div>
              <div v-if="isMetaVisible('kw', kwIdx, 'tags', kw.tags.length ? 'x' : '')" class="form-group">
                <label class="form-label">{{ t('robotEditor.tags') }} <button class="meta-close-btn" v-if="!kw.tags.length" @click="toggleMeta('kw', kwIdx, 'tags')">&times;</button></label>
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
              <div class="meta-toggles">
                <button v-if="!isMetaVisible('kw', kwIdx, 'tags', kw.tags.length ? 'x' : '')" class="meta-toggle-btn mt-tags" @click="toggleMeta('kw', kwIdx, 'tags')">+ Tags</button>
                <button v-if="!isMetaVisible('kw', kwIdx, 'setup', kw.setup)" class="meta-toggle-btn mt-setup" @click="toggleMeta('kw', kwIdx, 'setup')">+ Setup</button>
                <button v-if="!isMetaVisible('kw', kwIdx, 'teardown', kw.teardown)" class="meta-toggle-btn mt-teardown" @click="toggleMeta('kw', kwIdx, 'teardown')">+ Teardown</button>
                <button v-if="!isMetaVisible('kw', kwIdx, 'timeout', kw.timeout)" class="meta-toggle-btn mt-config" @click="toggleMeta('kw', kwIdx, 'timeout')">+ Timeout</button>
                <button v-if="!isMetaVisible('kw', kwIdx, 'return', kw.returnValue)" class="meta-toggle-btn mt-return" @click="toggleMeta('kw', kwIdx, 'return')">+ Return</button>
              </div>
              <div v-if="isMetaVisible('kw', kwIdx, 'setup', kw.setup) || isMetaVisible('kw', kwIdx, 'teardown', kw.teardown)" class="form-row">
                <div v-if="isMetaVisible('kw', kwIdx, 'setup', kw.setup)" class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.setup') }} <button class="meta-close-btn" v-if="!kw.setup" @click="toggleMeta('kw', kwIdx, 'setup')">&times;</button></label>
                  <span class="form-hl-wrap">
                    <span class="form-hl-overlay" v-html="highlightVariables(kw.setup)"></span>
                    <input v-model="kw.setup" class="form-input" style="width: 100%" :placeholder="t('robotEditor.setupPlaceholder')" spellcheck="false" />
                  </span>
                </div>
                <div v-if="isMetaVisible('kw', kwIdx, 'teardown', kw.teardown)" class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.teardown') }} <button class="meta-close-btn" v-if="!kw.teardown" @click="toggleMeta('kw', kwIdx, 'teardown')">&times;</button></label>
                  <span class="form-hl-wrap">
                    <span class="form-hl-overlay" v-html="highlightVariables(kw.teardown)"></span>
                    <input v-model="kw.teardown" class="form-input" style="width: 100%" :placeholder="t('robotEditor.teardownPlaceholder')" spellcheck="false" />
                  </span>
                </div>
              </div>
              <div v-if="isMetaVisible('kw', kwIdx, 'timeout', kw.timeout) || isMetaVisible('kw', kwIdx, 'return', kw.returnValue)" class="form-row">
                <div v-if="isMetaVisible('kw', kwIdx, 'timeout', kw.timeout)" class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.timeout') }} <button class="meta-close-btn" v-if="!kw.timeout" @click="toggleMeta('kw', kwIdx, 'timeout')">&times;</button></label>
                  <span class="form-hl-wrap">
                    <span class="form-hl-overlay" v-html="highlightVariables(kw.timeout)"></span>
                    <input v-model="kw.timeout" class="form-input" style="width: 100%" :placeholder="t('robotEditor.timeoutPlaceholder')" spellcheck="false" />
                  </span>
                </div>
                <div v-if="isMetaVisible('kw', kwIdx, 'return', kw.returnValue)" class="form-group flex-1">
                  <label class="form-label">{{ t('robotEditor.returnValue') }} <button class="meta-close-btn" v-if="!kw.returnValue" @click="toggleMeta('kw', kwIdx, 'return')">&times;</button></label>
                  <span class="form-hl-wrap">
                    <span class="form-hl-overlay" v-html="highlightVariables(kw.returnValue)"></span>
                    <input v-model="kw.returnValue" class="form-input" style="width: 100%" :placeholder="t('robotEditor.returnValuePlaceholder')" spellcheck="false" />
                  </span>
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
                        <input v-model="step.keyword" class="form-input step-keyword-input" spellcheck="false"
                          :style="{ width: Math.max(18, Math.min((step.keyword || '').length + 5, 60)) + 'ch' }"
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
                            <span v-if="s.args?.length" class="kw-suggestion-args">{{ s.args.map(a => a.replace(/^[$@&%]\{([^}]+)\}.*$/, '$1')).join(', ') }}</span>
                            <span class="kw-suggestion-source" :class="'source-' + (s.source === 'builtin' ? 'builtin' : s.source === 'local' || s.source === 'project' ? 'local' : 'library')">{{ s.source === 'builtin' ? t('robotEditor.builtinKeyword') : s.source === 'local' || s.source === 'project' ? t('robotEditor.localKeyword') : s.source }}</span>
                          </div>
                        </div>
                      </div>
                      <div v-if="step.args.length" class="step-args-group">
                        <span v-for="(arg, aIdx) in step.args" :key="aIdx" class="step-arg-chip arg-ac-wrapper">
                          <span v-if="getKeywordArgNames(step)[aIdx]" class="arg-label">{{ getKeywordArgNames(step)[aIdx] }}</span>
                          <span class="arg-highlight-wrap" :style="{ width: argInputWidth(step.args[aIdx]) }">
                            <span class="arg-highlight-overlay" v-html="highlightVariables(step.args[aIdx])"></span>
                            <input v-model="step.args[aIdx]" class="step-arg-input" spellcheck="false"
                              @scroll="syncOverlayScroll" :style="{ width: '100%' }"
                              :placeholder="getKeywordArgNames(step)[aIdx] || t('robotEditor.argPlaceholder')"
                              @input="onArgInput(($event.target as HTMLInputElement).value, `${sIdx}-${aIdx}`)"
                              @keydown="onArgKeydown($event, step, aIdx)"
                              @blur="onArgBlur" autocomplete="off" />
                          </span>
                          <div v-if="argAutocompleteKey === `${sIdx}-${aIdx}` && argAutocompleteItems.length" class="arg-ac-dropdown">
                            <div v-for="(v, vi) in argAutocompleteItems" :key="v"
                              class="arg-ac-item" :class="{ active: vi === argAutocompleteIndex }"
                              @mousedown.prevent="selectArgVar(step, aIdx, v)">{{ v }}</div>
                          </div>
                          <button class="chip-remove" @click="removeStepArg(step, aIdx)">&times;</button>
                        </span>
                      </div>
                      <button class="step-btn step-add-arg" :class="{ 'has-hint': nextArgHint(step) !== '+' }" @click="addStepArg(step)" :title="t('robotEditor.addArg')">{{ nextArgHint(step) }}</button>
                    </template>

                    <!-- Assignment -->
                    <template v-else-if="step.type === 'assignment'">
                      <span v-for="(rv, rvIdx) in step.returnVars" :key="rvIdx" class="step-var-chip">
                        <input v-model="step.returnVars[rvIdx]" class="step-var-input" spellcheck="false" placeholder="${var}" @blur="ensureReturnVarSyntax(step, rvIdx)" />
                        <button class="chip-remove" @click="removeReturnVar(step, rvIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-var" @click="addReturnVar(step)" title="+var">+v</button>
                      <span class="step-assign-eq">=</span>
                      <div class="keyword-autocomplete-wrapper">
                        <input v-model="step.keyword" class="form-input step-keyword-input" spellcheck="false"
                          :style="{ width: Math.max(18, Math.min((step.keyword || '').length + 5, 60)) + 'ch' }"
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
                            <span v-if="s.args?.length" class="kw-suggestion-args">{{ s.args.map(a => a.replace(/^[$@&%]\{([^}]+)\}.*$/, '$1')).join(', ') }}</span>
                            <span class="kw-suggestion-source" :class="'source-' + (s.source === 'builtin' ? 'builtin' : s.source === 'local' || s.source === 'project' ? 'local' : 'library')">{{ s.source === 'builtin' ? t('robotEditor.builtinKeyword') : s.source === 'local' || s.source === 'project' ? t('robotEditor.localKeyword') : s.source }}</span>
                          </div>
                        </div>
                      </div>
                      <div v-if="step.args.length" class="step-args-group">
                        <span v-for="(arg, aIdx) in step.args" :key="aIdx" class="step-arg-chip arg-ac-wrapper">
                          <span v-if="getKeywordArgNames(step)[aIdx]" class="arg-label">{{ getKeywordArgNames(step)[aIdx] }}</span>
                          <span class="arg-highlight-wrap" :style="{ width: argInputWidth(step.args[aIdx]) }">
                            <span class="arg-highlight-overlay" v-html="highlightVariables(step.args[aIdx])"></span>
                            <input v-model="step.args[aIdx]" class="step-arg-input" spellcheck="false"
                              @scroll="syncOverlayScroll" :style="{ width: '100%' }"
                              :placeholder="getKeywordArgNames(step)[aIdx] || t('robotEditor.argPlaceholder')"
                              @input="onArgInput(($event.target as HTMLInputElement).value, `${sIdx}-${aIdx}`)"
                              @keydown="onArgKeydown($event, step, aIdx)"
                              @blur="onArgBlur" autocomplete="off" />
                          </span>
                          <div v-if="argAutocompleteKey === `${sIdx}-${aIdx}` && argAutocompleteItems.length" class="arg-ac-dropdown">
                            <div v-for="(v, vi) in argAutocompleteItems" :key="v"
                              class="arg-ac-item" :class="{ active: vi === argAutocompleteIndex }"
                              @mousedown.prevent="selectArgVar(step, aIdx, v)">{{ v }}</div>
                          </div>
                          <button class="chip-remove" @click="removeStepArg(step, aIdx)">&times;</button>
                        </span>
                      </div>
                      <button class="step-btn step-add-arg" :class="{ 'has-hint': nextArgHint(step) !== '+' }" @click="addStepArg(step)" :title="t('robotEditor.addArg')">{{ nextArgHint(step) }}</button>
                    </template>

                    <!-- VAR -->
                    <template v-else-if="step.type === 'var'">
                      <span class="step-var-chip">
                        <input v-model="step.returnVars[0]" class="step-var-input" spellcheck="false" placeholder="${var}" @blur="ensureReturnVarSyntax(step, 0)" />
                      </span>
                      <span class="step-assign-eq">=</span>
                      <span v-for="(arg, aIdx) in step.args" :key="aIdx" class="step-arg-chip">
                        <span class="arg-highlight-wrap" :style="{ width: argInputWidth(step.args[aIdx]) }">
                          <span class="arg-highlight-overlay" v-html="highlightVariables(step.args[aIdx])"></span>
                          <input v-model="step.args[aIdx]" class="step-arg-input" spellcheck="false"
                            @scroll="syncOverlayScroll" :style="{ width: '100%' }"
                            :placeholder="t('robotEditor.valuePlaceholder')" />
                        </span>
                        <button class="chip-remove" @click="removeStepArg(step, aIdx)">&times;</button>
                      </span>
                      <button class="step-btn step-add-arg" @click="addStepArg(step)" :title="t('robotEditor.addValue')">+</button>
                      <select v-model="step.varScope" class="step-scope-select">
                        <option value="">scope</option>
                        <option v-for="s in VAR_SCOPES" :key="s" :value="s">{{ s }}</option>
                      </select>
                    </template>

                    <!-- FOR -->
                    <template v-else-if="step.type === 'for'">
                      <span class="form-hl-wrap hl-var-inline">
                        <span class="form-hl-overlay hl-mono" v-html="highlightVariables(step.loopVar)"></span>
                        <input v-model="step.loopVar" class="form-input step-var-input-inline" spellcheck="false" style="width: 100%" placeholder="${item}" />
                      </span>
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
                      <span class="form-hl-wrap flex-1 hl-condition-wrap">
                        <span class="form-hl-overlay hl-condition" v-html="highlightVariables(step.condition)"></span>
                        <input v-model="step.condition" class="form-input step-condition-input" style="width: 100%" :placeholder="t('robotEditor.conditionPlaceholder')" spellcheck="false" />
                      </span>
                    </template>

                    <!-- EXCEPT -->
                    <template v-else-if="step.type === 'except'">
                      <input v-model="step.exceptPattern" class="form-input step-keyword-input" spellcheck="false" :placeholder="t('robotEditor.exceptPatternPlaceholder')" />
                      <span v-if="step.exceptVar || step.exceptPattern" class="step-as-label">AS</span>
                      <span v-if="step.exceptVar || step.exceptPattern" class="form-hl-wrap hl-var-inline">
                        <span class="form-hl-overlay hl-mono" v-html="highlightVariables(step.exceptVar)"></span>
                        <input v-model="step.exceptVar" class="form-input step-var-input-inline" spellcheck="false" style="width: 100%" placeholder="${error}" />
                      </span>
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
                      <input v-model="step.comment" class="form-input flex-1 step-comment-input" spellcheck="false" placeholder="# ..." />
                    </template>

                    <div class="step-actions">
                      <button class="step-btn" @click="moveStep(kw.steps, sIdx, -1)" :disabled="sIdx === 0">&uarr;</button>
                      <button class="step-btn" @click="moveStep(kw.steps, sIdx, 1)" :disabled="sIdx === kw.steps.length - 1">&darr;</button>
                      <button class="step-btn danger" @click="removeStep(kw.steps, sIdx)" :title="t('common.delete')">&times;</button>
                    </div>
                  </div>

                  <div class="add-step-bar">
                    <button class="add-step-btn" @click="addStep(kw.steps)">+ {{ t('robotEditor.addStep') }}</button>
                    <button class="add-step-btn add-block" @click="addStep(kw.steps, 'var')">+ VAR</button>
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
.tab-toolbar .icon-btn { background: none; border: 1px solid var(--color-border); border-radius: 4px; cursor: pointer; font-size: 16px; line-height: 1; padding: 2px 4px; color: var(--color-text-muted); }
.tab-toolbar .icon-btn:hover { background: var(--color-bg); color: var(--color-primary); border-color: var(--color-primary); }

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

/* Section accent colors */
.section-settings > .section-header { border-left: 3px solid #3B7DD8; }
.section-settings .section-count { background: rgba(59, 125, 216, 0.1); color: #1a5fb4; }
.section-variables > .section-header { border-left: 3px solid #7c3aed; }
.section-variables .section-count { background: rgba(124, 58, 237, 0.1); color: #7c3aed; }
.section-testcases > .section-header { border-left: 3px solid #2e7d32; }
.section-testcases .section-count { background: rgba(46, 125, 50, 0.1); color: #2e7d32; }
.section-keywords > .section-header { border-left: 3px solid #d97706; }
.section-keywords .section-count { background: rgba(217, 119, 6, 0.1); color: #d97706; }
.section-body { padding: 14px; display: flex; flex-direction: column; gap: 8px; }
.collapse-icon { font-size: 10px; color: var(--color-text-muted); width: 14px; flex-shrink: 0; }

/* Setting/Variable rows */
.setting-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.setting-type-select { width: 160px; flex-shrink: 0; font-weight: 500; }
.setting-type-select.stype-library { background: #e3f2fd; color: #1565c0; border-color: #90caf9; }
.setting-type-select.stype-resource { background: #f3e8ff; color: #7c3aed; border-color: #d4c4f0; }
.setting-type-select.stype-variables { background: #f5f0ff; color: #7c3aed; border-color: #d4c4f0; }
.setting-type-select.stype-doc { background: #f5f5f5; color: #616161; border-color: #ccc; }
.setting-type-select.stype-setup { background: #e8f5e9; color: #2e7d32; border-color: #a5d6a7; }
.setting-type-select.stype-teardown { background: #fce4ec; color: #c62828; border-color: #ef9a9a; }
.setting-type-select.stype-config { background: #fff8e1; color: #e65100; border-color: #ffe0b2; }
.setting-type-select.stype-tags { background: #f0e6ff; color: #7c3aed; border-color: #d4c4f0; }
.setting-type-select.stype-meta { background: #e0f2f1; color: #00695c; border-color: #80cbc4; }
.setting-args { display: flex; gap: 4px; flex-wrap: wrap; }
.chip-edit-input { border: none; background: transparent; color: inherit; font-size: 12px; width: 80px; outline: none; }
.variable-row { display: flex; align-items: center; gap: 8px; }
.var-name-input { width: 200px; flex-shrink: 0; font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; color: #7c3aed; font-weight: 500; background: #faf8ff; border-color: #d4c4f0; }
.var-name-input:focus { border-color: #7c3aed; box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.15); }

/* Item cards */
.item-card { border: 1px solid var(--color-border); border-radius: 8px; }
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
.chip-arg { background: #e6f4ea; color: #1a7f37; }
.chip-arg-input { border: none; background: transparent; color: inherit; font: inherit; font-size: 12px; width: auto; min-width: 60px; max-width: 200px; outline: none; padding: 0; }
.chip-arg-input:focus { text-decoration: underline; }
.chip-remove { border: none; background: none; color: inherit; font-size: 14px; cursor: pointer; padding: 0 2px; opacity: 0.7; line-height: 1; }
.chip-remove:hover { opacity: 1; }

/* Keyword argument definition UI */
.kw-args-list { display: flex; flex-direction: column; gap: 4px; }
.kw-arg-row { display: flex; align-items: center; gap: 6px; padding: 4px 8px; border-radius: 6px; border: 1px solid var(--color-border); background: var(--color-bg); }
.kw-arg-row.kw-arg-sep { border: none; background: none; padding: 2px 0; justify-content: center; }
.kw-arg-type-badge { font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 8px; text-transform: uppercase; white-space: nowrap; flex-shrink: 0; }
.badge-required { background: #fee2e2; color: #dc2626; }
.badge-optional { background: #e0f2fe; color: #0284c7; }
.badge-varargs { background: #fef3c7; color: #d97706; }
.badge-kwargs { background: #f3e8ff; color: #7c3aed; }
.badge-named { background: #e0f2f1; color: #00695c; }
.kw-arg-name-input { border: none; background: transparent; font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; font-weight: 500; min-width: 60px; max-width: 160px; outline: none; padding: 2px 0; color: var(--color-text); }
.kw-arg-name-input:focus { text-decoration: underline; }
.kw-arg-eq { font-weight: 600; color: var(--color-text-muted); font-size: 12px; flex-shrink: 0; }
.kw-arg-default-input { border: none; background: transparent; font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; min-width: 60px; max-width: 160px; outline: none; padding: 2px 0; color: var(--color-text-muted); font-style: italic; }
.kw-arg-default-input:focus { text-decoration: underline; color: var(--color-text); }
.kw-arg-opt-btn { border: 1px dashed var(--color-border); background: none; font-size: 10px; color: var(--color-text-muted); padding: 1px 5px; border-radius: 4px; cursor: pointer; flex-shrink: 0; }
.kw-arg-opt-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }
.kw-arg-sep-line { flex: 1; height: 1px; background: var(--color-border); }
.kw-arg-sep-label { font-size: 10px; color: var(--color-text-muted); text-transform: uppercase; font-weight: 500; white-space: nowrap; padding: 0 8px; }
.kw-arg-add-buttons { display: flex; gap: 4px; margin-top: 6px; flex-wrap: wrap; }
.kw-arg-add-btn { border: 1px dashed var(--color-border); background: none; font-size: 11px; color: var(--color-text-muted); padding: 3px 8px; border-radius: 4px; cursor: pointer; }
.kw-arg-add-btn:hover:not(:disabled) { border-color: var(--color-primary); color: var(--color-primary); }
.kw-arg-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.chip-input-wrapper { display: flex; align-items: center; gap: 4px; }
.chip-input { border: 1px dashed var(--color-border); border-radius: 12px; padding: 3px 10px; font-size: 12px; background: transparent; color: var(--color-text); width: 140px; outline: none; }
.chip-input:focus { border-color: var(--color-primary); }
.chip-add-btn { border: none; background: var(--color-primary); color: white; width: 22px; height: 22px; border-radius: 50%; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; line-height: 1; }

/* Steps */
.steps-list { display: flex; flex-direction: column; gap: 4px; }
.step-row { display: flex; align-items: flex-start; gap: 6px; flex-wrap: wrap; min-height: 32px; transition: padding-left 0.15s; }
.step-number { font-size: 11px; color: var(--color-text-muted); width: 22px; text-align: right; flex-shrink: 0; margin-top: 6px; }

/* Step type selector */
.step-type-select {
  width: auto; min-width: 90px; padding: 3px 6px; border-radius: 4px;
  font-size: 11px; font-weight: 600; text-transform: uppercase; cursor: pointer;
  border: 1px solid var(--color-border); background: var(--color-bg); color: var(--color-text);
  flex-shrink: 0; margin-top: 3px;
}
.step-type-select.type-keyword { background: #f0f7ff; color: #1a5fb4; border-color: #b8d4f0; }
.step-type-select.type-assign { background: #f5f0ff; color: #7c3aed; border-color: #d4c4f0; }
.step-type-select.type-var { background: #e0f2f1; color: #00695c; border-color: #80cbc4; }
.step-type-select.type-loop { background: #fff8e1; color: #e65100; border-color: #ffe0b2; }
.step-type-select.type-condition { background: #e8f5e9; color: #2e7d32; border-color: #a5d6a7; }
.step-type-select.type-error { background: #fce4ec; color: #c62828; border-color: #ef9a9a; }
.step-type-select.type-flow { background: #eceff1; color: #455a64; border-color: #b0bec5; }
.step-type-select.type-comment { background: #f5f5f5; color: #757575; border-color: #ccc; }

/* Step inline fields */
.step-keyword-input { min-width: 160px; max-width: 500px; font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; padding: 4px 8px; }
.step-var-input-inline { width: 110px; font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; padding: 4px 8px; flex-shrink: 0; color: #7c3aed; font-weight: 500; background: #faf8ff; border-color: #d4c4f0; }
.step-var-input-inline:focus { border-color: #7c3aed; box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.15); }
.step-flavor-select { padding: 3px 6px; font-size: 12px; font-weight: 600; border: 1px solid #ffe0b2; background: #fff8e1; color: #e65100; border-radius: 4px; cursor: pointer; flex-shrink: 0; }
.step-scope-select { padding: 3px 6px; font-size: 11px; font-weight: 500; border: 1px solid #80cbc4; background: #e0f2f1; color: #00695c; border-radius: 4px; cursor: pointer; flex-shrink: 0; }
.step-comment-input { font-style: italic; color: #757575; font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; background: #fafafa; border-color: #e0e0e0; }
.step-condition-input { font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; background: #f6faf6; border-color: #a5d6a7; }
.step-condition-input:focus { border-color: #2e7d32; box-shadow: 0 0 0 2px rgba(46, 125, 50, 0.15); }
.form-hl-overlay.hl-condition {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  color: #2e7d32;
}

/* Step args group — stacks vertically when step-row overflows */
.step-args-group {
  display: flex; align-items: flex-start; gap: 4px; flex-wrap: wrap; min-width: 0;
}
.step-row.args-vertical .step-args-group {
  flex-direction: column; align-items: stretch; gap: 3px;
}
.step-row.args-vertical .step-args-group .step-arg-chip { width: 100%; }
.step-row.args-vertical .step-args-group .arg-highlight-wrap { flex: 1; max-width: none; }
.step-row.args-vertical .step-args-group .step-arg-input { max-width: none; }

/* Step arg chips */
.step-arg-chip {
  display: inline-flex; align-items: center; gap: 2px;
  padding: 2px 6px; background: var(--color-bg); border: 1px solid var(--color-border);
  border-radius: 4px; flex-shrink: 0;
}
.step-arg-input { border: none; background: transparent; color: var(--color-text); font-size: 12px; font-family: 'Fira Code', 'Consolas', monospace; min-width: 60px; max-width: 260px; outline: none; padding: 0; position: relative; z-index: 1; caret-color: var(--color-text); }
.step-arg-input::placeholder { color: var(--color-text-muted); opacity: 0.5; }
.arg-highlight-wrap { position: relative; display: inline-block; min-width: 60px; max-width: 260px; }
.arg-highlight-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; pointer-events: none; font-size: 12px; font-family: 'Fira Code', 'Consolas', monospace; white-space: pre; overflow: hidden; color: var(--color-text); display: block; }
.arg-highlight-overlay :deep(.hl-var) { color: #7c3aed; font-weight: 600; }
.arg-highlight-overlay :deep(.hl-env) { color: #0277bd; font-weight: 600; }
.arg-highlight-wrap .step-arg-input { color: transparent; caret-color: var(--color-text); }
.arg-highlight-wrap .step-arg-input::placeholder { color: var(--color-text-muted); opacity: 0.5; }

/* Step variable chips (for assignment) */
.step-var-chip {
  display: inline-flex; align-items: center; gap: 2px;
  padding: 2px 6px; background: #f5f0ff; border: 1px solid #d4c4f0;
  border-radius: 4px; flex-shrink: 0;
}
.step-var-input { border: none; background: transparent; color: #7c3aed; font-size: 12px; font-family: 'Fira Code', 'Consolas', monospace; width: 80px; outline: none; padding: 0; font-weight: 500; }

.step-assign-eq { font-weight: 700; color: #7c3aed; font-size: 14px; margin: 0 2px; flex-shrink: 0; }
.step-as-label { font-weight: 600; color: var(--color-text-muted); font-size: 11px; text-transform: uppercase; flex-shrink: 0; }

.step-add-arg { font-size: 14px !important; min-width: 22px !important; height: 22px !important; }
.step-add-arg.has-hint { font-size: 10px !important; padding: 0 6px !important; width: auto !important; white-space: nowrap; color: var(--color-text-muted); }
.step-add-var { font-size: 10px !important; width: 22px !important; height: 22px !important; }

.step-actions { display: flex; gap: 2px; flex-shrink: 0; margin-left: auto; }

.step-btn { border: 1px solid var(--color-border); background: var(--color-bg-card); color: var(--color-text-muted); width: 26px; height: 26px; border-radius: 4px; font-size: 12px; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.step-btn:hover:not(:disabled) { background: var(--color-bg); color: var(--color-text); }
.step-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.step-btn.danger:hover { color: var(--color-danger); border-color: var(--color-danger); }

/* Add step bar */
.add-step-bar { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px; }
.meta-toggles { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 4px; }
.meta-toggle-btn { border: 1px dashed var(--color-border); background: transparent; color: var(--color-text-muted); padding: 2px 10px; border-radius: 4px; font-size: 11px; cursor: pointer; font-weight: 500; }
.meta-toggle-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }
.meta-toggle-btn.mt-tags { color: #7c3aed; border-color: #d4c4f0; }
.meta-toggle-btn.mt-tags:hover { background: #f5f0ff; }
.meta-toggle-btn.mt-setup { color: #2e7d32; border-color: #a5d6a7; }
.meta-toggle-btn.mt-setup:hover { background: #e8f5e9; }
.meta-toggle-btn.mt-teardown { color: #c62828; border-color: #ef9a9a; }
.meta-toggle-btn.mt-teardown:hover { background: #fce4ec; }
.meta-toggle-btn.mt-config { color: #e65100; border-color: #ffe0b2; }
.meta-toggle-btn.mt-config:hover { background: #fff8e1; }
.meta-toggle-btn.mt-return { color: #455a64; border-color: #b0bec5; }
.meta-toggle-btn.mt-return:hover { background: #eceff1; }
.meta-close-btn { border: none; background: none; color: var(--color-text-muted); font-size: 14px; cursor: pointer; padding: 0 2px; opacity: 0.6; vertical-align: middle; }
.meta-close-btn:hover { opacity: 1; color: #dc2626; }
.add-step-btn { border: 1px dashed var(--color-border); background: transparent; color: var(--color-text-muted); padding: 4px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; text-align: left; }
.add-step-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }
.add-step-btn.add-keyword { color: #1a5fb4; border-color: #b8d4f0; }
.add-step-btn.add-keyword:hover { background: #f0f7ff; border-color: #1a5fb4; }
.add-step-btn.add-block { font-weight: 600; font-size: 11px; }
.add-step-btn.add-var { color: #00695c; border-color: #80cbc4; }
.add-step-btn.add-var:hover { background: #e0f2f1; border-color: #00695c; }
.add-step-btn.add-loop { color: #e65100; border-color: #ffe0b2; }
.add-step-btn.add-loop:hover { background: #fff8e1; border-color: #e65100; }
.add-step-btn.add-condition { color: #2e7d32; border-color: #a5d6a7; }
.add-step-btn.add-condition:hover { background: #e8f5e9; border-color: #2e7d32; }
.add-step-btn.add-error { color: #c62828; border-color: #ef9a9a; }
.add-step-btn.add-error:hover { background: #fce4ec; border-color: #c62828; }

/* Empty hints */
.empty-hint { padding: 16px; text-align: center; color: var(--color-text-muted); font-size: 13px; font-style: italic; }

/* Code Editor */
.code-editor { flex: 1; overflow: hidden; }
.code-editor :deep(.cm-editor) { height: 100%; }

/* Keyword autocomplete dropdown */
.keyword-autocomplete-wrapper { position: relative; display: inline-flex; }
.keyword-dropdown {
  position: absolute; top: 100%; left: 0; z-index: 1000;
  min-width: 280px; max-height: 220px; overflow-y: auto;
  background: var(--color-bg-card); border: 1px solid var(--color-border);
  border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-top: 2px;
}
.keyword-dropdown-item { padding: 6px 10px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.keyword-dropdown-item:hover, .keyword-dropdown-item.active { background: rgba(59,125,216,0.08); }
.kw-suggestion-name { font-family: 'Fira Code', monospace; font-size: 12px; }
.kw-suggestion-args { font-size: 10px; color: var(--color-text-muted); font-style: italic; margin-left: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 200px; }
.kw-suggestion-source { font-size: 10px; padding: 1px 6px; border-radius: 8px; font-weight: 600; text-transform: uppercase; }
.source-builtin { background: #e8f5e9; color: #2e7d32; }
.source-local { background: #f0e6ff; color: #7c3aed; }
.source-library { background: #e3f2fd; color: #1565c0; }

/* Argument labels */
.arg-label { font-size: 10px; color: var(--color-text-muted); font-weight: 500; margin-right: 2px; white-space: nowrap; }
.arg-ac-wrapper { position: relative; }
.arg-ac-dropdown { position: absolute; top: 100%; left: 0; z-index: 100; background: var(--color-bg-card); border: 1px solid var(--color-border); border-radius: 4px; box-shadow: var(--shadow-md); max-height: 160px; overflow-y: auto; min-width: 140px; }
.arg-ac-item { padding: 4px 10px; font-size: 12px; font-family: 'Fira Code', 'Consolas', monospace; cursor: pointer; color: var(--color-text); }
.arg-ac-item:hover, .arg-ac-item.active { background: var(--color-primary); color: #fff; }

/* Form input variable highlighting overlay */
.form-hl-wrap {
  position: relative; display: flex;
  background: var(--color-bg-card);
  border-radius: 6px;
}
.form-hl-wrap.hl-var-name { width: 200px; flex-shrink: 0; background: #faf8ff; }
.form-hl-wrap.hl-var-inline { width: 110px; flex-shrink: 0; background: #faf8ff; }
.form-hl-wrap.hl-condition-wrap { background: #f6faf6; }
.form-hl-overlay {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  pointer-events: none; z-index: 0;
  padding: 7px 11px;
  font-size: 13px;
  white-space: pre; overflow: hidden;
  color: var(--color-text);
}
.form-hl-overlay.hl-mono {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  font-weight: 500;
}
.hl-var-inline .form-hl-overlay { padding: 5px 9px; }
.hl-var-name .form-hl-overlay { padding: 7px 11px; }
.form-hl-overlay.hl-kw-default {
  padding: 2px 0;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  font-style: italic;
  color: var(--color-text-muted);
}
.form-hl-overlay :deep(.hl-var) { color: #7c3aed; font-weight: 600; }
.form-hl-overlay :deep(.hl-env) { color: #0277bd; font-weight: 600; }
.form-hl-wrap > .form-input,
.form-hl-wrap > input {
  color: transparent !important;
  background: transparent !important;
  caret-color: var(--color-text);
  position: relative; z-index: 1;
}
.form-hl-wrap > .form-input::placeholder,
.form-hl-wrap > input::placeholder { color: var(--color-text-muted); opacity: 0.5; }
.kw-default-wrap { min-width: 60px; max-width: 160px; }
.kw-default-wrap .kw-arg-default-input {
  color: transparent !important;
  background: transparent !important;
  caret-color: var(--color-text);
  position: relative; z-index: 1;
}
.kw-default-wrap .kw-arg-default-input::placeholder { color: var(--color-text-muted); opacity: 0.5; }

/* Setting library input */
.setting-library-input { width: 100%; font-family: 'Fira Code', 'Consolas', monospace; font-size: 12px; }
</style>
