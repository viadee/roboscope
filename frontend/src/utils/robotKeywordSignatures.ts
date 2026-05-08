/**
 * Robot Framework standard library keyword signatures.
 * Maps lowercase keyword name → array of argument descriptors.
 *
 * Conventions:
 *   name        — required positional argument
 *   name=default — optional with default value
 *   *args       — varargs
 *
 * Covers: BuiltIn, String, Collections, DateTime, OperatingSystem, Process, XML
 */

/**
 * Find the index of the `=` that separates `name[: type]` from `default`
 * at the top scope of `body`. Returns -1 when there is no default.
 *
 * Walks the string while tracking bracket depth (`()`, `[]`, `{}`) and
 * quote state (`'`, `"`) so an `=` inside a complex type like
 * `Annotated[str, Field(min_length=1)]` does not look like an arg
 * separator. Prefers the spaced form ` = ` when both are present at the
 * top level — that's what libdoc emits for typed signatures.
 */
function findTopLevelEquals(body: string): number {
  let depth = 0
  let inSingle = false
  let inDouble = false
  let firstPlain = -1

  for (let i = 0; i < body.length; i++) {
    const c = body[i]
    if (inSingle) { if (c === "'" && body[i - 1] !== '\\') inSingle = false; continue }
    if (inDouble) { if (c === '"' && body[i - 1] !== '\\') inDouble = false; continue }
    if (c === "'") { inSingle = true; continue }
    if (c === '"') { inDouble = true; continue }
    if (c === '(' || c === '[' || c === '{') { depth++; continue }
    if (c === ')' || c === ']' || c === '}') { depth--; continue }
    if (depth !== 0) continue
    if (c === '=') {
      // Prefer ` = ` (spaced) over plain `=`. Return the spaced index
      // immediately when seen; otherwise remember the first plain hit
      // and fall back to it if no spaced form turns up.
      if (body[i - 1] === ' ' && body[i + 1] === ' ') return i
      if (firstPlain === -1) firstPlain = i
    }
  }
  return firstPlain
}

// Story EDITOR-2 — parsed view of a single argument descriptor.
export interface ParsedArg {
  /** Bare parameter name (no type, no default). Empty for separators. */
  name: string
  /** Type annotation as written, e.g. "str", "int", "MouseButton",
   *  "timedelta | None". Null when the descriptor has no type info. */
  type: string | null
  /** Default value as written (without surrounding spaces or quotes).
   *  Null when the parameter is required. */
  defaultValue: string | null
  /** Structural role of this descriptor. */
  kind:
    | 'positional'        // name (required)
    | 'optional'          // name=default OR name: type = default
    | 'varargs'           // *args / *args: type
    | 'kwargs'            // **kwargs / **kwargs: type
    | 'named-only-sep'    // lone "*" — positional-only / named-only separator
    | 'optional-sep'      // lone "?" — optional separator (rare)
}

/**
 * Parse one argument descriptor as emitted by Robot Framework's
 * libdoc / library-introspection. Examples it must handle:
 *
 *   "selector"                              → positional
 *   "selector: str"                         → positional + type
 *   "base=None"                             → optional
 *   "clickCount: int = 1"                   → optional + type
 *   "button: MouseButton = left"            → optional + enum-like type
 *   "delay: timedelta | None = None"        → optional + union type
 *   "*items"                                → varargs
 *   "*modifiers: KeyboardModifier"          → varargs + type
 *   "**kwargs"                              → kwargs
 *   "**options: str"                        → kwargs + type
 *   "*"                                     → named-only separator
 *   "?"                                     → optional separator
 *
 * Robust against extra whitespace and around-the-equals styling.
 * Never throws — unknown shapes degrade to `{ kind: 'positional', name: raw }`.
 */
