/**
 * UX D3 (ux-flow-editor-resources.md) — inserting a keyword pre-seeds one
 * EMPTY argument slot per REQUIRED positional argument from its signature,
 * so the detail panel opens with the parameters the user must fill already
 * present (fixes F3: a resource keyword `[Arguments] ${url}` showed a bare
 * "+ add argument"). Optionals/varargs/kwargs stay behind the picker.
 *
 * Mounting FlowEditor (Vue Flow) is heavy, so this mirrors the real
 * `prefillRequiredArgs` logic standalone — the same shape pinned by the
 * other FlowEditor helper specs.
 */
import { describe, it, expect } from 'vitest'
import { parseArgSignature, type ParsedArg } from '@/utils/robotKeywordSignatures'

interface StepLike {
  type: string
  keyword: string
  args: string[]
}

/** Mirror of FlowEditor.vue::prefillRequiredArgs. */
function prefillRequiredArgs(step: StepLike, specsFor: (kw: string) => ParsedArg[] | null): void {
  if (step.type !== 'keyword' && step.type !== 'assignment') return
  if (step.args.length > 0) return
  const specs = specsFor(step.keyword)
  if (!specs) return
  for (const s of specs) {
    if (s.kind === 'positional') step.args.push('')
    else break
  }
}

const SIGS: Record<string, ParsedArg[]> = {
  // resource keyword — one required positional
  'open login page': ['${url}'].map(parseArgSignature),
  // library keyword — required selector then optionals
  click: ['selector', 'button=left', 'clickCount=1'].map(parseArgSignature),
  // two required positionals then a vararg
  'log many': ['first', 'second', '*rest'].map(parseArgSignature),
  // no required positionals (all optional, real defaults)
  log: ['level=INFO', 'html=False'].map(parseArgSignature),
}
const specsFor = (kw: string) => SIGS[kw.toLowerCase()] ?? null

function makeStep(keyword: string, type = 'keyword'): StepLike {
  return { type, keyword, args: [] }
}

describe('prefillRequiredArgs (D3)', () => {
  it('seeds one empty slot for a single required positional (the F3 case)', () => {
    const s = makeStep('Open Login Page')
    prefillRequiredArgs(s, specsFor)
    expect(s.args).toEqual([''])
  })

  it('seeds only the required positionals, stopping at the first optional', () => {
    const s = makeStep('Click')
    prefillRequiredArgs(s, specsFor)
    expect(s.args).toEqual(['']) // selector only; button/clickCount stay behind the picker
  })

  it('seeds multiple required positionals, stopping at a vararg', () => {
    const s = makeStep('Log Many')
    prefillRequiredArgs(s, specsFor)
    expect(s.args).toEqual(['', ''])
  })

  it('seeds nothing for an all-optional signature', () => {
    const s = makeStep('Log')
    prefillRequiredArgs(s, specsFor)
    expect(s.args).toEqual([])
  })

  it('seeds nothing for an unknown keyword (no signature)', () => {
    const s = makeStep('Totally Custom Keyword')
    prefillRequiredArgs(s, specsFor)
    expect(s.args).toEqual([])
  })

  it('never clobbers caller-provided args', () => {
    const s: StepLike = { type: 'keyword', keyword: 'Click', args: ['css=.btn'] }
    prefillRequiredArgs(s, specsFor)
    expect(s.args).toEqual(['css=.btn'])
  })

  it('ignores non-keyword step types (control structures)', () => {
    const s = makeStep('${x}', 'if')
    prefillRequiredArgs(s, specsFor)
    expect(s.args).toEqual([])
  })
})
