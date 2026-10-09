import { memo } from 'react'
import styles from './Components.module.css'

interface SkeletonBlockProps {
  className: string
  label: string
}

function SkeletonBlock({ className, label }: SkeletonBlockProps) {
  return <div className={className} aria-busy="true" aria-label={label} role="status" />
}

export const OverviewSkeleton = memo(function OverviewSkeleton() {
  return (
    <section className={styles.skeletonGrid} aria-label="Loading overview">
      {['Total Agents', 'Online', 'Offline', 'Total Reports', 'Total Groups'].map((label) => (
        <SkeletonBlock className={styles.skeletonCard} key={label} label={`Loading ${label}`} />
      ))}
    </section>
  )
})

export const TableSkeleton = memo(function TableSkeleton({
  label = 'Loading agents',
}: {
  label?: string
}) {
  return (
    <section className={styles.tableWrapper} aria-busy="true" aria-label={label}>
      <div className={styles.skeletonTable}>
        {Array.from({ length: 5 }, (_, index) => (
          <div className={styles.skeletonRow} key={index} />
        ))}
      </div>
    </section>
  )
})

export const MetricSkeleton = memo(function MetricSkeleton() {
  return (
    <section className={styles.skeletonMetricGrid} aria-label="Loading metrics">
      {Array.from({ length: 6 }, (_, index) => (
        <SkeletonBlock className={styles.skeletonCard} key={index} label="Loading metric" />
      ))}
    </section>
  )
})

export const ChartSkeleton = memo(function ChartSkeleton() {
  return (
    <section className={styles.skeletonChartGrid} aria-label="Loading history">
      {Array.from({ length: 4 }, (_, index) => (
        <SkeletonBlock className={styles.skeletonChart} key={index} label="Loading chart" />
      ))}
    </section>
  )
})
