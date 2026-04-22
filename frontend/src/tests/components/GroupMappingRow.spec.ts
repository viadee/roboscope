import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import GroupMappingRow from '@/components/teams/GroupMappingRow.vue'
import en from '@/i18n/locales/en'
import de from '@/i18n/locales/de'
import type { GroupMapping } from '@/types/domain.types'

function createTestI18n(locale: 'de' | 'en' = 'en') {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en',
    messages: { de, en },
  })
}

const SAMPLE: GroupMapping = {
  id: 42,
  idp_id: 1,
  team_id: 5,
  group_claim_value: 'engineering',
  role: 'viewer',
}

function mountRow(mapping: GroupMapping = SAMPLE, locale: 'de' | 'en' = 'en') {
  return mount(GroupMappingRow, {
    global: {
      plugins: [createTestI18n(locale)],
    },
    props: { mapping },
    attachTo: document.body,
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  document.body.innerHTML = ''
})

describe('GroupMappingRow', () => {
  describe('Display mode (AC2)', () => {
    it('renders role badge and group name', () => {
      const wrapper = mountRow()
      expect(wrapper.text()).toContain('engineering')
      expect(wrapper.find('[data-testid="role-badge"]').text()).toBe('viewer')
      expect(wrapper.find('[data-testid="role-select"]').exists()).toBe(false)
    })

    it('role badge has localized aria-label', () => {
      const wrapper = mountRow()
      const badge = wrapper.find('[data-testid="role-badge"]')
      expect(badge.attributes('aria-label')).toBe(
        'Edit role viewer for group engineering',
      )
    })

    it('delete button emits delete event', async () => {
      const wrapper = mountRow()
      await wrapper.find('[data-testid="row-delete"]').trigger('click')
      expect(wrapper.emitted('delete')?.[0]).toEqual([42])
    })
  })

  describe('Enter edit mode (AC3)', () => {
    it('clicking the role badge switches to edit mode', async () => {
      const wrapper = mountRow()
      await wrapper.find('[data-testid="role-badge"]').trigger('click')
      await flushPromises()
      expect(wrapper.find('[data-testid="role-select"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="role-badge"]').exists()).toBe(false)
    })

    it('Enter on the role badge switches to edit mode', async () => {
      const wrapper = mountRow()
      await wrapper
        .find('[data-testid="role-badge"]')
        .trigger('keydown', { key: 'Enter' })
      await flushPromises()
      expect(wrapper.find('[data-testid="role-select"]').exists()).toBe(true)
    })

    it('Space on the role badge also switches to edit mode', async () => {
      const wrapper = mountRow()
      await wrapper
        .find('[data-testid="role-badge"]')
        .trigger('keydown', { key: ' ' })
      await flushPromises()
      expect(wrapper.find('[data-testid="role-select"]').exists()).toBe(true)
    })
  })

  describe('Submit / Cancel (AC4)', () => {
    it('Enter in select submits and returns to Display', async () => {
      const wrapper = mountRow()
      await wrapper.find('[data-testid="role-badge"]').trigger('click')
      await flushPromises()

      const select = wrapper.find('[data-testid="role-select"]')
      await select.setValue('editor')
      await select.trigger('keydown', { key: 'Enter' })
      await flushPromises()

      expect(wrapper.emitted('update-role')?.[0]).toEqual([42, 'editor'])
      expect(wrapper.find('[data-testid="role-select"]').exists()).toBe(false)
    })

    it('Escape discards changes and returns to Display', async () => {
      const wrapper = mountRow()
      await wrapper.find('[data-testid="role-badge"]').trigger('click')
      await flushPromises()

      const select = wrapper.find('[data-testid="role-select"]')
      await select.setValue('admin')
      await select.trigger('keydown', { key: 'Escape' })
      await flushPromises()

      expect(wrapper.emitted('update-role')).toBeUndefined()
      expect(wrapper.find('[data-testid="role-select"]').exists()).toBe(false)
      // Badge still shows the original role.
      expect(wrapper.find('[data-testid="role-badge"]').text()).toBe('viewer')
    })

    it('submit with unchanged role does NOT emit', async () => {
      const wrapper = mountRow()
      await wrapper.find('[data-testid="role-badge"]').trigger('click')
      await flushPromises()
      await wrapper
        .find('[data-testid="role-select"]')
        .trigger('keydown', { key: 'Enter' })
      await flushPromises()
      expect(wrapper.emitted('update-role')).toBeUndefined()
    })

    it('clicking Save submits the new role', async () => {
      const wrapper = mountRow()
      await wrapper.find('[data-testid="role-badge"]').trigger('click')
      await flushPromises()
      await wrapper.find('[data-testid="role-select"]').setValue('runner')
      await wrapper.find('[data-testid="save-role"]').trigger('click')
      await flushPromises()
      expect(wrapper.emitted('update-role')?.[0]).toEqual([42, 'runner'])
    })

    it('clicking Cancel discards changes', async () => {
      const wrapper = mountRow()
      await wrapper.find('[data-testid="role-badge"]').trigger('click')
      await flushPromises()
      await wrapper.find('[data-testid="role-select"]').setValue('admin')
      await wrapper.find('[data-testid="cancel-role"]').trigger('click')
      await flushPromises()
      expect(wrapper.emitted('update-role')).toBeUndefined()
      expect(wrapper.find('[data-testid="role-badge"]').text()).toBe('viewer')
    })
  })

  describe('i18n (AC)', () => {
    it('renders German labels when locale is de', async () => {
      const wrapper = mountRow(SAMPLE, 'de')
      await wrapper.find('[data-testid="role-badge"]').trigger('click')
      await flushPromises()
      expect(wrapper.find('[data-testid="save-role"]').text()).toBe(
        'Speichern',
      )
      expect(wrapper.find('[data-testid="cancel-role"]').text()).toBe(
        'Abbrechen',
      )
    })
  })
})
