/**
 * Story EE-1 — Konami code easter egg.
 *
 * Verifies the composable triggers exactly once on the full sequence,
 * stays silent on partial / wrong sequences, and skips when focus is
 * inside a text-entry element.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'

import { useKonamiCode } from '@/composables/useKonamiCode'

const SEQUENCE = [
  'ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown',
  'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight',
  'KeyB', 'KeyA',
]

function dispatch(code: string, target: EventTarget = window) {
  target.dispatchEvent(new KeyboardEvent('keydown', { code, bubbles: true }))
}

function makeHost(onTrigger: () => void) {
  return defineComponent({
    setup() {
      useKonamiCode(onTrigger)
      return () => h('div')
    },
  })
}

describe('useKonamiCode', () => {
  let onTrigger: ReturnType<typeof vi.fn>
  let wrapper: VueWrapper | null = null

  beforeEach(() => {
    onTrigger = vi.fn()
    // Default matchMedia: reduced motion off.
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(),
    }))
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
      wrapper = null
    }
  })

  it('fires the callback after the full sequence', () => {
    wrapper = mount(makeHost(onTrigger), { attachTo: document.body })
    for (const code of SEQUENCE) dispatch(code)
    expect(onTrigger).toHaveBeenCalledTimes(1)
  })

  it('does NOT fire on a wrong sequence', () => {
    wrapper = mount(makeHost(onTrigger), { attachTo: document.body })
    for (const code of ['ArrowUp', 'ArrowDown', 'ArrowUp', 'ArrowDown']) dispatch(code)
    expect(onTrigger).not.toHaveBeenCalled()
  })

  it('resets buffer silently on a wrong key mid-sequence', () => {
    wrapper = mount(makeHost(onTrigger), { attachTo: document.body })
    // Three correct, then a wrong, then full sequence — should still trigger once.
    dispatch('ArrowUp'); dispatch('ArrowUp'); dispatch('ArrowDown')
    dispatch('Space') // wrong — buffer resets
    for (const code of SEQUENCE) dispatch(code)
    expect(onTrigger).toHaveBeenCalledTimes(1)
  })

  it('is retriggerable', () => {
    wrapper = mount(makeHost(onTrigger), { attachTo: document.body })
    for (const code of SEQUENCE) dispatch(code)
    for (const code of SEQUENCE) dispatch(code)
    expect(onTrigger).toHaveBeenCalledTimes(2)
  })

  it('ignores the sequence when focus is inside an <input>', () => {
    wrapper = mount(makeHost(onTrigger), { attachTo: document.body })
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()
    for (const code of SEQUENCE) dispatch(code, input)
    document.body.removeChild(input)
    expect(onTrigger).not.toHaveBeenCalled()
  })

  it('ignores the sequence when focus is inside a <textarea>', () => {
    wrapper = mount(makeHost(onTrigger), { attachTo: document.body })
    const ta = document.createElement('textarea')
    document.body.appendChild(ta)
    ta.focus()
    for (const code of SEQUENCE) dispatch(code, ta)
    document.body.removeChild(ta)
    expect(onTrigger).not.toHaveBeenCalled()
  })

  it('ignores the sequence inside a contenteditable element', () => {
    wrapper = mount(makeHost(onTrigger), { attachTo: document.body })
    const div = document.createElement('div')
    div.setAttribute('contenteditable', 'true')
    document.body.appendChild(div)
    for (const code of SEQUENCE) dispatch(code, div)
    document.body.removeChild(div)
    expect(onTrigger).not.toHaveBeenCalled()
  })

  it('does not fire when prefers-reduced-motion is reduce', () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('reduce'),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(),
    }))
    wrapper = mount(makeHost(onTrigger), { attachTo: document.body })
    for (const code of SEQUENCE) dispatch(code)
    expect(onTrigger).not.toHaveBeenCalled()
  })

  it('removes the keydown listener on unmount', () => {
    wrapper = mount(makeHost(onTrigger), { attachTo: document.body })
    wrapper.unmount()
    wrapper = null
    for (const code of SEQUENCE) dispatch(code)
    expect(onTrigger).not.toHaveBeenCalled()
  })
})
