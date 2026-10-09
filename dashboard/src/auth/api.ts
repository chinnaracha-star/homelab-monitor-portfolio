import { apiClient } from '../api/client'

export interface AuthUser {
  id: string
  username: string
  full_name: string
  role: string
  is_active: boolean
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
}

function apiUrl(path: string): string {
  const base = String(import.meta.env.VITE_API_BASE_URL).replace(/\/+$/, '')
  return `${base}${path.startsWith('/') ? path : `/${path}`}`
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  let response: Response
  try {
    response = await fetch(apiUrl('/auth/login'), {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
      cache: 'no-store',
      credentials: 'same-origin',
    })
  } catch {
    throw new Error('Network Error')
  }

  const payload = (await response.json().catch(() => null)) as
    | (LoginResponse & { error?: { message?: string } })
    | null
  if (!response.ok) {
    throw new Error(payload?.error?.message || 'Login failed')
  }
  if (!payload || typeof payload.access_token !== 'string') {
    throw new Error('Login failed')
  }
  return payload
}

export async function getCurrentUser(): Promise<AuthUser> {
  const response = await apiClient.get<AuthUser>('/auth/me')
  return response.data
}
