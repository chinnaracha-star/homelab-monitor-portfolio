import { useCallback } from 'react'
import { useAuth } from './AuthContext'
import { can as roleCan, type Permission } from './permissions'

export function useCan() {
  const { user } = useAuth()

  return useCallback(
    (permission: Permission) => roleCan(user?.role, permission),
    [user],
  )
}
