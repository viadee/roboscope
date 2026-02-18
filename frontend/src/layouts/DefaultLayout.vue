<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import BaseToast from '@/components/ui/BaseToast.vue'
import { useAuthStore } from '@/stores/auth.store'
import { useUiStore } from '@/stores/ui.store'
import { useWebSocket } from '@/composables/useWebSocket'

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
  <div class="app-layout" :class="{ 'sidebar-collapsed': !ui.sidebarOpen }">
    <AppSidebar />
    <div class="main-area">
      <AppHeader />
      <main class="main-content">
        <slot />
      </main>
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

.main-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
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
</style>
