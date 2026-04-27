import { describe, it, expect } from 'vitest'
import {
  parseArgSignature,
  getArgLabel,
  type ParsedArg,
} from '@/utils/robotKeywordSignatures'

describe('parseArgSignature', () => {
  it('parses a bare positional name', () => {
    expect(parseArgSignature('selector')).toEqual<ParsedArg>({
      name: 'selector',
      type: null,
      defaultValue: null,
      kind: 'positional',
    })
  })

  it('parses name + type (libdoc style)', () => {
    expect(parseArgSignature('selector: str')).toEqual<ParsedArg>({
      name: 'selector',
      type: 'str',
      defaultValue: null,
      kind: 'positional',
    })
  })

  it('parses name=default (legacy untyped style)', () => {
    expect(parseArgSignature('base=None')).toEqual<ParsedArg>({
      name: 'base',
      type: null,
      defaultValue: 'None',
      kind: 'optional',
    })
  })

  it('parses name + type + default', () => {
    expect(parseArgSignature('clickCount: int = 1')).toEqual<ParsedArg>({
      name: 'clickCount',
      type: 'int',
      defaultValue: '1',
      kind: 'optional',
    })
  })

  it('parses an enum-like type with default', () => {
    expect(parseArgSignature('button: MouseButton = left')).toEqual<ParsedArg>({
      name: 'button',
      type: 'MouseButton',
      defaultValue: 'left',
      kind: 'optional',
    })
  })

  it('parses a union type with default (T | None = None)', () => {
    expect(parseArgSignature('delay: timedelta | None = None')).toEqual<ParsedArg>({
      name: 'delay',
      type: 'timedelta | None',
      defaultValue: 'None',
      kind: 'optional',
    })
  })

  it('parses *varargs without type', () => {
    expect(parseArgSignature('*items')).toEqual<ParsedArg>({
      name: 'items',
      type: null,
      defaultValue: null,
      kind: 'varargs',
    })
  })

  it('parses *varargs with type', () => {
    expect(parseArgSignature('*modifiers: KeyboardModifier')).toEqual<ParsedArg>({
      name: 'modifiers',
      type: 'KeyboardModifier',
      defaultValue: null,
      kind: 'varargs',
    })
  })

  it('parses **kwargs without type', () => {
    expect(parseArgSignature('**kwargs')).toEqual<ParsedArg>({
      name: 'kwargs',
      type: null,
      defaultValue: null,
      kind: 'kwargs',
    })
  })

  it('parses **kwargs with type', () => {
    expect(parseArgSignature('**options: str')).toEqual<ParsedArg>({
      name: 'options',
      type: 'str',
      defaultValue: null,
      kind: 'kwargs',
    })
  })

  it('parses lone "*" as named-only separator', () => {
    expect(parseArgSignature('*')).toEqual<ParsedArg>({
      name: '',
      type: null,
      defaultValue: null,
      kind: 'named-only-sep',
    })
  })

  it('parses lone "?" as optional separator', () => {
    expect(parseArgSignature('?')).toEqual<ParsedArg>({
      name: '',
      type: null,
      defaultValue: null,
      kind: 'optional-sep',
    })
  })

  it('tolerates whitespace around separators', () => {
    expect(parseArgSignature('  base  =  None  ')).toEqual<ParsedArg>({
      name: 'base',
      type: null,
      defaultValue: 'None',
      kind: 'optional',
    })
  })

  it('treats "name=" (empty default) as no default — no stray placeholder', () => {
    expect(parseArgSignature('name=')).toEqual<ParsedArg>({
      name: 'name',
      type: null,
      defaultValue: null,
      kind: 'positional',
    })
  })

  it('falls back to positional with empty name for empty input', () => {
    expect(parseArgSignature('')).toEqual<ParsedArg>({
      name: '',
      type: null,
      defaultValue: null,
      kind: 'positional',
    })
  })

  it('does not split inside complex types — Annotated/Field', () => {
    expect(parseArgSignature('expr: Annotated[str, Field(min_length=1)]')).toEqual<ParsedArg>({
      name: 'expr',
      type: 'Annotated[str, Field(min_length=1)]',
      defaultValue: null,
      kind: 'positional',
    })
  })

  it('does not split inside string literals in Literal types', () => {
    expect(parseArgSignature("mode: Literal['a = b', 'c'] = 'a = b'")).toEqual<ParsedArg>({
      name: 'mode',
      type: "Literal['a = b', 'c']",
      defaultValue: "'a = b'",
      kind: 'optional',
    })
  })

  it('handles a default that itself contains an equals (rare)', () => {
    // body: foo: dict = {"a=b": 1}  → name=foo, type=dict, default={"a=b": 1}
    expect(parseArgSignature('foo: dict = {"a=b": 1}')).toEqual<ParsedArg>({
      name: 'foo',
      type: 'dict',
      defaultValue: '{"a=b": 1}',
      kind: 'optional',
    })
  })
})

describe('getArgLabel', () => {
  const t = (key: string, params?: Record<string, unknown>): string => {
    if (key === 'flowEditor.argLabels.fallback') return `arg ${params?.n}`
    if (key === 'flowEditor.argLabels.extraPositional') return 'extra positional'
    if (key === 'flowEditor.argLabels.extraNamed') return 'extra named'
    return key
  }

  const specs: ParsedArg[] = [
    { name: 'selector', type: 'str', defaultValue: null, kind: 'positional' },
    { name: 'button', type: 'MouseButton', defaultValue: 'left', kind: 'optional' },
    { name: 'modifiers', type: 'KeyboardModifier', defaultValue: null, kind: 'varargs' },
  ]

  it('returns the parameter name for in-range positional / optional args', () => {
    expect(getArgLabel(specs, 0, t)).toBe('selector')
    expect(getArgLabel(specs, 1, t)).toBe('button')
  })

  it('returns the localised "extra positional" for varargs entries and beyond', () => {
    expect(getArgLabel(specs, 2, t)).toBe('extra positional')
    expect(getArgLabel(specs, 3, t)).toBe('extra positional')
    expect(getArgLabel(specs, 99, t)).toBe('extra positional')
  })

  it('falls back to "arg N" for null specs', () => {
    expect(getArgLabel(null, 0, t)).toBe('arg 1')
  })

  it('falls back to "arg N" for empty specs', () => {
    expect(getArgLabel([], 1, t)).toBe('arg 2')
  })

  it('returns "extra named" for **kwargs entries', () => {
    const kwargsSpecs: ParsedArg[] = [
      { name: 'name', type: 'str', defaultValue: null, kind: 'positional' },
      { name: 'options', type: 'str', defaultValue: null, kind: 'kwargs' },
    ]
    expect(getArgLabel(kwargsSpecs, 1, t)).toBe('extra named')
    expect(getArgLabel(kwargsSpecs, 2, t)).toBe('extra named')
  })

  it('returns the parameter name when type info is missing', () => {
    const bare: ParsedArg[] = [
      { name: 'item', type: null, defaultValue: null, kind: 'positional' },
    ]
    expect(getArgLabel(bare, 0, t)).toBe('item')
  })
})
