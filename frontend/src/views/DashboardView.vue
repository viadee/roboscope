<script setup lang="ts">
/**
 * Dashboard — landing card grid pointing into every navigable section
 * of the app, plus a rotating tip-of-the-day card.
 *
 * The card grid replaces the previous KPIs / recent-runs / repo-grid
 * mix: each card is a clickable shortcut into one of the navigation
 * destinations (Repos, Explorer, Runs, Stats, …) so a fresh user can
 * navigate the whole product without scanning the sidebar.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.store'
import { todaysTipKey } from '@/utils/dailyTip'

const router = useRouter()
const auth = useAuthStore()
const { t } = useI18n()

interface DashboardCard {
  title: string
  description: string
  icon: string
  to: string
  /** Some cards (admin sections, recorder) only show when the user
   *  has the right role / the feature is enabled. */
  visible: boolean
  /** Tip card uses a tinted variant so it reads as informational
   *  rather than a navigation target. Navigation cards all share
   *  the default surface. */
  variant?: 'default' | 'tip'
}

const cards = computed<DashboardCard[]>(() => [
  {
    title: t('nav.repos'),
    description: t('dashboard.cards.reposDesc'),
    icon: '📁',
    to: '/repos',
    visible: true,
  },
  {
    title: t('nav.explorer'),
    description: t('dashboard.cards.explorerDesc'),
    icon: '🔍',
    to: '/explorer',
    visible: true,
  },
  {
    title: t('nav.execution'),
    description: t('dashboard.cards.runsDesc'),
    icon: '▶',
    to: '/runs',
    visible: true,
  },
  {
    title: t('nav.stats'),
    description: t('dashboard.cards.statsDesc'),
    icon: '📈',
    to: '/stats',
    visible: true,
  },
  {
    title: t('nav.recorder'),
    description: t('dashboard.cards.recorderDesc'),
    icon: '⏺',
    to: '/recordings/new',
    visible: auth.hasMinRole('editor'),
  },
  {
    title: t('nav.environments'),
    description: t('dashboard.cards.environmentsDesc'),
    icon: '⚙',
    to: '/environments',
    visible: auth.hasMinRole('editor'),
  },
  {
    title: t('nav.docs'),
    description: t('dashboard.cards.docsDesc'),
    icon: '📖',
    to: '/docs',
    visible: true,
  },
  {
    title: t('nav.settings'),
    description: t('dashboard.cards.settingsDesc'),
    icon: '🔧',
    to: '/settings',
    visible: auth.hasMinRole('admin'),
  },
])

const visibleCards = computed(() => cards.value.filter((c) => c.visible))

const tipKey = todaysTipKey()

function go(to: string) {
  router.push(to)
}
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('dashboard.title') }}</h1>
      <p class="text-muted">{{ t('dashboard.subtitle') }}</p>
    </div>

    <div class="dashboard-grid">
      <button
        v-for="card in visibleCards"
        :key="card.to"
        type="button"
        class="dashboard-card"
        :class="['dashboard-card--' + (card.variant ?? 'default')]"
        @click="go(card.to)"
      >
        <div class="dashboard-card__icon" aria-hidden="true">{{ card.icon }}</div>
        <div class="dashboard-card__title">{{ card.title }}</div>
        <p class="dashboard-card__desc">{{ card.description }}</p>
        <div class="dashboard-card__chevron" aria-hidden="true">→</div>
      </button>

      <!-- Tip-of-the-day card. Static (no click navigation) — purely
           informational; a fresh tip surfaces every calendar day. -->
      <div class="dashboard-card dashboard-card--tip" data-testid="tip-of-the-day">
        <div class="dashboard-card__icon" aria-hidden="true">💡</div>
        <div class="dashboard-card__title">{{ t('tips.label') }}</div>
        <p class="dashboard-card__desc">{{ t(tipKey) }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header h1 {
  margin-bottom: 4px;
}
.page-header p {
  margin: 0 0 24px;
  font-size: 14px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.dashboard-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 22px 22px 50px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 12px;
  background: var(--color-bg-card, #fff);
  text-align: left;
  font: inherit;
  color: inherit;
  cursor: pointer;
  transition: transform 0.12s, box-shadow 0.15s, border-color 0.15s;
  min-height: 160px;
}
.dashboard-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(16, 25, 51, 0.10);
  border-color: var(--color-primary, #2D63B0);
}
.dashboard-card:focus-visible {
  outline: 3px solid var(--color-primary, #2D63B0);
  outline-offset: 3px;
}

.dashboard-card__icon {
  font-size: 28px;
  line-height: 1;
}
.dashboard-card__title {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-navy, #1A2D50);
}
.dashboard-card__desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.45;
  color: var(--color-text-muted, #5A6380);
}
.dashboard-card__chevron {
  position: absolute;
  right: 18px;
  bottom: 14px;
  font-size: 18px;
  color: var(--color-primary, #2D63B0);
  opacity: 0.5;
  transition: opacity 0.15s, transform 0.15s;
}
.dashboard-card:hover .dashboard-card__chevron {
  opacity: 1;
  transform: translateX(3px);
}

/* Tip-of-the-day — non-clickable, slightly different surface so it
   reads as informational rather than a navigation target. */
.dashboard-card--tip {
  cursor: default;
  background: color-mix(in srgb, var(--color-primary, #2D63B0) 6%, var(--color-bg-card, #fff));
  border-color: color-mix(in srgb, var(--color-primary, #2D63B0) 30%, var(--color-border, #e2e8f0));
  padding-bottom: 22px;
}
.dashboard-card--tip:hover {
  transform: none;
  box-shadow: none;
  border-color: color-mix(in srgb, var(--color-primary, #2D63B0) 30%, var(--color-border, #e2e8f0));
}
</style>
