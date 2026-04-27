/**
 * Story EDITOR-4 — KeywordAutocompleteInput.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import KeywordAutocompleteInput from '@/components/editor/flow/KeywordAutocompleteInput.vue'
import { useExplorerStore } from '@/stores/explorer.store'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: { flowEditor: { keyword: 'Keyword' } },
  },
})

function mountComp(value = '') {
  return mount(KeywordAutocompleteInput, {
    props: { value },
    global: { plugins: [i18n] },
    attachTo: document.body, // so focus / click-outside work
  })
}

describe('KeywordAutocompleteInput', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
    // Seed the explorer cache with a few library kws — this is what
    // dynamic-library introspection would populate after a repo open.
    const explorer = useExplorerStore()
    explorer.keywords.push(
      { name: 'Click', library: 'Browser', doc: '', args: ['selector: str'] },
      { name: 'Click With Options', library: 'Browser', doc: '', args: ['selector: str'] },
      { name: 'Press Keys', library: 'Browser', doc: '', args: ['selector: str', '*keys: str'] },
    )
  })

  it('renders the input with the provided value', () => {
    const w = mountComp('Click')
    const input = w.find('[data-testid="kw-autocomplete-input"]')
    expect((input.element as HTMLInputElement).value).toBe('Click')
  })

  it('shows no dropdown until the user focuses or types', () => {
    const w = mountComp('Click')
    expect(w.find('[data-testid="kw-autocomplete-dropdown"]').exists()).toBe(false)
  })

  it('shows suggestions on input that prefix-match', async () => {
    const w = mountComp()
    const input = w.find('[data-testid="kw-autocomplete-input"]')
    await input.setValue('Cli')
    await flushPromises()
    const items = w.findAll('.kw-autocomplete-item')
    expect(items.length).toBeGreaterThan(0)
    // Both 'Click' and 'Click With Options' should appear (prefix)
    const names = items.map((i) => i.find('.kw-autocomplete-name').text())
    expect(names).toContain('Click')
    expect(names).toContain('Click With Options')
  })

  it('does not suggest below the 2-char threshold (parity with RobotEditor)', async () => {
    const w = mountComp()
    const input = w.find('[data-testid="kw-autocomplete-input"]')
    await input.setValue('C')
    await flushPromises()
    expect(w.find('[data-testid="kw-autocomplete-dropdown"]').exists()).toBe(false)
  })

  it('preserves the library author casing in the suggestion display', async () => {
    const explorer = useExplorerStore()
    explorer.keywords.push({
      name: 'Get Element By XPath',
      library: 'Browser',
      doc: '',
      args: ['xpath: str'],
    })
    const w = mountComp()
    const input = w.find('[data-testid="kw-autocomplete-input"]')
    await input.setValue('xpath')
    await flushPromises()
    const names = w.findAll('.kw-autocomplete-name').map((n) => n.text())
    expect(names).toContain('Get Element By XPath') // not "Get Element By Xpath"
  })

  it('orders prefix matches before substring matches', async () => {
    const w = mountComp()
    const input = w.find('[data-testid="kw-autocomplete-input"]')
    // 'press' is a prefix of 'Press Keys' and a substring of nothing else here.
    // 'cli' is a prefix of 'Click' and substring of nothing else either.
    // To exercise ordering we need a substring-only match — add one.
    const explorer = useExplorerStore()
    // The composable filters out kws with empty args, so give it one.
    explorer.keywords.push({ name: 'Quick Press', library: 'Custom', doc: '', args: ['x'] })
    await input.setValue('press')
    await flushPromises()
    const names = w.findAll('.kw-autocomplete-name').map((n) => n.text())
    // Prefix match ('Press Keys') comes before substring match ('Quick Press')
    expect(names.indexOf('Press Keys')).toBeLessThan(names.indexOf('Quick Press'))
  })

  it('emits select on Enter when a suggestion is highlighted', async () => {
    const w = mountComp()
    const input = w.find('[data-testid="kw-autocomplete-input"]')
    await input.setValue('Cli')
    await flushPromises()
    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'Enter' })
    expect(w.emitted('select')).toBeTruthy()
    expect(w.emitted('select')![0]).toEqual(['Click'])
  })

  it('emits select with the raw typed value on bare Enter (no highlight)', async () => {
    const w = mountComp()
    const input = w.find('[data-testid="kw-autocomplete-input"]')
    await input.setValue('My Custom Keyword')
    await input.trigger('keydown', { key: 'Enter' })
    expect(w.emitted('select')![0]).toEqual(['My Custom Keyword'])
  })

  it('closes the dropdown on Escape without committing', async () => {
    const w = mountComp()
    const input = w.find('[data-testid="kw-autocomplete-input"]')
    await input.setValue('Cli')
    await flushPromises()
    expect(w.find('[data-testid="kw-autocomplete-dropdown"]').exists()).toBe(true)
    await input.trigger('keydown', { key: 'Escape' })
    expect(w.find('[data-testid="kw-autocomplete-dropdown"]').exists()).toBe(false)
    expect(w.emitted('select')).toBeFalsy()
  })

  it('commits on click of a suggestion', async () => {
    const w = mountComp()
    const input = w.find('[data-testid="kw-autocomplete-input"]')
    await input.setValue('Cli')
    await flushPromises()
    const first = w.find('.kw-autocomplete-item')
    await first.trigger('mousedown')
    expect(w.emitted('select')).toBeTruthy()
    expect(w.emitted('select')![0]).toEqual(['Click'])
  })

  it('arrow keys clamp at the ends of the suggestion list', async () => {
    const w = mountComp()
    const input = w.find('[data-testid="kw-autocomplete-input"]')
    await input.setValue('Cli')
    await flushPromises()
    const itemCount = w.findAll('.kw-autocomplete-item').length
    // Down to the bottom + try one more
    for (let i = 0; i <= itemCount; i++) {
      await input.trigger('keydown', { key: 'ArrowDown' })
    }
    const items = w.findAll('.kw-autocomplete-item')
    const highlightedAt = items.findIndex((it) => it.classes().includes('is-highlighted'))
    expect(highlightedAt).toBe(itemCount - 1)
    // Up past zero
    for (let i = 0; i <= itemCount; i++) {
      await input.trigger('keydown', { key: 'ArrowUp' })
    }
    const items2 = w.findAll('.kw-autocomplete-item')
    expect(items2.findIndex((it) => it.classes().includes('is-highlighted'))).toBe(0)
  })

  it('shows the library label in the suggestion row', async () => {
    const w = mountComp()
    const input = w.find('[data-testid="kw-autocomplete-input"]')
    await input.setValue('Cli')
    await flushPromises()
    const libs = w.findAll('.kw-autocomplete-lib').map((l) => l.text())
    expect(libs).toContain('Browser')
  })

  it('falls back to "BuiltIn" label for static-fallback keywords', async () => {
    const w = mountComp()
    const input = w.find('[data-testid="kw-autocomplete-input"]')
    // 'log' is in RF_KEYWORD_SIGNATURES (BuiltIn library)
    await input.setValue('log')
    await flushPromises()
    const libs = w.findAll('.kw-autocomplete-lib').map((l) => l.text())
    expect(libs).toContain('BuiltIn')
  })
})
