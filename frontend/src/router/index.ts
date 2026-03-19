import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth.store'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { layout: 'auth', requiresAuth: false },
    },
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/repos',
      name: 'repos',
      component: () => import('@/views/ReposView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/explorer/:repoId?',
      name: 'explorer',
      component: () => import('@/views/ExplorerView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/runs',
      name: 'runs',
      component: () => import('@/views/ExecutionView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/environments',
      name: 'environments',
      component: () => import('@/views/EnvironmentsView.vue'),
      meta: { requiresAuth: true, minRole: 'editor' },
    },
    {
      path: '/reports/:id',
      name: 'report-detail',
      component: () => import('@/views/ReportDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/test-history',
      name: 'test-history',
      component: () => import('@/views/TestHistoryView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/stats',
      name: 'stats',
      component: () => import('@/views/StatsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { requiresAuth: true, minRole: 'admin' },
    },
    {
      path: '/docs',
      name: 'docs',
      component: () => import('@/views/DocsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/imprint',
      name: 'imprint',
      component: () => import('@/views/ImprintView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      redirect: '/dashboard',
    },
  ],
})

const ROLE_HIERARCHY: Record<string, number> = {
  viewer: 0,
  runner: 1,
  editor: 2,
  admin: 3,
}

router.beforeEach(async (to, from) => {
  const auth = useAuthStore()

  // Prevent redirect loops: if we just came from dashboard→login or login→dashboard, stop
  if (to.path === from.path) return

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // Validate token by fetching current user (only once per session)
  if (to.meta.requiresAuth && auth.isAuthenticated && !auth.user) {
    try {
      await auth.fetchCurrentUser()
    } catch {
      // Token is stale/invalid — already logged out by fetchCurrentUser
      // Redirect to login without creating a loop
      if (to.path !== '/login') {
        return { path: '/login' }
      }
      return
    }
    // After fetchCurrentUser, token may have been invalidated
    if (!auth.isAuthenticated) {
      return { path: '/login' }
    }
  }

  if (to.meta.minRole && auth.user) {
    const userLevel = ROLE_HIERARCHY[auth.user.role] ?? -1
    const requiredLevel = ROLE_HIERARCHY[to.meta.minRole as string] ?? 999
    if (userLevel < requiredLevel) {
      return { path: '/dashboard' }
    }
  }

  if (to.path === '/login' && auth.isAuthenticated) {
    return { path: '/dashboard' }
  }
})

export default router
