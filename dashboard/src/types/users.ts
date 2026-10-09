export type UserRole = 'admin' | 'operator' | 'viewer'

export interface ManagedUser {
  id: string
  username: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface UserCreatePayload {
  username: string
  full_name: string
  password: string
  role: UserRole
  is_active: boolean
}

export interface UserUpdatePayload {
  full_name: string
  role: UserRole
  is_active: boolean
}
