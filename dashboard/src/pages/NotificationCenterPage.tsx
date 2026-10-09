import { memo, useMemo, useState } from 'react'
import {
  getNotificationCenterStatistics,
  getNotificationDeliveryHistory,
  getNotificationHistory,
  getNotificationMetrics,
} from '../api/dashboard'
import { EmptyState } from '../components/EmptyState'
import { Icon } from '../components/Icon'
import { LastUpdated } from '../components/LastUpdated'
import { OverviewSkeleton, TableSkeleton } from '../components/Skeleton'
import { RelativeTime } from '../components/RelativeTime'
import { SectionError } from '../components/SectionError'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import componentStyles from '../components/Components.module.css'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { useNow } from '../hooks/useNow'
import { usePolling } from '../hooks/usePolling'
import type { NotificationCenterItem, NotificationDeliveryHistoryItem } from '../types/dashboard'
import {
  formatAverageDelivery,
  formatAverageRetry,
  formatDeliveryChannel,
  formatDeliveryError,
  formatDeliveryEvent,
  formatDeliverySpeed,
  formatDeliveryStatus,
  formatFailedTrend,
  formatLocalDateTime,
  formatRetryQuality,
  formatSuccessRate,
  formatSuccessRateTrend,
} from '../utils/format'
import styles from './Pages.module.css'

const EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

const METRIC_SKELETON_LABELS = [
  'Notifications Sent',
  'Success Rate',
  'Failed Notifications',
  'Average Delivery Time',
  'Average Retry Count',
  'Last Notification Time',
] as const

const MAX_DELIVERY_ROWS = 100

function deliveryFields(item: NotificationDeliveryHistoryItem) {
  return {
    time: formatLocalDateTime(item.sent_at ?? item.created_at),
    channel: formatDeliveryChannel(item.channel),
    channelKey: item.channel.toLowerCase() || 'unknown',
    event: formatDeliveryEvent(item.event),
    eventKey: item.event.toLowerCase() || 'unknown',
    status: formatDeliveryStatus(item.success),
    statusKey: item.success ? 'success' : 'failed',
    retry: String(item.retry_count),
    duration: formatAverageDelivery(item.duration_ms),
    error: formatDeliveryError(item.error_message),
  }
}

function DeliveryBadge({
  kind,
  value,
  label,
}: {
  kind: 'status' | 'event' | 'channel'
  value: string
  label: string
}) {
  return (
    <span
      className={styles.deliveryBadge}
      data-kind={kind}
      data-value={value}
      aria-label={`${kind} ${label}`}
    >
      {label}
    </span>
  )
}

function matchesDeliveryFilters(
  item: NotificationDeliveryHistoryItem,
  query: string,
  statusFilter: string,
  eventFilter: string,
  channelFilter: string,
): boolean {
  if (statusFilter === 'success' && !item.success) {
    return false
  }
  if (statusFilter === 'failed' && item.success) {
    return false
  }
  if (eventFilter !== 'all' && item.event.toLowerCase() !== eventFilter.toLowerCase()) {
    return false
  }
  if (channelFilter !== 'all' && item.channel.toLowerCase() !== channelFilter.toLowerCase()) {
    return false
  }
  const needle = query.trim().toLowerCase()
  if (!needle) {
    return true
  }
  const haystack = [
    item.channel,
    item.event,
    item.error_message ?? '',
    formatDeliveryChannel(item.channel),
    formatDeliveryEvent(item.event),
    formatDeliveryError(item.error_message),
  ]
    .join(' ')
    .toLowerCase()
  return haystack.includes(needle)
}

