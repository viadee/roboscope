/**
 * Story EDITOR-9 — pure helper tests for the named-arg picker logic.
 *
 * The picker UI itself is exercised manually (Vue Flow integration is
 * heavy to mount); these tests cover the data shape it relies on:
 * the spec lookup must understand the `name=value` form.
 */
import { describe, it, expect } from 'vitest'
import { parseArgSignature } from '@/utils/robotKeywordSignatures'
import type { ParsedArg } from '@/utils/robotKeywordSignatures'

const evaluateSpecs: ParsedArg[] = [
  'expression',
  'modules=None',
  'namespace=None',
].map(parseArgSignature)

/** Mirror of FlowEditor.vue's `specForSlot` logic — tested standalone. */
function specForSlot(
  args: string[],
  specs: ParsedArg[] | null,
  index: number,
): { spec: ParsedArg; viaName: boolean } | null {
  if (!specs) return null
  const value = args[index] ?? ''
  const m = /^([A-Za-z_][\w]*)\s*=/.exec(value)
  if (m) {
    const named = specs.find((s) => s.name === m[1])
    if (named) return { spec: named, viaName: true }
  }
  return specs[index] ? { spec: specs[index], viaName: false } : null
}

describe('specForSlot (Story EDITOR-9)', () => {
  it('resolves a positional slot by index', () => {
    const r = specForSlot(['1+1'], evaluateSpecs, 0)
    expect(r?.spec.name).toBe('expression')
    expect(r?.viaName).toBe(false)
  })

  it('resolves a name= slot by named lookup, ignoring positional index', () => {
    const r = specForSlot(['1+1', 'namespace=${vars}'], evaluateSpecs, 1)
    expect(r?.spec.name).toBe('namespace')
    expect(r?.viaName).toBe(true)
  })

  it('returns null when there is no spec at that index and no name match', () => {
    expect(specForSlot(['x', 'y', 'z'], null, 0)).toBeNull()
  })

  it('falls back to positional when name= name is unknown', () => {
    const r = specForSlot(['1+1', 'unknown=foo'], evaluateSpecs, 1)
    expect(r?.spec.name).toBe('modules')
    expect(r?.viaName).toBe(false)
  })

  it('does not match name= when there is whitespace before the name', () => {
    // Robot Framework named args do not allow leading whitespace in libdoc.
    const r = specForSlot(['1+1', '  namespace=foo'], evaluateSpecs, 1)
    expect(r?.spec.name).toBe('modules') // falls back positional
  })
})

/** Mirror of FlowEditor.vue's `addArgOptions` filter logic. */
function addArgOptions(args: string[], specs: ParsedArg[]) {
  const usedNames = new Set<string>()
  for (let i = 0; i < args.length; i++) {
    const v = args[i]
    const m = /^([A-Za-z_][\w]*)\s*=/.exec(v)
    if (m) {
      usedNames.add(m[1])
    } else {
      const positional = specs[i]
      if (positional && (positional.kind === 'positional' || positional.kind === 'optional')) {
        usedNames.add(positional.name)
      }
    }
  }
  const out: { name: string; isNextPositional: boolean }[] = []
  for (let i = 0; i < specs.length; i++) {
    const s = specs[i]
    if (s.kind !== 'positional' && s.kind !== 'optional') continue
    if (!s.name || usedNames.has(s.name)) continue
    out.push({ name: s.name, isNextPositional: i === args.length })
  }
  return out
}

describe('addArgOptions (Story EDITOR-9)', () => {
  it('lists every unused param when nothing is filled', () => {
    expect(addArgOptions([], evaluateSpecs).map((o) => o.name)).toEqual([
      'expression', 'modules', 'namespace',
    ])
  })

  it('marks the immediate next positional', () => {
    const opts = addArgOptions(['1+1'], evaluateSpecs)
    expect(opts.map((o) => o.name)).toEqual(['modules', 'namespace'])
    expect(opts[0].isNextPositional).toBe(true)
    expect(opts[1].isNextPositional).toBe(false)
  })

  it('detects names already used as positional', () => {
    const opts = addArgOptions(['1+1', 'os'], evaluateSpecs)
    expect(opts.map((o) => o.name)).toEqual(['namespace'])
  })

  it('detects names already used as `name=`', () => {
    const opts = addArgOptions(['1+1', 'namespace=${vars}'], evaluateSpecs)
    expect(opts.map((o) => o.name)).toEqual(['modules'])
  })

  it('returns empty when every named param is used', () => {
    const opts = addArgOptions(['1+1', 'os', 'locals()'], evaluateSpecs)
    expect(opts).toEqual([])
  })

  it('skips *args / **kwargs entries (out of V1 scope)', () => {
    const specs = ['selector', '*keys', '**opts'].map(parseArgSignature)
    const opts = addArgOptions(['#in'], specs)
    expect(opts).toEqual([])
  })
})
