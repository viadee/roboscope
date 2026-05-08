<!--
  TeamDetailView (Story 3-13).

  Serves two routes:
    /admin/teams/new      → minimal create form (no tabs)
    /admin/teams/:id      → team header + 3 tabs (Members / Group Mappings / Repos)

  Story 3-14 will replace the read-only role span on group-mapping rows
  with an inline edit component. Until then this view shows the mapping
  role as plain text.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useTeamsStore } from '@/stores/teams.store'
import { listAvailableGroups } from '@/api/teams.api'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import GroupMappingRow from '@/components/teams/GroupMappingRow.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const store = useTeamsStore()

type TabKey = 'members' | 'mappings' | 'repos'
const TABS: TabKey[] = ['members', 'mappings', 'repos']

const activeTab = ref<TabKey>('members')
const loading = ref(false)
const createMode = computed(() => route.params.id === 'new')
const teamIdParam = computed<number | null>(() => {
  const raw = route.params.id
  if (!raw || raw === 'new') return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
})

// --- New-team form ---
const newTeamName = ref('')
const newTeamDescription = ref('')
const newTeamError = ref<string | null>(null)

async function submitNewTeam() {
  newTeamError.value = null
  if (!newTeamName.value.trim()) {
    newTeamError.value = t('teams.detail.new.nameRequired')
    return
  }
  try {
    const team = await store.create({
      name: newTeamName.value.trim(),
      description: newTeamDescription.value.trim() || null,
    })
    router.push(`/admin/teams/${team.id}`)
  } catch (err: unknown) {
    newTeamError.value =
      (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      t('teams.detail.new.createFailed')
  }
}

// --- Members tab state ---
const addMemberUserId = ref('')
const addMemberRole = ref('viewer')
const addMemberError = ref<string | null>(null)

async function submitAddMember() {
  if (!teamIdParam.value) return
  addMemberError.value = null
  const uid = Number(addMemberUserId.value)
  if (!Number.isFinite(uid) || uid <= 0) {
    addMemberError.value = t('teams.detail.members.invalidUserId')
    return
  }
  try {
    await store.addMember(teamIdParam.value, uid, addMemberRole.value)
    addMemberUserId.value = ''
  } catch (err: unknown) {
    addMemberError.value =
      (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      t('teams.detail.members.addFailed')
  }
}

async function removeMember(memberId: number) {
  if (!teamIdParam.value) return
  await store.removeMember(teamIdParam.value, memberId)
}

// --- Group mappings tab state ---
const mappingIdpId = ref('')
const mappingGroup = ref('')
const mappingRole = ref('viewer')
const mappingError = ref<string | null>(null)
const availableGroups = ref<string[]>([])

async function refreshAvailableGroups() {
  const id = Number(mappingIdpId.value)
  if (!Number.isFinite(id) || id <= 0) {
    availableGroups.value = []
    return
  }
  try {
    availableGroups.value = await listAvailableGroups(id)
  } catch {
    availableGroups.value = []
  }
}

watch(mappingIdpId, refreshAvailableGroups)

async function submitAddMapping() {
  if (!teamIdParam.value) return
  mappingError.value = null
  const idpId = Number(mappingIdpId.value)
  if (!Number.isFinite(idpId) || idpId <= 0) {
    mappingError.value = t('teams.detail.mappings.invalidIdpId')
    return
  }
  if (!mappingGroup.value.trim()) {
    mappingError.value = t('teams.detail.mappings.groupRequired')
    return
  }
  try {
    await store.addGroupMapping(teamIdParam.value, {
      idp_id: idpId,
      group_name: mappingGroup.value.trim(),
      role: mappingRole.value,
    })
    mappingGroup.value = ''
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } })
      ?.response?.data?.detail
    if (detail === 'group_mapping.duplicate') {
      mappingError.value = t('teams.detail.mappings.duplicate')
    } else {
      mappingError.value = detail || t('teams.detail.mappings.addFailed')
    }
  }
}

async function removeMapping(mappingId: number) {
  await store.removeGroupMapping(mappingId)
}

