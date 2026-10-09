import { getPhotoEvents, getPhotoMonitorStats } from '../api/dashboard'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { OverviewSkeleton } from '../components/Skeleton'
import { StatCard } from '../components/StatCard'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { formatBytes } from '../utils/bytes'
import { displayFolderName, watchFolderList } from '../utils/photoFolders'
import { formatThaiDateTime, formatThaiTime } from '../utils/thaiDate'
import componentStyles from '../components/Components.module.css'
import userStyles from './UsersPage.module.css'
import pageStyles from './Pages.module.css'

const EVENTS = ['overview_updated'] as const

export function PhotoMonitorPage() {
  const stats = useLivePolling(getPhotoMonitorStats, EVENTS)
  const events = useLivePolling(() => getPhotoEvents(20), EVENTS)
  const items = events.data?.items ?? []
  const folders = stats.data ? watchFolderList(stats.data) : []
  const labels = stats.data?.watch_folder_labels?.length
    ? stats.data.watch_folder_labels
    : folders.map(displayFolderName)

  return (
    <section className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <div>
          <p className={pageStyles.eyebrow}>Operations</p>
          <h1 className={pageStyles.title}>Photo Monitor</h1>
          <p className={pageStyles.description}>
            Detects new image files in the configured NAS folders. No AI analysis and no
            CCTV integration. Configure watch folders in Settings.
          </p>
        </div>
        <div className={userStyles.actions}>
          <LastUpdated
            refreshing={stats.isRefreshing || events.isRefreshing}
            value={stats.lastUpdated}
          />
          <button
            className={userStyles.secondaryButton}
            type="button"
            onClick={() => {
              stats.retry()
              events.retry()
            }}
          >
            Retry all
          </button>
        </div>
      </header>
      {stats.error ? <SectionError title="Photo Monitor stats failed" onRetry={stats.retry} /> : null}
      {events.error ? <SectionError title="Photo events failed" onRetry={events.retry} /> : null}
      {!stats.data && !stats.error ? <OverviewSkeleton /> : null}
      {stats.data ? (
        <>
          <section className={pageStyles.statGrid} aria-label="Photo Monitor summary">
            <StatCard
              label="Status"
              value={stats.data.enabled ? '🟢 Running' : 'Stopped'}
            />
            <StatCard
              label="Watching"
              value={`${folders.length} folder${folders.length === 1 ? '' : 's'}`}
            />
            <StatCard label="Today's Photos" value={stats.data.today_count} />
            <StatCard label="Last Photo" value={stats.data.last_photo ?? '—'} />
            <StatCard label="Last Folder" value={stats.data.last_folder ?? '—'} />
            <StatCard
              label="Last Update"
              value={stats.data.last_update ? formatThaiTime(stats.data.last_update, false) : '—'}
            />
            <StatCard
              label="Indexed Files"
              value={`${(stats.data.indexed_files ?? 0).toLocaleString()} files indexed`}
            />
          </section>
          <section className={pageStyles.section} aria-labelledby="photo-monitor-folders-title">
            <h2 className={pageStyles.sectionTitle} id="photo-monitor-folders-title">
              Folders
            </h2>
            <ul className={pageStyles.folderList}>
              {labels.map((label) => (
                <li key={label}>
                  <p className={pageStyles.folderChip}>{label}</p>
                </li>
              ))}
            </ul>
          </section>
        </>
      ) : null}
      <section className={pageStyles.section} aria-labelledby="recent-photos-title">
        <h2 className={pageStyles.sectionTitle} id="recent-photos-title">
          Recent Photos
        </h2>
        {items.length === 0 && events.data ? (
          <EmptyState message="No photo events yet. Enable Photo Monitor in Settings and add an image to the watch folder." />
        ) : null}
        {items.length > 0 ? (
          <div className={componentStyles.tableWrapper}>
            <table className={componentStyles.table}>
              <caption className={pageStyles.srOnly}>Latest 20 photo events</caption>
              <thead>
                <tr>
                  <th scope="col">File</th>
                  <th scope="col">Folder</th>
                  <th scope="col">Size</th>
                  <th scope="col">Time</th>
                  <th scope="col">Telegram</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.filename}</td>
                    <td>{displayFolderName(item.folder)}</td>
                    <td>{formatBytes(item.size_bytes)}</td>
                    <td>{formatThaiDateTime(item.created_at, false)}</td>
                    <td>{item.telegram_sent ? 'Sent' : 'Not sent'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </section>
  )
}
