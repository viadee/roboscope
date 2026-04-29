/**
 * Tests for the boolean-input round-trip in the FlowEditor detail panel.
 *
 * Two bugs the user hit:
 *   1. Toggling a `name=value` bool slot (e.g. `force=True`) overwrote
 *      the entire slot with `True`, dropping the `name=` prefix. After
 *      the next render the slot resolved positionally and (if the
 *      positional spec at that index wasn't a bool) the checkbox
 *      vanished and a text input appeared mid-edit.
 *   2. The checkbox read the slot string verbatim through
 *      `readBoolValue`, so `force=True` came back as `false`. Plus
 *      `name=` (no default written) ignored the keyword's signature
 *      default and rendered unchecked.
 *
 * The actual `isBoolChecked` / `onBoolToggle` live inside
 * FlowEditor.vue's <script setup>; we test the regex contract that
 * underpins both. Mirrors the testing style of
 * FlowEditorAddArgPicker.spec.ts (helpers reproduced standalone).
 */
import { describe, it, expect } from 'vitest'
import {
  parseArgSignature,
  readBoolValue,
  writeBoolValue,
} from '@/utils/robotKeywordSignatures'
import type { ParsedArg } from '@/utils/robotKeywordSignatures'

// Mirror of FlowEditor.vue's `_NAMED_ARG_RE`.
const NAMED_ARG_RE = /^([A-Za-z_][\w]*)\s*=(.*)$/

/** Standalone clone of FlowEditor.vue::isBoolChecked. */
function isBoolChecked(args: string[], specs: ParsedArg[], index: number): boolean {
  const raw = args[index] ?? ''
  const m = NAMED_ARG_RE.exec(raw)
  const v = m ? m[2] : raw
  if (v) return readBoolValue(v)
  // Resolve spec by name first (mirrors `specForSlot`), fall back to
  // positional, then read the signature default.
  let spec: ParsedArg | undefined
  if (m) spec = specs.find((s) => s.name === m[1])
  if (!spec) spec = specs[index]
  return readBoolValue(spec?.defaultValue ?? '')
}

/** Standalone clone of FlowEditor.vue::onBoolToggle's slot-rewrite. */
function applyBoolToggle(args: string[], index: number, checked: boolean): string {
  const raw = args[index] ?? ''
  const m = NAMED_ARG_RE.exec(raw)
  return m ? `${m[1]}=${writeBoolValue(checked)}` : writeBoolValue(checked)
}

const clickSpecs: ParsedArg[] = [
  'selector',
  'button=left',
  'force=False',  // bool with explicit False default
  'noWaitAfter=True',  // bool with explicit True default
].map(parseArgSignature)

describe('isBoolChecked', () => {
  it('strips the `name=` prefix on a named-arg slot before reading', () => {
    // Bug #2 — without the fix, readBoolValue('force=True') is false.
    expect(isBoolChecked(['#login', 'left', 'force=True'], clickSpecs, 2)).toBe(true)
    expect(isBoolChecked(['#login', 'left', 'force=False'], clickSpecs, 2)).toBe(false)
  })

  it('falls back to the named spec default when the value half is empty', () => {
    // `force=` (no default written) → use the spec's `defaultValue`.
    // Resolves the spec via the name in the slot, NOT the positional
    // index — order in `clickSpecs` is {selector, button, force,
    // noWaitAfter}; `force=` at index 0 must still pull `force`'s
    // default (False), not selector's (no default).
    expect(isBoolChecked(['force='], clickSpecs, 0)).toBe(false)
    expect(isBoolChecked(['noWaitAfter='], clickSpecs, 0)).toBe(true)
  })

  it('falls back to the positional spec default for bare empty positional slots', () => {
    // Empty slot with no `=` → positional spec at that index.
    expect(isBoolChecked(['#login', 'left', ''], clickSpecs, 2)).toBe(false)
    expect(isBoolChecked(['#login', 'left', '', ''], clickSpecs, 3)).toBe(true)
  })

  it('reads bare positional values (no `name=`) via readBoolValue', () => {
    expect(isBoolChecked(['#login', 'left', 'True'], clickSpecs, 2)).toBe(true)
    expect(isBoolChecked(['#login', 'left', 'yes'], clickSpecs, 2)).toBe(true)
    expect(isBoolChecked(['#login', 'left', 'False'], clickSpecs, 2)).toBe(false)
  })
})

describe('applyBoolToggle', () => {
  it('preserves the `name=` prefix on a named-arg slot after toggle', () => {
    // Bug #1 — without the fix, `force=True` becomes `True` after a
    // toggle, the slot loses its identity, and the next render
    // resolves positionally to a different spec.
    expect(applyBoolToggle(['#login', 'left', 'force=False'], 2, true)).toBe('force=True')
    expect(applyBoolToggle(['#login', 'left', 'force=True'], 2, false)).toBe('force=False')
  })

  it('rewrites a bare positional slot with the canonical bool literal', () => {
    expect(applyBoolToggle(['#login', 'left', ''], 2, true)).toBe('True')
    expect(applyBoolToggle(['#login', 'left', 'yes'], 2, false)).toBe('False')
  })

  it('keeps the prefix even when the value half is empty', () => {
    // `force=` (no default written) toggled on → `force=True`, NOT
    // bare `True` — preserves the named-arg shape.
    expect(applyBoolToggle(['force='], 0, true)).toBe('force=True')
  })
})
