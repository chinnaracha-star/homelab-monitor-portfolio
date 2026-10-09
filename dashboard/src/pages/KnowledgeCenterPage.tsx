import { memo, useMemo, useState, type FormEvent } from 'react'
import { exportKnowledge, getKnowledge } from '../api/dashboard'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { OverviewSkeleton } from '../components/Skeleton'
import { SectionError } from '../components/SectionError'
import { LIVE_PAGE_POLL } from '../constants'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { formatThaiDateTime } from '../utils/thaiDate'
import styles from './Pages.module.css'

const EVENTS = ['overview_updated', 'alert_updated'] as const
const KINDS = ['all', 'incident', 'maintenance', 'system', 'backup', 'photo', 'telegram'] as const

export const KnowledgeCenterPage = memo(function KnowledgeCenterPage() {
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState<(typeof KINDS)[number]>('all')
  const loader = useMemo(() => () => getKnowledge(query, kind), [query, kind])
  const snapshot = useLivePolling(loader, EVENTS, LIVE_PAGE_POLL)
  const items = snapshot.data?.items ?? []

  async function onExport() {
    const blob = await exportKnowledge(query, kind)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'knowledge-center.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  function onFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    snapshot.retry()
  }

  return (
    <section className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Platform</p>
          <h1 className={styles.title}>Knowledge Center</h1>
          <p className={styles.description}>
            Timeline of alerts, backups, operations, photos, and Telegram history.
          </p>
        </div>
        <LastUpdated refreshing={snapshot.isRefreshing} value={snapshot.lastUpdated} />
      </header>

      <form className={styles.knowledgeToolbar} onSubmit={onFilter}>
        <label>
          Search
          <input
            aria-label="Search knowledge"
            onChange={(event) => setQuery(event.target.value)}
            type="search"
            value={query}
          />
        </label>
        <label>
          Filter
          <select
            aria-label="Filter knowledge kind"
            onChange={(event) => setKind(event.target.value as (typeof KINDS)[number])}
            value={kind}
          >
            {KINDS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <button type="submit">Apply</button>
        <button type="button" onClick={() => void onExport()}>
          Export
        </button>
      </form>

      {snapshot.error ? <SectionError title="Knowledge Center failed" onRetry={snapshot.retry} /> : null}
      {!snapshot.data && !snapshot.error ? <OverviewSkeleton /> : null}
      {snapshot.data && items.length === 0 ? <EmptyState message="No knowledge items match the current filters." /> : null}
      {items.length > 0 ? (
        <ol className={styles.timelineList} aria-label="Knowledge timeline">
          {items.map((item) => (
            <li className={styles.timelineItem} key={`${item.kind}-${item.timestamp}-${item.title}`}>
              <p className={styles.timelineKind}>{item.kind}</p>
              <p className={styles.timelineMessage}>{item.title}</p>
              <p className={styles.timelineTime}>{item.timestamp ? formatThaiDateTime(item.timestamp, false) : '—'}</p>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  )
})
