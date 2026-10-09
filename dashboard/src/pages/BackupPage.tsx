import { getBackupStatus } from '../api/dashboard'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { OverviewSkeleton } from '../components/Skeleton'
import { StatusBadge } from '../components/StatusBadge'
import badgeStyles from '../components/Components.module.css'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { formatBytes, formatDuration, formatPercent } from '../utils/bytes'
import { formatThaiDateTime } from '../utils/thaiDate'
import type { BackupStatus, SqliteBackupStatus } from '../types/dashboard'
import userStyles from './UsersPage.module.css'
import pageStyles from './Pages.module.css'
import styles from './BackupPage.module.css'

const BACKUP_EVENTS = ['overview_updated'] as const

const STATUS_MAP: Record<string, string> = {
  healthy: 'online',
  idle: 'online',
  running: 'warning',
  warning: 'warning',
  failed: 'offline',
  critical: 'offline',
  unknown: 'registered',
}

export function BackupPage() {
  const snapshot = useLivePolling(getBackupStatus, BACKUP_EVENTS)
  const backup = snapshot.data
  const empty = backup !== null && !backup.job_name && backup.status === 'unknown' && !backup.sqlite

  return (
    <section className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <div>
          <p className={pageStyles.eyebrow}>Operations</p>
          <h1 className={pageStyles.title}>Backup</h1>
          <p className={pageStyles.description}>
            SQLite database backups plus read-only status of replication to the TS-253 Pro backup
            NAS. This dashboard never starts, stops, deletes, or moves backups.
          </p>
        </div>
        <div className={userStyles.actions}>
          <LastUpdated refreshing={snapshot.isRefreshing} value={snapshot.lastUpdated} />
          <button className={userStyles.secondaryButton} type="button" onClick={snapshot.retry}>
            Retry
          </button>
        </div>
      </header>
      {snapshot.error ? <SectionError title="Backup API failed" onRetry={snapshot.retry} /> : null}
      {!snapshot.data && !snapshot.error ? <OverviewSkeleton /> : null}
      {empty && !backup?.sqlite ? <EmptyState message="No backup job has reported a snapshot." /> : null}
      {backup?.sqlite ? <SqliteBackupCards sqlite={backup.sqlite} /> : null}
      {backup && !empty ? <BackupCards backup={backup} /> : null}
    </section>
  )
}

function SqliteBackupCards({ sqlite }: { sqlite: SqliteBackupStatus }) {
  return (
    <section className={styles.cardGrid} aria-label="SQLite backup cards">
      <article className={styles.card} aria-label="Latest Backup card">
        <h2 className={styles.cardTitle}>Latest Backup</h2>
        <p className={styles.cardValue}>{formatTimestamp(sqlite.latest_at)}</p>
        <p className={styles.cardMeta}>{sqlite.latest_file || 'No file yet'}</p>
      </article>
      <article className={styles.card} aria-label="SQLite Backup Status card">
        <h2 className={styles.cardTitle}>Backup Status</h2>
        <p className={styles.cardValue}>{titleCase(sqlite.status)}</p>
        <p className={styles.cardMeta}>{sqlite.enabled ? 'Scheduled' : 'Disabled'}</p>
      </article>
      <article className={styles.card} aria-label="SQLite Backup Size card">
        <h2 className={styles.cardTitle}>Backup Size</h2>
        <p className={styles.cardValue}>{formatBytes(sqlite.size_bytes)}</p>
        <p className={styles.cardMeta}>Uncompressed {formatBytes(sqlite.uncompressed_bytes)}</p>
      </article>
      <article className={styles.card} aria-label="Next Scheduled Backup card">
        <h2 className={styles.cardTitle}>Next Scheduled Backup</h2>
        <p className={styles.cardValue}>{formatTimestamp(sqlite.next_scheduled)}</p>
      </article>
      <article className={styles.card} aria-label="Retention Summary card">
        <h2 className={styles.cardTitle}>Retention Summary</h2>
        <p className={styles.cardValue}>
          {sqlite.retention_daily} Daily
        </p>
        <p className={styles.cardMeta}>
          {sqlite.retention_weekly} Weekly · {sqlite.retention_monthly} Monthly
        </p>
      </article>
      <article className={styles.card} aria-label="Last Verification card">
        <h2 className={styles.cardTitle}>Last Verification</h2>
        <p className={styles.cardValue}>{sqlite.integrity}</p>
        <p className={styles.cardMeta}>{formatTimestamp(sqlite.last_verification)}</p>
      </article>
    </section>
  )
}

