import { useUiStore } from '@/stores/ui.store'

export function useToast() {
  const ui = useUiStore()
  return {
    success: ui.success,
    error: ui.error,
    info: ui.info,
    warning: ui.warning,
  }
}
