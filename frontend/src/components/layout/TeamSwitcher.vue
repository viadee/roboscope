<script setup lang="ts">
/**
 * Story 4-4: TeamSwitcher — header chip that shows the active team and
 * lets multi-team users switch context. Single-team users see a static
 * label (no dropdown).
 *
 * The "active team" is persisted client-side in localStorage as
 * `roboscope.active_team_id`. Future server-side preference field (see
 * UX spec) can replace the localStorage layer without changing the API
 * of this component.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth.store'

const STORAGE_KEY = 'roboscope.active_team_id'

const auth = useAuthStore()

const teams = computed(() => auth.user?.teams ?? [])
const isOpen = ref(false)
const activeTeamId = ref<number | null>(null)

function initialActiveTeam(): number | null {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) {
    const parsed = Number(stored)
    if (!Number.isNaN(parsed) && teams.value.some((t) => t.id === parsed)) {
      return parsed
    }
  }
  return auth.user?.default_team_id ?? teams.value[0]?.id ?? null
}

onMounted(() => {
  activeTeamId.value = initialActiveTeam()
})

watch(teams, () => {
  if (activeTeamId.value && !teams.value.some((t) => t.id === activeTeamId.value)) {
    activeTeamId.value = initialActiveTeam()
  }
})

const activeTeam = computed(() =>
  teams.value.find((t) => t.id === activeTeamId.value) ?? null,
)

function selectTeam(id: number) {
  activeTeamId.value = id
  localStorage.setItem(STORAGE_KEY, String(id))
  isOpen.value = false
  // Re-render the current route so downstream components re-read the
  // active team. vue-router handles in-place reload cleanly.
  window.dispatchEvent(new CustomEvent('roboscope:active-team-changed', { detail: { teamId: id } }))
}

function onKeyDown(event: KeyboardEvent) {
  if (!isOpen.value) return
  const ids = teams.value.map((t) => t.id)
  const current = activeTeamId.value
  const idx = current !== null ? ids.indexOf(current) : -1
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    const next = ids[(idx + 1) % ids.length]
    activeTeamId.value = next
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    const prev = ids[(idx - 1 + ids.length) % ids.length]
    activeTeamId.value = prev
  } else if (event.key === 'Enter' && activeTeamId.value !== null) {
    selectTeam(activeTeamId.value)
  } else if (event.key === 'Escape') {
    isOpen.value = false
  }
}
</script>

<template>
  <!-- Zero teams: render nothing -->
  <template v-if="teams.length === 0" />

  <!-- Single team: static label -->
  <span v-else-if="teams.length === 1" class="team-switcher team-switcher--single">
    {{ activeTeam?.name ?? teams[0].name }}
  </span>

  <!-- Multi-team: chip dropdown -->
  <div v-else class="team-switcher" @keydown="onKeyDown">
    <button
      type="button"
      class="team-switcher__chip"
      :aria-expanded="isOpen"
      aria-haspopup="listbox"
      @click="isOpen = !isOpen"
    >
      <span class="team-switcher__name">{{ activeTeam?.name ?? '—' }}</span>
      <span class="team-switcher__chevron" aria-hidden="true">▾</span>
    </button>
    <ul v-if="isOpen" class="team-switcher__menu" role="listbox">
      <li
        v-for="t in teams"
        :key="t.id"
        role="option"
        :aria-selected="t.id === activeTeamId"
        :class="['team-switcher__item', { 'is-active': t.id === activeTeamId }]"
        @click="selectTeam(t.id)"
      >
        {{ t.name }}
      </li>
    </ul>
  </div>
</template>

<style scoped>
.team-switcher {
  position: relative;
  display: inline-block;
  font-size: 0.9rem;
}

.team-switcher--single {
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  background: rgba(59, 125, 216, 0.1);
  color: var(--color-primary, #3B7DD8);
}

.team-switcher__chip {
  padding: 0.25rem 0.6rem;
  border: 1px solid var(--color-primary, #3B7DD8);
  border-radius: 999px;
  background: transparent;
  color: var(--color-primary, #3B7DD8);
  font: inherit;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.team-switcher__menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 160px;
  padding: 0.25rem 0;
  margin: 0;
  list-style: none;
  background: var(--color-surface, white);
  border: 1px solid var(--color-border, #ddd);
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  z-index: 100;
}

.team-switcher__item {
  padding: 0.4rem 0.75rem;
  cursor: pointer;
}

.team-switcher__item:hover,
.team-switcher__item.is-active {
  background: rgba(59, 125, 216, 0.1);
}
</style>
