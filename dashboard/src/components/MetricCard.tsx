import { memo } from 'react'
import type { MetricLevel } from '../utils/metrics'
import styles from './Components.module.css'

interface MetricCardProps {
  title: string
  value: string
  unit?: string
  subtitle?: string
  level?: MetricLevel
}

const levelClassName = {
  normal: styles.metricNormal,
  warning: styles.metricWarning,
  critical: styles.metricCritical,
  unknown: undefined,
}

export const MetricCard = memo(function MetricCard({
  title,
  value,
  unit,
  subtitle,
  level = 'unknown',
}: MetricCardProps) {
  return (
    <article
      className={`${styles.metricCard} ${levelClassName[level] ?? ''}`.trim()}
      aria-label={`${title} ${value}${unit ? ` ${unit}` : ''}`}
    >
      <h3 className={styles.metricLabel}>{title}</h3>
      <p className={styles.metricValueRow}>
        <span className={`${styles.metricValue} ${styles.valuePulse}`} key={value}>
          {value}
        </span>
        {unit ? <span className={styles.metricUnit}>{unit}</span> : null}
      </p>
      {subtitle ? <p className={styles.metricDetail}>{subtitle}</p> : null}
    </article>
  )
})
