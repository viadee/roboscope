import { StreamLanguage, HighlightStyle } from '@codemirror/language'
import { tags as t } from '@lezer/highlight'

// Comprehensive Robot Framework keyword set (based on npp-robot + RF5/RF7)
export const RF_BUILTINS = new Set([
  // BuiltIn library
  'call method', 'catenate', 'comment', 'continue for loop', 'continue for loop if',
  'convert to binary', 'convert to boolean', 'convert to bytes', 'convert to hex',
  'convert to integer', 'convert to number', 'convert to octal', 'convert to string',
  'create dictionary', 'create list', 'evaluate', 'exit for loop', 'exit for loop if',
  'fail', 'fatal error', 'get count', 'get length', 'get library instance',
  'get time', 'get variable value', 'get variables', 'import library', 'import resource',
  'import variables', 'keyword should exist', 'length should be', 'log', 'log many',
  'log to console', 'log variables', 'no operation', 'pass execution', 'pass execution if',
  'regexp escape', 'reload library', 'remove tags', 'repeat keyword', 'replace variables',
  'return from keyword', 'return from keyword if', 'run keyword', 'run keyword and continue on failure',
  'run keyword and expect error', 'run keyword and ignore error', 'run keyword and return',
  'run keyword and return if', 'run keyword and return status', 'run keyword if',
  'run keyword if all critical tests passed', 'run keyword if all tests passed',
  'run keyword if any critical tests failed', 'run keyword if any tests failed',
  'run keyword if test failed', 'run keyword if test passed',
  'run keyword if timeout occurred', 'run keyword unless', 'run keywords',
  'set global variable', 'set library search order', 'set log level',
  'set suite documentation', 'set suite metadata', 'set suite variable',
  'set tags', 'set test documentation', 'set test message', 'set test variable',
  'set variable', 'set variable if', 'should be empty', 'should be equal',
  'should be equal as integers', 'should be equal as numbers', 'should be equal as strings',
  'should be true', 'should contain', 'should contain x times', 'should end with',
  'should match', 'should match regexp', 'should not be empty', 'should not be equal',
  'should not be equal as integers', 'should not be equal as numbers',
  'should not be equal as strings', 'should not be true', 'should not contain',
  'should not end with', 'should not match', 'should not match regexp',
  'should not start with', 'should start with', 'sleep',
  'variable should exist', 'variable should not exist', 'wait until keyword succeeds',
  'skip', 'skip if',
  // String library
  'convert to lowercase', 'convert to uppercase', 'decode bytes to string',
  'encode string to bytes', 'fetch from left', 'fetch from right',
  'generate random string', 'get line', 'get line count',
  'get lines containing string', 'get lines matching pattern', 'get lines matching regexp',
  'get regexp matches', 'get substring', 'remove string', 'remove string using regexp',
  'replace string', 'replace string using regexp', 'should be byte string',
  'should be lowercase', 'should be string', 'should be titlecase',
  'should be unicode string', 'should be uppercase', 'should not be string',
  'split string', 'split string from right', 'split string to characters', 'split to lines',
  // Collections library
  'append to list', 'combine lists', 'convert to dictionary', 'convert to list',
  'copy dictionary', 'copy list', 'count values in list', 'dictionaries should be equal',
  'dictionary should contain item', 'dictionary should contain key',
  'dictionary should contain sub dictionary', 'dictionary should contain value',
  'dictionary should not contain key', 'dictionary should not contain value',
  'get dictionary items', 'get dictionary keys', 'get dictionary values',
  'get from dictionary', 'get from list', 'get index from list',
  'get match count', 'get matches', 'get slice from list', 'insert into list',
  'keep in dictionary', 'list should contain sub list', 'list should contain value',
  'list should not contain duplicates', 'list should not contain value',
  'lists should be equal', 'log dictionary', 'log list', 'pop from dictionary',
  'remove duplicates', 'remove from dictionary', 'remove from list',
  'remove values from list', 'reverse list', 'set list value', 'set to dictionary',
  'should contain match', 'should not contain match', 'sort list',
  // DateTime library
  'add time to date', 'add time to time', 'convert date', 'convert time',
  'get current date', 'subtract date from date', 'subtract time from date',
  'subtract time from time',
  // OperatingSystem library
  'append to environment variable', 'append to file', 'copy directory', 'copy file',
  'copy files', 'count directories in directory', 'count files in directory',
  'count items in directory', 'create binary file', 'create directory', 'create file',
  'directory should be empty', 'directory should exist', 'directory should not be empty',
  'directory should not exist', 'empty directory', 'environment variable should be set',
  'environment variable should not be set', 'file should be empty', 'file should exist',
  'file should not be empty', 'file should not exist', 'get binary file',
  'get environment variable', 'get environment variables', 'get file', 'get file size',
  'get modified time', 'grep file', 'join path', 'join paths',
  'list directories in directory', 'list directory', 'list files in directory',
  'log environment variables', 'log file', 'move directory', 'move file', 'move files',
  'normalize path', 'remove directory', 'remove environment variable', 'remove file',
  'remove files', 'run', 'run and return rc', 'run and return rc and output',
  'set environment variable', 'set modified time', 'should exist', 'should not exist',
  'split extension', 'split path', 'touch', 'wait until created', 'wait until removed',
  // Process library
  'get process id', 'get process object', 'get process result', 'is process running',
  'join command line', 'process should be running', 'process should be stopped',
  'run process', 'send signal to process', 'split command line', 'start process',
  'stop all processes', 'stop process', 'switch process', 'terminate all processes',
  'terminate process', 'wait for process',
  // Telnet library
  'close all connections', 'close connection', 'execute command', 'login',
  'open connection', 'read', 'read until', 'read until prompt', 'read until regexp',
  'set default log level', 'set encoding', 'set newline', 'set prompt',
  'set telnetlib log level', 'set timeout', 'switch connection', 'write',
  'write bare', 'write control character', 'write until expected output',
  // XML library
  'add element', 'clear element', 'copy element', 'element attribute should be',
  'element attribute should match', 'element should exist', 'element should not exist',
  'element should not have attribute', 'element text should be', 'element text should match',
  'element to string', 'elements should be equal', 'elements should match',
  'evaluate xpath', 'get child elements', 'get element', 'get element attribute',
  'get element attributes', 'get element count', 'get element text', 'get elements',
  'get elements texts', 'log element', 'parse xml', 'remove element',
  'remove element attribute', 'remove element attributes', 'remove elements',
  'remove elements attribute', 'remove elements attributes', 'save xml',
  'set element attribute', 'set element tag', 'set element text',
  'set elements attribute', 'set elements tag', 'set elements text',
  // Screenshot library
  'set screenshot directory', 'take screenshot', 'take screenshot without embedding',
  // Dialogs library
  'execute manual step', 'get selection from user', 'get value from user', 'pause execution',
])

