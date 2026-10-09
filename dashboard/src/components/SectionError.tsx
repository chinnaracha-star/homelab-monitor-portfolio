import { memo } from 'react'
import styles from './Components.module.css'

interface SectionErrorProps {
  title?: string
  message?: string
  onRetry: () => void
}

export const SectionError = memo(function SectionError({
  title = 'Unable to load this section',
  message = 'The request failed. Other dashboard sections remain available.',
  onRetry,
}: SectionErrorProps) {
  return (
    <section className={styles.sectionError} role="alert">
      <p className={styles.errorTitle}>{title}</p>
      <p className={styles.errorMessage}>{message}</p>
      <button className={styles.retryButton} type="button" onClick={onRetry} aria-label="Retry section">
        Retry
      </button>
    </section>
  )
})
