import { memo, useMemo, useState } from 'react'
import { getAlertHistory, getAlertStatistics } from '../api/dashboard'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { OverviewSkeleton, TableSkeleton } from '../components/Skeleton'
import { RelativeTime } from '../components/RelativeTime'
import { SectionError } from '../components/SectionError'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { useNow } from '../hooks/useNow'
import type { AlertHistoryEntry } from '../types/dashboard'
import { formatDuration } from '../utils/time'
import componentStyles from '../components/Components.module.css'
import styles from './Pages.module.css'

const EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

export const AlertTimelinePage = memo(function AlertTimelinePage() {
  const now = useNow()
  const history = useLivePolling(getAlertHistory, EVENTS)
  const statistics = useLivePolling(getAlertStatistics, EVENTS)
  const [status, setStatus] = useState('all')
  const [severity, setSeverity] = useState('all')
  const [agent, setAgent] = useState('all')
  const [alertType, setAlertType] = useState('all')
  const [date, setDate] = useState('')

  const items = useMemo(() => {
    return (history.data ?? []).filter((item) => {
      if (status !== 'all' && item.status !== status) {
        return false
      }
      if (severity !== 'all' && item.severity !== severity) {
        return false
      }
      if (agent !== 'all' && item.agent_id !== agent) {
        return false
      }
      if (alertType !== 'all' && item.alert_type !== alertType) {
        return false
      }
      if (date && !item.started_at.startsWith(date)) {
        return false
      }
      return true
    })
  }, [agent, alertType, date, history.data, severity, status])

  const agents = useMemo(() => {
    const map = new Map<string, string>()
    for (const item of history.data ?? []) {
      map.set(item.agent_id, item.agent_name)
    }
    return [...map.entries()]
  }, [history.data])

  const types = useMemo(
    () => [...new Set((history.data ?? []).map((item) => item.alert_type))],
    [history.data],
  )

  const error = history.error || statistics.error
  const retry = () => {
    history.retry()
    statistics.retry()
  }

  return (
    <section className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Monitoring</p>
          <h1 className={styles.title}>Alert Timeline</h1>
          <p className={styles.description}>Read-only history of alert lifecycles.</p>
        </div>
        <LastUpdated
          refreshing={history.isRefreshing || statistics.isRefreshing}
          value={history.lastUpdated}
        />
      </header>

      {error ? <SectionError title="Alert timeline failed" onRetry={retry} /> : null}
      {!statistics.data && !error ? <OverviewSkeleton /> : null}

      {statistics.data ? (
        <section className={styles.section} aria-labelledby="alert-stats-title">
          <h2 className={styles.sectionTitle} id="alert-stats-title">
            Statistics
          </h2>
          <section className={styles.statGrid} aria-label="Alert statistics">
            <StatCard label="Active Alerts" value={statistics.data.active_alerts} />
            <StatCard label="Recovered Today" value={statistics.data.recovered_today} />
            <StatCard
              label="Average Duration"
              value={formatDuration(statistics.data.average_duration_seconds)}
            />
            <StatCard label="Critical Count" value={statistics.data.critical_count} />
            <StatCard label="Warning Count" value={statistics.data.warning_count} />
            <StatCard label="Recovery Rate" value={`${statistics.data.recovery_rate}%`} />
            <StatCard label="Recovered" value={statistics.data.recovered} />
            <StatCard label="Total" value={statistics.data.total} />
          </section>
        </section>
      ) : null}

      <section className={styles.section} aria-labelledby="alert-filters-title">
        <h2 className={styles.sectionTitle} id="alert-filters-title">
          Filters
        </h2>
        <section className={styles.filterBar} aria-label="Alert filters">
          <FilterSelect id="status-filter" label="Status" value={status} onChange={setStatus} options={['all', 'active', 'recovered']} />
          <FilterSelect id="severity-filter" label="Severity" value={severity} onChange={setSeverity} options={['all', 'critical', 'warning', 'info']} />
          <FilterSelect
            id="agent-filter"
            label="Agent"
            value={agent}
            onChange={setAgent}
            options={['all', ...agents.map(([id]) => id)]}
            labels={Object.fromEntries([['all', 'all'], ...agents])}
          />
          <FilterSelect id="type-filter" label="Alert Type" value={alertType} onChange={setAlertType} options={['all', ...types]} />
          <p className={styles.filterField}>
            <label htmlFor="date-filter">Date</label>
            <input id="date-filter" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </p>
        </section>
      </section>

      {!history.data && !error ? <TableSkeleton label="Loading timeline" /> : null}
      {history.data && items.length === 0 ? <EmptyState message="No alert history yet." /> : null}
      {items.length > 0 ? (
        <ol className={styles.timelineList} aria-label="Alert timeline">
          {items.map((item) => (
            <TimelineEntry item={item} key={item.id} now={now} />
          ))}
        </ol>
      ) : null}
    </section>
  )
})

function FilterSelect({
  id,
  label,
  value,
  onChange,
  options,
  labels,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  options: string[]
  labels?: Record<string, string>
}) {
  return (
    <p className={styles.filterField}>
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option} value={option}>
            {labels?.[option] ?? option}
          </option>
        ))}
      </select>
    </p>
  )
}

function TimelineEntry({ item, now }: { item: AlertHistoryEntry; now: number }) {
  return (
    <li className={styles.timelineItem}>
      <p className={styles.timelineKind}>{item.alert_type.replaceAll('_', ' ')}</p>
      <StatusBadge kind="lifecycle" status={item.status} />
      <p className={styles.timelineMessage}>{item.agent_name}</p>
      <dl className={componentStyles.alertMeta}>
        <div>
          <dt>Started</dt>
          <dd>
            <RelativeTime now={now} value={item.started_at} />
          </dd>
        </div>
        <div>
          <dt>Recovered</dt>
          <dd>{item.recovered_at ? <RelativeTime now={now} value={item.recovered_at} /> : '—'}</dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>{formatDuration(item.duration_seconds)}</dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{item.source}</dd>
        </div>
        <div>
          <dt>Threshold</dt>
          <dd>{item.threshold ?? '—'}</dd>
        </div>
        <div>
          <dt>Peak Value</dt>
          <dd>{item.peak_value ?? '—'}</dd>
        </div>
      </dl>
    </li>
  )
}
