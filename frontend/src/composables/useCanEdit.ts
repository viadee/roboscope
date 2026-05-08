/**
 * Story 4-6: canonical permission composable for editor-like views.
 *
 * Consumes the effective_roles_by_repo map that /auth/me now returns
 * (Story 4-1) and resolves a per-repo { canEdit, canRun, role,
 * readOnlyReason } tuple.
 *
 * Fallback (no entry in the map): returns the user's global role. This
 * preserves pre-Phase-4 behavior where a RUNNER without team grants
 * could still Run on any repo (assuming backend accepts it).
 */
import { computed, type ComputedRef } from 'vue'
import type { Role } from '@/types/domain.types'
import { useAuthStore } from '@/stores/auth.store'

const ROLE_RANK: Record<Role, number> = {
  viewer: 0,
  runner: 1,
  editor: 2,
  admin: 3,
}

export interface CanEditResult {
  canEdit: ComputedRef<boolean>
  canRun: ComputedRef<boolean>
  role: ComputedRef<Role>
  readOnlyReason: ComputedRef<string | null>
}

export function useCanEdit(repoId: ComputedRef<number | null | undefined> | number | null | undefined): CanEditResult {
  const auth = useAuthStore()

  const resolvedRepoId = computed(() => {
    const raw = typeof repoId === 'object' && repoId !== null && 'value' in repoId
      ? (repoId as ComputedRef<number | null | undefined>).value
      : (repoId as number | null | undefined)
    return raw ?? null
  })

  const role = computed<Role>(() => {
    const repoMap = auth.user?.effective_roles_by_repo ?? {}
    const id = resolvedRepoId.value
    if (id !== null && Object.prototype.hasOwnProperty.call(repoMap, String(id))) {
      return repoMap[String(id)] as Role
    }
    return (auth.user?.role as Role) ?? 'viewer'
  })

  const canEdit = computed(() => ROLE_RANK[role.value] >= ROLE_RANK.editor)
  const canRun = computed(() => ROLE_RANK[role.value] >= ROLE_RANK.runner)

  const readOnlyReason = computed<string | null>(() => {
    if (canEdit.value) return null
    if (role.value === 'viewer') return 'viewer'
    if (role.value === 'runner') return 'runner'
    return 'unknown'
  })

  return { canEdit, canRun, role, readOnlyReason }
}
