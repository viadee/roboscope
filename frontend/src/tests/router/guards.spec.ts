import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'

// A small stub route table — importing the whole router would pull in every
// lazy-loaded view. The guard itself is the real exported `authGuard`.

// Mock the auth store so we can flip isAuthenticated at will.
let _isAuthenticated = false
let _user: { role: string } | null = null
let _fetchCurrentUser: () => Promise<void> = vi.fn().mockResolvedValue(undefined)

vi.mock('@/stores/auth.store', () => ({
  useAuthStore: () => ({
    get isAuthenticated() {
      return _isAuthenticated
    },
    get user() {
      return _user
    },
    fetchCurrentUser: (...args: unknown[]) => _fetchCurrentUser.apply(null, args as []),
  }),
}))

// Route components are irrelevant to guard behaviour — use trivial stubs.
const stub = { template: '<div />' }

async function makeRouter() {
  // Import after the store mock is registered.
  const { authGuard } = await import('@/router/index')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: stub, meta: { requiresAuth: false } },
      { path: '/dashboard', name: 'dashboard', component: stub, meta: { requiresAuth: true } },
      { path: '/reports/:id', name: 'report', component: stub, meta: { requiresAuth: true } },
      { path: '/', redirect: '/dashboard' },
    ],
  })
  router.beforeEach(authGuard)
  return router
}

describe('router guards — deep-link preservation (Story 2-4)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    _isAuthenticated = false
    _user = null
    _fetchCurrentUser = vi.fn().mockResolvedValue(undefined)
  })

  it('unauthenticated access to a protected route redirects to /login with return_to (AC1)', async () => {
    const router = await makeRouter()
    await router.push('/reports/42')
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.return_to).toBe('/reports/42')
    // Legacy key is not emitted.
    expect(router.currentRoute.value.query.redirect).toBeUndefined()
  })

  it('stale token (fetchCurrentUser rejects) redirects to /login with return_to (AC2)', async () => {
    _isAuthenticated = true
    _user = null
    // The real store logs out before rethrowing — mirror that, otherwise the
    // guard's `/login && isAuthenticated → /dashboard` branch would loop forever.
    _fetchCurrentUser = vi.fn().mockImplementation(() => {
      _isAuthenticated = false
      return Promise.reject(new Error('token invalid'))
    })

    const router = await makeRouter()
    await router.push('/reports/42')
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.return_to).toBe('/reports/42')
  })

  it('first-time visit to /login does not carry self-referential return_to (AC5)', async () => {
    const router = await makeRouter()
    await router.push('/login')
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.return_to).toBeUndefined()
  })

  it('same-path navigation is a no-op (loop guard)', async () => {
    const router = await makeRouter()
    await router.push('/login')
    // Second push to the same path is a noop — query is empty.
    await router.push('/login')
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.return_to).toBeUndefined()
  })

  it('authenticated user accessing a protected route passes through', async () => {
    _isAuthenticated = true
    _user = { role: 'admin' }
    const router = await makeRouter()
    await router.push('/reports/42')
    expect(router.currentRoute.value.path).toBe('/reports/42')
  })
})