/**
 * EDITOR-11 — Robot Framework syntax for CodeMirror.
 *
 * Tokenizer is hand-written (StreamLanguage) but emits a richer set of
 * standard CodeMirror token names than the previous version, so the
 * default highlight style colours each role distinctly:
 *
 *   - section header               → 'heading'
 *   - test case / keyword def name → 'definition'
 *   - keyword call                 → 'function'
 *   - control flow / BDD prefix    → 'keyword'
 *   - variable inner structure     → 'bracket' / 'variableName' / 'number'
 *   - library namespace            → 'tagName'   (`Browser` in `Browser.Click`)
 *   - dot in `Library.Keyword`     → 'punctuation'
 *   - escape sequences in args     → 'string-2'
 *   - named-arg `name=`            → 'attributeName' + 'operator'
 *   - continuation `...`           → 'meta'
 *   - quoted strings               → 'string'
 *   - numbers                      → 'number'
 *   - settings / [Tags] / [Setup]  → 'meta'
 *
 * Inspired by the RobotCode TextMate grammar (the IntelliJ plugin's
 * upstream); a verbatim TextMate runtime would require Monaco — see
 * story EDITOR-12.
 */

const SETTINGS_KEYWORDS = /^(Library|Resource|Variables|Suite Setup|Suite Teardown|Test Setup|Test Teardown|Test Template|Test Timeout|Force Tags|Default Tags|Metadata|Documentation|Test Tags|Keyword Tags|Name)\b/i
const SETTING_TAGS = /^\[(Setup|Tags|Teardown|Documentation|Arguments|Return|Template|Timeout)\]/i
const CONTROL_FLOW = /^\b(FOR|END|IF|ELSE IF|ELSE|TRY|EXCEPT|FINALLY|WHILE|BREAK|CONTINUE|RETURN|IN|IN RANGE|IN ENUMERATE|IN ZIP)\b/
const BDD = /^(Given|When|Then|And|But)(?=\s)/i
const ATOMS = /^\b(True|False|None|TRUE|FALSE|NONE|EMPTY|SPACE|NULL)\b/
const ESCAPE_SEQ = /^\\[ntr\\$"'{}@%&xu]/
const VAR_OPENER = /^[$@%&]\{/
const NAMED_ARG = /^([A-Za-z_][\w]*)=/

interface State {
  section: string
  /** True after the line has emitted its keyword / setting; subsequent
   *  cells are arguments and skip the keyword-detection paths. */
  lineHasKeyword: boolean
  /** Depth of nested `${…}`. While > 0 the tokenizer enters the
   *  variable-inner state and emits `bracket` / `variableName` tokens
   *  separately rather than swallowing the whole `${…}` as one. */
  varDepth: number
  /** True right after a `Library` namespace token, so the next call
   *  consumes the `.` as punctuation rather than starting a new pass. */
  expectDotAfterNs: boolean
}

export function robotLanguage() {
  return StreamLanguage.define({
    startState(): State {
      return { section: '', lineHasKeyword: false, varDepth: 0, expectDotAfterNs: false }
    },
    token(stream, state: State) {
      // ---- Inside a variable: emit fine-grained tokens ----
      if (state.varDepth > 0) {
        if (stream.match(/^\}/)) {
          state.varDepth--
          return 'bracket'
        }
        if (stream.match(VAR_OPENER)) {
          state.varDepth++
          return 'bracket'
        }
        // Numeric subscript inside ${list}[0]-style — not actually
        // reachable here (we exit the var first), kept for future.
        if (stream.match(/^[A-Za-z_][\w ]*/)) return 'variableName'
        // Lone special char like a stray `$` inside a var name
        stream.next()
        return 'variableName'
      }

      // ---- Beginning of line: section headers, defs, continuation ----
      if (stream.sol()) {
        // In Variables section EVERY non-empty cell after the first is a
        // raw value, not a keyword call. Pre-arm lineHasKeyword so the
        // word matcher takes the argument-territory branch.
        state.lineHasKeyword = state.section === 'variables'
        state.expectDotAfterNs = false

        // Section headers: *** Settings ***, *** Test Cases ***, …
        if (stream.match(/^\*{3}\s*(Settings?|Variables?|Test Cases?|Tasks?|Keywords?|Comments?)\s*\*{0,3}/i)) {
          const text = stream.current().toLowerCase()
          if (text.includes('setting')) state.section = 'settings'
          else if (text.includes('variable')) state.section = 'variables'
          else if (text.includes('test') || text.includes('task')) state.section = 'testcases'
          else if (text.includes('keyword')) state.section = 'keywords'
          else state.section = 'comments'
          return 'heading'
        }

        // Comment section — colour the entire line as comment.
        if (state.section === 'comments') {
          stream.skipToEnd()
          return 'comment'
        }

        // Continuation marker after the leading whitespace: `    ...`.
        // Carry over `lineHasKeyword` from the previous logical line so
        // continuation cells are still treated as arguments.
        if (stream.match(/^\s+\.\.\.(?=\s|$)/)) {
          state.lineHasKeyword = true
          return 'meta'
        }

        // Test case / keyword definition: not indented, in a body section.
        if ((state.section === 'testcases' || state.section === 'keywords')
            && !stream.match(/^\s/, false)) {
          // Consume the whole def name up to a double-space cell separator
          // or the end of the line. Embedded `${var}` highlighting in
          // names is intentionally skipped for V1.
          stream.match(/^[^\s][^ ]*( [^ ]+)*/)
          return 'definition'
        }
      }

      // ---- Trailing dot after a library namespace token ----
      if (state.expectDotAfterNs) {
        state.expectDotAfterNs = false
        if (stream.match(/^\./)) return 'punctuation'
      }

      // ---- Inline comment (anywhere on the line) ----
      if (stream.match(/^#.*/)) return 'comment'

      // ---- Cell separator (two or more spaces) ----
      if (stream.match(/^  +/)) return 'punctuation'

      // ---- Variable opener: enter the inner state ----
      if (stream.match(VAR_OPENER)) {
        state.varDepth = 1
        return 'bracket'
      }

      // ---- Variable index `[0]` directly after `}` ----
      if (stream.match(/^\[/)) return 'bracket'
      if (stream.match(/^\]/)) return 'bracket'

      // ---- Setting tags like [Setup], [Tags], … ----
      if (stream.match(SETTING_TAGS)) {
        state.lineHasKeyword = true
        return 'meta'
      }

      // ---- Settings section keywords (Library, Resource, …) ----
      if (state.section === 'settings' && stream.match(SETTINGS_KEYWORDS)) {
        state.lineHasKeyword = true
        return 'meta'
      }

      // ---- Control flow keywords (RF5+) ----
      if (stream.match(CONTROL_FLOW)) {
        state.lineHasKeyword = true
        return 'keyword'
      }

      // ---- BDD prefix (only at the start of a kw-call, before kw) ----
      if (!state.lineHasKeyword && stream.match(BDD)) return 'keyword'

      // ---- Continuation `...` mid-line (rare; usually at SOL) ----
      if (stream.match(/^\.\.\.(?=\s|$)/)) return 'meta'

      // ---- Words: keyword call OR library namespace OR argument ----
      if (stream.match(/^[A-Za-z_]/, false)) {
        if (!state.lineHasKeyword) {
          // First word of a non-control line — try Library.Keyword first.
          const remaining = stream.string.slice(stream.pos)
          const lib = remaining.match(/^([A-Z][\w]*)(?=\.[A-Z])/)
          if (lib) {
            stream.pos += lib[1].length
            state.expectDotAfterNs = true
            return 'tagName' // 'tagName' renders as namespace via default style
          }
          // Plain keyword call — greedy match against the BuiltIn set.
          const cellMatch = remaining.match(/^[A-Za-z_][\w]*(?: [A-Za-z_][\w]*)*/)
          if (cellMatch) {
            const cellText = cellMatch[0]
            const words = cellText.split(' ')
            for (let len = words.length; len >= 1; len--) {
              const candidate = words.slice(0, len).join(' ')
              if (RF_BUILTINS.has(candidate.toLowerCase())) {
                stream.pos += candidate.length
                state.lineHasKeyword = true
                return 'function'
              }
            }
            // Custom / project keyword — still highlight as a call.
            stream.pos += cellText.length
            state.lineHasKeyword = true
            return 'function'
          }
          stream.next()
          return null
        }
        // Past the first keyword on the line → argument territory.
        // Named argument `name=value` ⇒ name as attribute, then `=`.
        if (stream.match(NAMED_ARG)) {
          // Backstep past the `=` so the next call emits it as operator.
          stream.pos -= 1
          return 'attributeName'
        }
        // Atoms (True/False/None/EMPTY/SPACE/NULL).
        if (stream.match(ATOMS)) return 'atom'
        // Plain argument word — consume up to next special / whitespace.
        stream.match(/^[A-Za-z_][\w]*/)
        return null
      }

      // ---- Argument-territory micro-tokens ----
      if (stream.match(ESCAPE_SEQ)) return 'string-2'
      if (stream.match(/^==/)) return 'operator'
      if (stream.match(/^=/)) return 'operator'
      if (stream.match(/^"(?:[^"\\]|\\.)*"/)) return 'string'
      if (stream.match(/^'(?:[^'\\]|\\.)*'/)) return 'string'
      if (stream.match(/^-?\d+(\.\d+)?\b/)) return 'number'

      // ---- Skip plain whitespace (single space between cells of a kw call) ----
      if (stream.eatSpace()) return null

      // ---- Catch-all: consume one char so we make progress ----
      stream.next()
      return null
    },
  })
}

/**
 * RoboScope-branded highlight style for the code-tab editor. Replaces
 * `defaultHighlightStyle` so the new tokens emitted by `robotLanguage()`
 * (function call, keyword definition, namespace, escape, atom, named-arg
 * attribute, operator, variable braces) get distinct colours rather than
 * folding into the generic CodeMirror palette.
 *
 * Colours match the brand vars in `frontend/src/assets/styles/main.css`:
 *   --color-primary  #3B7DD8 (blue)
 *   --color-accent   #D4883E (orange)
 *   --color-navy     #1A2D50 (deep navy)
 */
export const robotHighlightStyle = HighlightStyle.define([
  // Section headers (*** Settings ***) — strong navy heading.
  { tag: t.heading, color: '#1A2D50', fontWeight: '700' },

  // Comments — muted grey, italic.
  { tag: [t.comment, t.lineComment, t.blockComment], color: '#6B7A99', fontStyle: 'italic' },

  // Test case / keyword DEFINITION names — brand-blue, bold (loud).
  { tag: t.definition(t.name), color: '#1A2D50', fontWeight: '700' },

  // Keyword CALLS (the verbs in test bodies) — brand-blue, regular.
  { tag: [t.function(t.name), t.function(t.variableName)], color: '#3B7DD8' },

  // Library namespace (`Browser` in `Browser.Click`).
  { tag: t.tagName, color: '#7B61FF' },

  // Control-flow words (FOR / IF / END / WHILE) and BDD prefixes —
  // accent orange so they read as structural, not as keywords-of-RF.
  { tag: [t.keyword, t.controlKeyword], color: '#D4883E', fontWeight: '600' },

  // Setting / [Tag] / continuation `...` — muted teal-ish.
  { tag: t.meta, color: '#2C9846', fontWeight: '500' },

  // Variable braces `${ }` and index brackets `[ ]`.
  { tag: t.bracket, color: '#7B61FF', fontWeight: '500' },

  // Variable names inside `${name}`.
  { tag: t.variableName, color: '#1A2D50' },

  // Strings (quoted).
  { tag: t.string, color: '#2C9846' },

  // Escape sequences inside arguments (`\n`, `\t`, `\\`).
  { tag: t.special(t.string), color: '#D4883E', fontWeight: '600' },

  // Numbers.
  { tag: t.number, color: '#C0392B' },

  // Atoms (True / False / None / EMPTY / SPACE).
  { tag: t.atom, color: '#C0392B', fontWeight: '600' },

  // Named-argument names (`force` in `force=True`).
  { tag: t.attributeName, color: '#7B61FF', fontStyle: 'italic' },

  // Operators (`=`, `==`).
  { tag: t.operator, color: '#D4883E' },

  // Cell separators (2+ spaces) and dots — keep them faint.
  { tag: t.punctuation, color: '#9AA5BF' },
])
