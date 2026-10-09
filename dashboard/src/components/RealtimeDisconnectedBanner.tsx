import { memo } from 'react'
import styles from './Components.module.css'

export const RealtimeDisconnectedBanner = memo(function RealtimeDisconnectedBanner() {
  return (
    <section className={styles.realtimeBanner} role="status">
      <p className={styles.realtimeBannerTitle}>Realtime disconnected</p>
      <p className={styles.realtimeBannerMessage}>
        Showing the last loaded data. The dashboard is retrying automatically and will
        resume live updates when the connection returns.
      </p>
    </section>
  )
})