export function parseArgSignature(raw: string): ParsedArg {
  const trimmed = raw.trim()
  const empty = (kind: ParsedArg['kind']): ParsedArg => ({
    name: '',
    type: null,
    defaultValue: null,
    kind,
  })
  if (trimmed === '*') return empty('named-only-sep')
  if (trimmed === '?') return empty('optional-sep')

  let kind: ParsedArg['kind'] = 'positional'
  let body = trimmed
  if (body.startsWith('**')) {
    kind = 'kwargs'
    body = body.slice(2)
  } else if (body.startsWith('*')) {
    kind = 'varargs'
    body = body.slice(1)
  }

  // Split off the default value first. RF libdoc emits two flavours:
  //   "clickCount: int = 1"   ← typed args use ` = ` (with spaces)
  //   "base=None"             ← untyped (legacy) args use `=` (no spaces)
  // Use a bracket / quote aware scan so we don't split inside complex
  // types like `Annotated[str, Field(min_length=1)]` or `Literal['a = b']`.
  let defaultValue: string | null = null
  let nameAndType = body
  const sepIdx = findTopLevelEquals(body)
  if (sepIdx >= 0) {
    const rawDefault = body.slice(sepIdx + 1).trim()
    // `name=` (empty default) shouldn't yield a placeholder — treat as
    // "has no default" so the UI doesn't display a stray "default: ".
    defaultValue = rawDefault === '' ? null : rawDefault
    nameAndType = body.slice(0, sepIdx).trimEnd()
  }

  if (defaultValue !== null && kind === 'positional') kind = 'optional'

  let name = nameAndType
  let type: string | null = null
  const colonIdx = nameAndType.indexOf(':')
  if (colonIdx >= 0) {
    name = nameAndType.slice(0, colonIdx).trim()
    type = nameAndType.slice(colonIdx + 1).trim()
    if (type === '') type = null
  }

  return { name, type, defaultValue, kind }
}

// ---------------------------------------------------------------------
// Story EDITOR-3 — friendly, non-developer type chip + control resolver.
// Maps a raw libdoc type string ("str", "int", "bool", "timedelta",
// "Literal['a','b']", …) to a localisable label, an icon, and the kind
// of input control the detail panel should render. Pure data — no
// validation, no coercion.
// ---------------------------------------------------------------------

export type ArgControl = 'text' | 'number' | 'integer' | 'checkbox' | 'select' | 'duration'

export interface FriendlyType {
  /** Icon glyph for the type chip (Aa, 123, ✓, ⏱, …). Always set. */
  icon: string
  /** Localisable label key under `flowEditor.argTypes.*`. Always set. */
  labelKey: string
  /** Input control kind for the detail panel. */
  control: ArgControl
  /** True when the type is `T | None` — i.e. the input is optional. */
  optional: boolean
  /** When `control === 'select'`, the literal choice values. */
  choices: string[] | null
  /** The raw type string, kept for the tooltip. Empty when null. */
  raw: string
}

/**
 * Split `body` on `sep` at top scope only — i.e. ignore separators
 * inside brackets `(…)` `[…]` `{…}` and inside string literals.
 */
function splitTopLevel(body: string, sep: string): string[] {
  const out: string[] = []
  let cur = ''
  let depth = 0
  let inS = false, inD = false
  for (let i = 0; i < body.length; i++) {
    const c = body[i]
    if ((inS || inD) && c === '\\' && i + 1 < body.length) { cur += c + body[i + 1]; i++; continue }
    if (inS) { if (c === "'") inS = false; cur += c; continue }
    if (inD) { if (c === '"') inD = false; cur += c; continue }
    if (c === "'") { inS = true; cur += c; continue }
    if (c === '"') { inD = true; cur += c; continue }
    if (c === '[' || c === '(' || c === '{') { depth++; cur += c; continue }
    if (c === ']' || c === ')' || c === '}') { depth--; cur += c; continue }
    if (depth === 0 && c === sep) { out.push(cur); cur = ''; continue }
    cur += c
  }
  out.push(cur)
  return out
}

function parseLiteralChoices(t: string): string[] | null {
  // Match Literal[...] / OneOf[...] — capture from the first `[` to the
  // LAST `]` so nested brackets in choice values (e.g. `'a[1]'`) survive.
  const m = /^(?:Literal|OneOf)\s*\[(.+)\]\s*$/is.exec(t)
  if (!m) return null
  const inner = m[1].trim()
  if (!inner) return []
  // Split on commas at top level (not inside quotes / brackets).
  // Honours `\\` as the escape character inside string literals.
  const out: string[] = []
  let cur = ''
  let inS = false, inD = false, depth = 0
  for (let i = 0; i < inner.length; i++) {
    const c = inner[i]
    if ((inS || inD) && c === '\\' && i + 1 < inner.length) {
      // Pass through escape + the following char unchanged.
      cur += c + inner[i + 1]
      i++
      continue
    }
    if (inS) { if (c === "'") inS = false; else cur += c; continue }
    if (inD) { if (c === '"') inD = false; else cur += c; continue }
    if (c === "'") { inS = true; continue }
    if (c === '"') { inD = true; continue }
    if (c === '[' || c === '(' || c === '{') { depth++; cur += c; continue }
    if (c === ']' || c === ')' || c === '}') { depth--; cur += c; continue }
    if (c === ',' && depth === 0) {
      if (cur.trim()) out.push(cur.trim())
      cur = ''
      continue
    }
    cur += c
  }
  if (cur.trim()) out.push(cur.trim())
  return out
}

