import { memo } from 'react'
import { StatCard } from './StatCard'
import type { RemoteAccess } from '../types/dashboard'
import styles from '../pages/Pages.module.css'
import userStyles from '../pages/UsersPage.module.css'

function remoteDashboardUrl(hostname: string | null | undefined): string | null {
  if (!hostname) {
    return null
  }
  return `https://${hostname}`
}

function remoteConnectionLabel(status: RemoteAccess['status']): string {
  if (status === 'connected') {
    return 'Connected'
  }
  if (status === 'unknown') {
    return 'Unknown'
  }
  return 'Disconnected'
}

function onOff(value: boolean): string {
  return value ? 'Enabled' : 'Disabled'
}

export const RemoteAccessCard = memo(function RemoteAccessCard({
  access,
  showActions = false,
  onCopy,
  onOpen,
}: {
  access: RemoteAccess
  showActions?: boolean
  onCopy?: (url: string) => void
  onOpen?: (url: string) => void
}) {
  const url = remoteDashboardUrl(access.hostname)
  const connection = remoteConnectionLabel(access.status)

  return (
    <section className={styles.section} aria-labelledby="remote-access-title">
      <h2 className={styles.sectionTitle} id="remote-access-title">
        Remote Access
      </h2>
      <section className={styles.remoteAccessGrid} aria-label="Remote access status">
        <StatCard label="Connection" value={connection} />
        <StatCard label="Provider" value={access.provider || 'tailscale'} />
        <StatCard label="Hostname" value={access.hostname ?? '—'} />
        <StatCard label="Dashboard Public URL" value={url ?? '—'} />
        <StatCard label="HTTPS" value={onOff(access.https)} />
        <StatCard label="Serve" value={onOff(access.serve_enabled)} />
        <StatCard label="Funnel" value={onOff(access.funnel_enabled)} />
        <StatCard label="Public Exposure" value={access.public ? 'Yes' : 'No'} />
        <StatCard label="Tailnet IP" value={access.tailnet_ip ?? '—'} />
      </section>
      {showActions ? (
        <div className={styles.remoteAccessActions}>
          <button
            className={userStyles.secondaryButton}
            disabled={!url}
            type="button"
            onClick={() => url && onCopy?.(url)}
          >
            Copy URL
          </button>
          <button
            className={userStyles.secondaryButton}
            disabled={!url}
            type="button"
            onClick={() => url && onOpen?.(url)}
          >
            Open Dashboard
          </button>
        </div>
      ) : null}
    </section>
  )
})
