<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth.store'
import { useUiStore } from '@/stores/ui.store'
import { useTour } from '@/composables/useTour'
import BaseButton from '@/components/ui/BaseButton.vue'

const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()
const { t, locale } = useI18n()
const { startTour } = useTour()

const languages = ['de', 'en', 'fr', 'es'] as const

function switchLanguage(lang: string) {
  locale.value = lang
  localStorage.setItem('lang', lang)
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <header class="app-header">
    <div class="header-left">
      <button class="toggle-btn" @click="ui.toggleSidebar" :aria-label="t('common.menu')">
        &#9776;
      </button>
    </div>
    <div class="header-right">
      <div class="lang-switcher">
        <button
          v-for="lang in languages"
          :key="lang"
          class="lang-btn"
          :class="{ active: locale === lang }"
          @click="switchLanguage(lang)"
        >
          {{ lang.toUpperCase() }}
        </button>
      </div>
      <button
        class="notification-btn"
        :class="{ active: ui.notificationsEnabled }"
        :title="ui.notificationsEnabled ? t('notifications.enabled') : t('notifications.disabled')"
        @click="ui.toggleNotifications()"
      >
        <span v-if="ui.notificationsEnabled">&#128276;</span>
        <span v-else>&#128277;</span>
      </button>
      <button
        class="notification-btn tour-btn"
        :title="t('tour.startTutorial')"
        @click="startTour()"
      >
        &#127891;
      </button>
      <span class="header-user">{{ auth.user?.username }}</span>
      <BaseButton variant="ghost" size="sm" @click="logout">{{ t('common.logout') }}</BaseButton>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  height: var(--header-height);
  background: var(--color-bg-header);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: 0 1px 3px rgba(16, 25, 51, 0.04);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toggle-btn {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: var(--color-text-muted);
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.toggle-btn:hover {
  background: var(--color-border-light);
  color: var(--color-navy);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-user {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted);
}

.lang-switcher {
  display: flex;
  gap: 2px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 2px;
}

.lang-btn {
  padding: 2px 8px;
  border: none;
  background: none;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  cursor: pointer;
  border-radius: 3px;
  transition: all 0.15s;
}

.lang-btn:hover {
  color: var(--color-text);
  background: var(--color-border-light);
}

.lang-btn.active {
  background: var(--color-primary);
  color: white;
}

.notification-btn {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  color: var(--color-text-muted);
  transition: all 0.15s;
}

.notification-btn:hover {
  background: var(--color-border-light);
  color: var(--color-text);
}

.notification-btn.active {
  color: var(--color-primary);
  border-color: var(--color-primary);
}

@media (max-width: 768px) {
  .app-header {
    padding: 0 12px;
  }

  .header-right {
    gap: 8px;
  }

  .header-user {
    display: none;
  }

  .lang-btn {
    padding: 2px 5px;
    font-size: 10px;
  }
}
</style>