/**
 * Resolve a raw type string into a friendly label + control.
 * Always returns a value — unknown types degrade to the `unknown` bucket
 * with the raw string carried through for the tooltip.
 */
export function friendlyType(rawType: string | null | undefined): FriendlyType {
  const raw = (rawType ?? '').trim()

  // `Optional[T]` → recurse on T and flag optional.
  const optWrap = /^Optional\s*\[\s*(.+)\s*\]\s*$/is.exec(raw)
  if (optWrap) {
    const inner = friendlyType(optWrap[1])
    return { ...inner, optional: true, raw }
  }

  // Union types: `T | None`, `None | T`, `T | None | U`, `int | str` …
  // Split at the top level (ignore `|` inside brackets) and treat any
  // `None` member as the optional-flag signal. Recurse on the remainder.
  if (raw.includes('|')) {
    const parts = splitTopLevel(raw, '|').map((p) => p.trim()).filter(Boolean)
    const hasNone = parts.some((p) => p === 'None')
    if (hasNone && parts.length > 1) {
      const rest = parts.filter((p) => p !== 'None').join(' | ')
      const inner = friendlyType(rest)
      return { ...inner, optional: true, raw }
    }
  }

  // Strip leading `*` / `**` for varargs/kwargs typed shapes — though
  // this helper is rarely called for those (the row label handles them);
  // keep it defensive.
  const stripped = raw.replace(/^\*\*?/, '').trim()
  const literalChoices = parseLiteralChoices(stripped)

  let icon = '?'
  let labelKey = 'flowEditor.argTypes.unknown'
  let control: ArgControl = 'text'
  let choices: string[] | null = null

  if (raw === '') {
    // empty / null type
  } else if (literalChoices) {
    icon = '▼'
    labelKey = 'flowEditor.argTypes.choice'
    control = 'select'
    choices = literalChoices
  } else if (/^str$/i.test(stripped)) {
    icon = 'Aa'
    labelKey = 'flowEditor.argTypes.text'
    control = 'text'
  } else if (/^int$/i.test(stripped)) {
    icon = '123'
    labelKey = 'flowEditor.argTypes.integer'
    control = 'integer'
  } else if (/^float$|^number$/i.test(stripped)) {
    icon = '1.0'
    labelKey = 'flowEditor.argTypes.number'
    control = 'number'
  } else if (/^bool(ean)?$/i.test(stripped)) {
    icon = '✓'
    labelKey = 'flowEditor.argTypes.yesNo'
    control = 'checkbox'
  } else if (/^timedelta$/i.test(stripped)) {
    icon = '⏱'
    labelKey = 'flowEditor.argTypes.duration'
    control = 'duration'
  } else if (/^(pathlib\.)?path$/i.test(stripped)) {
    icon = '\u{1F4C1}'
    labelKey = 'flowEditor.argTypes.path'
    control = 'text'
  } else if (/^any$/i.test(stripped)) {
    icon = '*'
    labelKey = 'flowEditor.argTypes.any'
    control = 'text'
  } else if (/^(dict|list|tuple|set|sequence|mapping|iterable)\b/i.test(stripped)) {
    icon = '[ ]'
    labelKey = 'flowEditor.argTypes.collection'
    control = 'text'
  }

  return { icon, labelKey, control, optional: false, choices, raw }
}

const TRUTHY_BOOL_LITERALS = new Set(['true', 'yes', 'on', '1'])

/** Read the boolean intent of a Robot Framework string (truthy / falsy). */
export function readBoolValue(v: string | undefined): boolean {
  if (!v) return false
  return TRUTHY_BOOL_LITERALS.has(v.trim().toLowerCase())
}

