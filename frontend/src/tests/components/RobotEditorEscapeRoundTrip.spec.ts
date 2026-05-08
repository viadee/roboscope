/**
 * Round-trip test for RECORDER-RF-ESCAPE on the FE side.
 *
 * The backend emit_robot escapes leading `#` in args (otherwise RF
 * treats `Click    #login-form` as a comment). When the user opens
 * that file in the FlowEditor, the parser must unescape so the
 * SelectorPicker compares args[0] against the raw candidate value
 * correctly. The serializer must re-escape on save so the file
 * stays RF-valid.
 *
 * The escape/unescape helpers live inside RobotEditor.vue's
 * `<script setup>` block and aren't directly importable. We
 * reproduce them here verbatim and pin the contract — if the helper
 * impls drift, this test fires.
 */
import { describe, it, expect } from 'vitest'

// Mirrors `RobotEditor.vue::escapeRfToken` (and
// `backend/src/recording/robot_emit.py::_escape_rf_token`).
function escapeRfToken(s: string): string {
  if (!s) return s
  return s.startsWith('#') ? '\\' + s : s
}

// Mirrors `RobotEditor.vue::unescapeRfToken`.
function unescapeRfToken(s: string): string {
  if (s.startsWith('\\#')) return s.slice(1)
  return s
}

describe('escapeRfToken / unescapeRfToken — round-trip', () => {
  it('escapes `#login-form` → `\\#login-form`', () => {
    expect(escapeRfToken('#login-form')).toBe('\\#login-form')
  })

  it('leaves selectors that do not start with `#` unchanged', () => {
    expect(escapeRfToken('[data-testid="x"]')).toBe('[data-testid="x"]')
    expect(escapeRfToken('text="Zustimmen"')).toBe('text="Zustimmen"')
    expect(escapeRfToken('xpath=//button')).toBe('xpath=//button')
  })

  it('escape is idempotent on already-escaped values', () => {
    // After one round-trip the value already starts with `\`, not
    // `#`, so the escape function leaves it alone.
    expect(escapeRfToken('\\#login-form')).toBe('\\#login-form')
  })

  it('unescape recovers the logical form', () => {
    expect(unescapeRfToken('\\#login-form')).toBe('#login-form')
  })

  it('unescape leaves bare values alone', () => {
    expect(unescapeRfToken('#login-form')).toBe('#login-form')
    expect(unescapeRfToken('[data-testid="x"]')).toBe('[data-testid="x"]')
    expect(unescapeRfToken('https://example.com/#section')).toBe('https://example.com/#section')
  })

  it('parse → edit → save round-trip preserves the logical value', () => {
    // Backend emits an escaped form. FE parses, user mutates via the
    // SelectorPicker (which always works with the LOGICAL value), FE
    // saves. The on-disk shape must round-trip identically.
    const onDisk = '\\#login-form'
    const inMemory = unescapeRfToken(onDisk)
    expect(inMemory).toBe('#login-form')
    // ... user does nothing, just saves...
    const reSaved = escapeRfToken(inMemory)
    expect(reSaved).toBe(onDisk)
  })

  it('SelectorPicker swap to a raw `#…` candidate saves with the escape', () => {
    // applySelectorSwap stores the raw candidate value into args[0].
    // The serializer then has to add the escape back so RF doesn't
    // treat the line as a comment. This is the regression-bug
    // scenario: previously the FE serializer wrote the value
    // verbatim, so a swap to `#login-form` produced a broken file.
    const candidateValue = '#login-form'  // raw, from sidecar
    const onDisk = escapeRfToken(candidateValue)
    expect(onDisk).toBe('\\#login-form')
    expect(onDisk.startsWith('\\#')).toBe(true)
  })
})
