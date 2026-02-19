<script setup lang="ts">
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth.store'
import { useUiStore } from '@/stores/ui.store'
import { useExecutionStore } from '@/stores/execution.store'
import { computed } from 'vue'
import mateoLogo from '@/assets/mateo-logo.png'

const route = useRoute()
const auth = useAuthStore()
const ui = useUiStore()
const execution = useExecutionStore()
const { t } = useI18n()

const activeCount = computed(() => execution.activeRuns.length)

const navItems = computed(() => {
  const items = [
    { path: '/dashboard', labelKey: 'nav.dashboard', icon: '\u2302' },
    { path: '/repos', labelKey: 'nav.repos', icon: '\uD83D\uDCC1' },
    { path: '/explorer', labelKey: 'nav.explorer', icon: '\uD83D\uDD0D' },
    { path: '/runs', labelKey: 'nav.execution', icon: '\u25B6', badge: activeCount.value || undefined },
    { path: '/stats', labelKey: 'nav.stats', icon: '\uD83D\uDCC8' },
    { path: '/docs', labelKey: 'nav.docs', icon: '\uD83D\uDCD6' },
  ]

  if (auth.hasMinRole('editor')) {
    items.push({ path: '/environments', labelKey: 'nav.environments', icon: '\u2699' })
  }

  if (auth.hasMinRole('admin')) {
    items.push({ path: '/settings', labelKey: 'nav.settings', icon: '\uD83D\uDD27' })
  }

  return items
})

function isActive(path: string): boolean {
  return route.path.startsWith(path)
}

// Close sidebar on route change when on mobile
watch(() => route.path, () => {
  ui.closeSidebarOnMobile()
})
</script>

<template>
  <!-- Mobile overlay backdrop -->
  <Transition name="fade">
    <div
      v-if="ui.isMobile && ui.sidebarOpen"
      class="sidebar-backdrop"
      @click="ui.toggleSidebar"
    ></div>
  </Transition>

  <aside class="sidebar" :class="{ collapsed: !ui.sidebarOpen, mobile: ui.isMobile }">
    <div class="sidebar-header">
      <router-link to="/dashboard" class="logo">
        <img :src="mateoLogo" alt="mateo" class="logo-img" v-if="ui.sidebarOpen" />
        <span class="logo-collapsed" v-else>m</span>
      </router-link>
    </div>

    <nav class="sidebar-nav">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-label" v-if="ui.sidebarOpen">{{ t(item.labelKey) }}</span>
        <span v-if="item.badge && ui.sidebarOpen" class="nav-badge">{{ item.badge }}</span>
      </router-link>
    </nav>

    <div class="sidebar-footer" v-if="ui.sidebarOpen">
      <div class="user-info">
        <div class="user-avatar">{{ auth.user?.username?.charAt(0)?.toUpperCase() }}</div>
        <div class="user-details">
          <span class="user-name">{{ auth.user?.username }}</span>
          <span class="user-role">{{ auth.user?.role }}</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
}

.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  width: var(--sidebar-width);
  background: linear-gradient(180deg, #162044 0%, var(--color-bg-sidebar) 100%);
  color: var(--color-text-sidebar);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease, transform 0.2s ease;
  z-index: 100;
  overflow: hidden;
}

.sidebar.collapsed {
  width: 60px;
}

.sidebar.mobile {
  width: var(--sidebar-width);
  transform: translateX(0);
}

.sidebar.mobile.collapsed {
  width: var(--sidebar-width);
  transform: translateX(calc(-1 * var(--sidebar-width)));
}

.sidebar-header {
  padding: 20px 16px 16px;
  border-bottom: 1px solid rgba(180, 189, 217, 0.12);
}

.logo {
  text-decoration: none;
  color: white;
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-img {
  height: 54px;
  width: auto;
}

.logo-collapsed {
  font-size: 24px;
  font-weight: 800;
  color: var(--color-primary);
}

.sidebar-nav {
  flex: 1;
  padding: 16px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  color: var(--color-text-sidebar);
  text-decoration: none;
  font-size: 14px;
  font-weight: 450;
  transition: all 0.15s ease;
}

.nav-item:hover {
  background: rgba(60, 181, 161, 0.1);
  color: #ffffff;
}

.nav-item.active {
  background: rgba(60, 181, 161, 0.18);
  color: var(--color-primary-light);
  font-weight: 500;
}

.nav-item.active .nav-icon {
  color: var(--color-primary);
}

.nav-icon {
  font-size: 16px;
  width: 24px;
  text-align: center;
  flex-shrink: 0;
}

.nav-label {
  flex: 1;
}

.nav-badge {
  background: var(--color-primary);
  color: white;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
}

.sidebar-footer {
  padding: 14px 16px;
  border-top: 1px solid rgba(180, 189, 217, 0.12);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark));
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.user-details {
  display: flex;
  flex-direction: column;
}

.user-name {
  font-size: 13px;
  font-weight: 500;
  color: #ffffff;
}

.user-role {
  font-size: 11px;
  color: var(--color-text-light);
  text-transform: capitalize;
}

/* Fade transition for backdrop */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
