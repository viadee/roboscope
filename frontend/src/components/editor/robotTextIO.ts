/**
 * robotTextIO — pure, testable parse/serialize for Robot Framework `.robot`
 * (and `.resource`) files used by the RobotEditor / FlowEditor.
 *
 * Story: Flow Editor — Verification & Hardening (round-trip fidelity).
 *
 * Extracted verbatim from `RobotEditor.vue` so the parse→edit→serialize path
 * is unit-testable in isolation (golden-corpus identity tests) and so the
 * round-trip-fidelity fixes live in one auditable place.
 *
 * ROUND-TRIP CONTRACT (what we guarantee):
 *  - Semantic identity: parse→serialize of an untouched file produces a
 *    Robot-Framework-EQUIVALENT file. Cell separators are NORMALISED to four
 *    spaces and blank lines inside bodies are dropped — that is a documented,
 *    RF-safe normalisation, not corruption.
 *  - No silent corruption: inline trailing comments (`Keyword  arg  # note`)
 *    stay comments (previously they were swallowed as an escaped `\#` arg);
 *    comments sitting above a test case / keyword are preserved as leading
 *    comments; `...` continuations, escapes, and `${}`/`@{}`/`&{}`/`%{}`
 *    variable references survive.
 *  - Unknown / not-yet-modelled constructs are passed through, never mangled.
 */

// --- Step Types ---
export type StepType =
  | 'keyword' | 'assignment' | 'var' | 'for' | 'end' | 'if' | 'else_if' | 'else'
  | 'while' | 'try' | 'except' | 'finally' | 'break' | 'continue' | 'return' | 'comment'

export const STEP_TYPES: StepType[] = [
  'keyword', 'assignment', 'var', 'comment',
  'for', 'if', 'else_if', 'else', 'while',
  'try', 'except', 'finally',
  'end', 'break', 'continue', 'return',
]

export const VAR_SCOPES = ['LOCAL', 'TEST', 'TASK', 'SUITE', 'GLOBAL'] as const

export const LOOP_FLAVORS = ['IN', 'IN RANGE', 'IN ENUMERATE', 'IN ZIP']

// --- Interfaces ---
export interface RobotSettingEntry { key: string; value: string; args: string[] }
export interface RobotVariable { name: string; value: string }

export interface RobotStep {
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
  comment: string        // comment: full-line comment text
  // Round-trip-fidelity — an inline comment trailing a real step line, e.g.
  // `Click    ${sel}    # wait for it`. Preserved verbatim and re-appended on
  // serialize. Without this it was parsed as an arg and escaped to `\#…`.
  trailingComment?: string
  rbs_id?: string        // RECORDER-IDMAP — see flow/flowConverter.ts
  _lineNumber?: number    // DEBUG-3 — 1-based source line; set by parseRobotText
}

export interface RobotTestCase {
  name: string; documentation: string; tags: string[]
  setup: string; teardown: string; timeout: string; template: string
  steps: RobotStep[]
  // Story FE-TPL — data-driven test rows. When `[Template]` is set, the test's
  // body rows are argument-sets for the template keyword (NOT keyword steps).
  // Each entry is one row's cells. Empty/absent for non-templated tests.
  templateRows?: string[][]
  // Round-trip-fidelity — comments sitting at column 0 directly above this
  // item. Previously such a line became a test case NAMED `# comment`.
  leadingComments?: string[]
}
export interface RobotKeyword {
  name: string; documentation: string; arguments: string[]; tags: string[]
  setup: string; teardown: string; timeout: string; returnValue: string
  steps: RobotStep[]
  leadingComments?: string[]
}
export interface RobotForm {
  settings: RobotSettingEntry[]
  variables: RobotVariable[]
  testCases: RobotTestCase[]
  keywords: RobotKeyword[]
  preambleLines: string[]
  // Round-trip-fidelity — column-0 comments after the last item in a
  // test-case / keyword section with no following item to attach to.
  trailingComments?: string[]
}

export function makeStep(type: StepType = 'keyword'): RobotStep {
  return {
    type, keyword: '', args: [], returnVars: [],
    condition: '', loopVar: '${item}', loopFlavor: 'IN', loopValues: [],
    exceptPattern: '', exceptVar: '', varScope: '', comment: '',
  }
}

