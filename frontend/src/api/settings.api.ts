import apiClient from './client'
import type { SettingUpdateRequest } from '@/types/api.types'
import type { AppSetting } from '@/types/domain.types'

export async function getSettings(category?: string): Promise<AppSetting[]> {
  const response = await apiClient.get<AppSetting[]>('/settings', {
    params: category ? { category } : {},
  })
  return response.data
}

export async function updateSettings(settings: SettingUpdateRequest[]): Promise<AppSetting[]> {
  const response = await apiClient.patch<AppSetting[]>('/settings', { settings })
  return response.data
}
