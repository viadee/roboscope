<script setup lang="ts">
/**
 * Story 4-2 + 4-5 — FirstLoginView / WelcomeCard.
 * Three sections. Amber left-accent on Section 1. No card borders.
 * Handles zero-teams and zero-repos empty states.
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth.store'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const teams = computed(() => auth.user?.teams ?? [])
const roleMap = computed(() => auth.user?.effective_roles_by_repo ?? {})
const name = computed(() => auth.user?.username ?? '')
const role = computed(() => auth.user?.role ?? 'viewer')

const hasTeams = computed(() => teams.value.length > 0)
const repoIds = computed(() => Object.keys(roleMap.value))
const hasRepos = computed(() => repoIds.value.length > 0)

const whyAccessKey = computed(() => {
  if (hasTeams.value) return 'viaTeam'
  if (hasRepos.value) return 'viaProject'
  return 'noAccess'
})

const firstTeamName = computed(() => teams.value[0]?.name ?? '')

async function dismissAndGo(path: string) {
  try {
    await auth.markFirstLoginComplete()
  } catch {
    // Fail open — continue the flow even if the PATCH failed.
  }
  router.push(path)
}
</script>

<template>
  <div class="welcome-wrapper">
    <!-- Section 1 — greeting + Why-You-Have-Access -->
    <section class="welcome-section welcome-section--primary" aria-labelledby="welcome-heading">
      <h1 id="welcome-heading" class="welcome-heading">
        {{ t('welcome.heading', { name }) }}
      </h1>
      <p class="welcome-subheading">{{ t('welcome.subheading') }}</p>

      <p v-if="whyAccessKey === 'viaTeam'" class="welcome-why">
        {{ t('welcome.whyAccess.viaTeam', { team: firstTeamName, role }) }}
      </p>
      <p v-else-if="whyAccessKey === 'viaProject'" class="welcome-why">
        {{ t('welcome.whyAccess.viaProject', { repo: repoIds[0], role }) }}
      </p>
      <p v-else class="welcome-why welcome-why--empty">
        {{ t('welcome.whyAccess.noAccess') }}
      </p>
    </section>

    <!-- Section 2 — primary CTA OR zero-repos empty state -->
    <section v-if="hasRepos" class="welcome-section">
      <button
        type="button"
        class="welcome-cta welcome-cta--primary"
        @click="dismissAndGo(`/explorer/${repoIds[0]}`)"
      >
        {{ t('welcome.cta.openRepo', { repo: repoIds[0] }) }}
      </button>
      <button
        type="button"
        class="welcome-cta welcome-cta--secondary"
        @click="dismissAndGo('/repos')"
      >
        {{ t('welcome.cta.browseTeams') }}
      </button>
    </section>
    <section v-else class="welcome-section welcome-section--empty">
      <p v-if="hasTeams">{{ t('welcome.whyAccess.viaTeam', { team: firstTeamName, role }) }}</p>
      <button
        type="button"
        class="welcome-cta welcome-cta--secondary"
        @click="dismissAndGo('/repos')"
      >
        {{ t('welcome.cta.browseTeams') }}
      </button>
    </section>

    <!-- Section 3 — tour teaser (de-emphasized) -->
    <section class="welcome-section welcome-section--tour">
      <button
        type="button"
        class="welcome-skip"
        @click="dismissAndGo('/dashboard')"
      >
        {{ t('welcome.cta.dismissTour') }}
      </button>
    </section>
  </div>
</template>

<style scoped>
.welcome-wrapper {
  max-width: 720px;
  margin: 2rem auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.welcome-section {
  padding: 1.25rem 0;
}

.welcome-section--primary {
  padding-left: 1rem;
  border-left: 4px solid var(--color-accent, #D4883E);
}

.welcome-section--tour {
  opacity: 0.7;
  font-size: 0.9rem;
}

.welcome-heading {
  margin: 0 0 0.25rem;
  font-size: 1.75rem;
}

.welcome-subheading {
  margin: 0 0 1rem;
  color: var(--color-text-secondary, #555);
}

.welcome-why {
  margin: 0.5rem 0;
}

.welcome-why--empty {
  color: var(--color-text-secondary, #555);
  font-style: italic;
}

.welcome-cta {
  margin: 0.25rem 0.5rem 0.25rem 0;
  padding: 0.6rem 1.2rem;
  border: 1px solid transparent;
  border-radius: 4px;
  font: inherit;
  cursor: pointer;
}

.welcome-cta--primary {
  background: var(--color-primary, #2D63B0);
  color: white;
}

.welcome-cta--secondary {
  background: transparent;
  border-color: var(--color-primary, #2D63B0);
  color: var(--color-primary, #2D63B0);
}

.welcome-skip {
  background: transparent;
  border: none;
  color: var(--color-text-secondary, #555);
  cursor: pointer;
  text-decoration: underline;
  font: inherit;
}
</style>
