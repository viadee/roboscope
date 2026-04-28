<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import BaseToast from '@/components/ui/BaseToast.vue'
import DefaultPasswordBanner from '@/components/auth/DefaultPasswordBanner.vue'
import { useAuthStore } from '@/stores/auth.store'
import { useUiStore } from '@/stores/ui.store'
import { useWebSocket } from '@/composables/useWebSocket'
import { useTour } from '@/composables/useTour'

const { t } = useI18n()

const auth = useAuthStore()
const ui = useUiStore()
const { connect, disconnect } = useWebSocket()
const { startTour, tourCompleted } = useTour()

onMounted(async () => {
  if (auth.isAuthenticated && !auth.user) {
    await auth.fetchCurrentUser()
  }
  connect()

  // Auto-start tour for first-time users
  if (!tourCompleted.value) {
    setTimeout(() => {
      startTour()
    }, 1000)
  }
})

onUnmounted(() => {
  disconnect()
})
</script>

<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': !ui.sidebarOpen, 'is-mobile': ui.isMobile }">
    <AppSidebar />
    <!-- Story A11Y-1: keyboard users tab in → see this link first → skip past sidebar -->
    <a class="skip-to-main" href="#main">{{ t('a11y.skipToMain') }}</a>
    <div class="main-area">
      <AppHeader />
      <DefaultPasswordBanner />
      <main id="main" class="main-content" tabindex="-1">
        <slot />
      </main>
      <footer class="app-footer">
        <span>&copy; {{ new Date().getFullYear() }} viadee Unternehmensberatung AG</span>
        <span class="footer-sep">|</span>
        <a href="https://www.viadee.de" target="_blank" rel="noopener">viadee.de</a>
        <span class="footer-sep">|</span>
        <router-link to="/imprint">{{ t('imprint.title') }}</router-link>
      </footer>
    </div>

    <!-- Toast Notifications -->
    <div class="toast-container">
      <TransitionGroup name="slide">
        <BaseToast
          v-for="toast in ui.toasts"
          :key="toast.id"
          :toast="toast"
          @close="ui.removeToast(toast.id)"
        />
      </TransitionGroup>
    </div>
  </div>
</template>

<style scoped>
/* Story A11Y-1: skip-to-main link — visually hidden until focused */
.skip-to-main {
  position: absolute;
  left: -9999px;
  top: 0;
  z-index: 10000;
  padding: 8px 16px;
  background: var(--color-primary, #3B7DD8);
  color: #fff;
  text-decoration: none;
  font-weight: 600;
  border-radius: 0 0 4px 0;
}
.skip-to-main:focus {
  left: 0;
  outline: 2px solid #fff;
  outline-offset: -4px;
}

.app-layout {
  display: flex;
  min-height: 100vh;
}

.main-area {
  flex: 1;
  margin-left: var(--sidebar-width);
  transition: margin-left 0.2s ease;
  display: flex;
  flex-direction: column;
}

.sidebar-collapsed .main-area {
  margin-left: 60px;
}

/* On mobile, sidebar is an overlay — main area takes full width */
.is-mobile .main-area {
  margin-left: 0 !important;
}

.main-content {
  flex: 1;
  overflow-y: auto;
}

.app-footer {
  padding: 12px 24px;
  font-size: 12px;
  color: var(--color-text-muted);
  border-top: 1px solid var(--color-border-light);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.app-footer a {
  color: var(--color-primary);
  text-decoration: none;
}

.app-footer a:hover {
  text-decoration: underline;
}

.footer-sep {
  color: var(--color-border);
}

.toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 380px;
}

@media (max-width: 768px) {
  .app-footer {
    padding: 10px 12px;
    justify-content: center;
    text-align: center;
  }

  .toast-container {
    left: 12px;
    right: 12px;
    max-width: none;
  }
}
</style>
