import { memo, useMemo, useState } from 'react'
import { getIncident, getIncidentStatistics, getIncidents } from '../api/dashboard'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { OverviewSkeleton, TableSkeleton } from '../components/Skeleton'
import { RelativeTime } from '../components/RelativeTime'
import { SectionError } from '../components/SectionError'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { useNow } from '../hooks/useNow'
import { formatDuration } from '../utils/time'
import styles from './Pages.module.css'

const EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

export const IncidentsPage = memo(function IncidentsPage() {
  const now = useNow()
  const incidents = useLivePolling(getIncidents, EVENTS)
  const statistics = useLivePolling(getIncidentStatistics, EVENTS)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const detail = useLivePolling(
    () => (selectedId ? getIncident(selectedId) : Promise.resolve(null)),
    EVENTS,
    { enabled: Boolean(selectedId), resetKey: selectedId ?? 'none' },
  )
  const mostCommonCause = useMemo(() => {
    const causes = (incidents.data ?? []).map((item) => item.cause).filter(Boolean)
    if (causes.length === 0) {
      return '—'
    }
    return causes.sort(
      (left, right) => causes.filter((item) => item === right).length - causes.filter((item) => item === left).length,
    )[0]
  }, [incidents.data])
  const error = incidents.error || statistics.error
  const retry = () => {
    incidents.retry()
    statistics.retry()
    detail.retry()
  }

  return (
    <section className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Monitoring</p>
          <h1 className={styles.title}>Incidents</h1>
          <p className={styles.description}>Grouped related alerts for the same agent.</p>
        </div>
        <LastUpdated refreshing={incidents.isRefreshing} value={incidents.lastUpdated} />
      </header>
      {error ? <SectionError title="Incidents failed" onRetry={retry} /> : null}
      {!statistics.data && !error ? <OverviewSkeleton /> : null}
      {statistics.data ? (
        <section className={styles.statGrid} aria-label="Incident statistics">
          <StatCard label="Open Incidents" value={statistics.data.open_count} />
          <StatCard label="Recovered Incidents" value={statistics.data.recovered_count} />
          <StatCard label="Average Duration" value={formatDuration(statistics.data.average_duration_seconds)} />
          <StatCard label="Most Common Cause" value={mostCommonCause} />
          <StatCard label="Top Affected Agent" value={statistics.data.top_affected_agent || '—'} />
        </section>
      ) : null}
      {!incidents.data && !error ? <TableSkeleton label="Loading incidents" /> : null}
      {incidents.data && incidents.data.length === 0 ? <EmptyState message="No incidents yet." /> : null}
      {incidents.data && incidents.data.length > 0 ? (
        <ol className={styles.timelineList} aria-label="Incident timeline">
          {incidents.data.map((item) => (
            <li className={styles.timelineItem} key={item.id}>
              <button className={styles.incidentButton} type="button" onClick={() => setSelectedId(item.id)}>
                <p className={styles.timelineKind}>{item.cause.replaceAll('_', ' ')}</p>
                <StatusBadge kind="lifecycle" status={item.status} />
                <p className={styles.timelineMessage}>
                  {item.agent_name} · {item.alert_count} alerts
                </p>
                <p className={styles.timelineTime}>
                  <RelativeTime now={now} value={item.started_at} /> · {formatDuration(item.duration_seconds)}
                </p>
              </button>
            </li>
          ))}
        </ol>
      ) : null}
      {selectedId && detail.data ? (
        <article className={styles.section} aria-label="Incident details">
          <h2 className={styles.sectionTitle}>Incident Details</h2>
          <p className={styles.timelineMessage}>{detail.data.agent_name}</p>
          <StatusBadge kind="lifecycle" status={detail.data.status} />
          <p className={styles.reportMeta}>
            {detail.data.alert_count} affected alerts · {formatDuration(detail.data.duration_seconds)}
          </p>
          <ul className={styles.timelineList} aria-label="Affected alerts">
            {detail.data.affected_alerts.map((alert) => (
              <li className={styles.timelineItem} key={alert.id}>
                {alert.alert_type} · {alert.severity}
              </li>
            ))}
          </ul>
        </article>
      ) : null}
    </section>
  )
})
