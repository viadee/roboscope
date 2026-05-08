<!--
  TeamListView (Story 3-12).

  Admin list of all teams. Empty-state offers two equal-weight CTAs:
  [+ New Team] and [Import from IdP groups]. Once teams exist, renders
  a data-table with client-side search + sort and per-row actions.
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useTeamsStore } from '@/stores/teams.store'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import type { Team } from '@/types/domain.types'

const { t } = useI18n()
const router = useRouter()
const store = useTeamsStore()

const query = ref('')
const debouncedQuery = ref('')
const sortBy = ref<'name' | 'created_at'>('name')
const sortDir = ref<'asc' | 'desc'>('asc')

const showDelete = ref(false)
const pendingDelete = ref<Team | null>(null)
const deleteError = ref<string | null>(null)

let _searchTimer: ReturnType<typeof setTimeout> | null = null
function onSearch(v: string) {
  query.value = v
  if (_searchTimer) clearTimeout(_searchTimer)
  _searchTimer = setTimeout(() => {
    debouncedQuery.value = v.trim().toLowerCase()
  }, 300)
}

const hasTeams = computed(() => store.teams.length > 0)

const filteredTeams = computed(() => {
  const q = debouncedQuery.value
  const rows = q
    ? store.teams.filter((t) => t.name.toLowerCase().includes(q))
    : [...store.teams]
  const dir = sortDir.value === 'asc' ? 1 : -1
  rows.sort((a, b) => {
    if (sortBy.value === 'name') {
      return dir * a.name.localeCompare(b.name)
    }
    return dir * a.created_at.localeCompare(b.created_at)
  })
  return rows
})

function toggleSort(column: 'name' | 'created_at') {
  if (sortBy.value === column) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = column
    sortDir.value = 'asc'
  }
}

function goNew() {
  router.push('/admin/teams/new')
}

function goImport() {
  // Story 3-14 will introduce the dedicated import wizard route;
  // until it ships, the empty-state CTA points at the same "new"
  // route to avoid a dead link.
  router.push('/admin/teams/new')
}

function goDetail(team: Team) {
  router.push(`/admin/teams/${team.id}`)
}

function openDelete(team: Team) {
  pendingDelete.value = team
  deleteError.value = null
  showDelete.value = true
}

async function confirmDelete() {
  if (!pendingDelete.value) return
  try {
    await store.remove(pendingDelete.value.id)
    showDelete.value = false
    pendingDelete.value = null
  } catch (err) {
    deleteError.value = (err as Error).message || t('teams.list.deleteFailed')
  }
}

onMounted(async () => {
  await store.load()
})
</script>