export const NotificationCenterPage = memo(function NotificationCenterPage() {
  const now = useNow()
  const history = useLivePolling(getNotificationHistory, EVENTS)
  const statistics = useLivePolling(getNotificationCenterStatistics, EVENTS)
  const metrics = useLivePolling(getNotificationMetrics, EVENTS)
  const deliveryHistory = usePolling(getNotificationDeliveryHistory, { intervalMs: 0 })
  const [severity, setSeverity] = useState('all')
  const [source, setSource] = useState('all')
  const [readState, setReadState] = useState('all')
  const [agent, setAgent] = useState('all')
  const [date, setDate] = useState('')
  const [deliveryQuery, setDeliveryQuery] = useState('')
  const [deliveryStatus, setDeliveryStatus] = useState('all')
  const [deliveryEvent, setDeliveryEvent] = useState('all')
  const [deliveryChannel, setDeliveryChannel] = useState('all')
  const deliveryItems = useMemo(() => {
    return (deliveryHistory.data?.items ?? []).slice(0, MAX_DELIVERY_ROWS)
  }, [deliveryHistory.data])
  const filteredDeliveryItems = useMemo(() => {
    return deliveryItems.filter((item) =>
      matchesDeliveryFilters(item, deliveryQuery, deliveryStatus, deliveryEvent, deliveryChannel),
    )
  }, [deliveryChannel, deliveryEvent, deliveryItems, deliveryQuery, deliveryStatus])
  const items = useMemo(() => {
    return (history.data?.items ?? []).filter((item) => {
      if (severity !== 'all' && item.severity !== severity) {
        return false
      }
      if (source !== 'all' && item.source !== source) {
        return false
      }
      if (readState !== 'all' && item.read_state !== readState) {
        return false
      }
      if (agent !== 'all' && item.agent_id !== agent) {
        return false
      }
      if (date && !item.created_at.startsWith(date)) {
        return false
      }
      return true
    })
  }, [agent, date, history.data, readState, severity, source])
  const agents = useMemo(() => {
    const map = new Map<string, string>()
    for (const item of history.data?.items ?? []) {
      if (item.agent_id && item.agent_name) {
        map.set(item.agent_id, item.agent_name)
      }
    }
    return [...map.entries()]
  }, [history.data])
  const groups = useMemo(() => {
    const map = new Map<string, NotificationCenterItem[]>()
    for (const item of items) {
      const day = item.created_at.slice(0, 10)
      map.set(day, [...(map.get(day) ?? []), item])
    }
    return [...map.entries()]
  }, [items])
  const error = history.error || statistics.error || metrics.error
  const retry = () => {
    history.retry()
    statistics.retry()
    metrics.retry()
  }

  return (
    <section className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Monitoring</p>
          <h1 className={styles.title}>Notification Center</h1>
          <p className={styles.description}>Delivery metrics and history for notifications.</p>
        </div>
        <LastUpdated
          refreshing={history.isRefreshing || metrics.isRefreshing}
          value={metrics.lastUpdated ?? history.lastUpdated}
        />
      </header>
      {error ? <SectionError title="Notification center failed" onRetry={retry} /> : null}
      {!metrics.data && !error ? (
        <section className={styles.metricsCardGrid} aria-label="Loading notification metrics">
          {METRIC_SKELETON_LABELS.map((label) => (
            <article
              className={componentStyles.skeletonCard}
              key={label}
              aria-busy="true"
              aria-label={`Loading ${label}`}
            />
          ))}
        </section>
      ) : null}
      {metrics.data ? (
        <section className={styles.metricsCardGrid} aria-label="Notification delivery metrics">
          <StatCard label="Notifications Sent" value={metrics.data.total_sent} />
          <StatCard
            label="Success Rate"
            value={formatSuccessRate(metrics.data.success_rate)}
            meta={formatSuccessRateTrend(metrics.data.success_rate)}
            statusKind={metrics.data.success_rate >= 95 ? 'excellent' : 'warning'}
          />
          <StatCard
            label="Failed Notifications"
            value={metrics.data.total_failed}
            meta={formatFailedTrend(metrics.data.total_failed)}
            statusKind={metrics.data.total_failed === 0 ? 'good' : 'warning'}
          />
          <StatCard
            label="Average Delivery Time"
            value={formatAverageDelivery(metrics.data.average_duration_ms)}
            meta={formatDeliverySpeed(metrics.data.average_duration_ms)}
            statusKind={metrics.data.average_duration_ms <= 200 ? 'good' : 'warning'}
          />
          <StatCard
            label="Average Retry Count"
            value={formatAverageRetry(metrics.data.average_retry_count)}
            meta={formatRetryQuality(metrics.data.average_retry_count)}
            statusKind={metrics.data.average_retry_count <= 0.25 ? 'excellent' : 'warning'}
          />
          <StatCard
            label="Last Notification Time"
            value={formatLocalDateTime(metrics.data.last_notification_at)}
          />
        </section>
      ) : null}
      <section className={styles.deliveryHistory} aria-labelledby="delivery-history-heading">
        <h2 className={styles.sectionTitle} id="delivery-history-heading">
          Delivery History
        </h2>
        {deliveryHistory.error ? (
          <SectionError title="Delivery history failed" onRetry={deliveryHistory.retry} />
        ) : null}
        {!deliveryHistory.data && !deliveryHistory.error ? (
          <TableSkeleton label="Loading delivery history" />
        ) : null}
        {deliveryHistory.data && deliveryItems.length === 0 ? (
          <EmptyState message="No notification history yet." />
        ) : null}
        {deliveryHistory.data && deliveryItems.length > 0 ? (
          <>
            <section className={styles.deliveryFilterBar} aria-label="Delivery history filters">
              <p className={`${styles.filterField} ${styles.deliverySearchField}`}>
                <label htmlFor="delivery-search">Search</label>
                <input
                  className={componentStyles.searchInput}
                  id="delivery-search"
                  type="search"
                  value={deliveryQuery}
                  placeholder="Channel, event, or error"
                  onChange={(event) => setDeliveryQuery(event.target.value)}
                />
              </p>
              <p className={styles.filterField}>
                <label htmlFor="delivery-status">Status</label>
                <select
                  id="delivery-status"
                  value={deliveryStatus}
                  onChange={(event) => setDeliveryStatus(event.target.value)}
                >
                  <option value="all">All</option>
                  <option value="success">Success</option>
                  <option value="failed">Failed</option>
                </select>
              </p>
              <p className={styles.filterField}>
                <label htmlFor="delivery-event">Event</label>
                <select
                  id="delivery-event"
                  value={deliveryEvent}
                  onChange={(event) => setDeliveryEvent(event.target.value)}
                >
                  <option value="all">All</option>
                  <option value="activated">Activated</option>
                  <option value="recovered">Recovered</option>
                </select>
              </p>
              <p className={styles.filterField}>
                <label htmlFor="delivery-channel">Channel</label>
                <select
                  id="delivery-channel"
                  value={deliveryChannel}
                  onChange={(event) => setDeliveryChannel(event.target.value)}
                >
                  <option value="all">All</option>
                  <option value="telegram">Telegram</option>
                </select>
              </p>
            </section>
            <p className={styles.deliveryCount} aria-live="polite">
              Showing {filteredDeliveryItems.length} of {deliveryItems.length} notifications
            </p>
            {filteredDeliveryItems.length === 0 ? (
              <EmptyState message="No matching notifications." />
            ) : (
              <>
                <section className={styles.deliveryTableWrap} aria-label="Delivery history table">
                  <table className={styles.deliveryTable}>
                    <caption className={styles.visuallyHidden}>Notification delivery attempts</caption>
                    <thead>
                      <tr>
                        <th scope="col">Time</th>
                        <th scope="col">Channel</th>
                        <th scope="col">Event</th>
                        <th scope="col">Status</th>
                        <th scope="col">Retry</th>
                        <th scope="col">Duration</th>
                        <th scope="col">Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDeliveryItems.map((item, index) => {
                        const row = deliveryFields(item)
                        return (
                          <tr
                            key={`${item.id}-${item.created_at}-${item.retry_count}-${index}`}
                            tabIndex={0}
                            aria-label={`${row.time} ${row.channel} ${row.event} ${row.status}`}
                          >
                            <td>{row.time}</td>
                            <td>
                              <DeliveryBadge kind="channel" value={row.channelKey} label={row.channel} />
                            </td>
                            <td>
                              <DeliveryBadge kind="event" value={row.eventKey} label={row.event} />
                            </td>
                            <td>
                              <DeliveryBadge kind="status" value={row.statusKey} label={row.status} />
                            </td>
                            <td>{row.retry}</td>
                            <td>{row.duration}</td>
                            <td className={styles.deliveryError}>{row.error}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </section>
                <section className={styles.deliveryCardList} aria-label="Delivery history cards">
                  {filteredDeliveryItems.map((item, index) => {
                    const row = deliveryFields(item)
                    return (
                      <article
                        className={styles.deliveryCard}
                        key={`${item.id}-${item.created_at}-${item.retry_count}-card-${index}`}
                        tabIndex={0}
                        aria-label={`${row.time} ${row.channel} ${row.event} ${row.status}`}
                      >
                        <dl>
                          <div className={styles.deliveryCardRow}>
                            <dt>Time</dt>
                            <dd>{row.time}</dd>
                          </div>
                          <div className={styles.deliveryCardRow}>
                            <dt>Channel</dt>
                            <dd>
                              <DeliveryBadge kind="channel" value={row.channelKey} label={row.channel} />
                            </dd>
                          </div>
                          <div className={styles.deliveryCardRow}>
                            <dt>Event</dt>
                            <dd>
                              <DeliveryBadge kind="event" value={row.eventKey} label={row.event} />
                            </dd>
                          </div>
                          <div className={styles.deliveryCardRow}>
                            <dt>Status</dt>
                            <dd>
                              <DeliveryBadge kind="status" value={row.statusKey} label={row.status} />
                            </dd>
                          </div>
                          <div className={styles.deliveryCardRow}>
                            <dt>Retry</dt>
                            <dd>{row.retry}</dd>
                          </div>
                          <div className={styles.deliveryCardRow}>
                            <dt>Duration</dt>
                            <dd>{row.duration}</dd>
                          </div>
                          <div className={styles.deliveryCardRow}>
                            <dt>Error</dt>
                            <dd className={styles.deliveryError}>{row.error}</dd>
                          </div>
                        </dl>
                      </article>
                    )
                  })}
                </section>
              </>
            )}
          </>
        ) : null}
      </section>
      {!statistics.data && !error ? <OverviewSkeleton /> : null}
      {statistics.data ? (
        <section className={styles.statGrid} aria-label="Notification statistics">
          <StatCard label="Unread" value={statistics.data.unread} />
          <StatCard label="Today" value={statistics.data.today} />
          <StatCard label="This Week" value={statistics.data.this_week} />
          <StatCard label="Critical" value={statistics.data.critical} />
        </section>
      ) : null}
      <section className={styles.filterBar} aria-label="Notification filters">
        <p className={styles.filterField}>
          <label htmlFor="nc-severity">Severity</label>
          <select id="nc-severity" value={severity} onChange={(event) => setSeverity(event.target.value)}>
            <option value="all">all</option>
            <option value="critical">critical</option>
            <option value="warning">warning</option>
            <option value="info">info</option>
          </select>
        </p>
        <p className={styles.filterField}>
          <label htmlFor="nc-source">Source</label>
          <select id="nc-source" value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="all">all</option>
            <option value="telegram">telegram</option>
            <option value="discord">discord</option>
            <option value="slack">slack</option>
            <option value="email">email</option>
          </select>
        </p>
        <p className={styles.filterField}>
          <label htmlFor="nc-read">Read</label>
          <select id="nc-read" value={readState} onChange={(event) => setReadState(event.target.value)}>
            <option value="all">all</option>
            <option value="unread">unread</option>
            <option value="read">read</option>
          </select>
        </p>
        <p className={styles.filterField}>
          <label htmlFor="nc-agent">Agent</label>
          <select id="nc-agent" value={agent} onChange={(event) => setAgent(event.target.value)}>
            <option value="all">all</option>
            {agents.map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
        </p>
        <p className={styles.filterField}>
          <label htmlFor="nc-date">Date</label>
          <input id="nc-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </p>
      </section>
      {!history.data && !error ? <TableSkeleton label="Loading notifications" /> : null}
      {history.data && items.length === 0 ? <EmptyState message="No notifications yet." /> : null}
      {groups.map(([day, dayItems]) => (
        <section className={styles.section} key={day} aria-label={`Notifications ${day}`}>
          <h2 className={styles.sectionTitle}>{day}</h2>
          <ol className={styles.timelineList} aria-label="Notification timeline">
            {dayItems.map((item) => (
              <li className={styles.timelineItem} key={item.id}>
                <Icon name={item.kind === 'backup' ? 'backup' : 'notification'} />
                <StatusBadge kind="lifecycle" status={item.read_state === 'read' ? 'recovered' : 'active'} />
                <p className={styles.timelineKind}>{item.severity}</p>
                <p className={styles.timelineMessage}>{item.title}</p>
                <p className={styles.timelineTime}>{item.description}</p>
                <p className={styles.timelineTime}>
                  {item.agent_name ?? 'system'} · {item.source} · <RelativeTime now={now} value={item.created_at} />
                </p>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </section>
  )
})
