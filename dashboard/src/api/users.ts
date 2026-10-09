import { apiClient } from './client'
import type { ManagedUser, UserCreatePayload, UserUpdatePayload } from '../types/users'

export async function listUsers(): Promise<ManagedUser[]> {
  const response = await apiClient.get<ManagedUser[]>('/users')
  return response.data
}

export async function createUser(payload: UserCreatePayload): Promise<ManagedUser> {
  const response = await apiClient.post<ManagedUser>('/users', payload)
  return response.data
}

export async function updateUser(userId: string, payload: UserUpdatePayload): Promise<ManagedUser> {
  const response = await apiClient.put<ManagedUser>(
    `/users/${encodeURIComponent(userId)}`,
    payload,
  )
  return response.data
}

export async function resetUserPassword(userId: string, password: string): Promise<ManagedUser> {
  const response = await apiClient.patch<ManagedUser>(
    `/users/${encodeURIComponent(userId)}/password`,
    { password },
  )
  return response.data
}

export async function updateUserStatus(userId: string, isActive: boolean): Promise<ManagedUser> {
  const response = await apiClient.patch<ManagedUser>(
    `/users/${encodeURIComponent(userId)}/status`,
    { is_active: isActive },
  )
  return response.data
}

export async function deleteUser(userId: string): Promise<void> {
  await apiClient.delete(`/users/${encodeURIComponent(userId)}`)
}
