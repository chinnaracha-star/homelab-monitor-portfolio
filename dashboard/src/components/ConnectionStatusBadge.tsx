import { memo } from 'react'
import type { ConnectionStatus } from '../hooks/useDashboardSocket'
import styles from './Layout.module.css'

const labels: Record<ConnectionStatus, string> = {
  connected: '🟢 Connected',
  connecting: '🟡 Connecting',
  disconnected: '🔴 Disconnected',
}

interface ConnectionStatusBadgeProps {
  status: ConnectionStatus
}

export const ConnectionStatusBadge = memo(function ConnectionStatusBadge({
  status,
}: ConnectionStatusBadgeProps) {
  return (
    <span className={styles.connectionStatus} aria-live="polite">
      {labels[status]}
    </span>
  )
})
