import { QnapDiskHealth } from './QnapDiskHealth'
import { StatusBadge } from './StatusBadge'
import { Icon, type IconName } from './Icon'
import type { InfrastructureSnapshot } from '../types/dashboard'
import { formatThaiDateTime } from '../utils/thaiDate'
import userStyles from '../pages/UsersPage.module.css'
import styles from '../pages/InfrastructurePage.module.css'

const LABELS: Record<string, string> = {
  qnap: 'QNAP',
  docker: 'Docker',
  immich: 'Immich',
  qumagie: 'QuMagie',
  backup: 'Backup',
}

const ICONS: Record<string, IconName> = {
  qnap: 'qnap',
  docker: 'docker',
  immich: 'immich',
  qumagie: 'photo',
  backup: 'backup',
}

const STATUS_MAP: Record<string, string> = {
  healthy: 'online',
  degraded: 'warning',
  unhealthy: 'offline',
  unknown: 'registered',
}

interface InfrastructureCardProps {
  snapshot: InfrastructureSnapshot
  onRetry: (service: string) => void
}

export function InfrastructureCard({ snapshot, onRetry }: InfrastructureCardProps) {
  const hidden =
    snapshot.service === 'qnap'
      ? new Set([
          'disks',
          'cpu_tempc',
          'sys_tempc',
          'temperature_celsius',
          'disk_temp_warning_c',
          'disk_temp_critical_c',
        ])
      : new Set(['disks'])
  const entries = Object.entries(snapshot.summary).filter(
    ([key, value]) => key !== 'error' && !hidden.has(key) && !Array.isArray(value),
  )

  return (
    <article
      className={styles.connectorCard}
      data-service={snapshot.service}
      aria-label={`${LABELS[snapshot.service] ?? snapshot.service} connector`}
    >
      <header className={styles.connectorHeader}>
        <h2 className={styles.connectorName}>
          {ICONS[snapshot.service] ? <Icon name={ICONS[snapshot.service]} /> : null}{' '}
          {LABELS[snapshot.service] ?? snapshot.service}
        </h2>
        <StatusBadge status={STATUS_MAP[snapshot.status] ?? snapshot.status} />
      </header>
      <p className={styles.meta}>Version {snapshot.version || 'unknown'}</p>
      <p className={styles.meta}>
        Last update {snapshot.updated_at ? formatThaiDateTime(snapshot.updated_at, false) : 'never'}
      </p>
      {snapshot.service === 'qnap' ? <QnapDiskHealth summary={snapshot.summary} /> : null}
      {entries.length > 0 ? (
        <dl className={styles.summaryList}>
          {entries.map(([key, value]) => (
            <div key={key}>
              <dt>{key.replaceAll('_', ' ')}</dt>
              <dd>{formatValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className={styles.meta}>No summary yet.</p>
      )}
      <div className={styles.retryRow}>
        <button
          className={userStyles.secondaryButton}
          type="button"
          onClick={() => onRetry(snapshot.service)}
        >
          Retry
        </button>
      </div>
    </article>
  )
}

function formatValue(value: string | number | boolean | null | unknown): string {
  if (typeof value === 'boolean') {
    return value ? 'yes' : 'no'
  }
  if (value === null) {
    return '—'
  }
  return String(value)
}
