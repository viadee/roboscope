/**
 * EDITOR-11 — smoke tests for the Robot Framework CodeMirror grammar.
 *
 * StreamLanguage isn't trivially mountable in JSDOM, so we tokenise a
 * line manually by stepping the language's `token()` callback over a
 * fake StringStream substitute. The goal is to lock the high-value
 * structural choices (keyword call vs. definition vs. namespace, inner
 * `${…}` braces, escape sequences, named-arg + operator split) so a
 * future refactor of the tokenizer cannot silently regress them.
 */
import { describe, it, expect } from 'vitest'
import { robotLanguage, robotHighlightStyle } from '@/utils/robotLanguage'

interface State {
  section: string
  lineHasKeyword: boolean
  varDepth: number
  expectDotAfterNs: boolean
}

/** Walk the language token() over `line` and return [token, text] pairs. */
function tokenise(line: string, initialState?: Partial<State>): Array<[string | null, string]> {
  const lang = robotLanguage()
  // StreamLanguage's `token` is the spec function; we re-derive a
  // minimal StringStream-compatible object that satisfies what the
  // tokenizer actually uses (sol, eol, pos, string, match, next,
  // current, eatSpace, skipToEnd).
  const out: Array<[string | null, string]> = []
  let pos = 0
  const string = line
  const stream = {
    pos: 0,
    string,
    start: 0,
    indentation() { return 0 },
    sol() { return this.pos === 0 },
    eol() { return this.pos >= this.string.length },
    next(): string | undefined {
      if (this.pos >= this.string.length) return undefined
      return this.string[this.pos++]
    },
    peek() { return this.string[this.pos] },
    eatSpace() {
      const start = this.pos
      while (this.pos < this.string.length && /[ \t]/.test(this.string[this.pos])) this.pos++
      return this.pos > start
    },
    skipToEnd() { this.pos = this.string.length },
    match(re: RegExp | string, consume = true, caseFold = false): RegExpMatchArray | boolean | null {
      if (typeof re === 'string') {
        const slice = this.string.slice(this.pos, this.pos + re.length)
        const eq = caseFold ? slice.toLowerCase() === re.toLowerCase() : slice === re
        if (eq && consume) this.pos += re.length
        return eq
      }
      const m = this.string.slice(this.pos).match(re)
      if (m && (m.index ?? 0) === 0) {
        if (consume) this.pos += m[0].length
        return m
      }
      return null
    },
    current() { return this.string.slice(this.start, this.pos) },
  }
  // @ts-expect-error — minimal StringStream stand-in
  stream.start = 0
  // @ts-expect-error
  stream.pos = 0
  const state: State = {
    section: initialState?.section ?? '',
    lineHasKeyword: initialState?.lineHasKeyword ?? false,
    varDepth: initialState?.varDepth ?? 0,
    expectDotAfterNs: initialState?.expectDotAfterNs ?? false,
  }
  let safety = 1000
  while (stream.pos < stream.string.length && safety-- > 0) {
    stream.start = stream.pos
    // @ts-expect-error — StreamLanguage parser shape
    const tok = (lang as { streamParser: { token: (s: typeof stream, st: State) => string | null } }).streamParser.token(stream, state)
    if (stream.pos === stream.start) {
      // Defensive: emit one char as null and step
      stream.pos++
    }
    out.push([tok, stream.string.slice(stream.start, stream.pos)])
    pos = stream.pos
  }
  void pos
  return out
}

describe('robotLanguage tokenizer', () => {
  it('marks section headers with the heading tag', () => {
    const tokens = tokenise('*** Settings ***')
    expect(tokens[0]).toEqual(['heading', '*** Settings ***'])
  })

  it('control flow keywords get the keyword tag', () => {
    const tokens = tokenise('FOR    ${i}    IN RANGE    10')
    const tags = tokens.map((t) => t[0])
    expect(tags).toContain('keyword') // FOR (and IN RANGE)
    expect(tags).toContain('bracket') // ${ }
    expect(tags).toContain('variableName') // i
  })

  it('keyword calls get the function tag, definitions get the definition tag', () => {
    const callTokens = tokenise('    Click    selector', { section: 'testcases' })
    expect(callTokens.find((t) => t[0] === 'function')?.[1]).toBe('Click')

    const defTokens = tokenise('Recording 17', { section: 'testcases' })
    expect(defTokens[0]).toEqual(['definition', 'Recording 17'])
  })

  it('library prefix `Browser.Click` splits into namespace + dot + function', () => {
    const tokens = tokenise('    Browser.Click    selector', { section: 'testcases' })
    const meaningful = tokens.filter((t) => t[0] !== null && t[0] !== 'punctuation')
    // First three meaningful tokens: namespace, dot-as-punctuation (filtered), function.
    // We re-include punctuation here to confirm the dot is captured separately.
    const seq = tokens.map((t) => `${t[0]}:${t[1]}`)
    const idxNs = seq.findIndex((s) => s.startsWith('tagName:Browser'))
    const idxDot = seq.findIndex((s) => s === 'punctuation:.')
    const idxFn = seq.findIndex((s) => s.startsWith('function:Click'))
    expect(idxNs).toBeGreaterThanOrEqual(0)
    expect(idxDot).toBeGreaterThan(idxNs)
    expect(idxFn).toBeGreaterThan(idxDot)
  })

  it('inner `${…}` structure is split into bracket + variableName + bracket', () => {
    const tokens = tokenise('${USER}')
    const tags = tokens.map((t) => t[0])
    expect(tags).toEqual(['bracket', 'variableName', 'bracket'])
  })

  it('escape sequences in argument cells get the string-2 tag', () => {
    const tokens = tokenise('    Log    Hello\\nWorld', { section: 'testcases' })
    expect(tokens.some((t) => t[0] === 'string-2' && t[1] === '\\n')).toBe(true)
  })

  it('named arguments split into attribute + operator + value', () => {
    const tokens = tokenise('    Click    selector    button=left', { section: 'testcases' })
    const seq = tokens.map((t) => `${t[0]}:${t[1]}`)
    expect(seq.some((s) => s === 'attributeName:button')).toBe(true)
    expect(seq.some((s) => s === 'operator:=')).toBe(true)
  })

  it('variables section pre-arms argument territory so values are not mis-coloured as kw calls', () => {
    const tokens = tokenise('${USER}      admin', { section: 'variables' })
    // 'admin' must NOT be tagged as 'function' — it's a value.
    const adminToken = tokens.find((t) => t[1] === 'admin')
    expect(adminToken?.[0]).not.toBe('function')
  })

  it('comment section colours every line as a comment', () => {
    const tokens = tokenise('Anything goes here', { section: 'comments' })
    expect(tokens[0]).toEqual(['comment', 'Anything goes here'])
  })

  it('continuation `...` at the start of an indented line gets the meta tag', () => {
    const tokens = tokenise('    ...    extra', { section: 'testcases' })
    const tags = tokens.map((t) => t[0])
    expect(tags[0]).toBe('meta')
  })

  it('atoms (True / False / None) get the atom tag in argument territory', () => {
    const tokens = tokenise('    Click    selector    True', { section: 'testcases' })
    expect(tokens.find((t) => t[1] === 'True')?.[0]).toBe('atom')
  })
})

describe('robotHighlightStyle', () => {
  it('is a CodeMirror HighlightStyle (smoke check)', () => {
    expect(robotHighlightStyle).toBeTruthy()
    // HighlightStyle exposes a `module` field at runtime; just confirm it
    // looks like a syntax-highlighting extension export.
    expect(typeof (robotHighlightStyle as { module?: unknown }).module).not.toBe('undefined')
  })
})
