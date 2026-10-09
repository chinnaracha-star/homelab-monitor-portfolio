import { useCallback, useState } from 'react'

export function useLocalStorage(key: string, fallback: string): [string, (value: string) => void] {
  const [value, setValue] = useState(() => {
    try {
      return window.localStorage.getItem(key) ?? fallback
    } catch {
      return fallback
    }
  })

  const update = useCallback(
    (next: string) => {
      setValue(next)
      try {
        window.localStorage.setItem(key, next)
      } catch {
        // Ignore storage failures in private browsing.
      }
    },
    [key],
  )

  return [value, update]
}