async function onMappingRoleUpdate(mappingId: number, role: string) {
  await store.updateGroupMappingRole(mappingId, role)
}

// --- Keyboard nav for tabs ---
function onTabKeydown(ev: KeyboardEvent) {
  const idx = TABS.indexOf(activeTab.value)
  if (ev.key === 'ArrowRight') {
    ev.preventDefault()
    activeTab.value = TABS[(idx + 1) % TABS.length]
  } else if (ev.key === 'ArrowLeft') {
    ev.preventDefault()
    activeTab.value = TABS[(idx - 1 + TABS.length) % TABS.length]
  }
}

// --- Load ---
async function load() {
  if (!teamIdParam.value) return
  loading.value = true
  try {
    await store.loadDetail(teamIdParam.value)
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => route.params.id, load)
</script>

<template>
  <div class="team-detail-view">
    <!-- Create mode -->
    <div v-if="createMode" class="create-form">
      <h1>{{ t('teams.detail.new.title') }}</h1>
      <form @submit.prevent="submitNewTeam">
        <div class="form-group">
          <label>{{ t('teams.detail.new.nameLabel') }}</label>
          <input
            v-model="newTeamName"
            type="text"
            class="form-input"
            data-testid="new-team-name"
            required
          />
        </div>
        <div class="form-group">
          <label>{{ t('teams.detail.new.descriptionLabel') }}</label>
          <input
            v-model="newTeamDescription"
            type="text"
            class="form-input"
            data-testid="new-team-description"
          />
        </div>
        <p v-if="newTeamError" class="error-text">{{ newTeamError }}</p>
        <BaseButton type="submit" variant="primary" size="lg">
          {{ t('teams.detail.new.submit') }}
        </BaseButton>
      </form>
    </div>

    <!-- Detail mode -->
    <template v-else>
      <div v-if="loading" class="loading">
        <BaseSpinner />
      </div>
      <template v-else-if="store.detail">
        <header class="page-header">
          <h1>{{ store.detail.name }}</h1>
          <p v-if="store.detail.description" class="page-desc">
            {{ store.detail.description }}
          </p>
        </header>

        <div
          role="tablist"
          class="tablist"
          data-testid="tablist"
          @keydown="onTabKeydown"
        >
          <button
            v-for="key in TABS"
            :key="key"
            type="button"
            role="tab"
            class="tab"
            :class="{ active: activeTab === key }"
            :aria-selected="activeTab === key"
            :tabindex="activeTab === key ? 0 : -1"
            :data-testid="`tab-${key}`"
            @click="activeTab = key"
          >
            {{ t(`teams.detail.tabs.${key}`) }}
          </button>
        </div>

        <!-- Members tab -->
        <section
          v-show="activeTab === 'members'"
          role="tabpanel"
          class="tab-panel"
        >
          <div
            v-if="store.detail.members.length === 0"
            class="empty-inline"
            data-testid="members-empty"
          >
            {{ t('teams.detail.members.empty') }}
          </div>
          <ul v-else class="member-list" data-testid="member-list">
            <li
              v-for="m in store.detail.members"
              :key="m.id"
              class="member-row"
            >
              <span class="member-email">{{ m.email }}</span>
              <span class="member-role">{{ m.role }}</span>
              <span class="member-source">{{ m.source }}</span>
              <button
                type="button"
                class="action-link danger"
                data-testid="member-delete"
                @click="removeMember(m.id)"
              >
                {{ t('teams.detail.members.remove') }}
              </button>
            </li>
          </ul>
          <form class="inline-form" @submit.prevent="submitAddMember">
            <input
              v-model="addMemberUserId"
              type="number"
              class="form-input"
              :placeholder="t('teams.detail.members.userIdPlaceholder')"
              data-testid="add-member-user-id"
            />
            <select
              v-model="addMemberRole"
              class="form-input"
              data-testid="add-member-role"
            >
              <option value="viewer">viewer</option>
              <option value="runner">runner</option>
              <option value="editor">editor</option>
              <option value="admin">admin</option>
            </select>
            <BaseButton type="submit" variant="primary">
              {{ t('teams.detail.members.add') }}
            </BaseButton>
          </form>
          <p v-if="addMemberError" class="error-text">{{ addMemberError }}</p>
        </section>

        <!-- Group mappings tab -->
        <section
          v-show="activeTab === 'mappings'"
          role="tabpanel"
          class="tab-panel"
        >
          <div
            v-if="store.groupMappings.length === 0"
            class="empty-inline"
            data-testid="mappings-empty"
          >
            {{ t('teams.detail.mappings.empty') }}
          </div>
          <ul v-else class="mapping-list" data-testid="mapping-list">
            <GroupMappingRow
              v-for="m in store.groupMappings"
              :key="m.id"
              :mapping="m"
              @update-role="onMappingRoleUpdate"
              @delete="removeMapping"
            />
          </ul>
          <form class="inline-form" @submit.prevent="submitAddMapping">
            <input
              v-model="mappingIdpId"
              type="number"
              class="form-input"
              :placeholder="t('teams.detail.mappings.idpIdPlaceholder')"
              data-testid="mapping-idp-id"
            />
            <input
              v-model="mappingGroup"
              :list="availableGroups.length ? 'available-groups-datalist' : undefined"
              type="text"
              class="form-input"
              :placeholder="t('teams.detail.mappings.groupPlaceholder')"
              data-testid="mapping-group"
            />
            <datalist
              v-if="availableGroups.length"
              id="available-groups-datalist"
            >
              <option
                v-for="g in availableGroups"
                :key="g"
                :value="g"
              />
            </datalist>
            <select
              v-model="mappingRole"
              class="form-input"
              data-testid="mapping-role"
            >
              <option value="viewer">viewer</option>
              <option value="runner">runner</option>
              <option value="editor">editor</option>
              <option value="admin">admin</option>
            </select>
            <BaseButton type="submit" variant="primary">
              {{ t('teams.detail.mappings.add') }}
            </BaseButton>
          </form>
          <p v-if="mappingError" class="error-text">{{ mappingError }}</p>
        </section>

        <!-- Repositories tab -->
        <section
          v-show="activeTab === 'repos'"
          role="tabpanel"
          class="tab-panel"
        >
          <div class="info-note" data-testid="repos-note">
            {{ t('teams.detail.repos.note') }}
          </div>
        </section>
      </template>
    </template>
  </div>
</template>

<style scoped>
.team-detail-view {
  padding: 24px;
}
.create-form {
  max-width: 480px;
}
.create-form h1,
.page-header h1 {
  margin: 0 0 12px;
  color: var(--color-navy);
}
.page-desc {
  color: var(--color-text-muted);
  margin: 0 0 24px;
}
.form-group {
  margin-bottom: 16px;
}
.form-group label {
  display: block;
  font-weight: 500;
  margin-bottom: 6px;
}
.form-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 14px;
}
.tablist {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid var(--color-border);
  margin-bottom: 20px;
}
.tab {
  padding: 10px 18px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  color: var(--color-text-muted);
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
}
.tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}
.tab-panel {
  min-height: 200px;
  background: white;
  border-radius: var(--radius-lg);
  padding: 20px;
}
.empty-inline {
  text-align: center;
  padding: 32px;
  color: var(--color-text-muted);
}
.member-list,
.mapping-list {
  list-style: none;
  padding: 0;
  margin: 0 0 16px;
}
.member-row,
.mapping-row {
  display: grid;
  grid-template-columns: 1fr 100px 100px auto;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border);
  align-items: center;
}
.member-email,
.mapping-group {
  font-weight: 500;
}
.member-role,
.mapping-role,
.member-source {
  font-size: 13px;
  color: var(--color-text-muted);
}
.inline-form {
  display: flex;
  gap: 8px;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}
.inline-form .form-input {
  width: auto;
  flex: 1;
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
.info-note {
  padding: 20px;
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
}
.error-text {
  color: var(--color-danger);
  margin-top: 8px;
}
.loading {
  display: flex;
  justify-content: center;
  padding: 48px;
}
</style>
