import { useState } from 'react'
import { getNotifications, retryNotification, sendTestNotification } from '../api/dashboard'
import { useCan } from '../auth/useCan'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { TableSkeleton } from '../components/Skeleton'
import { StatusBadge } from '../components/StatusBadge'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { getErrorMessage } from '../utils/errors'
import { formatThaiDateTime } from '../utils/thaiDate'
import componentStyles from '../components/Components.module.css'
import userStyles from './UsersPage.module.css'
import pageStyles from './Pages.module.css'

const NOTIFY_EVENTS = ['overview_updated', 'alert_updated'] as const

export function NotificationsPage() {
  const canSend = useCan()('send_notifications')
  const notifications = useLivePolling(getNotifications, NOTIFY_EVENTS)
  const [toast, setToast] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleRetry(notificationId: string) {
    setError(null)
    try {
      await retryNotification(notificationId)
      setToast('Notification retried.')
      notifications.retry()
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    }
  }

  async function handleTest() {
    setError(null)
    try {
      await sendTestNotification()
      setToast('Test notification sent.')
      notifications.retry()
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    }
  }

  const rows = notifications.data?.notifications ?? []

  return (
    <section className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <div>
          <p className={pageStyles.eyebrow}>Operations</p>
          <h1 className={pageStyles.title}>Notifications</h1>
          <p className={pageStyles.description}>Delivery history for alert notifications.</p>
        </div>
        <div className={userStyles.actions}>
          <LastUpdated refreshing={notifications.isRefreshing} value={notifications.lastUpdated} />
          {canSend ? (
            <button className={userStyles.primaryButton} type="button" onClick={() => void handleTest()}>
              Send test
            </button>
          ) : null}
        </div>
      </header>
      {toast ? (
        <p className={userStyles.toast} role="status">
          {toast}
        </p>
      ) : null}
      {error ? (
        <p className={userStyles.formError} role="alert">
          {error}
        </p>
      ) : null}
      {notifications.error ? (
        <SectionError title="Notifications API failed" onRetry={notifications.retry} />
      ) : null}
      {!notifications.data && !notifications.error ? (
        <TableSkeleton label="Loading notifications" />
      ) : null}
      {notifications.data && rows.length === 0 ? <EmptyState message="No notifications yet." /> : null}
      {rows.length > 0 ? (
        <section className={componentStyles.tableWrapper}>
          <table className={componentStyles.table} aria-label="Notification deliveries">
            <thead>
              <tr>
                <th scope="col">Channel</th>
                <th scope="col">Recipient</th>
                <th scope="col">Status</th>
                <th scope="col">Error</th>
                <th scope="col">Sent</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((item) => (
                <tr key={item.id}>
                  <td>{item.channel}</td>
                  <td>{item.recipient}</td>
                  <td>
                    <StatusBadge
                      status={
                        item.status === 'sent' ? 'online' : item.status === 'failed' ? 'offline' : 'registered'
                      }
                    />
                  </td>
                  <td>{item.error_message || '—'}</td>
                  <td>{item.sent_at ? formatThaiDateTime(item.sent_at, false) : '—'}</td>
                  <td>
                    {canSend && item.status === 'failed' ? (
                      <button
                        className={userStyles.secondaryButton}
                        type="button"
                        onClick={() => void handleRetry(item.id)}
                      >
                        Retry
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </section>
  )
}
