import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth.store'

vi.mock('@/api/auth.api', () => ({
  login: vi.fn(),
  getMe: vi.fn(),
}))

import * as authApi from '@/api/auth.api'

describe('auth.store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    ;(localStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue(null)
    ;(localStorage.setItem as ReturnType<typeof vi.fn>).mockClear()
    ;(localStorage.removeItem as ReturnType<typeof vi.fn>).mockClear()
  })

  describe('initial state', () => {
    it('is not authenticated when no token is stored', () => {
      const store = useAuthStore()
      expect(store.isAuthenticated).toBe(false)
      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
      expect(store.currentUser).toBeNull()
    })

    it('defaults userRole to viewer when no user is loaded', () => {
      const store = useAuthStore()
      expect(store.userRole).toBe('viewer')
    })
  })

  describe('login', () => {
    it('stores tokens and fetches current user on successful login', async () => {
      const tokenResponse = {
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'bearer',
        expires_in: 3600,
      }
      const mockUser = {
        id: 1,
        email: 'admin@mateox.local',
        username: 'admin',
        role: 'admin' as const,
        is_active: true,
        created_at: '2024-01-01T00:00:00Z',
        last_login_at: null,
      }

      vi.mocked(authApi.login).mockResolvedValue(tokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      const store = useAuthStore()
      await store.login('admin@mateox.local', 'admin')

      expect(authApi.login).toHaveBeenCalledWith({
        email: 'admin@mateox.local',
        password: 'admin',
      })
      expect(store.token).toBe('test-access-token')
      expect(store.isAuthenticated).toBe(true)
      expect(localStorage.setItem).toHaveBeenCalledWith('access_token', 'test-access-token')
      expect(localStorage.setItem).toHaveBeenCalledWith('refresh_token', 'test-refresh-token')
      expect(authApi.getMe).toHaveBeenCalled()
      expect(store.user).toEqual(mockUser)
    })

    it('propagates error when login API call fails', async () => {
      vi.mocked(authApi.login).mockRejectedValue(new Error('Invalid credentials'))

      const store = useAuthStore()
      await expect(store.login('bad@email.com', 'wrong')).rejects.toThrow('Invalid credentials')
      expect(store.isAuthenticated).toBe(false)
    })
  })

  describe('logout', () => {
    it('clears user, token, and localStorage items', async () => {
      const tokenResponse = {
        access_token: 'test-token',
        refresh_token: 'test-refresh',
        token_type: 'bearer',
        expires_in: 3600,
      }
      const mockUser = {
        id: 1,
        email: 'admin@mateox.local',
        username: 'admin',
        role: 'admin' as const,
        is_active: true,
        created_at: '2024-01-01T00:00:00Z',
        last_login_at: null,
      }

      vi.mocked(authApi.login).mockResolvedValue(tokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      const store = useAuthStore()
      await store.login('admin@mateox.local', 'admin')

      store.logout()

      expect(store.user).toBeNull()
      expect(store.token).toBeNull()
      expect(store.isAuthenticated).toBe(false)
      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token')
      expect(localStorage.removeItem).toHaveBeenCalledWith('refresh_token')
    })
  })

  describe('hasMinRole', () => {
    it('returns true when user role meets the minimum', async () => {
      const mockUser = {
        id: 1,
        email: 'admin@mateox.local',
        username: 'admin',
        role: 'admin' as const,
        is_active: true,
        created_at: '2024-01-01T00:00:00Z',
        last_login_at: null,
      }

      vi.mocked(authApi.login).mockResolvedValue({
        access_token: 'tok',
        refresh_token: 'ref',
        token_type: 'bearer',
        expires_in: 3600,
      })
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      const store = useAuthStore()
      await store.login('admin@mateox.local', 'admin')

      expect(store.hasMinRole('viewer')).toBe(true)
      expect(store.hasMinRole('runner')).toBe(true)
      expect(store.hasMinRole('editor')).toBe(true)
      expect(store.hasMinRole('admin')).toBe(true)
    })

    it('returns false when user role is below the minimum', async () => {
      const mockUser = {
        id: 2,
        email: 'viewer@mateox.local',
        username: 'viewer',
        role: 'viewer' as const,
        is_active: true,
        created_at: '2024-01-01T00:00:00Z',
        last_login_at: null,
      }

      vi.mocked(authApi.login).mockResolvedValue({
        access_token: 'tok',
        refresh_token: 'ref',
        token_type: 'bearer',
        expires_in: 3600,
      })
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      const store = useAuthStore()
      await store.login('viewer@mateox.local', 'pass')

      expect(store.hasMinRole('viewer')).toBe(true)
      expect(store.hasMinRole('runner')).toBe(false)
      expect(store.hasMinRole('editor')).toBe(false)
      expect(store.hasMinRole('admin')).toBe(false)
    })

    it('returns false for unknown role input', () => {
      const store = useAuthStore()
      expect(store.hasMinRole('superadmin')).toBe(false)
    })
  })

  describe('fetchCurrentUser', () => {
    it('does nothing when no token is present', async () => {
      const store = useAuthStore()
      await store.fetchCurrentUser()

      expect(authApi.getMe).not.toHaveBeenCalled()
      expect(store.user).toBeNull()
    })

    it('fetches and sets the current user when a token exists', async () => {
      const mockUser = {
        id: 1,
        email: 'admin@mateox.local',
        username: 'admin',
        role: 'editor' as const,
        is_active: true,
        created_at: '2024-01-01T00:00:00Z',
        last_login_at: null,
      }

      vi.mocked(authApi.login).mockResolvedValue({
        access_token: 'tok',
        refresh_token: 'ref',
        token_type: 'bearer',
        expires_in: 3600,
      })
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      const store = useAuthStore()
      // Set token via login first
      await store.login('admin@mateox.local', 'admin')
      vi.mocked(authApi.getMe).mockClear()

      // Now fetch user again
      vi.mocked(authApi.getMe).mockResolvedValue({ ...mockUser, username: 'updated' })
      await store.fetchCurrentUser()

      expect(authApi.getMe).toHaveBeenCalledOnce()
      expect(store.user?.username).toBe('updated')
    })

    it('calls logout when fetchCurrentUser fails', async () => {
      vi.mocked(authApi.login).mockResolvedValue({
        access_token: 'tok',
        refresh_token: 'ref',
        token_type: 'bearer',
        expires_in: 3600,
      })
      vi.mocked(authApi.getMe)
        .mockResolvedValueOnce({
          id: 1,
          email: 'a@b.c',
          username: 'a',
          role: 'admin',
          is_active: true,
          created_at: '2024-01-01T00:00:00Z',
          last_login_at: null,
        })
        .mockRejectedValueOnce(new Error('Unauthorized'))

      const store = useAuthStore()
      await store.login('a@b.c', 'pass')
      expect(store.isAuthenticated).toBe(true)

      await store.fetchCurrentUser()

      expect(store.user).toBeNull()
      expect(store.token).toBeNull()
      expect(store.isAuthenticated).toBe(false)
    })
  })
})
