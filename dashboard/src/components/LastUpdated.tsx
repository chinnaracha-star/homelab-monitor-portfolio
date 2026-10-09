import { memo } from 'react'
import { formatThaiDateTime } from '../utils/thaiDate'
import styles from './Components.module.css'

interface LastUpdatedProps {
  value: Date | null
  refreshing: boolean
}

export const LastUpdated = memo(function LastUpdated({ value, refreshing }: LastUpdatedProps) {
  if (!value && !refreshing) {
    return null
  }

  return (
    <p className={styles.lastUpdated} aria-live="polite">
      {value ? (
        <>
          <span>Last updated:</span>
          <time className={styles.thaiStamp} dateTime={value.toISOString()}>
            {formatThaiDateTime(value)}
          </time>
        </>
      ) : null}
      {refreshing ? (
        <>
          <span className={styles.refreshSpinner} aria-hidden="true" />
          <span className={styles.refreshingLabel} role="status">
            Refreshing...
          </span>
        </>
      ) : (
        <span className={styles.refreshSuccess} role="status" aria-label="Refresh succeeded">
          ✓
        </span>
      )}
    </p>
  )
})
