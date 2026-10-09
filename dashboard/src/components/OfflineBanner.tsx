import { memo } from 'react'
import { formatThaiDateTime } from '../utils/thaiDate'
import { useOptionalPwa } from '../pwa/PwaProvider'
import styles from './Components.module.css'

export const OfflineBanner = memo(function OfflineBanner({
  lastUpdated = null,
  cached = false,
}: {
  lastUpdated?: Date | null
  cached?: boolean
}) {
  const pwa = useOptionalPwa()
  if (!pwa?.offline && !cached) {
    return null
  }

  return (
    <section className={styles.offlineBanner} role="status" aria-label="Offline status">
      <p className={styles.realtimeBannerTitle}>Offline</p>
      <p className={styles.realtimeBannerMessage}>Last Updated</p>
      <p className={styles.realtimeBannerMessage}>
        {lastUpdated ? formatThaiDateTime(lastUpdated, false) : 'Never'}
      </p>
      <p className={styles.realtimeBannerMessage}>Cached Data</p>
    </section>
  )
})
