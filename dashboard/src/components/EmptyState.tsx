import { memo } from 'react'
import styles from './Components.module.css'

interface EmptyStateProps {
  message: string
}

export const EmptyState = memo(function EmptyState({ message }: EmptyStateProps) {
  return (
    <section className={styles.emptyState} role="status">
      <p>{message}</p>
    </section>
  )
})
