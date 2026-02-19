import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useUiStore } from '@/stores/ui.store'

describe('ui.store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('initial state', () => {
    it('has sidebar open by default on desktop', () => {
      // Default window.innerWidth is 1024 in jsdom, which is >= 768
      const store = useUiStore()
      expect(store.sidebarOpen).toBe(true)
    })

    it('has no toasts by default', () => {
      const store = useUiStore()
      expect(store.toasts).toEqual([])
    })

    it('exposes isMobile computed', () => {
      const store = useUiStore()
      expect(typeof store.isMobile).toBe('boolean')
    })
  })

  describe('toggleSidebar', () => {
    it('closes sidebar when it is open', () => {
      const store = useUiStore()
      expect(store.sidebarOpen).toBe(true)

      store.toggleSidebar()
      expect(store.sidebarOpen).toBe(false)
    })

    it('opens sidebar when it is closed', () => {
      const store = useUiStore()
      store.toggleSidebar() // close
      store.toggleSidebar() // re-open
      expect(store.sidebarOpen).toBe(true)
    })
  })

  describe('closeSidebarOnMobile', () => {
    it('does nothing on desktop', () => {
      const store = useUiStore()
      store.sidebarOpen = true
      store.closeSidebarOnMobile()
      expect(store.sidebarOpen).toBe(true)
    })

    it('closes sidebar when isMobile is true', () => {
      const store = useUiStore()
      store.sidebarOpen = true
      // Simulate mobile by setting windowWidth below breakpoint
      ;(store as any).windowWidth = 500
      store.closeSidebarOnMobile()
      expect(store.sidebarOpen).toBe(false)
    })
  })

  describe('addToast', () => {
    it('adds a toast with correct properties', () => {
      const store = useUiStore()
      store.addToast('Test Title', 'Test message', 'success', 5000)

      expect(store.toasts).toHaveLength(1)
      expect(store.toasts[0]).toMatchObject({
        title: 'Test Title',
        message: 'Test message',
        type: 'success',
        timeout: 5000,
      })
      expect(store.toasts[0].id).toBeDefined()
    })

    it('defaults type to info and timeout to 5000', () => {
      const store = useUiStore()
      store.addToast('Info', 'Info message')

      expect(store.toasts[0].type).toBe('info')
      expect(store.toasts[0].timeout).toBe(5000)
    })

    it('assigns incrementing ids to toasts', () => {
      const store = useUiStore()
      store.addToast('First', 'msg1')
      store.addToast('Second', 'msg2')

      expect(store.toasts[1].id).toBeGreaterThan(store.toasts[0].id)
    })

    it('auto-removes toast after timeout', () => {
      const store = useUiStore()
      store.addToast('Auto Remove', 'Will be removed', 'info', 3000)
      expect(store.toasts).toHaveLength(1)

      vi.advanceTimersByTime(3000)
      expect(store.toasts).toHaveLength(0)
    })

    it('does not auto-remove toast when timeout is 0', () => {
      const store = useUiStore()
      store.addToast('Persistent', 'Will stay', 'warning', 0)
      expect(store.toasts).toHaveLength(1)

      vi.advanceTimersByTime(10000)
      expect(store.toasts).toHaveLength(1)
    })
  })

  describe('removeToast', () => {
    it('removes a specific toast by id', () => {
      const store = useUiStore()
      store.addToast('First', 'msg1', 'info', 0)
      store.addToast('Second', 'msg2', 'info', 0)

      const firstId = store.toasts[0].id
      store.removeToast(firstId)

      expect(store.toasts).toHaveLength(1)
      expect(store.toasts[0].title).toBe('Second')
    })

    it('does nothing when removing a non-existent id', () => {
      const store = useUiStore()
      store.addToast('Only', 'msg', 'info', 0)

      store.removeToast(9999)
      expect(store.toasts).toHaveLength(1)
    })
  })

  describe('convenience methods', () => {
    it('success() adds a success toast', () => {
      const store = useUiStore()
      store.success('Done', 'All good')

      expect(store.toasts[0].type).toBe('success')
      expect(store.toasts[0].title).toBe('Done')
      expect(store.toasts[0].message).toBe('All good')
    })

    it('error() adds an error toast with 8000ms timeout', () => {
      const store = useUiStore()
      store.error('Failed', 'Something went wrong')

      expect(store.toasts[0].type).toBe('error')
      expect(store.toasts[0].timeout).toBe(8000)
    })

    it('info() adds an info toast', () => {
      const store = useUiStore()
      store.info('Note')

      expect(store.toasts[0].type).toBe('info')
      expect(store.toasts[0].message).toBe('')
    })

    it('warning() adds a warning toast', () => {
      const store = useUiStore()
      store.warning('Watch out', 'Be careful')

      expect(store.toasts[0].type).toBe('warning')
    })
  })
})
