import axios from 'axios'

interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
  }
}

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    return (
      error.response?.data?.error?.message ??
      error.message ??
      'The API returned an unexpected response.'
    )
  }

  return error instanceof Error ? error.message : 'An unexpected error occurred.'
}

export function isApiErrorCode(error: unknown, code: string): boolean {
  return (
    axios.isAxiosError<ApiErrorBody>(error) && error.response?.data?.error?.code === code
  )
}

export function isNotFound(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 404
}