// --- Escape helpers (mirror backend/src/recording/robot_emit.py) ---

/**
 * Reverse of `escapeRfToken`. Strips the leading `\` from `\#…` so the
 * user-visible value matches the logical selector / arg.
 */
export function unescapeRfToken(s: string): string {
  if (s.startsWith('\\#')) return s.slice(1)
  return s
}

/**
 * Robot Framework's lexer treats any token that STARTS with `#` as a comment.
 * A real arg value `#login-form` must be emitted as `\#login-form`. Idempotent.
 */
export function escapeRfToken(s: string): string {
  if (!s) return s
  return s.startsWith('#') ? '\\' + s : s
}

// --- Step line parser ---
const _RBS_ID_CELL = /^# rbs:([a-f0-9]{8,32})$/
const SEP = '    '

// Story FE-TPL — a body row inside a templated test is DATA unless its first
// cell is a control-structure marker (RF allows FOR/IF/WHILE/TRY wrapping a
// templated body); those stay real steps so we never force control flow into
// the data table.
const _CONTROL_FIRST_CELLS = new Set([
  'FOR', 'END', 'IF', 'ELSE', 'ELSE IF', 'WHILE', 'TRY', 'EXCEPT', 'FINALLY',
  'BREAK', 'CONTINUE', 'RETURN', 'VAR',
])

function isControlRow(bodyTrimmed: string): boolean {
  const first = bodyTrimmed.split(/  +|\t+/)[0]
  return _CONTROL_FIRST_CELLS.has(first)
}

/**
 * A cell is an inline-comment opener when it starts with a bare `#` that is
 * NOT the recorder's `# rbs:<id>` marker (handled separately). An escaped
 * arg (`\#…`) starts with `\`, so it is correctly NOT treated as a comment.
 */
function isInlineCommentCell(cell: string): boolean {
  return cell.startsWith('#') && !_RBS_ID_CELL.test(cell)
}

export function parseStepLine(raw: string): RobotStep {
  const step = makeStep()
  const trimmed = raw.trim()
  if (!trimmed) return step

  // Full-line comment
  if (trimmed.startsWith('#')) {
    step.type = 'comment'
    step.comment = trimmed
    return step
  }

  // Split into cells on 2+ spaces or tab
  let cells = trimmed.split(/  +|\t+/).filter(c => c !== '')
  if (cells.length === 0) return step

  // Story RECORDER-IDMAP — peel off the trailing `# rbs:<id>` cell BEFORE
  // anything else treats it as an arg or as an inline comment.
  const lastCell = cells[cells.length - 1]
  const idMatch = _RBS_ID_CELL.exec(lastCell)
  if (idMatch) {
    step.rbs_id = idMatch[1]
    cells.pop()
    if (cells.length === 0) return step
  }

  // Round-trip-fidelity — peel off an inline trailing comment. Everything
  // from the first bare-`#` cell to end of line is the comment. (A leading
  // `#` was handled above as a full-line comment, so any `#` cell here is at
  // index >= 1 and trails a real step.)
  const commentIdx = cells.findIndex(isInlineCommentCell)
  if (commentIdx >= 0) {
    step.trailingComment = cells.slice(commentIdx).join(' ')
    cells = cells.slice(0, commentIdx)
    if (cells.length === 0) {
      // Only an rbs id + comment, no actual step — emit as a comment line.
      step.type = 'comment'
      step.comment = step.trailingComment
      step.trailingComment = undefined
      return step
    }
  }

  const first = cells[0]

  // Control flow markers
  if (first === 'FOR') {
    step.type = 'for'
    step.loopVar = cells[1] || '${item}'
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

  // Variable assignment: ${var}=  Keyword  args  (also multi-assign / ` =`)
  const VAR_RE = /^[$@&%]\{[^}]+\}\s*=?$/
  const returnVars: string[] = []
  let keywordIdx = 0
  for (let i = 0; i < cells.length; i++) {
    const cell = cells[i].trim()
    if (VAR_RE.test(cell)) {
      const varName = cell.replace(/\s*=$/, '')
      returnVars.push(varName)
      if (cell.endsWith('=')) { keywordIdx = i + 1; break }
      if (i + 1 < cells.length && cells[i + 1].trim() === '=') { keywordIdx = i + 2; break }
    } else if (cell === '=' && returnVars.length > 0) {
      keywordIdx = i + 1; break
    } else {
      keywordIdx = i; break
    }
  }

  if (returnVars.length > 0 && keywordIdx < cells.length) {
    step.type = 'assignment'
    step.returnVars = returnVars
    step.keyword = cells[keywordIdx]
    step.args = cells.slice(keywordIdx + 1).map(unescapeRfToken)
    return step
  }

  // Regular keyword call
  step.type = 'keyword'
  step.keyword = cells[0]
  step.args = cells.slice(1).map(unescapeRfToken)
  return step
}

