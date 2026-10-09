import { memo } from 'react'
import { cacheStatusLabel, serviceWorkerLabel } from '../pwa/manifest'
import { usePwa } from '../pwa/PwaProvider'
import { StatCard } from './StatCard'
import pageStyles from '../pages/Pages.module.css'
import styles from '../pages/SettingsPage.module.css'
import userStyles from '../pages/UsersPage.module.css'

export const PwaSettingsCard = memo(function PwaSettingsCard() {
  const pwa = usePwa()

  return (
    <section className={styles.reportsSection} aria-labelledby="application-title">
      <h2 className={styles.channelTitle} id="application-title">
        Application
      </h2>
      <p className={styles.channelHint}>Install and update HomeLab Monitor on this device.</p>
      <section className={pageStyles.remoteAccessGrid} aria-label="Application status">
        <StatCard label="Display" value={pwa.installed ? 'Installed' : 'Browser'} />
        <StatCard label="Installed" value={pwa.installed ? 'Yes' : 'No'} />
        <StatCard label="Service Worker" value={serviceWorkerLabel(pwa.serviceWorker === 'registered')} />
        <StatCard label="Cache Status" value={cacheStatusLabel(pwa.cacheReady)} />
        <StatCard label="Version" value={pwa.version} />
        <StatCard label="Update Available" value={pwa.updateAvailable ? 'Yes' : 'No'} />
      </section>
      <div className={pageStyles.remoteAccessActions}>
        {pwa.installed ? null : (
          <button
            className={userStyles.secondaryButton}
            disabled={!pwa.canInstall}
            type="button"
            onClick={() => void pwa.install()}
          >
            Install
          </button>
        )}
        <button className={userStyles.secondaryButton} type="button" onClick={() => void pwa.checkForUpdate()}>
          Check for Update
        </button>
        <button className={userStyles.secondaryButton} type="button" onClick={() => void pwa.clearCache()}>
          Clear Cache
        </button>
      </div>
    </section>
  )
})