/** Canonical write form for booleans we round-trip into `.robot` source. */
export function writeBoolValue(b: boolean): 'True' | 'False' {
  return b ? 'True' : 'False'
}

/**
 * True when `v` looks like a Robot Framework variable reference
 * (`${VAR}`, `@{LIST}`, `&{DICT}`). Used by typed input controls to fall
 * back to a plain text input — replacing `${TRUE}` with the literal
 * `False` because a checkbox naively read `${TRUE}` as falsy would be
 * silent data loss.
 */
export function isVariableRef(v: string | undefined | null): boolean {
  if (!v) return false
  return /^[$@&]\{.+\}$/.test(v.trim())
}

/**
 * Resolve the user-facing label for the input at positional `index`.
 * Falls back to the localised "arg N" placeholder when nothing better is
 * known. `*args` / `**kwargs` propagate forward: any positional past the
 * varargs entry is also labelled "extra positional".
 */
export function getArgLabel(
  argSpecs: ParsedArg[] | null,
  index: number,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  const fallback = () => t('flowEditor.argLabels.fallback', { n: index + 1 })
  if (!argSpecs || argSpecs.length === 0) return fallback()

  // Find the position of `*args` / `**kwargs` in the signature so we can
  // number entries inside the varargs group as "1", "2", "3" — much
  // friendlier than repeating "extra positional" forever.
  const varargsIdx = argSpecs.findIndex((s) => s.kind === 'varargs')

  const spec = argSpecs[index]
  if (spec) {
    if (spec.kind === 'varargs') return '1'
    if (spec.kind === 'kwargs') return t('flowEditor.argLabels.extraNamed')
    if (spec.name) return spec.name
    return fallback()
  }

  // Past the declared signature — number from the start of varargs if
  // present, otherwise fall back to the generic placeholder.
  const last = argSpecs[argSpecs.length - 1]
  if (varargsIdx >= 0 && last?.kind === 'varargs') {
    return String(index - varargsIdx + 1)
  }
  if (last?.kind === 'kwargs') return t('flowEditor.argLabels.extraNamed')
  return fallback()
}

