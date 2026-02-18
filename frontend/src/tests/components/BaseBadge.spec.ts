import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseBadge from '@/components/ui/BaseBadge.vue'

describe('BaseBadge', () => {
  describe('rendering', () => {
    it('renders slot content when provided', () => {
      const wrapper = mount(BaseBadge, {
        slots: { default: 'Custom Text' },
      })
      expect(wrapper.text()).toBe('Custom Text')
    })

    it('renders status text as default slot content when no slot is provided', () => {
      const wrapper = mount(BaseBadge, {
        props: { status: 'PASSED' },
      })
      expect(wrapper.text()).toBe('PASSED')
    })

    it('renders as a span element', () => {
      const wrapper = mount(BaseBadge)
      expect(wrapper.element.tagName).toBe('SPAN')
    })
  })

  describe('variant classes', () => {
    it('applies badge-default class when no variant or status is provided', () => {
      const wrapper = mount(BaseBadge)
      expect(wrapper.classes()).toContain('badge-default')
    })

    it('applies badge-success class for success variant', () => {
      const wrapper = mount(BaseBadge, {
        props: { variant: 'success' },
      })
      expect(wrapper.classes()).toContain('badge-success')
    })

    it('applies badge-danger class for danger variant', () => {
      const wrapper = mount(BaseBadge, {
        props: { variant: 'danger' },
      })
      expect(wrapper.classes()).toContain('badge-danger')
    })

    it('applies badge-warning class for warning variant', () => {
      const wrapper = mount(BaseBadge, {
        props: { variant: 'warning' },
      })
      expect(wrapper.classes()).toContain('badge-warning')
    })

    it('applies badge-info class for info variant', () => {
      const wrapper = mount(BaseBadge, {
        props: { variant: 'info' },
      })
      expect(wrapper.classes()).toContain('badge-info')
    })
  })

  describe('status classes', () => {
    it('applies status-based class when status prop is provided', () => {
      const wrapper = mount(BaseBadge, {
        props: { status: 'PASSED' },
      })
      expect(wrapper.classes()).toContain('status-passed')
    })

    it('lowercases the status for the class name', () => {
      const wrapper = mount(BaseBadge, {
        props: { status: 'FAILED' },
      })
      expect(wrapper.classes()).toContain('status-failed')
    })

    it('uses status class instead of variant class when status is provided', () => {
      const wrapper = mount(BaseBadge, {
        props: { status: 'Running', variant: 'success' },
      })
      // status takes precedence in the ternary
      expect(wrapper.classes()).toContain('status-running')
      expect(wrapper.classes()).not.toContain('badge-success')
    })
  })
})