<template>
  <div class="team-list-view">
    <header class="page-header">
      <h1>{{ t('teams.list.title') }}</h1>
      <p class="page-desc">{{ t('teams.list.description') }}</p>
    </header>

    <div v-if="store.loading && !hasTeams" class="loading">
      <BaseSpinner />
    </div>

    <div v-else-if="!hasTeams" class="empty-state" data-testid="empty-state">
      <h2>{{ t('teams.list.empty.heading') }}</h2>
      <p>{{ t('teams.list.empty.description') }}</p>
      <div class="empty-actions">
        <BaseButton variant="primary" size="lg" @click="goNew">
          {{ t('teams.list.actions.newTeam') }}
        </BaseButton>
        <BaseButton variant="primary" size="lg" @click="goImport">
          {{ t('teams.list.actions.importFromIdp') }}
        </BaseButton>
      </div>
    </div>

    <div v-else>
      <div class="toolbar">
        <input
          :value="query"
          type="search"
          class="search-input"
          :placeholder="t('teams.list.searchPlaceholder')"
          :aria-label="t('teams.list.searchPlaceholder')"
          data-testid="search-input"
          @input="onSearch(($event.target as HTMLInputElement).value)"
        />
        <div class="header-actions">
          <BaseButton variant="secondary" @click="goImport">
            {{ t('teams.list.actions.importFromIdp') }}
          </BaseButton>
          <BaseButton variant="primary" @click="goNew">
            {{ t('teams.list.actions.newTeam') }}
          </BaseButton>
        </div>
      </div>

      <table class="data-table">
        <thead>
          <tr>
            <th
              scope="col"
              class="sortable"
              @click="toggleSort('name')"
            >
              {{ t('teams.list.columns.name') }}
              <span v-if="sortBy === 'name'" aria-hidden="true">
                {{ sortDir === 'asc' ? '↑' : '↓' }}
              </span>
            </th>
            <th scope="col">{{ t('teams.list.columns.description') }}</th>
            <th
              scope="col"
              class="sortable"
              @click="toggleSort('created_at')"
            >
              {{ t('teams.list.columns.created') }}
              <span v-if="sortBy === 'created_at'" aria-hidden="true">
                {{ sortDir === 'asc' ? '↑' : '↓' }}
              </span>
            </th>
            <th scope="col" class="actions-col">
              {{ t('teams.list.columns.actions') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="team in filteredTeams"
            :key="team.id"
            class="team-row"
            :data-team-id="team.id"
          >
            <td class="team-name">{{ team.name }}</td>
            <td>{{ team.description || '—' }}</td>
            <td>{{ new Date(team.created_at).toLocaleDateString() }}</td>
            <td class="actions-col">
              <button
                type="button"
                class="action-link"
                data-testid="row-edit"
                @click="goDetail(team)"
              >
                {{ t('teams.list.actions.edit') }}
              </button>
              <button
                type="button"
                class="action-link danger"
                data-testid="row-delete"
                @click="openDelete(team)"
              >
                {{ t('teams.list.actions.delete') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <BaseModal
      v-if="showDelete && pendingDelete"
      v-model="showDelete"
      :title="t('teams.list.deleteModal.title')"
    >
      <p>
        {{ t('teams.list.deleteModal.confirm', { name: pendingDelete.name }) }}
      </p>
      <p v-if="deleteError" class="error-text">{{ deleteError }}</p>
      <template #footer>
        <BaseButton variant="secondary" @click="showDelete = false">
          {{ t('teams.list.deleteModal.cancel') }}
        </BaseButton>
        <BaseButton variant="danger" @click="confirmDelete">
          {{ t('teams.list.deleteModal.confirmButton') }}
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.team-list-view {
  padding: 24px;
}
.page-header {
  margin-bottom: 24px;
}
.page-header h1 {
  margin: 0 0 6px;
  color: var(--color-navy);
}
.page-desc {
  margin: 0;
  color: var(--color-text-muted);
}
.loading {
  display: flex;
  justify-content: center;
  padding: 48px;
}
.empty-state {
  text-align: center;
  padding: 64px 24px;
  background: white;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-lg);
}
.empty-state h2 {
  margin: 0 0 12px;
  color: var(--color-navy);
}
.empty-actions {
  margin-top: 24px;
  display: flex;
  gap: 12px;
  justify-content: center;
}
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}
.search-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 14px;
}
.search-input:focus {
  outline: 2px solid var(--color-primary);
  outline-offset: -1px;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.data-table th {
  background: var(--color-bg);
  padding: 12px 16px;
  text-align: left;
  font-weight: 600;
  color: var(--color-text-muted);
  border-bottom: 1px solid var(--color-border);
}
.data-table th.sortable {
  cursor: pointer;
  user-select: none;
}
.data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}
.team-row:hover {
  background: var(--color-bg);
}
.team-name {
  font-weight: 500;
  color: var(--color-navy);
}
.actions-col {
  width: 160px;
  text-align: right;
}
.action-link {
  background: none;
  border: none;
  padding: 4px 8px;
  color: var(--color-primary);
  cursor: pointer;
  font-family: inherit;
  font-size: 13px;
  text-decoration: underline;
}
.action-link.danger {
  color: var(--color-danger);
}
.error-text {
  color: var(--color-danger);
  margin: 8px 0 0;
}
</style>
