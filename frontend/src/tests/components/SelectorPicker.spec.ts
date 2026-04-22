import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import SelectorPicker from '@/components/recorder/SelectorPicker.vue'
import type { RecordedCommand } from '@/types/recorder.types'

function mk(command: RecordedCommand) {
  const i18n = createI18n({
    legacy: false,
    locale: 'en',
    messages: {
      en: {
        recorder: {
          selector: {
            swapAriaLabel: 'Swap selector strategy',
            strategy: {
              testid: 'Test ID',
              aria: 'ARIA',
              text: 'Text',
              css: 'CSS',
              xpath: 'XPath',
              pw_locator: 'Playwright',
              automation_id: 'AutomationId',
              uia_name: 'UIA Name',
              uia_class_name: 'UIA Class',
            },
          },
        },
      },
    },
  })
  return mount(SelectorPicker, {
    props: { command },
    global: { plugins: [i18n] },
  })
}

const baseCmd: RecordedCommand = {
  index: 0,
  keyword: 'Click',
  args: {},
  selector_candidates: [
    { strategy: 'testid', value: '[data-testid="submit"]', quality_score: 95, verified_unique: true },
    { strategy: 'aria', value: 'role=button[name="Submit"]', quality_score: 80, verified_unique: false },
    { strategy: 'css', value: 'button.btn-primary', quality_score: 50, verified_unique: false },
    { strategy: 'xpath', value: '/html/body/div/button', quality_score: 25, verified_unique: false },
  ],
  active_candidate_index: 0,
}

describe('SelectorPicker', () => {
  beforeEach(() => {
    // vue-test-utils sometimes carries doc listeners across tests — scrub.
    document.body.innerHTML = ''
  })

  it('renders the active selector value', () => {
    const w = mk(baseCmd)
    expect(w.find('.selector-picker__value').text()).toBe('[data-testid="submit"]')
  })

  it('applies the good-quality dot class for a 95-score testid', () => {
    const w = mk(baseCmd)
    const dot = w.find('.selector-picker__dot')
    expect(dot.classes()).toContain('selector-picker__dot--good')
  })

  it('renders an amber dot for a 50-score css selector', () => {
    const cmd: RecordedCommand = { ...baseCmd, active_candidate_index: 2 }
    const w = mk(cmd)
    const dot = w.find('.selector-picker__dot')
    expect(dot.classes()).toContain('selector-picker__dot--ok')
  })

  it('renders a red dot for a 25-score absolute xpath', () => {
    const cmd: RecordedCommand = { ...baseCmd, active_candidate_index: 3 }
    const w = mk(cmd)
    const dot = w.find('.selector-picker__dot')
    expect(dot.classes()).toContain('selector-picker__dot--poor')
  })

  it('opens the menu on toggle and closes on outside click', async () => {
    const w = mk(baseCmd)
    expect(w.find('.selector-picker__menu').exists()).toBe(false)

    await w.find('.selector-picker__toggle').trigger('click')
    expect(w.find('.selector-picker__menu').exists()).toBe(true)

    // Simulate an outside click — the component adds a document listener.
    document.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()
    expect(w.find('.selector-picker__menu').exists()).toBe(false)
  })

  it('emits update:activeIndex when a new candidate is picked', async () => {
    const w = mk(baseCmd)
    await w.find('.selector-picker__toggle').trigger('click')

    const items = w.findAll('.selector-picker__item')
    expect(items.length).toBe(baseCmd.selector_candidates.length)
    // Pick the second item (aria).
    await items[1].trigger('click')

    const events = w.emitted('update:activeIndex')
    expect(events).toBeTruthy()
    expect(events![0]).toEqual([1])
  })

  it('hides the toggle button when there is only one candidate', () => {
    const cmd: RecordedCommand = {
      ...baseCmd,
      selector_candidates: [baseCmd.selector_candidates[0]],
      active_candidate_index: 0,
    }
    const w = mk(cmd)
    expect(w.find('.selector-picker__toggle').exists()).toBe(false)
  })

  it('renders nothing when there are zero candidates', () => {
    const cmd: RecordedCommand = {
      ...baseCmd,
      selector_candidates: [],
    }
    const w = mk(cmd)
    expect(w.find('.selector-picker').exists()).toBe(false)
  })

  it('marks verified-unique candidates with the check indicator', async () => {
    const w = mk(baseCmd)
    await w.find('.selector-picker__toggle').trigger('click')
    const items = w.findAll('.selector-picker__item')
    // First item (testid) is verified_unique=true.
    expect(items[0].find('.selector-picker__unique').exists()).toBe(true)
    expect(items[1].find('.selector-picker__unique').exists()).toBe(false)
  })

  it('strategy label matches the i18n key', async () => {
    const w = mk(baseCmd)
    await w.find('.selector-picker__toggle').trigger('click')
    const items = w.findAll('.selector-picker__item')
    expect(items[0].find('.selector-picker__strategy').text()).toBe('Test ID')
    expect(items[2].find('.selector-picker__strategy').text()).toBe('CSS')
  })
})
