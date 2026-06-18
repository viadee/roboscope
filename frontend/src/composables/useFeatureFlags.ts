/**
 * Epic GOV — deployment feature flags shared across the app.
 *
 * Singleton: the resolved flag set is fetched once from `/config/features`
 * and cached. Flags change only via an admin settings edit or a deployment
 * restart (ENV override), so there is no polling — callers can `refresh()`
 * after an admin saves settings.
 *
 * Default-enabled semantics: `isEnabled` returns true while loading or for an
 * unknown flag, so UI affordances never flicker hidden and a fetch failure
 * degrades to "feature visible" (the server still enforces — UI hiding is
 * convenience only).
 */
import { ref } from 'vue'
import { getFeatures } from '@/api/governance.api'

const flags = ref<Record<string, boolean>>({})
const locked = ref<Record<string, boolean>>({})
const loaded = ref(false)
let inflight: Promise<void> | null = null

async function refresh(): Promise<void> {
  // Auth gate: skip the fetch with no token. An unauthenticated call to
  // /config/features returns 401, and the axios interceptor reacts to 401
  // with a full page reload — which would re-mount the layout and re-invoke
  // this composable, looping. (CLAUDE.md: "Singleton composables + auth".)
  if (!localStorage.getItem('access_token')) return
  try {
    const res = await getFeatures()
    flags.value = res.flags
    locked.value = res.locked
    loaded.value = true
  } catch {
    // Leave defaults (everything enabled); the server enforces regardless.
  }
}

export function useFeatureFlags() {
  if (!loaded.value && !inflight) {
    inflight = refresh().finally(() => {
      inflight = null
    })
  }

  /** True unless the flag is explicitly disabled (default-enabled). */
  function isEnabled(flag: string): boolean {
    return flags.value[flag] !== false
  }

  /** True when the flag is locked by an ENV override (non-editable in UI). */
  function isLocked(flag: string): boolean {
    return locked.value[flag] === true
  }

  /** Forget the cached flags (call on logout so the next login refetches for
   *  the new user — flags could differ if an admin changed them). */
  function reset() {
    loaded.value = false
    flags.value = {}
    locked.value = {}
    inflight = null
  }

  return { isEnabled, isLocked, refresh, reset, loaded }
}
