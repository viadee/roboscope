import apiClient from './client'
import type {
  GroupMapping,
  GroupMappingCreate,
  Team,
  TeamCreate,
  TeamDetail,
  TeamMemberDetail,
  TeamUpdate,
} from '@/types/domain.types'

const BASE = '/teams'
const GROUP_MAPPINGS_BASE = '/group-mappings'

export async function listTeams(): Promise<Team[]> {
  const resp = await apiClient.get<Team[]>(BASE)
  return resp.data
}

export async function getTeam(id: number): Promise<TeamDetail> {
  const resp = await apiClient.get<TeamDetail>(`${BASE}/${id}`)
  return resp.data
}

export async function createTeam(data: TeamCreate): Promise<Team> {
  const resp = await apiClient.post<Team>(BASE, data)
  return resp.data
}

export async function updateTeam(id: number, data: TeamUpdate): Promise<Team> {
  const resp = await apiClient.put<Team>(`${BASE}/${id}`, data)
  return resp.data
}

export async function deleteTeam(id: number): Promise<void> {
  await apiClient.delete(`${BASE}/${id}`)
}

// --- Members ---

export async function addMember(
  teamId: number,
  data: { user_id: number; role: string },
): Promise<TeamMemberDetail> {
  const resp = await apiClient.post<TeamMemberDetail>(
    `${BASE}/${teamId}/members`,
    data,
  )
  return resp.data
}

export async function removeMember(
  teamId: number,
  memberId: number,
): Promise<void> {
  await apiClient.delete(`${BASE}/${teamId}/members/${memberId}`)
}

// --- Group mappings ---

export async function listGroupMappings(
  teamId: number,
): Promise<GroupMapping[]> {
  const resp = await apiClient.get<GroupMapping[]>(
    `${BASE}/${teamId}/group-mappings`,
  )
  return resp.data
}

export async function createGroupMapping(
  teamId: number,
  data: GroupMappingCreate,
): Promise<GroupMapping> {
  const resp = await apiClient.post<GroupMapping>(
    `${BASE}/${teamId}/group-mappings`,
    data,
  )
  return resp.data
}

export async function updateGroupMapping(
  mappingId: number,
  data: { role: string },
): Promise<GroupMapping> {
  const resp = await apiClient.patch<GroupMapping>(
    `${GROUP_MAPPINGS_BASE}/${mappingId}`,
    data,
  )
  return resp.data
}

export async function deleteGroupMapping(mappingId: number): Promise<void> {
  await apiClient.delete(`${GROUP_MAPPINGS_BASE}/${mappingId}`)
}

export async function listAvailableGroups(idpId: number): Promise<string[]> {
  const resp = await apiClient.get<string[]>(
    `/auth/idp-providers/${idpId}/available-groups`,
  )
  return resp.data
}
