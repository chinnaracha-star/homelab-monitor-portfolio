import { memo } from 'react'
import { normalizeStatus } from '../utils/agents'
import styles from './Components.module.css'

interface StatusBadgeProps {
  status: string
  alertCount?: number
  kind?: 'agent' | 'service' | 'lifecycle'
}

const agentLabels: Record<string, string> = {
  online: 'Online',
  offline: 'Offline',
  warning: 'Warning',
  registered: 'Unknown',
  unknown: 'Unknown',
  healthy: 'Online',
  critical: 'Offline',
}

const serviceLabels: Record<string, string> = {
  running: 'Running',
  stopped: 'Stopped',
  restarting: 'Restarting',
  unknown: 'Unknown',
  enabled: 'Enabled',
  disabled: 'Disabled',
  healthy: 'Healthy',
  critical: 'Critical',
}

function serviceClass(status: string): string {
  const normalized = status.toLowerCase()
  if (normalized === 'running') {
    return 'running'
  }
  if (normalized === 'healthy') {
    return 'online'
  }
  if (normalized === 'stopped' || normalized === 'failed') {
    return 'stopped'
  }
  if (normalized === 'critical') {
    return 'offline'
  }
  if (normalized === 'restarting' || normalized === 'warning') {
    return 'warning'
  }
  return 'unknown'
}

export const StatusBadge = memo(function StatusBadge({
  status,
  alertCount = 0,
  kind = 'agent',
}: StatusBadgeProps) {
  if (kind === 'lifecycle') {
    const normalized = status.toLowerCase()
    const recovered = normalized === 'recovered' || normalized === 'resolved'
    const label = recovered ? 'RECOVERED' : 'ACTIVE'
    const className = recovered ? styles.online : styles.offline
    return (
      <span className={`${styles.badge} ${className}`} aria-label={`Status ${label}`}>
        {label}
      </span>
    )
  }

  if (kind === 'service') {
    const normalized = status.toLowerCase()
    const label = serviceLabels[normalized] ?? status
    const className = styles[serviceClass(normalized)] ?? styles.unknown
    return (
      <span className={`${styles.badge} ${className}`} aria-label={`Status ${label}`}>
        {label}
      </span>
    )
  }

  const displayStatus = normalizeStatus(status, alertCount)
  const label = agentLabels[displayStatus] ?? status
  const countLabel = alertCount > 0 ? ` ${alertCount}` : ''
  const className = styles[displayStatus] ?? styles.unknown

  return (
    <span
      className={`${styles.badge} ${className}`}
      aria-label={`Status ${label}${alertCount > 0 ? `, ${alertCount} alerts` : ''}`}
    >
      {label}
      {countLabel ? <span className={styles.badgeCount}>{alertCount}</span> : null}
    </span>
  )
})
