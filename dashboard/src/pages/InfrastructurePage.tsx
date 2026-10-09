import { getInfrastructure } from '../api/dashboard'
import { EmptyState } from '../components/EmptyState'
import { InfrastructureCard } from '../components/InfrastructureCard'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { OverviewSkeleton } from '../components/Skeleton'
import { LIVE_PAGE_POLL } from '../constants'
import { useLivePolling } from '../hooks/useDashboardSocket'
import userStyles from './UsersPage.module.css'
import pageStyles from './Pages.module.css'
import styles from './InfrastructurePage.module.css'

const INFRA_EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

export function InfrastructurePage() {
  const snapshot = useLivePolling(getInfrastructure, INFRA_EVENTS, LIVE_PAGE_POLL)
  const services = snapshot.data?.services ?? []

  return (
    <section className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <div>
          <p className={pageStyles.eyebrow}>Operations</p>
          <h1 className={pageStyles.title}>Infrastructure</h1>
          <p className={pageStyles.description}>
            Read-only snapshots from QNAP, Docker, Immich, QuMagie, and backup connectors.
          </p>
        </div>
        <div className={userStyles.actions}>
          <LastUpdated refreshing={snapshot.isRefreshing} value={snapshot.lastUpdated} />
          <button className={userStyles.secondaryButton} type="button" onClick={snapshot.retry}>
            Retry all
          </button>
        </div>
      </header>
      {snapshot.error ? (
        <SectionError title="Infrastructure API failed" onRetry={snapshot.retry} />
      ) : null}
      {!snapshot.data && !snapshot.error ? <OverviewSkeleton /> : null}
      {snapshot.data && services.length === 0 ? (
        <EmptyState message="No infrastructure connectors reported a snapshot." />
      ) : null}
      {services.length > 0 ? (
        <section className={styles.connectorGrid} aria-label="Infrastructure connectors">
          {services.map((item) => (
            <InfrastructureCard key={item.service} snapshot={item} onRetry={() => snapshot.retry()} />
          ))}
        </section>
      ) : null}
    </section>
  )
}
