import { memo } from 'react'
import {
  getCapacityBackup,
  getCapacityOverview,
  getCapacityPhotos,
  getCapacityStorage,
  getCapacitySystem,
} from '../api/dashboard'
import {
  AnalyticsBarChart,
  AnalyticsGaugeChart,
  AnalyticsLineChart,
} from '../components/AnalyticsCharts'
import { ChartSkeleton, OverviewSkeleton } from '../components/Skeleton'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { StatCard } from '../components/StatCard'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { formatBytes } from '../utils/bytes'
import { SERVICE_COLORS } from '../utils/colors'
import { formatThaiDate } from '../utils/thaiDate'
import styles from './Pages.module.css'

const CAPACITY_EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

function remainingLabel(days: number | null): string {
  if (days == null) {
    return '—'
  }
  return `${days} days`
}

export const CapacityPage = memo(function CapacityPage() {
  const overview = useLivePolling(getCapacityOverview, CAPACITY_EVENTS)
  const storage = useLivePolling(getCapacityStorage, CAPACITY_EVENTS)
  const photos = useLivePolling(getCapacityPhotos, CAPACITY_EVENTS)
  const backup = useLivePolling(getCapacityBackup, CAPACITY_EVENTS)
  const system = useLivePolling(getCapacitySystem, CAPACITY_EVENTS)
  const sections = [overview, storage, photos, backup, system]
  const isRefreshing = sections.some((section) => section.isRefreshing)
  const lastUpdated =
    sections
      .map((section) => section.lastUpdated)
      .filter((value): value is Date => value !== null)
      .sort((left, right) => right.getTime() - left.getTime())[0] ?? null
  const hasError = sections.some((section) => section.error)
  const retryAll = () => {
    for (const section of sections) {
      section.retry()
    }
  }

  return (
    <section className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Read-only forecasts</p>
          <h1 className={styles.title}>Capacity Planning</h1>
          <p className={styles.description}>
            Storage, photo, and backup projections with an overall capacity score.
          </p>
        </div>
        <LastUpdated refreshing={isRefreshing} value={lastUpdated} />
      </header>

      <section className={styles.section} aria-labelledby="capacity-cards-title">
        <h2 className={styles.sectionTitle} id="capacity-cards-title">
          Summary
        </h2>
        {overview.error ? (
          <SectionError title="Capacity overview failed" onRetry={overview.retry} />
        ) : null}
        {!overview.data && !overview.error ? <OverviewSkeleton /> : null}
        {overview.data ? (
          <section className={styles.statGrid} aria-label="Capacity summary">
            <StatCard
              label="Storage Remaining"
              value={remainingLabel(overview.data.storage_remaining_days)}
            />
            <StatCard
              label="Estimated Full Date"
              value={overview.data.estimated_full_date ? formatThaiDate(overview.data.estimated_full_date) : '—'}
            />
            <StatCard label="Growth Per Day" value={`+${formatBytes(overview.data.growth_per_day)}/day`} />
            <StatCard label="Photo Forecast" value={overview.data.photo_forecast} />
            <StatCard label="Backup Forecast" value={overview.data.backup_forecast || '—'} />
            <StatCard label="Capacity Score" value={overview.data.capacity_score} />
          </section>
        ) : null}
      </section>

      <section className={styles.section} aria-labelledby="capacity-recommendations-title">
        <h2 className={styles.sectionTitle} id="capacity-recommendations-title">
          Recommendations
        </h2>
        {overview.data && overview.data.recommendations.length === 0 ? (
          <EmptyState message="No capacity recommendations yet." />
        ) : null}
        {overview.data && overview.data.recommendations.length > 0 ? (
          <ul className={styles.recommendationList}>
            {overview.data.recommendations.map((item) => (
              <li className={styles.recommendationItem} key={item}>
                {item}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className={styles.section} aria-labelledby="capacity-charts-title">
        <h2 className={styles.sectionTitle} id="capacity-charts-title">
          Charts
        </h2>
        {hasError ? <SectionError title="Capacity charts failed" onRetry={retryAll} /> : null}
        {!storage.data && !hasError ? <ChartSkeleton /> : null}
        <section className={styles.chartGrid} aria-label="Capacity charts">
          {storage.data ? (
            <AnalyticsLineChart
              title="Storage Projection"
              series={storage.data.series}
              color={SERVICE_COLORS.storage}
              unit="%"
            />
          ) : null}
          {photos.data ? (
            <AnalyticsBarChart title="Photo Projection" series={photos.data.series} color={SERVICE_COLORS.photos} />
          ) : null}
          {backup.data ? (
            <AnalyticsBarChart title="Backup Growth" series={backup.data.series} color={SERVICE_COLORS.backup} />
          ) : null}
          {overview.data ? (
            <AnalyticsGaugeChart title="Capacity Score Gauge" score={overview.data.capacity_score} />
          ) : null}
        </section>
      </section>
    </section>
  )
})
