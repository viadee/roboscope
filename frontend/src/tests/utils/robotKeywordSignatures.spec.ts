import { describe, it, expect } from 'vitest'
import {
  parseArgSignature,
  getArgLabel,
  friendlyType,
  isVariableRef,
  readBoolValue,
  writeBoolValue,
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

describe('friendlyType (Story EDITOR-3)', () => {
  it('maps str → text control', () => {
    const ft = friendlyType('str')
    expect(ft.control).toBe('text')
    expect(ft.labelKey).toBe('flowEditor.argTypes.text')
    expect(ft.icon).toBe('Aa')
    expect(ft.optional).toBe(false)
  })

  it('maps int / float to numeric controls', () => {
    expect(friendlyType('int').control).toBe('integer')
    expect(friendlyType('float').control).toBe('number')
    expect(friendlyType('number').control).toBe('number')
  })

  it('maps bool / boolean to checkbox', () => {
    expect(friendlyType('bool').control).toBe('checkbox')
    expect(friendlyType('boolean').control).toBe('checkbox')
  })

  it('maps timedelta to duration', () => {
    const ft = friendlyType('timedelta')
    expect(ft.control).toBe('duration')
    expect(ft.icon).toBe('⏱')
  })

  it('maps Path / pathlib.Path to text with folder icon', () => {
    expect(friendlyType('Path').labelKey).toBe('flowEditor.argTypes.path')
    expect(friendlyType('pathlib.Path').labelKey).toBe('flowEditor.argTypes.path')
  })

  it('maps Any / unknown to the unknown bucket', () => {
    expect(friendlyType('Any').labelKey).toBe('flowEditor.argTypes.any')
    expect(friendlyType('JsonReply').labelKey).toBe('flowEditor.argTypes.unknown')
  })

  it('maps Literal[...] to a select with parsed choices', () => {
    const ft = friendlyType("Literal['a', 'b', 'c']")
    expect(ft.control).toBe('select')
    expect(ft.choices).toEqual(['a', 'b', 'c'])
  })

  it('maps OneOf[...] to a select too', () => {
    const ft = friendlyType("OneOf['x', 'y']")
    expect(ft.control).toBe('select')
    expect(ft.choices).toEqual(['x', 'y'])
  })

  it('marks T | None as optional and recurses on T', () => {
    const ft = friendlyType('int | None')
    expect(ft.control).toBe('integer')
    expect(ft.optional).toBe(true)
    expect(ft.raw).toBe('int | None')
  })

  it('handles None | T (reverse order)', () => {
    const ft = friendlyType('None | str')
    expect(ft.control).toBe('text')
    expect(ft.optional).toBe(true)
  })

  it('maps dict / list / tuple to the collection bucket', () => {
    expect(friendlyType('dict[str, int]').labelKey).toBe('flowEditor.argTypes.collection')
    expect(friendlyType('list[str]').labelKey).toBe('flowEditor.argTypes.collection')
    expect(friendlyType('tuple[int, ...]').labelKey).toBe('flowEditor.argTypes.collection')
  })

  it('null / empty type → unknown bucket but no crash', () => {
    expect(friendlyType(null).labelKey).toBe('flowEditor.argTypes.unknown')
    expect(friendlyType('').labelKey).toBe('flowEditor.argTypes.unknown')
  })

  it('carries the raw type through the tooltip slot', () => {
    expect(friendlyType('AssertionOperator | None').raw).toBe('AssertionOperator | None')
  })
})

describe('boolean read/write helpers (Story EDITOR-3)', () => {
  it('reads RF truthy aliases', () => {
    expect(readBoolValue('True')).toBe(true)
    expect(readBoolValue('true')).toBe(true)
    expect(readBoolValue('YES')).toBe(true)
    expect(readBoolValue('on')).toBe(true)
    expect(readBoolValue('1')).toBe(true)
  })

  it('reads RF falsy values', () => {
    expect(readBoolValue('False')).toBe(false)
    expect(readBoolValue('no')).toBe(false)
    expect(readBoolValue('off')).toBe(false)
    expect(readBoolValue('')).toBe(false)
    expect(readBoolValue(undefined)).toBe(false)
  })

  it('writes the canonical True / False capitalisation', () => {
    expect(writeBoolValue(true)).toBe('True')
    expect(writeBoolValue(false)).toBe('False')
  })
})

describe('friendlyType (review fixes M3 + S2)', () => {
  it('handles Optional[T] (PEP 484 alternative spelling)', () => {
    const ft = friendlyType('Optional[int]')
    expect(ft.control).toBe('integer')
    expect(ft.optional).toBe(true)
    expect(ft.raw).toBe('Optional[int]')
  })

  it('handles 3-way unions like int | None | str (None in middle)', () => {
    const ft = friendlyType('int | None | str')
    expect(ft.optional).toBe(true)
    // After stripping `None`, the remainder is `int | str` — not a
    // recognised single type, falls through to unknown but keeps optional.
    expect(ft.labelKey).toBe('flowEditor.argTypes.unknown')
  })

  it('parses Literal with nested brackets in the values', () => {
    const ft = friendlyType("Literal['a[1]', 'b']")
    expect(ft.control).toBe('select')
    expect(ft.choices).toEqual(['a[1]', 'b'])
  })
})

describe('isVariableRef', () => {
  it('matches RF variable shapes', () => {
    expect(isVariableRef('${TRUE}')).toBe(true)
    expect(isVariableRef('${some var}')).toBe(true)
    expect(isVariableRef('@{LIST}')).toBe(true)
    expect(isVariableRef('&{DICT}')).toBe(true)
    expect(isVariableRef('  ${X}  ')).toBe(true)
  })

  it('rejects plain values', () => {
    expect(isVariableRef('text=foo')).toBe(false)
    expect(isVariableRef('True')).toBe(false)
    expect(isVariableRef('')).toBe(false)
    expect(isVariableRef(undefined)).toBe(false)
    expect(isVariableRef(null)).toBe(false)
  })
})
