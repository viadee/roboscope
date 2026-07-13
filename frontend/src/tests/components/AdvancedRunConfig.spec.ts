/**
 * EXEC.10 — AdvancedRunConfig: curated modifier picker emits selections, and
 * the repo-confined code-loading levers only emit paths AFTER the explicit
 * consent checkbox is ticked (never leak a path without consent).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AdvancedRunConfig from '@/components/execution/AdvancedRunConfig.vue'
import en from '@/i18n/locales/en'

vi.mock('@/api/execution.api', () => ({ getRunModifiers: vi.fn() }))
import { getRunModifiers } from '@/api/execution.api'

const i18n = createI18n({ legacy: false, locale: 'en', messages: { en } })

function mountIt(props = {}) {
  return mount(AdvancedRunConfig, {
    props: { argsText: '', variablesText: '', ...props },
    global: { plugins: [i18n] },
  })
}

beforeEach(() => {
  vi.mocked(getRunModifiers).mockReset()
})

describe('AdvancedRunConfig modifier picker', () => {
  it('emits the selected curated modifier with kind', async () => {
    vi.mocked(getRunModifiers).mockResolvedValue([
      { key: 'roboscope_tag_stamp', kind: 'prerun', label: 'Tag stamper', tier: 'vendor', description: '', args_schema: [] },
    ])
    const w = mountIt()
    await flushPromises()
    const cb = w.find('[data-testid="modifier-roboscope_tag_stamp"] input[type="checkbox"]')
    expect(cb.exists()).toBe(true)
    await cb.setValue(true)
    const ev = w.emitted('update:modifiers')
    expect(ev).toBeTruthy()
    expect(ev![ev!.length - 1][0]).toEqual([
      { key: 'roboscope_tag_stamp', kind: 'prerun', args: [] },
    ])
  })
})

describe('AdvancedRunConfig code-loading consent', () => {
  it('gates the path input behind consent and only emits once consented', async () => {
    vi.mocked(getRunModifiers).mockResolvedValue([])
    const w = mountIt({ showPythonPath: true })
    await flushPromises()
    const ta = w.find('[data-testid="advanced-pythonpath-input"]')
    // input is disabled until consent (no path can leak without consent)
    expect(ta.attributes('disabled')).toBeDefined()
    // consent first → enables input; still nothing typed → empty
    await w.find('[data-testid="pythonpath-consent"]').setValue(true)
    expect(ta.attributes('disabled')).toBeUndefined()
    let ev = w.emitted('update:pythonPaths')
    expect(ev![ev!.length - 1][0]).toEqual([])
    // now typing a repo-relative path emits it
    await ta.setValue('libs/custom')
    ev = w.emitted('update:pythonPaths')
    expect(ev![ev!.length - 1][0]).toEqual(['libs/custom'])
  })

  it('hides the lever when its flag prop is false', async () => {
    vi.mocked(getRunModifiers).mockResolvedValue([])
    const w = mountIt({ showPythonPath: false, showVariableFile: false })
    await flushPromises()
    expect(w.find('[data-testid="pythonpath-lever"]').exists()).toBe(false)
    expect(w.find('[data-testid="variablefile-lever"]').exists()).toBe(false)
  })
})
