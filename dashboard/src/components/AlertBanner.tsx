import { memo } from 'react'
import { Link } from 'react-router-dom'
import { getActiveAlerts } from '../api/dashboard'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { alertLabels } from '../utils/metrics'
import styles from './Components.module.css'

const ALERT_EVENTS = ['overview_updated', 'alert_updated'] as const

export const AlertBanner = memo(function AlertBanner() {
  const { data: alerts } = useLivePolling(getActiveAlerts, ALERT_EVENTS)

  if (!alerts || alerts.length === 0) {
    return null
  }

  const preview = alerts[0]

  return (
    <Link className={styles.alertBanner} to="/alerts" aria-label="View active alerts">
      <strong className={styles.alertTitle}>
        ⚠ Active Alerts ({alerts.length})
      </strong>
      <span className={styles.alertPreview}>
        <span>{alertLabels[preview.kind] ?? preview.kind}</span>
        <span>{preview.agent_name}</span>
      </span>
    </Link>
  )
})
