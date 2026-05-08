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

  it('keeps the toggle button visible when there is only one candidate so user can edit / add', () => {
    // Story EDITOR-CUSTOM-SEL — even with a single candidate the
    // user must be able to OPEN the menu (to edit the candidate's
    // value or add a new one). The toggle therefore renders as
    // long as there's >= 1 candidate; only the *aria-label* swaps
    // to "edit / add" mode when there are no swap targets.
    const cmd: RecordedCommand = {
      ...baseCmd,
      selector_candidates: [baseCmd.selector_candidates[0]],
      active_candidate_index: 0,
    }
    const w = mk(cmd)
    expect(w.find('.selector-picker__toggle').exists()).toBe(true)
    expect(w.find('.selector-picker__toggle').attributes('aria-label')).toMatch(/edit/i)
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

  /**
   * Legacy sidecars (saved before the synthesizer dropped
   * `_pw_locator`) still contain `pw_locator` candidates whose
   * value is Playwright JS API syntax — Browser library cannot
   * parse it. The picker must NOT let users swap to one of those
   * rows; surface them only in the active-position display (if
   * the legacy file already had one there).
   */
  describe('legacy pw_locator candidates', () => {
    const legacyCmd: RecordedCommand = {
      index: 0,
      keyword: 'Click',
      args: {},
      selector_candidates: [
        { strategy: 'testid', value: '[data-testid="submit"]', quality_score: 95, verified_unique: true },
        { strategy: 'aria', value: 'role=button[name="Submit"]', quality_score: 80, verified_unique: false },
        // Legacy pw_locator rows — must be hidden from the menu.
        { strategy: 'pw_locator', value: 'getByRole("button", { name: "Submit" })', quality_score: 75, verified_unique: false },
        { strategy: 'pw_locator', value: 'getByText("Submit", { exact: true })', quality_score: 70, verified_unique: false },
        { strategy: 'css', value: 'button.btn-primary', quality_score: 50, verified_unique: false },
      ],
      active_candidate_index: 0,
    }

    it('hides pw_locator rows from the swap menu', async () => {
      const w = mk(legacyCmd)
      await w.find('.selector-picker__toggle').trigger('click')
      const items = w.findAll('.selector-picker__item')
      // 5 candidates total, 2 hidden (pw_locator) → 3 visible.
      expect(items.length).toBe(3)
      const strategies = items.map(i =>
        i.find('.selector-picker__strategy').text(),
      )
      expect(strategies).not.toContain('Playwright')
      // The visible ones still render in the original sort order.
      expect(strategies).toEqual(['Test ID', 'ARIA', 'CSS'])
    })

    it('emits the original index when swapping past hidden pw_locator rows', async () => {
      const w = mk(legacyCmd)
      await w.find('.selector-picker__toggle').trigger('click')
      const items = w.findAll('.selector-picker__item')
      // Pick the third visible item (CSS). Its ORIGINAL index in
      // the un-filtered list is 4, since two pw_locator rows sit
      // between the second visible (ARIA, idx 1) and CSS.
      await items[2].trigger('click')
      const events = w.emitted('update:activeIndex')
      expect(events).toBeTruthy()
      expect(events![0]).toEqual([4])
    })

    it('keeps the toggle visible when only one non-legacy candidate remains so user can edit / add', () => {
      // Story EDITOR-CUSTOM-SEL — user can still want to edit the
      // single survivor or append a custom alternative, even when
      // the original sidecar's only non-pw_locator row is the
      // single testid. Toggle stays open; the aria-label flips to
      // "edit / add" to reflect the lack of swap targets.
      const cmd: RecordedCommand = {
        ...legacyCmd,
        selector_candidates: [
          { strategy: 'testid', value: '[data-testid="x"]', quality_score: 95, verified_unique: true },
          { strategy: 'pw_locator', value: 'getByRole("button")', quality_score: 75, verified_unique: false },
          { strategy: 'pw_locator', value: 'getByText("x")', quality_score: 70, verified_unique: false },
        ],
      }
      const w = mk(cmd)
      expect(w.find('.selector-picker__toggle').exists()).toBe(true)
      expect(w.find('.selector-picker__toggle').attributes('aria-label')).toMatch(/edit/i)
    })

    it('still displays the active candidate even if it is pw_locator', () => {
      // Pathological legacy state: someone manually set active to a
      // pw_locator row before the filter shipped. The user must
      // still SEE the broken value (so they can swap away from it),
      // even though the menu hides pw_locator entries.
      const cmd: RecordedCommand = {
        ...legacyCmd,
        active_candidate_index: 2,  // pw_locator getByRole
      }
      const w = mk(cmd)
      expect(w.find('.selector-picker__value').text()).toBe(
        'getByRole("button", { name: "Submit" })',
      )
    })
  })

  /**
   * Story EDITOR-CUSTOM-SEL — user edits an existing candidate or
   * appends a brand-new one. Both flows go through emit; the
   * parent FlowEditor mutates the sidecar in place.
   */
  describe('custom edit + add', () => {
    it('edit pencil → opens an inline editor with the current value', async () => {
      const w = mk(baseCmd)
      await w.find('.selector-picker__toggle').trigger('click')

      const items = w.findAll('.selector-picker__item')
      // Click the ✏ pencil on the first row (testid).
      await items[0].find('.selector-picker__edit').trigger('click')

      // Inline editor renders the current value.
      const input = items[0].find<HTMLInputElement>('.selector-picker__edit-input')
      expect(input.exists()).toBe(true)
      expect(input.element.value).toBe('[data-testid="submit"]')

      // Strategy dropdown reflects the candidate's strategy.
      const select = items[0].find<HTMLSelectElement>('.selector-picker__strategy-select')
      expect(select.element.value).toBe('testid')
    })

    it('edit → save emits update:candidate with the new value + strategy', async () => {
      const w = mk(baseCmd)
      await w.find('.selector-picker__toggle').trigger('click')
      const items = w.findAll('.selector-picker__item')
      await items[0].find('.selector-picker__edit').trigger('click')

      const input = items[0].find<HTMLInputElement>('.selector-picker__edit-input')
      await input.setValue('[data-test-id="my-button"]')

      // Click the ✓ save button.
      await items[0].find('.selector-picker__edit-action--save').trigger('click')

      const events = w.emitted('update:candidate')
      expect(events).toBeTruthy()
      expect(events![0]).toEqual([{
        index: 0,
        value: '[data-test-id="my-button"]',
        strategy: 'testid',
      }])
    })

    it('edit → cancel does NOT emit anything', async () => {
      const w = mk(baseCmd)
      await w.find('.selector-picker__toggle').trigger('click')
      const items = w.findAll('.selector-picker__item')
      await items[0].find('.selector-picker__edit').trigger('click')
      await items[0].find('.selector-picker__edit-action--cancel').trigger('click')

      expect(w.emitted('update:candidate')).toBeFalsy()
    })

    it('add custom row → emits add:candidate with auto-detected strategy', async () => {
      const w = mk(baseCmd)
      await w.find('.selector-picker__toggle').trigger('click')

      // Click the "+ Add custom" trigger.
      await w.find('[data-testid="selector-picker-add"]').trigger('click')

      // Type an XPath value — strategy should auto-flip to xpath.
      const input = w.find<HTMLInputElement>('.selector-picker__edit-input')
      await input.setValue('//button[@aria-label="Save"]')

      // Save.
      await w.find('[data-testid="selector-picker-add-save"]').trigger('click')

      const events = w.emitted('add:candidate')
      expect(events).toBeTruthy()
      expect(events![0]).toEqual([{
        value: '//button[@aria-label="Save"]',
        strategy: 'xpath',
      }])
    })

    it('strategy auto-detect: text=foo → text', async () => {
      const w = mk(baseCmd)
      await w.find('.selector-picker__toggle').trigger('click')
      await w.find('[data-testid="selector-picker-add"]').trigger('click')
      await w.find<HTMLInputElement>('.selector-picker__edit-input').setValue('text=Login')
      await w.find('[data-testid="selector-picker-add-save"]').trigger('click')
      const events = w.emitted('add:candidate')
      expect(events![0][0]).toMatchObject({ strategy: 'text' })
    })

    it('strategy auto-detect: [data-testid=…] → testid', async () => {
      const w = mk(baseCmd)
      await w.find('.selector-picker__toggle').trigger('click')
      await w.find('[data-testid="selector-picker-add"]').trigger('click')
      await w.find<HTMLInputElement>('.selector-picker__edit-input').setValue('[data-testid="x"]')
      await w.find('[data-testid="selector-picker-add-save"]').trigger('click')
      const events = w.emitted('add:candidate')
      expect(events![0][0]).toMatchObject({ strategy: 'testid' })
    })

    it('strategy auto-detect: bare CSS → css', async () => {
      const w = mk(baseCmd)
      await w.find('.selector-picker__toggle').trigger('click')
      await w.find('[data-testid="selector-picker-add"]').trigger('click')
      await w.find<HTMLInputElement>('.selector-picker__edit-input').setValue('button.btn-primary')
      await w.find('[data-testid="selector-picker-add-save"]').trigger('click')
      const events = w.emitted('add:candidate')
      expect(events![0][0]).toMatchObject({ strategy: 'css' })
    })
  })
})
