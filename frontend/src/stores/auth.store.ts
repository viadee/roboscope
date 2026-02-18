import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '@/api/auth.api'
import type { User } from '@/types/domain.types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('access_token'))

  const isAuthenticated = computed(() => !!token.value)
  const currentUser = computed(() => user.value)
  const userRole = computed(() => user.value?.role ?? 'viewer')

  function hasMinRole(minRole: string): boolean {
    const hierarchy: Record<string, number> = { viewer: 0, runner: 1, editor: 2, admin: 3 }
    return (hierarchy[userRole.value] ?? -1) >= (hierarchy[minRole] ?? 999)
  }

  async function login(email: string, password: string) {
    const response = await authApi.login({ email, password })
    token.value = response.access_token
    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('refresh_token', response.refresh_token)
    await fetchCurrentUser()
  }

  async function fetchCurrentUser() {
    if (!token.value) return
    try {
      user.value = await authApi.getMe()
    } catch {
      logout()
    }
  }

  function logout() {
    user.value = null
    token.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  return { user, token, isAuthenticated, currentUser, userRole, hasMinRole, login, logout, fetchCurrentUser }
})
