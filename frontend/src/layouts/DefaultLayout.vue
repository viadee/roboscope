<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import BaseToast from '@/components/ui/BaseToast.vue'
import { useAuthStore } from '@/stores/auth.store'
import { useUiStore } from '@/stores/ui.store'
import { useWebSocket } from '@/composables/useWebSocket'

const { t } = useI18n()

const auth = useAuthStore()
const ui = useUiStore()
const { connect, disconnect } = useWebSocket()

onMounted(async () => {
  if (auth.isAuthenticated && !auth.user) {
    await auth.fetchCurrentUser()
  }
  connect()
})

onUnmounted(() => {
  disconnect()
})
</script>

<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': !ui.sidebarOpen, 'is-mobile': ui.isMobile }">
    <AppSidebar />
    <div class="main-area">
      <AppHeader />
      <main class="main-content">
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