export const RF_KEYWORD_SIGNATURES = new Map<string, string[]>([
  // =====================================================================
  // BuiltIn Library
  // =====================================================================
  ['call method', ['object', 'method_name', '*args']],
  ['catenate', ['*items']],
  ['comment', ['*messages']],
  ['continue for loop', []],
  ['continue for loop if', ['condition']],
  ['convert to binary', ['item', 'base=None', 'prefix=None', 'length=None']],
  ['convert to boolean', ['item']],
  ['convert to bytes', ['input', 'input_type=text']],
  ['convert to hex', ['item', 'base=None', 'prefix=None', 'length=None', 'lowercase=False']],
  ['convert to integer', ['item', 'base=None']],
  ['convert to number', ['item', 'precision=None']],
  ['convert to octal', ['item', 'base=None', 'prefix=None', 'length=None']],
  ['convert to string', ['item']],
  ['create dictionary', ['*items']],
  ['create list', ['*items']],
  ['evaluate', ['expression', 'modules=None', 'namespace=None']],
  ['exit for loop', []],
  ['exit for loop if', ['condition']],
  ['fail', ['msg=None', '*tags']],
  ['fatal error', ['msg=None']],
  ['get count', ['container', 'item']],
  ['get length', ['item']],
  ['get library instance', ['name', 'all=False']],
  ['get time', ['format=timestamp', 'time_=NOW']],
  ['get variable value', ['name', 'default=None']],
  ['get variables', ['no_decoration=False']],
  ['import library', ['name', '*args']],
  ['import resource', ['path']],
  ['import variables', ['path', '*args']],
  ['keyword should exist', ['name', 'msg=None']],
  ['length should be', ['item', 'length', 'msg=None']],
  ['log', ['message', 'level=INFO', 'html=False', 'console=False', 'repr=False']],
  ['log many', ['*messages']],
  ['log to console', ['message', 'stream=STDOUT', 'no_newline=False']],
  ['log variables', ['level=INFO']],
  ['no operation', []],
  ['pass execution', ['message', '*tags']],
  ['pass execution if', ['condition', 'message', '*tags']],
  ['regexp escape', ['*patterns']],
  ['reload library', ['name_or_instance']],
  ['remove tags', ['*tags']],
  ['repeat keyword', ['repeat', 'name', '*args']],
  ['replace variables', ['text']],
  ['return from keyword', ['*return_values']],
  ['return from keyword if', ['condition', '*return_values']],
  ['run keyword', ['name', '*args']],
  ['run keyword and continue on failure', ['name', '*args']],
  ['run keyword and expect error', ['expected_error', 'name', '*args']],
  ['run keyword and ignore error', ['name', '*args']],
  ['run keyword and return', ['name', '*args']],
  ['run keyword and return if', ['condition', 'name', '*args']],
  ['run keyword and return status', ['name', '*args']],
  ['run keyword and warn on failure', ['name', '*args']],
  ['run keyword if', ['condition', 'name', '*args']],
  ['run keyword if all tests passed', ['name', '*args']],
  ['run keyword if any tests failed', ['name', '*args']],
  ['run keyword if test failed', ['name', '*args']],
  ['run keyword if test passed', ['name', '*args']],
  ['run keyword if timeout occurred', ['name', '*args']],
  ['run keyword unless', ['condition', 'name', '*args']],
  ['run keywords', ['*keywords']],
  ['set global variable', ['name', '*values']],
  ['set library search order', ['*search_order']],
  ['set local variable', ['name', '*values']],
  ['set log level', ['level']],
  ['set suite documentation', ['doc', 'append=False', 'top=False']],
  ['set suite metadata', ['name', 'value', 'append=False', 'top=False']],
  ['set suite variable', ['name', '*values']],
  ['set tags', ['*tags']],
  ['set task variable', ['name', '*values']],
  ['set test documentation', ['doc', 'append=False']],
  ['set test message', ['message', 'append=False']],
  ['set test variable', ['name', '*values']],
  ['set variable', ['*values']],
  ['set variable if', ['condition', '*values']],
  ['should be empty', ['item', 'msg=None']],
  ['should be equal', ['first', 'second', 'msg=None', 'values=True', 'ignore_case=False']],
  ['should be equal as integers', ['first', 'second', 'msg=None', 'values=True', 'base=None']],
  ['should be equal as numbers', ['first', 'second', 'msg=None', 'values=True', 'precision=6']],
  ['should be equal as strings', ['first', 'second', 'msg=None', 'values=True', 'ignore_case=False']],
  ['should be true', ['condition', 'msg=None']],
  ['should contain', ['container', 'item', 'msg=None', 'values=True', 'ignore_case=False']],
  ['should contain any', ['container', '*items', 'msg=None']],
  ['should contain x times', ['container', 'item', 'count', 'msg=None', 'ignore_case=False']],
  ['should end with', ['str1', 'str2', 'msg=None', 'values=True', 'ignore_case=False']],
  ['should match', ['string', 'pattern', 'msg=None', 'values=True', 'ignore_case=False']],
  ['should match regexp', ['string', 'pattern', 'msg=None', 'values=True']],
  ['should not be empty', ['item', 'msg=None']],
  ['should not be equal', ['first', 'second', 'msg=None', 'values=True', 'ignore_case=False']],
  ['should not be equal as integers', ['first', 'second', 'msg=None', 'values=True', 'base=None']],
  ['should not be equal as numbers', ['first', 'second', 'msg=None', 'values=True', 'precision=6']],
  ['should not be equal as strings', ['first', 'second', 'msg=None', 'values=True', 'ignore_case=False']],
  ['should not be true', ['condition', 'msg=None']],
  ['should not contain', ['container', 'item', 'msg=None', 'values=True', 'ignore_case=False']],
  ['should not contain any', ['container', '*items', 'msg=None']],
  ['should not end with', ['str1', 'str2', 'msg=None', 'values=True', 'ignore_case=False']],
  ['should not match', ['string', 'pattern', 'msg=None', 'values=True', 'ignore_case=False']],
  ['should not match regexp', ['string', 'pattern', 'msg=None', 'values=True']],
  ['should not start with', ['str1', 'str2', 'msg=None', 'values=True', 'ignore_case=False']],
  ['should start with', ['str1', 'str2', 'msg=None', 'values=True', 'ignore_case=False']],
  ['skip', ['msg=None']],
  ['skip if', ['condition', 'msg=None']],
  ['sleep', ['time_', 'reason=None']],
  ['variable should exist', ['name', 'msg=None']],
  ['variable should not exist', ['name', 'msg=None']],
  ['wait until keyword succeeds', ['retry', 'retry_interval', 'name', '*args']],

  // =====================================================================
  // String Library
  // =====================================================================
  ['convert to lower case', ['string']],
  ['convert to upper case', ['string']],
  ['decode bytes to string', ['bytes', 'encoding=UTF-8']],
  ['encode string to bytes', ['string', 'encoding=UTF-8']],
  ['fetch from left', ['string', 'marker']],
  ['fetch from right', ['string', 'marker']],
  ['format string', ['template', '*args', '**kwargs']],
  ['generate random string', ['length=8', 'chars=[LETTERS][NUMBERS]']],
  ['get line', ['string', 'line_number']],
  ['get line count', ['string']],
  ['get lines containing string', ['string', 'pattern', 'case_insensitive=False']],
  ['get lines matching pattern', ['string', 'pattern', 'case_insensitive=False']],
  ['get lines matching regexp', ['string', 'pattern']],
  ['get regexp matches', ['string', 'pattern', '*groups']],
  ['get substring', ['string', 'start', 'end=None']],
  ['remove string', ['string', '*removables']],
  ['remove string using regexp', ['string', '*patterns']],
  ['replace string', ['string', 'search_for', 'replace_with', 'count=-1']],
  ['replace string using regexp', ['string', 'pattern', 'replace_with', 'count=0']],
  ['should be byte string', ['item', 'msg=None']],
  ['should be lower case', ['string', 'msg=None']],
  ['should be string', ['item', 'msg=None']],
  ['should be title case', ['string', 'msg=None', 'exclude=None']],
  ['should be unicode string', ['item', 'msg=None']],
  ['should be upper case', ['string', 'msg=None']],
  ['should not be string', ['item', 'msg=None']],
  ['split string', ['string', 'separator=None', 'max_split=-1']],
  ['split string from right', ['string', 'separator=None', 'max_split=-1']],
  ['split string to characters', ['string']],
  ['split to lines', ['string', 'start=0', 'end=None']],
  ['strip string', ['string', 'mode=both', 'characters=None']],

  // =====================================================================
  // Collections Library
  // =====================================================================
  ['append to list', ['list_', '*values']],
  ['combine lists', ['*lists']],
  ['convert to list', ['item']],
  ['copy dictionary', ['dictionary', 'deepcopy=False']],
  ['copy list', ['list_', 'deepcopy=False']],
  ['count values in list', ['list_', 'value', 'start=0', 'end=None']],
  ['dictionaries should be equal', ['dict1', 'dict2', 'msg=None', 'values=True']],
  ['dictionary should contain item', ['dictionary', 'key', 'value', 'msg=None']],
  ['dictionary should contain key', ['dictionary', 'key', 'msg=None']],
  ['dictionary should contain sub dictionary', ['dict1', 'dict2', 'msg=None', 'values=True']],
  ['dictionary should contain value', ['dictionary', 'value', 'msg=None']],
  ['dictionary should not contain key', ['dictionary', 'key', 'msg=None']],
  ['dictionary should not contain value', ['dictionary', 'value', 'msg=None']],
  ['get dictionary items', ['dictionary', 'sort_keys=True']],
  ['get dictionary keys', ['dictionary', 'sort_keys=True']],
  ['get dictionary values', ['dictionary', 'sort_keys=True']],
  ['get from dictionary', ['dictionary', 'key', 'default=None']],
  ['get from list', ['list_', 'index']],
  ['get match count', ['list', 'pattern', 'case_insensitive=False', 'whitespace_insensitive=False']],
  ['get matches', ['list', 'pattern', 'case_insensitive=False', 'whitespace_insensitive=False']],
  ['get slice from list', ['list_', 'start=0', 'end=None']],
  ['insert into list', ['list_', 'index', 'value']],
  ['keep in dictionary', ['dictionary', '*keys']],
  ['list should contain sub list', ['list1', 'list2', 'msg=None', 'values=True']],
  ['list should contain value', ['list_', 'value', 'msg=None']],
  ['list should not contain duplicates', ['list_', 'msg=None']],
  ['list should not contain value', ['list_', 'value', 'msg=None']],
  ['lists should be equal', ['list1', 'list2', 'msg=None', 'values=True', 'names=None']],
  ['log dictionary', ['dictionary', 'level=INFO']],
  ['log list', ['list_', 'level=INFO']],
  ['pop from dictionary', ['dictionary', 'key', 'default=']],
  ['remove duplicates', ['list_']],
  ['remove from dictionary', ['dictionary', '*keys']],
  ['remove from list', ['list_', 'index']],
  ['remove values from list', ['list_', '*values']],
  ['reverse list', ['list_']],
  ['set list value', ['list_', 'index', 'value']],
  ['set to dictionary', ['dictionary', '*key_value_pairs']],
  ['should contain match', ['list', 'pattern', 'msg=None', 'case_insensitive=False', 'whitespace_insensitive=False']],
  ['should not contain match', ['list', 'pattern', 'msg=None', 'case_insensitive=False', 'whitespace_insensitive=False']],
  ['sort list', ['list_']],

  // =====================================================================
  // DateTime Library
  // =====================================================================
  ['add time to date', ['date', 'time', 'result_format=timestamp', 'exclude_millis=False', 'date_format=None']],
  ['add time to time', ['time1', 'time2', 'result_format=number', 'exclude_millis=False']],
  ['convert date', ['date', 'result_format=timestamp', 'exclude_millis=False', 'date_format=None']],
  ['convert time', ['time', 'result_format=number', 'exclude_millis=False']],
  ['get current date', ['time_zone=local', 'increment=0', 'result_format=timestamp', 'exclude_millis=False']],
  ['subtract date from date', ['date1', 'date2', 'result_format=number', 'exclude_millis=False', 'date1_format=None', 'date2_format=None']],
  ['subtract time from date', ['date', 'time', 'result_format=timestamp', 'exclude_millis=False', 'date_format=None']],
  ['subtract time from time', ['time1', 'time2', 'result_format=number', 'exclude_millis=False']],

  // =====================================================================
  // OperatingSystem Library
  // =====================================================================
  ['append to environment variable', ['name', '*values', 'separator=']],
  ['append to file', ['path', 'content', 'encoding=UTF-8']],
  ['copy directory', ['source', 'destination']],
  ['copy file', ['source', 'destination']],
  ['copy files', ['*sources_and_destination']],
  ['count directories in directory', ['path', 'pattern=None']],
  ['count files in directory', ['path', 'pattern=None']],
  ['count items in directory', ['path', 'pattern=None']],
  ['create binary file', ['path', 'content']],
  ['create directory', ['path']],
  ['create file', ['path', 'content=', 'encoding=UTF-8']],
  ['directory should be empty', ['path', 'msg=None']],
  ['directory should exist', ['path', 'msg=None']],
  ['directory should not be empty', ['path', 'msg=None']],
  ['directory should not exist', ['path', 'msg=None']],
  ['empty directory', ['path']],
  ['environment variable should be set', ['name', 'msg=None']],
  ['environment variable should not be set', ['name', 'msg=None']],
  ['file should be empty', ['path', 'msg=None']],
  ['file should exist', ['path', 'msg=None']],
  ['file should not be empty', ['path', 'msg=None']],
  ['file should not exist', ['path', 'msg=None']],
  ['get binary file', ['path']],
  ['get environment variable', ['name', 'default=None']],
  ['get environment variables', []],
  ['get file', ['path', 'encoding=UTF-8']],
  ['get file size', ['path']],
  ['get modified time', ['path', 'format=timestamp']],
  ['grep file', ['path', 'pattern', 'encoding=UTF-8']],
  ['join path', ['base', '*parts']],
  ['join paths', ['base', '*paths']],
  ['list directories in directory', ['path', 'pattern=None', 'absolute=False']],
  ['list directory', ['path', 'pattern=None', 'absolute=False']],
  ['list files in directory', ['path', 'pattern=None', 'absolute=False']],
  ['log environment variables', ['level=INFO']],
  ['log file', ['path', 'encoding=UTF-8']],
  ['move directory', ['source', 'destination']],
  ['move file', ['source', 'destination']],
  ['move files', ['*sources_and_destination']],
  ['normalize path', ['path']],
  ['remove directory', ['path', 'recursive=False']],
  ['remove environment variable', ['*names']],
  ['remove file', ['path']],
  ['remove files', ['*paths']],
  ['run', ['command']],
  ['run and return rc', ['command']],
  ['run and return rc and output', ['command']],
  ['set environment variable', ['name', 'value']],
  ['set modified time', ['path', 'mtime=None']],
  ['should exist', ['path', 'msg=None']],
  ['should not exist', ['path', 'msg=None']],
  ['split extension', ['path']],
  ['split path', ['path']],
  ['touch', ['path']],
  ['wait until created', ['path', 'timeout=1 minute']],
  ['wait until removed', ['path', 'timeout=1 minute']],

  // =====================================================================
  // Process Library
  // =====================================================================
  ['get process id', ['handle=None']],
  ['get process object', ['handle=None']],
  ['get process result', ['handle=None', 'rc=False', 'stdout=False', 'stderr=False', 'stdout_path=False', 'stderr_path=False']],
  ['is process running', ['handle=None']],
  ['join command line', ['*args']],
  ['process should be running', ['handle=None', 'error_message=Process is not running.']],
  ['process should be stopped', ['handle=None', 'error_message=Process is running.']],
  ['run process', ['command', '*arguments', '**configuration']],
  ['send signal to process', ['signal', 'handle=None', 'group=False']],
  ['split command line', ['args', 'escaping=False']],
  ['start process', ['command', '*arguments', '**configuration']],
  ['switch process', ['handle']],
  ['terminate all processes', ['kill=False']],
  ['terminate process', ['handle=None', 'kill=False']],
  ['wait for process', ['handle=None', 'timeout=None', 'on_timeout=continue']],

  // =====================================================================
  // XML Library
  // =====================================================================
  ['add element', ['source', 'element', 'index=None', 'xpath=.']],
  ['clear element', ['source', 'xpath=.', 'clear_tail=False']],
  ['copy element', ['source', 'xpath=.']],
  ['element attribute should be', ['source', 'name', 'expected', 'xpath=.', 'message=None']],
  ['element attribute should match', ['source', 'name', 'pattern', 'xpath=.', 'message=None']],
  ['element should exist', ['source', 'xpath=.', 'message=None']],
  ['element should not exist', ['source', 'xpath=.', 'message=None']],
  ['element should not have attribute', ['source', 'name', 'xpath=.', 'message=None']],
  ['element text should be', ['source', 'expected', 'xpath=.', 'normalize_whitespace=False', 'message=None']],
  ['element text should match', ['source', 'pattern', 'xpath=.', 'normalize_whitespace=False', 'message=None']],
  ['element to string', ['source', 'xpath=.', 'encoding=None']],
  ['elements should be equal', ['source', 'expected', 'exclude_children=False', 'normalize_whitespace=False']],
  ['elements should match', ['source', 'expected', 'exclude_children=False', 'normalize_whitespace=False']],
  ['evaluate xpath', ['source', 'expression', 'context=.']],
  ['get child elements', ['source', 'xpath=.']],
  ['get element', ['source', 'xpath=.']],
  ['get element attribute', ['source', 'name', 'xpath=.', 'default=None']],
  ['get element attributes', ['source', 'xpath=.']],
  ['get element count', ['source', 'xpath=.']],
  ['get element text', ['source', 'xpath=.', 'normalize_whitespace=False']],
  ['get elements', ['source', 'xpath=.']],
  ['get elements texts', ['source', 'xpath=.', 'normalize_whitespace=False']],
  ['log element', ['source', 'level=INFO', 'xpath=.']],
  ['parse xml', ['source', 'keep_clark_notation=False', 'strip_namespaces=False']],
  ['remove element', ['source', 'xpath=', 'remove_tail=False']],
  ['remove element attribute', ['source', 'name', 'xpath=.']],
  ['remove element attributes', ['source', 'xpath=.']],
  ['remove elements', ['source', 'xpath=', 'remove_tail=False']],
  ['remove elements attribute', ['source', 'name', 'xpath=.']],
  ['remove elements attributes', ['source', 'xpath=.']],
  ['save xml', ['source', 'path', 'encoding=UTF-8']],
  ['set element attribute', ['source', 'name', 'value', 'xpath=.']],
  ['set element tag', ['source', 'tag', 'xpath=.']],
  ['set element text', ['source', 'text=None', 'tail=None', 'xpath=.']],
  ['set elements attribute', ['source', 'name', 'value', 'xpath=.']],
  ['set elements tag', ['source', 'tag', 'xpath=.']],
  ['set elements text', ['source', 'text=None', 'tail=None', 'xpath=.']],
])
