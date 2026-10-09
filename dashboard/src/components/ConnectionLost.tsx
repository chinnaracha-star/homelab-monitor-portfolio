import { memo } from 'react'
import styles from './Components.module.css'

interface ConnectionLostProps {
  onRetry: () => void
}

export const ConnectionLost = memo(function ConnectionLost({ onRetry }: ConnectionLostProps) {
  return (
    <section className={styles.error} role="alert">
      <div>
        <p className={styles.errorTitle}>Connection lost</p>
        <p className={styles.errorMessage}>The dashboard could not reach the monitoring API.</p>
        <button className={styles.retryButton} type="button" onClick={onRetry} aria-label="Retry">
          Retry
        </button>
      </div>
    </section>
  )
})
