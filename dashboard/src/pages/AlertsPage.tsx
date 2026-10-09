import { memo, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { getActiveAlerts } from '../api/dashboard'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { RelativeTime } from '../components/RelativeTime'
import { SectionError } from '../components/SectionError'
import { TableSkeleton } from '../components/Skeleton'
import { StatusBadge } from '../components/StatusBadge'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { useNow } from '../hooks/useNow'
import type { ActiveAlert } from '../types/dashboard'
import { alertLabels } from '../utils/metrics'
import { formatDuration, liveAlertDurationSeconds } from '../utils/time'
import componentStyles from '../components/Components.module.css'
import styles from './Pages.module.css'

const ALERT_EVENTS = ['overview_updated', 'alert_updated'] as const

function loadAlerts() {
  return getActiveAlerts(true)
}

function isRecovered(alert: ActiveAlert): boolean {
  const status = (alert.status ?? 'active').toLowerCase()
  return status === 'recovered' || status === 'resolved'
}

function AlertCard({ alert, now }: { alert: ActiveAlert; now: number }) {
  const recovered = isRecovered(alert)
  const started = alert.started_at ?? alert.opened_at
  const lastTriggered = alert.last_triggered_at ?? alert.last_observed_at
  const duration = formatDuration(
    liveAlertDurationSeconds(started, alert.recovered_at, alert.status, now, alert.duration_seconds),
  )

  return (
    <li>
      <Link
        className={componentStyles.alertItem}
        to={`/agents/${alert.agent_id}`}
        aria-label={`${alertLabels[alert.kind] ?? alert.kind} on ${alert.agent_name}`}
      >
        <article>
          <span className={componentStyles.alertKind}>{alertLabels[alert.kind] ?? alert.kind}</span>
          <span className={componentStyles.alertAgent}>{alert.agent_name}</span>
          <StatusBadge kind="lifecycle" status={recovered ? 'recovered' : 'active'} />
          <dl className={componentStyles.alertMeta}>
            <div>
              <dt>Started</dt>
              <dd>
                <RelativeTime now={now} value={started} />
              </dd>
            </div>
            <div>
              <dt>Duration</dt>
              <dd>{duration}</dd>
            </div>
            <div>
              <dt>Last Triggered</dt>
              <dd>
                <RelativeTime now={now} value={lastTriggered} />
              </dd>
            </div>
            <div>
              <dt>Recovered</dt>
              <dd>
                {recovered ? <RelativeTime now={now} value={alert.recovered_at ?? null} /> : '—'}
              </dd>
            </div>
          </dl>
        </article>
      </Link>
    </li>
  )
}

export const AlertsPage = memo(function AlertsPage() {
  const now = useNow()
  const { data: alerts, error, isRefreshing, lastUpdated, retry } = useLivePolling(
    loadAlerts,
    ALERT_EVENTS,
  )

  const activeAlerts = useMemo(
    () => (alerts ?? []).filter((alert) => !isRecovered(alert)),
    [alerts],
  )
  const recoveredAlerts = useMemo(
    () => (alerts ?? []).filter((alert) => isRecovered(alert)),
    [alerts],
  )

  return (
    <section className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Notifications</p>
          <h1 className={styles.title}>Active alerts</h1>
          <p className={styles.description}>Current issues detected by the alert engine.</p>
        </div>
        <LastUpdated refreshing={isRefreshing} value={lastUpdated} />
      </header>

      {error ? <SectionError title="Alerts API failed" onRetry={retry} /> : null}
      {!alerts && !error ? <TableSkeleton label="Loading alerts" /> : null}

      {activeAlerts.length > 0 ? (
        <ul className={componentStyles.alertList} aria-label="Active alerts">
          {activeAlerts.map((alert) => (
            <AlertCard alert={alert} key={alert.id} now={now} />
          ))}
        </ul>
      ) : null}

      {alerts && activeAlerts.length === 0 && recoveredAlerts.length === 0 && !error ? (
        <EmptyState message="No alerts yet." />
      ) : null}

      {alerts && activeAlerts.length === 0 && recoveredAlerts.length > 0 && !error ? (
        <p className={styles.reportMeta}>No active alerts.</p>
      ) : null}

      <section className={styles.resolvedGroup} aria-labelledby="recovered-alerts-title">
        <h2 className={styles.sectionTitle} id="recovered-alerts-title">
          Recovered ({recoveredAlerts.length})
        </h2>
        {recoveredAlerts.length === 0 ? (
          <p className={styles.reportMeta}>No recovered alerts.</p>
        ) : (
          <ul className={componentStyles.alertList} aria-label="Recovered alerts">
            {recoveredAlerts.map((alert) => (
              <AlertCard alert={alert} key={alert.id} now={now} />
            ))}
          </ul>
        )}
      </section>
    </section>
  )
})
