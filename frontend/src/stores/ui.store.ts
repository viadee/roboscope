import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Toast {
  id: number
  title: string
  message: string
  type: 'success' | 'error' | 'info' | 'warning'
  timeout?: number
}

export const useUiStore = defineStore('ui', () => {
  const sidebarOpen = ref(true)
  const toasts = ref<Toast[]>([])
  let toastId = 0

  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
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

  return { sidebarOpen, toasts, toggleSidebar, addToast, removeToast, success, error, info, warning }
})
