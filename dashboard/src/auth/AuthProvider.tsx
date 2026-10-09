import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getCurrentUser, login as loginRequest, type AuthUser } from './api'
import { AuthContext } from './AuthContext'
import { clearAccessToken, getAccessToken, setAccessToken } from './storage'

export function AuthProvider({ children }: { children: ReactNode }) {
  const hasToken = Boolean(getAccessToken())
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(hasToken)

  useEffect(() => {
    if (!hasToken) {
      return
    }

    void getCurrentUser()
      .then((currentUser) => setUser(currentUser))
      .catch(() => {
        clearAccessToken()
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [hasToken])

  const login = useCallback(async (username: string, password: string) => {
    const response = await loginRequest(username, password)
    setAccessToken(response.access_token)
    setUser(await getCurrentUser())
  }, [])

  const logout = useCallback(() => {
    clearAccessToken()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, login, logout }),
    [loading, login, logout, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
