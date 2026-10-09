import { StatusBadge } from './StatusBadge'
import badgeStyles from './Components.module.css'
import type { InfrastructureSnapshot } from '../types/dashboard'
import { formatBytes, formatPercent } from '../utils/bytes'
import { formatThaiDateTime } from '../utils/thaiDate'
import userStyles from '../pages/UsersPage.module.css'
import infraStyles from '../pages/InfrastructurePage.module.css'
import styles from '../pages/PhotoServicesPage.module.css'

const STATUS_MAP: Record<string, string> = {
  healthy: 'online',
  degraded: 'warning',
  unhealthy: 'offline',
  unknown: 'registered',
}

interface PhotoServiceCardProps {
  snapshot: InfrastructureSnapshot
  title: string
  onRetry: () => void
}

export function PhotoServiceCard({ snapshot, title, onRetry }: PhotoServiceCardProps) {
  const health = String(snapshot.summary.health ?? snapshot.status)

  return (
    <article className={infraStyles.connectorCard} data-service="immich" aria-label={`${title} card`}>
      <header className={infraStyles.connectorHeader}>
        <h2 className={infraStyles.connectorName}>{title}</h2>
        <StatusBadge status={STATUS_MAP[snapshot.status] ?? snapshot.status} />
      </header>
      <p className={infraStyles.meta}>Status {snapshot.status}</p>
      <p className={infraStyles.meta}>Version {snapshot.version || 'unknown'}</p>
      <p className={infraStyles.meta}>
        Last update {snapshot.updated_at ? formatThaiDateTime(snapshot.updated_at, false) : 'never'}
      </p>
      <p className={infraStyles.meta}>Health {health}</p>
      <div className={infraStyles.retryRow}>
        <button className={userStyles.secondaryButton} type="button" onClick={onRetry}>
          Retry
        </button>
      </div>
    </article>
  )
}

interface StorageCardProps {
  snapshot: InfrastructureSnapshot | undefined
  onRetry: () => void
}

export function StorageCard({ snapshot, onRetry }: StorageCardProps) {
  const summary = snapshot?.summary ?? {}
  const capacity = Number(summary.capacity_bytes ?? 0)
  const used = Number(summary.used_bytes ?? 0)
  const free = Number(summary.free_bytes ?? 0)
  const percent = Number(summary.storage_percent ?? summary.storage_used_percent ?? 0)
  const health = String(summary.storage_health ?? 'unknown')
  const healthLabel = health === 'critical' ? 'Critical' : health === 'warning' ? 'Warning' : 'Healthy'
  const healthClass =
    health === 'critical' ? badgeStyles.critical : health === 'warning' ? badgeStyles.warning : badgeStyles.healthy

  return (
    <article className={infraStyles.connectorCard} data-service="qnap" aria-label="QNAP Storage card">
      <header className={infraStyles.connectorHeader}>
        <h2 className={infraStyles.connectorName}>QNAP Storage</h2>
        <StatusBadge status={STATUS_MAP[snapshot?.status ?? 'unknown'] ?? 'registered'} />
      </header>
      <p className={infraStyles.meta}>Status {snapshot?.status ?? 'unknown'}</p>
      <p className={infraStyles.meta}>Version {snapshot?.version || 'unknown'}</p>
      <p className={infraStyles.meta}>
        Last update {snapshot?.updated_at ? formatThaiDateTime(snapshot.updated_at, false) : 'never'}
      </p>
      <p className={infraStyles.meta}>
        Health {typeof snapshot?.summary.health === 'string' ? snapshot.summary.health : snapshot?.status ?? 'unknown'}
      </p>
      <dl className={infraStyles.summaryList}>
        <div>
          <dt>Capacity</dt>
          <dd>{formatBytes(capacity)}</dd>
        </div>
        <div>
          <dt>Used</dt>
          <dd>{formatBytes(used)}</dd>
        </div>
        <div>
          <dt>Free</dt>
          <dd>{formatBytes(free)}</dd>
        </div>
        <div>
          <dt>Usage</dt>
          <dd>{formatPercent(percent)}</dd>
        </div>
      </dl>
      <label className={styles.meterLabel} htmlFor="qnap-storage-usage">
        Storage usage
      </label>
      <meter
        className={styles.storageMeter}
        id="qnap-storage-usage"
        min={0}
        max={100}
        low={80}
        high={90}
        optimum={40}
        value={Number.isFinite(percent) ? percent : 0}
      >
        {formatPercent(percent)}
      </meter>
      <p className={`${badgeStyles.badge} ${healthClass}`} aria-label={`Storage ${healthLabel}`}>
        {healthLabel}
      </p>
      <div className={infraStyles.retryRow}>
        <button className={userStyles.secondaryButton} type="button" onClick={onRetry}>
          Retry
        </button>
      </div>
    </article>
  )
}
