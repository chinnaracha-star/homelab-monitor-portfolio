import { Outlet } from 'react-router-dom'
import { ForbiddenPage } from '../pages/ForbiddenPage'
import { useCan } from './useCan'
import type { Permission } from './permissions'

export function PermissionRoute({ permission }: { permission: Permission }) {
  const can = useCan()

  if (!can(permission)) {
    return <ForbiddenPage />
  }

  return <Outlet />
}
