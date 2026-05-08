import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  addMember as apiAddMember,
  createGroupMapping as apiCreateMapping,
  createTeam as apiCreate,
  deleteGroupMapping as apiDeleteMapping,
  deleteTeam as apiDelete,
  getTeam as apiGetDetail,
  listGroupMappings as apiListMappings,
  listTeams,
  removeMember as apiRemoveMember,
  updateGroupMapping as apiUpdateMapping,
  updateTeam as apiUpdate,
} from '@/api/teams.api'
import type {
  GroupMapping,
  GroupMappingCreate,
  Team,
  TeamCreate,
  TeamDetail,
  TeamUpdate,
} from '@/types/domain.types'

export const useTeamsStore = defineStore('teams', () => {
  const teams = ref<Team[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      teams.value = await listTeams()
    } catch (err) {
      error.value = (err as Error).message || 'load failed'
    } finally {
      loading.value = false
    }
  }

  async function create(data: TeamCreate): Promise<Team> {
    const created = await apiCreate(data)
    teams.value = [...teams.value, created]
    return created
  }

  async function update(id: number, data: TeamUpdate): Promise<Team> {
    const updated = await apiUpdate(id, data)
    teams.value = teams.value.map((t) => (t.id === id ? updated : t))
    return updated
  }

  async function remove(id: number): Promise<void> {
    await apiDelete(id)
    teams.value = teams.value.filter((t) => t.id !== id)
  }

  // --- Detail view (Story 3-13) ---

  const detail = ref<TeamDetail | null>(null)
  const groupMappings = ref<GroupMapping[]>([])

  async function loadDetail(id: number): Promise<void> {
    const [team, mappings] = await Promise.all([
      apiGetDetail(id),
      apiListMappings(id),
    ])
    detail.value = team
    groupMappings.value = mappings
  }

  async function addMember(
    teamId: number,
    userId: number,
    role: string,
  ): Promise<void> {
    await apiAddMember(teamId, { user_id: userId, role })
    await loadDetail(teamId)
  }

  async function removeMember(teamId: number, memberId: number): Promise<void> {
    await apiRemoveMember(teamId, memberId)
    if (detail.value) {
      detail.value = {
        ...detail.value,
        members: detail.value.members.filter((m) => m.id !== memberId),
      }
    }
  }

  async function addGroupMapping(
    teamId: number,
    data: GroupMappingCreate,
  ): Promise<GroupMapping> {
    const mapping = await apiCreateMapping(teamId, data)
    groupMappings.value = [...groupMappings.value, mapping]
    return mapping
  }

  async function updateGroupMappingRole(
    mappingId: number,
    role: string,
  ): Promise<GroupMapping> {
    const updated = await apiUpdateMapping(mappingId, { role })
    groupMappings.value = groupMappings.value.map((m) =>
      m.id === mappingId ? updated : m,
    )
    return updated
  }

  async function removeGroupMapping(mappingId: number): Promise<void> {
    await apiDeleteMapping(mappingId)
    groupMappings.value = groupMappings.value.filter((m) => m.id !== mappingId)
  }

  return {
    teams,
    loading,
    error,
    detail,
    groupMappings,
    load,
    create,
    update,
    remove,
    loadDetail,
    addMember,
    removeMember,
    addGroupMapping,
    updateGroupMappingRole,
    removeGroupMapping,
  }
})