// --- Step serializer ---

export function serializeStep(step: RobotStep): string {
  // Story RECORDER-IDMAP — append the trailing `# rbs:<id>`.
  // Round-trip-fidelity — also re-append a preserved inline comment. The
  // comment goes AFTER the rbs id so both survive.
  const withTrailers = (line: string): string => {
    let out = line
    if (step.rbs_id) out += `${SEP}# rbs:${step.rbs_id}`
    if (step.trailingComment) out += `${SEP}${step.trailingComment}`
    return out
  }

  // RECORDER-RF-ESCAPE — mirror the backend escape on the save path.
  const args = step.args.map(escapeRfToken)

  switch (step.type) {
    case 'keyword':
      return withTrailers([step.keyword, ...args].filter(Boolean).join(SEP))
    case 'assignment': {
      const vars = step.returnVars.map((v, i) =>
        i === step.returnVars.length - 1 ? v + '=' : v
      )
      return withTrailers([...vars, step.keyword, ...args].filter(Boolean).join(SEP))
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

/**
 * Parse `.robot` content into a RobotForm. Pure: returns a fresh form and
 * never mutates external state. Throws on a structural error.
 */
export function parseRobotText(content: string): RobotForm {
  const lines = content.split('\n')
  const form: RobotForm = {
    settings: [], variables: [], testCases: [], keywords: [], preambleLines: [],
  }

  let currentSection: 'none' | 'settings' | 'variables' | 'testcases' | 'keywords' = 'none'
  let currentItem: RobotTestCase | RobotKeyword | null = null
  let currentItemType: 'testcase' | 'keyword' | null = null
  // Round-trip-fidelity — column-0 comments waiting to attach to the next item.
  let pendingLeadingComments: string[] = []

  const flushItem = () => {
    if (currentItem && currentItemType) {
      if (currentItemType === 'testcase') form.testCases.push(currentItem as RobotTestCase)
      else form.keywords.push(currentItem as RobotKeyword)
    }
    currentItem = null
    currentItemType = null
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trimEnd()

    // Section header
    const headerMatch = trimmed.match(SECTION_HEADER_RE)
    if (headerMatch) {
      flushItem()
      const sectionName = headerMatch[1].toLowerCase()
      if (sectionName.startsWith('setting')) currentSection = 'settings'
      else if (sectionName.startsWith('variable')) currentSection = 'variables'
      else if (sectionName.startsWith('test') || sectionName.startsWith('task')) currentSection = 'testcases'
      else if (sectionName.startsWith('keyword')) currentSection = 'keywords'
      continue
    }

    if (currentSection === 'none') {
      form.preambleLines.push(trimmed)
      continue
    }

    if (currentSection === 'settings') {
      if (!trimmed || trimmed.startsWith('#')) {
        if (trimmed.startsWith('#')) {
          form.settings.push({ key: '#', value: trimmed, args: [] })
        }
        continue
      }
      if (trimmed.startsWith('...')) {
        const cont = trimmed.slice(3).trim()
        const last = form.settings[form.settings.length - 1]
        if (last && last.key !== '#') {
          last.value = last.value ? `${last.value}\n${cont}` : cont
        }
        continue
      }
      const parts = trimmed.split(/  +|\t+/).filter(p => p !== '')
      if (parts.length >= 1) {
        form.settings.push({ key: parts[0], value: parts[1] || '', args: parts.slice(2) })
      }
      continue
    }

    if (currentSection === 'variables') {
      if (!trimmed || trimmed.startsWith('#')) {
        if (trimmed.startsWith('#')) {
          form.variables.push({ name: '#', value: trimmed })
        }
        continue
      }
      if (trimmed.startsWith('...')) {
        const cont = trimmed.slice(3).trim()
        const last = form.variables[form.variables.length - 1]
        if (last && last.name !== '#') {
          last.value = last.value ? `${last.value}${SEP}${cont}` : cont
        }
        continue
      }
      const parts = trimmed.split(/  +|\t+/).filter(p => p !== '')
      if (parts.length >= 1) {
        form.variables.push({ name: parts[0], value: parts.slice(1).join(SEP) })
      }
      continue
    }

    if (currentSection === 'testcases' || currentSection === 'keywords') {
      if (!trimmed) continue

      const isIndented = /^\s/.test(line) || line.startsWith('\t')

      // Round-trip-fidelity — a column-0 comment is NOT a test case header.
      // Buffer it as a leading comment for the next item (previously it
      // became an item literally named `# comment`).
      if (!isIndented && trimmed.startsWith('#')) {
        pendingLeadingComments.push(trimmed)
        continue
      }

      if (!isIndented && trimmed) {
        flushItem()
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
        if (pendingLeadingComments.length) {
          currentItem.leadingComments = pendingLeadingComments
          pendingLeadingComments = []
        }
        continue
      }

      if (currentItem && isIndented) {
        const bodyTrimmed = trimmed.trim()

        // Story FE-TPL — is this a data row of a templated test?
        const tcItem = currentItemType === 'testcase' ? (currentItem as RobotTestCase) : null
        const inTemplate = !!tcItem && !!tcItem.template

        // Continuation line
        if (bodyTrimmed.startsWith('...')) {
          const contCells = bodyTrimmed.slice(3).trim().split(/  +|\t+/).filter(c => c !== '')
          // A `...` after a template data row extends that row.
          if (inTemplate && tcItem!.templateRows && tcItem!.templateRows.length > 0
              && currentItem.steps.length === 0) {
            tcItem!.templateRows[tcItem!.templateRows.length - 1].push(...contCells)
            continue
          }
          if (currentItem.steps.length > 0) {
            const prev = currentItem.steps[currentItem.steps.length - 1]
            switch (prev.type) {
              case 'keyword':
              case 'assignment':
              case 'return':
                prev.args.push(...contCells.map(unescapeRfToken))
                break
              case 'for':
                prev.loopValues.push(...contCells)
                break
              default:
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

        // Story FE-TPL — a non-control body row of a templated test is a data
        // row (cells = args for the template keyword), NOT a keyword step.
        if (inTemplate && !isControlRow(bodyTrimmed)) {
          const cells = bodyTrimmed.split(/  +|\t+/).filter((c) => c !== '')
          if (!tcItem!.templateRows) tcItem!.templateRows = []
          tcItem!.templateRows.push(cells)
          continue
        }

        // Structured step. DEBUG-3 — annotate 1-based source line.
        const parsed = parseStepLine(bodyTrimmed)
        parsed._lineNumber = i + 1
        currentItem.steps.push(parsed)
      }
      continue
    }
  }

  flushItem()
  // Dangling column-0 comments after the last item in a body section.
  if (pendingLeadingComments.length) form.trailingComments = pendingLeadingComments

  return form
}

/**
 * Multi-line settings fold/unfold. See RobotEditor's original note: a
 * `[Documentation]` value with `\n` must re-emit as `...` continuation rows
 * or RF re-parses each line as a new top-level item.
 */
export function emitMultilineSetting(tag: string, value: string): string[] {
  const parts = value.split('\n')
  const out: string[] = []
  out.push(SEP + tag + SEP + parts[0])
  for (let i = 1; i < parts.length; i++) {
    out.push(SEP + '...' + SEP + parts[i])
  }
  return out
}

/**
 * Serialize a RobotForm back to `.robot` text. Pure. `isResource` suppresses
 * the `*** Test Cases ***` section (resource files have no test cases).
 */
export function serializeRobotForm(form: RobotForm, opts: { isResource?: boolean } = {}): string {
  const isResource = opts.isResource ?? false
  const lines: string[] = []

  for (const pl of form.preambleLines) lines.push(pl)

  if (form.settings.length > 0) {
    if (lines.length > 0 && lines[lines.length - 1] !== '') lines.push('')
    lines.push('*** Settings ***')
    for (const s of form.settings) {
      if (s.key === '#') { lines.push(s.value); continue }
      if (s.value && s.value.includes('\n')) {
        const parts = s.value.split('\n')
        let firstLine = s.key + SEP + parts[0]
        for (const a of s.args) firstLine += SEP + a
        lines.push(firstLine)
        for (let i = 1; i < parts.length; i++) lines.push('...' + SEP + parts[i])
        continue
      }
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

  const emitLeading = (item: RobotTestCase | RobotKeyword) => {
    if (item.leadingComments) for (const c of item.leadingComments) lines.push(c)
  }

  if (!isResource && form.testCases.length > 0) {
    if (lines.length > 0 && lines[lines.length - 1] !== '') lines.push('')
    lines.push('*** Test Cases ***')
    for (let tcIdx = 0; tcIdx < form.testCases.length; tcIdx++) {
      const tc = form.testCases[tcIdx]
      emitLeading(tc)
      const tcName = tc.name.trim() || `Test Case ${tcIdx + 1}`
      lines.push(tcName)
      if (tc.documentation) lines.push(...emitMultilineSetting('[Documentation]', tc.documentation))
      if (tc.tags.length > 0) lines.push(SEP + '[Tags]' + SEP + tc.tags.join(SEP))
      if (tc.setup) lines.push(SEP + '[Setup]' + SEP + tc.setup)
      if (tc.teardown) lines.push(SEP + '[Teardown]' + SEP + tc.teardown)
      if (tc.timeout) lines.push(SEP + '[Timeout]' + SEP + tc.timeout)
      if (tc.template) lines.push(SEP + '[Template]' + SEP + tc.template)
      // Story FE-TPL — data rows (each cell-array is one argument set).
      if (tc.templateRows) {
        for (const row of tc.templateRows) lines.push(SEP + row.join(SEP))
      }
      for (const step of tc.steps) lines.push(SEP + serializeStep(step))
      lines.push('')
    }
  }

  if (form.keywords.length > 0) {
    if (lines.length > 0 && lines[lines.length - 1] !== '') lines.push('')
    lines.push('*** Keywords ***')
    for (let kwIdx = 0; kwIdx < form.keywords.length; kwIdx++) {
      const kw = form.keywords[kwIdx]
      emitLeading(kw)
      const kwName = kw.name.trim() || `Keyword ${kwIdx + 1}`
      lines.push(kwName)
      if (kw.arguments.length) lines.push(SEP + '[Arguments]' + SEP + kw.arguments.join(SEP))
      if (kw.documentation) lines.push(...emitMultilineSetting('[Documentation]', kw.documentation))
      if (kw.tags.length > 0) lines.push(SEP + '[Tags]' + SEP + kw.tags.join(SEP))
      if (kw.setup) lines.push(SEP + '[Setup]' + SEP + kw.setup)
      if (kw.teardown) lines.push(SEP + '[Teardown]' + SEP + kw.teardown)
      if (kw.timeout) lines.push(SEP + '[Timeout]' + SEP + kw.timeout)
      if (kw.returnValue) lines.push(SEP + '[Return]' + SEP + kw.returnValue)
      for (const step of kw.steps) lines.push(SEP + serializeStep(step))
      lines.push('')
    }
  }

  // Dangling column-0 comments after the last item.
  if (form.trailingComments) for (const c of form.trailingComments) lines.push(c)

  let result = lines.join('\n')
  result = result.replace(/\n{3,}/g, '\n\n')
  if (!result.endsWith('\n')) result += '\n'
  return result
}
