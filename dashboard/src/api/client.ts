import axios from 'axios'
import { clearAccessToken, getAccessToken } from '../auth/storage'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL

if (!apiBaseUrl) {
  throw new Error('VITE_API_BASE_URL is required')
}

export const apiClient = axios.create({
  baseURL: apiBaseUrl.replace(/\/+$/, ''),
  headers: {
    Accept: 'application/json',
  },
  timeout: 10_000,
})

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const requestUrl = String(error.config?.url ?? '')
      if (!requestUrl.includes('/auth/login')) {
        clearAccessToken()
        if (window.location.pathname !== '/login') {
          window.location.assign('/login')
        }
      }
    }
    return Promise.reject(error)
  },
)
