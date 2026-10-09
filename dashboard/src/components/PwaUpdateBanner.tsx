import { memo } from 'react'
import { useOptionalPwa } from '../pwa/PwaProvider'
import styles from './Components.module.css'
import userStyles from '../pages/UsersPage.module.css'

export const PwaUpdateBanner = memo(function PwaUpdateBanner() {
  const pwa = useOptionalPwa()
  if (!pwa?.updateAvailable) {
    return null
  }

  return (
    <section className={styles.updateBanner} role="status">
      <div>
        <p className={styles.realtimeBannerTitle}>Update Available</p>
        <p className={styles.realtimeBannerMessage}>A newer version of HomeLab Monitor is ready.</p>
      </div>
      <div className={styles.bannerActions}>
        <button className={userStyles.primaryButton} type="button" onClick={() => void pwa.applyUpdate()}>
          Reload
        </button>
        <button className={userStyles.secondaryButton} type="button" onClick={pwa.dismissUpdate}>
          Dismiss
        </button>
      </div>
    </section>
  )
})
