/**
 * Story 5-2 — shared polling of the SSO emergency-bypass status so both
 * the admin view and the app-shell banner read the same source.
 *
 * Lightweight singleton: one poller per page. Components that call
 * `useBypassStatus()` get the same reactive refs. When no component is
 * consuming it the poller is torn down.
 */
import { computed, ref } from 'vue'
import { getBypassStatus, type BypassStatus } from '@/api/emergencyBypass.api'

const status = ref<BypassStatus | null>(null)
const subscribers = ref(0)
let pollHandle: number | undefined

const POLL_INTERVAL_MS = 60_000  // 60s — bypass state changes are infrequent

async function refresh() {
  try {
    status.value = await getBypassStatus()
  } catch {
    // 401 or 403 for non-admin users — silently ignore, banner is
    // admin-only anyway (see `visibleForAdmin` guard in caller).
    status.value = null
  }
}

function startPolling() {
  if (pollHandle !== undefined) return
  refresh()
  pollHandle = window.setInterval(refresh, POLL_INTERVAL_MS)
}

function stopPolling() {
  if (pollHandle !== undefined) {
    window.clearInterval(pollHandle)
    pollHandle = undefined
  }
}

export function useBypassStatus() {
  subscribers.value += 1
  if (subscribers.value === 1) startPolling()

  function release() {
    subscribers.value = Math.max(0, subscribers.value - 1)
    if (subscribers.value === 0) stopPolling()
  }

  const active = computed(() => status.value?.active === true)
  const remainingMinutes = computed(() => {
    if (!status.value?.active || !status.value.expires_at) return null
    const diff = new Date(status.value.expires_at).getTime() - Date.now()
    return diff > 0 ? Math.round(diff / 60000) : 0
  })

  return { status, active, remainingMinutes, refresh, release }
}
