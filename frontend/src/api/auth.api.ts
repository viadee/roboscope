import apiClient from './client'
import type { LoginRequest } from '@/types/api.types'
import type { TokenResponse, User } from '@/types/domain.types'

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/auth/login', data)
  return response.data
}

export async function refreshToken(refresh_token: string): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/auth/refresh', { refresh_token })
  return response.data
}

export async function getMe(): Promise<User> {
  const response = await apiClient.get<User>('/auth/me')
  return response.data
}

export async function patchFirstLoginComplete(value: boolean): Promise<User> {
  const response = await apiClient.patch<User>('/auth/me/first-login-complete', { value })
  return response.data
}

/** Story SECURITY-1 — rotate the current user's password. 204 on success. */
export async function changePassword(data: {
  current_password: string
  new_password: string
}): Promise<void> {
  await apiClient.post('/auth/change-password', data)
}

export async function getUsers(): Promise<User[]> {
  const response = await apiClient.get<User[]>('/auth/users')
  return response.data
}

export async function createUser(data: { email: string; username: string; password: string; role: string }): Promise<User> {
  const response = await apiClient.post<User>('/auth/users', data)
  return response.data
}

export async function updateUser(id: number, data: Partial<User>): Promise<User> {
  const response = await apiClient.patch<User>(`/auth/users/${id}`, data)
  return response.data
}

export async function deleteUser(id: number): Promise<void> {
  await apiClient.delete(`/auth/users/${id}`)
}
