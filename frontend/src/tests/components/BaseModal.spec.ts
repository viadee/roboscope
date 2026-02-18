import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseModal from '@/components/ui/BaseModal.vue'

describe('BaseModal', () => {
  const mountModal = (props: Record<string, unknown> = {}, slots: Record<string, string> = {}) => {
    return mount(BaseModal, {
      props: {
        modelValue: true,
        ...props,
      },
      slots: {
        default: 'Modal content',
        ...slots,
      },
      global: {
        stubs: {
          Teleport: true,
          Transition: false,
        },
      },
    })
  }

  describe('visibility', () => {
    it('renders modal content when modelValue is true', () => {
      const wrapper = mountModal({ modelValue: true })
      expect(wrapper.find('.modal-backdrop').exists()).toBe(true)
      expect(wrapper.find('.modal-body').exists()).toBe(true)
      expect(wrapper.text()).toContain('Modal content')
    })

    it('does not render modal content when modelValue is false', () => {
      const wrapper = mountModal({ modelValue: false })
      expect(wrapper.find('.modal-backdrop').exists()).toBe(false)
      expect(wrapper.find('.modal-body').exists()).toBe(false)
    })
  })

  describe('close behavior', () => {
    it('emits update:modelValue with false when backdrop is clicked', async () => {
      const wrapper = mountModal()
      await wrapper.find('.modal-backdrop').trigger('click')
      expect(wrapper.emitted('update:modelValue')).toBeTruthy()
      expect(wrapper.emitted('update:modelValue')![0]).toEqual([false])
    })

    it('emits update:modelValue with false when close button is clicked', async () => {
      const wrapper = mountModal({ title: 'Test Title' })
      await wrapper.find('.modal-close').trigger('click')
      expect(wrapper.emitted('update:modelValue')).toBeTruthy()
      expect(wrapper.emitted('update:modelValue')![0]).toEqual([false])
    })

    it('does not emit close when clicking inside the modal (not backdrop)', async () => {
      const wrapper = mountModal()
      await wrapper.find('.modal').trigger('click')
      expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    })
  })

  describe('title', () => {
    it('renders title when title prop is provided', () => {
      const wrapper = mountModal({ title: 'My Modal Title' })
      expect(wrapper.find('.modal-header').exists()).toBe(true)
      expect(wrapper.find('.modal-header h3').text()).toBe('My Modal Title')
    })

    it('does not render header when no title is provided', () => {
      const wrapper = mountModal()
      expect(wrapper.find('.modal-header').exists()).toBe(false)
    })
  })

  describe('size classes', () => {
    it('applies modal-md class by default', () => {
      const wrapper = mountModal()
      expect(wrapper.find('.modal').classes()).toContain('modal-md')
    })

    it('applies modal-sm class for sm size', () => {
      const wrapper = mountModal({ size: 'sm' })
      expect(wrapper.find('.modal').classes()).toContain('modal-sm')
    })

    it('applies modal-lg class for lg size', () => {
      const wrapper = mountModal({ size: 'lg' })
      expect(wrapper.find('.modal').classes()).toContain('modal-lg')
    })
  })

  describe('footer slot', () => {
    it('renders footer when footer slot is provided', () => {
      const wrapper = mountModal({}, { footer: '<button>Save</button>' })
      expect(wrapper.find('.modal-footer').exists()).toBe(true)
      expect(wrapper.find('.modal-footer').text()).toContain('Save')
    })

    it('does not render footer when no footer slot is provided', () => {
      const wrapper = mountModal()
      expect(wrapper.find('.modal-footer').exists()).toBe(false)
    })
  })
})
