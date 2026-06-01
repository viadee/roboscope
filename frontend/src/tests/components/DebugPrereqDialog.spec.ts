/**
 * Locks the contract that `e2e/tests/debug-session.spec.ts` depends on:
 *   - sentinel `<span data-testid="debug-prereq-dialog">` is Teleported to body
 *     iff `open=true` (E2E asserts toHaveCount(1) when open, 0 when closed)
 *   - Cancel / Install buttons emit `cancel` / `install`
 *   - `installing` prop disables both buttons
 *
 * A refactor that drops the sentinel pattern would silently break the
 * Playwright suite; this guard catches it at Vitest time.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'

import DebugPrereqDialog from '@/components/debug/DebugPrereqDialog.vue'
import en from '@/i18n/locales/en'

function createTestI18n() {
  return createI18n({
    legacy: false,
    locale: 'en',
    fallbackLocale: 'en',
    messages: { en },
  })
}

function mountDialog(props: {
  open?: boolean
  packageName?: string
  installing?: boolean
  installError?: string | null
} = {}) {
  return mount(DebugPrereqDialog, {
    attachTo: document.body,
    props: {
      open: props.open ?? false,
      packageName: props.packageName ?? 'robotcode',
      installing: props.installing ?? false,
      installError: props.installError ?? null,
    },
    global: {
      plugins: [createTestI18n()],
      stubs: {
        BaseModal: {
          props: ['modelValue', 'title', 'size'],
          template:
            '<div v-if="modelValue" data-modal-root><slot /><slot name="footer" /></div>',
        },
        BaseButton: {
          props: ['variant', 'disabled', 'loading'],
          emits: ['click'],
          template:
            '<button :disabled="disabled" :data-variant="variant" :data-loading="loading" @click="$emit(\'click\', $event)"><slot /></button>',
        },
      },
    },
  })
}

describe('DebugPrereqDialog', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('renders zero sentinel spans when closed', () => {
    mountDialog({ open: false })
    const sentinels = document.body.querySelectorAll(
      'span[data-testid="debug-prereq-dialog"]',
    )
    expect(sentinels.length).toBe(0)
  })

  it('renders exactly one sentinel span teleported to body when open', () => {
    mountDialog({ open: true })
    const sentinels = document.body.querySelectorAll(
      'span[data-testid="debug-prereq-dialog"]',
    )
    expect(sentinels.length).toBe(1)
    expect(sentinels[0].getAttribute('aria-hidden')).toBe('true')
  })

  it('removes the sentinel when the open prop flips back to false', async () => {
    const wrapper = mountDialog({ open: true })
    expect(
      document.body.querySelectorAll('span[data-testid="debug-prereq-dialog"]').length,
    ).toBe(1)
    await wrapper.setProps({ open: false })
    expect(
      document.body.querySelectorAll('span[data-testid="debug-prereq-dialog"]').length,
    ).toBe(0)
  })

  it('emits cancel when the cancel button is clicked', async () => {
    const wrapper = mountDialog({ open: true })
    const cancelBtn = wrapper.find('[data-testid="debug-prereq-cancel-btn"]')
    expect(cancelBtn.exists()).toBe(true)
    await cancelBtn.trigger('click')
    expect(wrapper.emitted('cancel')).toBeTruthy()
    expect(wrapper.emitted('cancel')!.length).toBe(1)
  })

  it('emits install when the install button is clicked', async () => {
    const wrapper = mountDialog({ open: true })
    const installBtn = wrapper.find('[data-testid="debug-prereq-install-btn"]')
    expect(installBtn.exists()).toBe(true)
    await installBtn.trigger('click')
    expect(wrapper.emitted('install')).toBeTruthy()
    expect(wrapper.emitted('install')!.length).toBe(1)
  })

  it('disables both buttons while installing', () => {
    const wrapper = mountDialog({ open: true, installing: true })
    const cancelBtn = wrapper.find('[data-testid="debug-prereq-cancel-btn"]')
    const installBtn = wrapper.find('[data-testid="debug-prereq-install-btn"]')
    expect(cancelBtn.attributes('disabled')).toBeDefined()
    expect(installBtn.attributes('disabled')).toBeDefined()
    expect(installBtn.attributes('data-loading')).toBe('true')
  })
})
