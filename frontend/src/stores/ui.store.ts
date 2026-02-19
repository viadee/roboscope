import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Toast {
  id: number
  title: string
  message: string
  type: 'success' | 'error' | 'info' | 'warning'
  timeout?: number
}

const MOBILE_BREAKPOINT = 768

export const useUiStore = defineStore('ui', () => {
  const sidebarOpen = ref(window.innerWidth >= MOBILE_BREAKPOINT)
  const windowWidth = ref(window.innerWidth)
  const toasts = ref<Toast[]>([])
  let toastId = 0

  const isMobile = computed(() => windowWidth.value < MOBILE_BREAKPOINT)

  // Browser notification state
  const notificationsEnabled = ref(localStorage.getItem('notifications_enabled') === 'true')
  const notificationPermission = ref<NotificationPermission>(
    typeof Notification !== 'undefined' ? Notification.permission : 'denied',
  )

  async function requestNotificationPermission(): Promise<boolean> {
    if (typeof Notification === 'undefined') return false
    const result = await Notification.requestPermission()
    notificationPermission.value = result
    return result === 'granted'
  }

  async function toggleNotifications() {
    if (notificationsEnabled.value) {
      notificationsEnabled.value = false
      localStorage.setItem('notifications_enabled', 'false')
      return
    }
    if (notificationPermission.value !== 'granted') {
      const granted = await requestNotificationPermission()
      if (!granted) return
    }
    notificationsEnabled.value = true
    localStorage.setItem('notifications_enabled', 'true')
  }

  function sendBrowserNotification(title: string, body: string, tag?: string) {
    if (!notificationsEnabled.value) return
    if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return
    if (document.hasFocus()) return // don't notify if user is already looking at the app
    new Notification(title, { body, tag, icon: '/favicon.ico' })
  }

  function handleResize() {
    windowWidth.value = window.innerWidth
    if (windowWidth.value < MOBILE_BREAKPOINT) {
      sidebarOpen.value = false
    }
  }

  // Listen for resize events
  window.addEventListener('resize', handleResize)

  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }

  function closeSidebarOnMobile() {
    if (isMobile.value) {
      sidebarOpen.value = false
    }
  }

  function addToast(title: string, message: string, type: Toast['type'] = 'info', timeout = 5000) {
    const id = ++toastId
    toasts.value.push({ id, title, message, type, timeout })
    if (timeout > 0) {
      setTimeout(() => removeToast(id), timeout)
    }
  }

  function removeToast(id: number) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  function success(title: string, message = '') {
    addToast(title, message, 'success')
  }

  function error(title: string, message = '') {
    addToast(title, message, 'error', 8000)
  }

  function info(title: string, message = '') {
    addToast(title, message, 'info')
  }

  function warning(title: string, message = '') {
    addToast(title, message, 'warning')
  }

  return { sidebarOpen, isMobile, windowWidth, toasts, notificationsEnabled, notificationPermission, toggleSidebar, closeSidebarOnMobile, addToast, removeToast, success, error, info, warning, toggleNotifications, sendBrowserNotification }
})
