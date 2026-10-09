import { getPhotoServices } from '../api/dashboard'
import { EmptyState } from '../components/EmptyState'
import { PhotoServiceCard, StorageCard } from '../components/PhotoServiceCards'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { OverviewSkeleton } from '../components/Skeleton'
import { StatCard } from '../components/StatCard'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { formatBytes, formatPercent } from '../utils/bytes'
import { formatThaiDateTime } from '../utils/thaiDate'
import userStyles from './UsersPage.module.css'
import pageStyles from './Pages.module.css'
import infraStyles from './InfrastructurePage.module.css'
import styles from './PhotoServicesPage.module.css'

const PHOTO_EVENTS = ['overview_updated'] as const

export function PhotoServicesPage() {
  const snapshot = useLivePolling(getPhotoServices, PHOTO_EVENTS)
  const services = snapshot.data?.services ?? []
  const byName = Object.fromEntries(services.map((item) => [item.service, item]))
  const stats = snapshot.data?.stats

  return (
    <section className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <div>
          <p className={pageStyles.eyebrow}>Operations</p>
          <h1 className={pageStyles.title}>Photo Services</h1>
          <p className={pageStyles.description}>
            Read-only view of Immich, QuMagie, and QNAP storage. Photos stay on the NAS
            workflow: Phone, Qfile Pro, QNAP TS-453Be, shared folder, Immich, QuMagie.
            This dashboard never uploads, moves, or modifies NAS data.
          </p>
        </div>
        <div className={userStyles.actions}>
          <LastUpdated refreshing={snapshot.isRefreshing} value={snapshot.lastUpdated} />
          <button className={userStyles.secondaryButton} type="button" onClick={snapshot.retry}>
            Retry all
          </button>
        </div>
      </header>
      {snapshot.error ? <SectionError title="Photo Services API failed" onRetry={snapshot.retry} /> : null}
      {!snapshot.data && !snapshot.error ? <OverviewSkeleton /> : null}
      {snapshot.data && services.length === 0 ? (
        <EmptyState message="No photo services reported a snapshot." />
      ) : null}
      {services.length > 0 ? (
        <section className={infraStyles.connectorGrid} aria-label="Photo service cards">
          {byName.immich ? (
            <PhotoServiceCard snapshot={byName.immich} title="Immich" onRetry={snapshot.retry} />
          ) : null}
          {byName.qumagie ? (
            <PhotoServiceCard snapshot={byName.qumagie} title="QuMagie" onRetry={snapshot.retry} />
          ) : null}
          <StorageCard snapshot={byName.qnap} onRetry={snapshot.retry} />
        </section>
      ) : null}
      {stats ? (
        <section className={styles.statsSection} aria-label="Photo statistics">
          <h2 className={pageStyles.sectionTitle}>Photo statistics</h2>
          <div className={pageStyles.statGrid}>
            <StatCard label="Indexed Photos" value={stats.indexed_photos} />
            <StatCard label="Indexed Videos" value={stats.indexed_videos} />
            <StatCard label="Albums" value={stats.albums} />
            <StatCard label="Users" value={stats.users} />
            <article className={styles.statNote} aria-label={`Storage Used ${formatBytes(stats.storage_used)}`}>
              <p className={styles.statNoteLabel}>Storage Used</p>
              <p className={styles.statNoteValue}>{formatBytes(stats.storage_used)}</p>
            </article>
            <article className={styles.statNote} aria-label={`Storage Free ${formatBytes(stats.storage_free)}`}>
              <p className={styles.statNoteLabel}>Storage Free</p>
              <p className={styles.statNoteValue}>{formatBytes(stats.storage_free)}</p>
            </article>
            <article className={styles.statNote} aria-label={`Storage % ${formatPercent(stats.storage_percent)}`}>
              <p className={styles.statNoteLabel}>Storage %</p>
              <p className={styles.statNoteValue}>{formatPercent(stats.storage_percent)}</p>
            </article>
            <StatCard label="Thumbnail Queue" value={stats.thumbnail_queue} />
            <StatCard label="Face Queue" value={stats.face_queue} />
            <article className={styles.statNote} aria-label={`Last Scan ${stats.last_scan || 'unknown'}`}>
              <p className={styles.statNoteLabel}>Last Scan</p>
              <p className={styles.statNoteValue}>
                {stats.last_scan ? formatThaiDateTime(stats.last_scan, false) : 'unknown'}
              </p>
            </article>
          </div>
        </section>
      ) : null}
      {stats ? (
        <section className={styles.trendGrid} aria-label="Storage and photo trends">
          <article className={styles.trendCard} aria-label="Storage History">
            <h2 className={styles.trendTitle}>Storage History</h2>
            <p className={styles.trendEyebrow}>Used</p>
            <dl className={styles.periodList}>
              <div className={styles.periodRow}>
                <dt>Yesterday</dt>
                <dd>{formatBytes(stats.storage_history.yesterday)}</dd>
              </div>
              <div className={styles.periodRow}>
                <dt>Today</dt>
                <dd>{formatBytes(stats.storage_history.today)}</dd>
              </div>
              <div className={styles.periodRow}>
                <dt>Last Week</dt>
                <dd>{formatBytes(stats.storage_history.last_week)}</dd>
              </div>
            </dl>
          </article>
          <article className={styles.trendCard} aria-label="Photo Growth">
            <h2 className={styles.trendTitle}>Photo Growth</h2>
            <p className={styles.trendEyebrow}>Photos</p>
            <dl className={styles.periodList}>
              <div className={styles.periodRow}>
                <dt>Today</dt>
                <dd>{formatDelta(stats.photo_growth.today)}</dd>
              </div>
              <div className={styles.periodRow}>
                <dt>Yesterday</dt>
                <dd>{formatDelta(stats.photo_growth.yesterday)}</dd>
              </div>
              <div className={styles.periodRow}>
                <dt>This Week</dt>
                <dd>{formatDelta(stats.photo_growth.this_week)}</dd>
              </div>
            </dl>
          </article>
        </section>
      ) : null}
    </section>
  )
}

function formatDelta(value: number): string {
  const amount = Number.isFinite(value) ? Math.trunc(value) : 0
  const formatted = Math.abs(amount).toLocaleString()
  if (amount > 0) {
    return `+${formatted}`
  }
  if (amount < 0) {
    return `-${formatted}`
  }
  return formatted
}