function BackupCards({ backup }: { backup: BackupStatus }) {
  const health = backup.backup_health || backup.status
  const healthClass =
    health === 'failed' || health === 'critical'
      ? badgeStyles.critical
      : health === 'warning'
        ? badgeStyles.warning
        : badgeStyles.healthy
  const healthLabel = titleCase(health)

  return (
    <section className={styles.cardGrid} aria-label="Backup cards">
      <article className={styles.card} aria-label="Backup Status card">
        <header>
          <h2 className={styles.cardTitle}>Backup Status</h2>
        </header>
        <StatusBadge status={STATUS_MAP[backup.backup_health] ?? backup.backup_health} />
        <p className={styles.cardValue}>{titleCase(backup.backup_health || backup.status)}</p>
        <p className={styles.cardMeta}>{backup.job_name || 'Backup'}</p>
      </article>
      <article className={styles.card} aria-label="Backup Progress card">
        <h2 className={styles.cardTitle}>Backup Progress</h2>
        <p className={styles.cardValue}>{backup.status === 'running' ? 'Running' : titleCase(backup.status)}</p>
        <p className={styles.cardMeta}>{formatPercent(backup.progress_percent)}</p>
        <label className={styles.meterLabel} htmlFor="backup-progress">
          Running percent
        </label>
        <meter
          className={styles.progressMeter}
          id="backup-progress"
          min={0}
          max={100}
          value={Number.isFinite(backup.progress_percent) ? backup.progress_percent : 0}
        >
          {formatPercent(backup.progress_percent)}
        </meter>
      </article>
      <article className={styles.card} aria-label="Last Backup card">
        <h2 className={styles.cardTitle}>Last Backup</h2>
        <p className={styles.cardValue}>{formatTimestamp(backup.last_backup)}</p>
      </article>
      <article className={styles.card} aria-label="Next Backup card">
        <h2 className={styles.cardTitle}>Next Backup</h2>
        <p className={styles.cardValue}>{formatTimestamp(backup.next_backup)}</p>
      </article>
      <article className={styles.card} aria-label="Duration card">
        <h2 className={styles.cardTitle}>Duration</h2>
        <p className={styles.cardValue}>{formatDuration(backup.duration_seconds)}</p>
      </article>
      <article className={styles.card} aria-label="Backup Size card">
        <h2 className={styles.cardTitle}>Backup Size</h2>
        <p className={styles.cardValue}>{formatTebibytes(backup.backup_size_bytes)}</p>
      </article>
      <article className={styles.card} aria-label="Destination NAS card">
        <h2 className={styles.cardTitle}>Destination NAS</h2>
        <p className={styles.cardValue}>{backup.destination.model || 'TS-253 Pro'}</p>
        <p className={styles.cardMeta}>{backup.destination.hostname || 'unknown host'}</p>
        <p className={styles.cardMeta}>{backup.destination.ip || 'no address'}</p>
      </article>
      <article className={styles.card} aria-label="Health Badge card">
        <h2 className={styles.cardTitle}>Health Badge</h2>
        <p className={`${badgeStyles.badge} ${healthClass}`} aria-label={`Backup ${healthLabel}`}>
          {healthLabel}
        </p>
      </article>
      <article className={styles.card} aria-label="Last Error card">
        <h2 className={styles.cardTitle}>Last Error</h2>
        <p className={styles.cardValue}>{backup.last_error || 'None'}</p>
      </article>
      <article className={styles.card} aria-label="Backup History card">
        <h2 className={styles.cardTitle}>Backup History</h2>
        <dl className={styles.periodList}>
          {backup.history.map((item) => (
            <div className={styles.periodRow} key={item.period}>
              <dt>{item.label}</dt>
              <dd>{titleCase(item.status)}</dd>
            </div>
          ))}
        </dl>
      </article>
    </section>
  )
}

function formatTebibytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0.00 TB'
  }
  return `${(bytes / 1024 ** 4).toFixed(2)} TB`
}

function formatTimestamp(value: string): string {
  if (!value) {
    return 'unknown'
  }
  const formatted = formatThaiDateTime(value, false)
  return formatted === '—' ? value : formatted
}

function titleCase(value: string): string {
  if (!value) {
    return 'Unknown'
  }
  return value.charAt(0).toUpperCase() + value.slice(1)
}
