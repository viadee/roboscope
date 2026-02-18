import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseButton from '@/components/ui/BaseButton.vue'

describe('BaseButton', () => {
  describe('rendering', () => {
    it('renders slot content', () => {
      const wrapper = mount(BaseButton, {
        slots: { default: 'Click me' },
      })
      expect(wrapper.text()).toContain('Click me')
    })

    it('renders as a button element', () => {
      const wrapper = mount(BaseButton)
      expect(wrapper.element.tagName).toBe('BUTTON')
    })
  })

  describe('events', () => {
    it('emits click event when clicked', async () => {
      const wrapper = mount(BaseButton, {
        slots: { default: 'Click' },
      })
      await wrapper.trigger('click')
      expect(wrapper.emitted('click')).toHaveLength(1)
    })

    it('does not emit click event when disabled', async () => {
      const wrapper = mount(BaseButton, {
        props: { disabled: true },
        slots: { default: 'Disabled' },
      })
      await wrapper.trigger('click')
      // Disabled buttons don't fire click events in the DOM
      expect(wrapper.emitted('click')).toBeUndefined()
    })
  })

  describe('disabled state', () => {
    it('sets disabled attribute when disabled prop is true', () => {
      const wrapper = mount(BaseButton, {
        props: { disabled: true },
      })
      expect(wrapper.attributes('disabled')).toBeDefined()
    })

    it('is not disabled by default', () => {
      const wrapper = mount(BaseButton)
      expect(wrapper.attributes('disabled')).toBeUndefined()
    })

    it('is disabled when loading is true', () => {
      const wrapper = mount(BaseButton, {
        props: { loading: true },
      })
      expect(wrapper.attributes('disabled')).toBeDefined()
    })
  })

  describe('variant classes', () => {
    it('applies btn-primary class by default', () => {
      const wrapper = mount(BaseButton)
      expect(wrapper.classes()).toContain('btn-primary')
    })

    it('applies btn-secondary class for secondary variant', () => {
      const wrapper = mount(BaseButton, {
        props: { variant: 'secondary' },
      })
      expect(wrapper.classes()).toContain('btn-secondary')
    })

    it('applies btn-danger class for danger variant', () => {
      const wrapper = mount(BaseButton, {
        props: { variant: 'danger' },
      })
      expect(wrapper.classes()).toContain('btn-danger')
    })

    it('applies btn-ghost class for ghost variant', () => {
      const wrapper = mount(BaseButton, {
        props: { variant: 'ghost' },
      })
      expect(wrapper.classes()).toContain('btn-ghost')
    })
  })

  describe('size classes', () => {
    it('applies btn-md class by default', () => {
      const wrapper = mount(BaseButton)
      expect(wrapper.classes()).toContain('btn-md')
    })

    it('applies btn-sm class for sm size', () => {
      const wrapper = mount(BaseButton, {
        props: { size: 'sm' },
      })
      expect(wrapper.classes()).toContain('btn-sm')
    })

    it('applies btn-lg class for lg size', () => {
      const wrapper = mount(BaseButton, {
        props: { size: 'lg' },
      })
      expect(wrapper.classes()).toContain('btn-lg')
    })
  })

  describe('loading state', () => {
    it('shows spinner element when loading', () => {
      const wrapper = mount(BaseButton, {
        props: { loading: true },
        slots: { default: 'Loading...' },
      })
      expect(wrapper.find('.spinner').exists()).toBe(true)
    })

    it('does not show spinner when not loading', () => {
      const wrapper = mount(BaseButton, {
        slots: { default: 'Ready' },
      })
      expect(wrapper.find('.spinner').exists()).toBe(false)
    })
  })
})
