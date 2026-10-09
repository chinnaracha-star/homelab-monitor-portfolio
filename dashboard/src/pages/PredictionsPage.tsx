import { memo } from 'react'
import {
  getPredictionsBackup,
  getPredictionsOverview,
  getPredictionsPhotos,
  getPredictionsStorage,
  getPredictionsSystem,
} from '../api/dashboard'
import { AnalyticsLineChart } from '../components/AnalyticsCharts'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { ChartSkeleton, OverviewSkeleton } from '../components/Skeleton'
import { SectionError } from '../components/SectionError'
import { StatCard } from '../components/StatCard'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { SERVICE_COLORS } from '../utils/colors'
import styles from './Pages.module.css'

const EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

export const PredictionsPage = memo(function PredictionsPage() {
  const overview = useLivePolling(getPredictionsOverview, EVENTS)
  const storage = useLivePolling(getPredictionsStorage, EVENTS)
  const system = useLivePolling(getPredictionsSystem, EVENTS)
  const photos = useLivePolling(getPredictionsPhotos, EVENTS)
  const backup = useLivePolling(getPredictionsBackup, EVENTS)
  const sections = [overview, storage, system, photos, backup]
  const error = sections.find((section) => section.error)?.error ?? null
  const retry = () => {
    for (const section of sections) {
      section.retry()
    }
  }

  return (
    <section className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Analytics</p>
          <h1 className={styles.title}>Predictive Alerting</h1>
          <p className={styles.description}>Rule-based forecasts from trends and capacity planning.</p>
        </div>
        <LastUpdated refreshing={overview.isRefreshing} value={overview.lastUpdated} />
      </header>
      {error ? <SectionError title="Predictions failed" onRetry={retry} /> : null}
      {!overview.data && !error ? <OverviewSkeleton /> : null}
      {overview.data ? (
        <>
          <section className={styles.statGrid} aria-label="Forecast cards">
            <StatCard label="Overall Risk" value={overview.data.overall_risk} />
            <StatCard label="Storage Forecast" value={overview.data.storage.risk} />
            <StatCard label="CPU Forecast" value={overview.data.system.risk} />
            <StatCard label="Memory Forecast" value={overview.data.system.risk} />
            <StatCard label="Backup Forecast" value={overview.data.backup.risk} />
            <StatCard label="Photo Forecast" value={overview.data.photos.risk} />
          </section>
          <section className={styles.section} aria-labelledby="prediction-rec-title">
            <h2 className={styles.sectionTitle} id="prediction-rec-title">
              Recommendations
            </h2>
            {overview.data.recommendations.length === 0 ? (
              <EmptyState message="No predictions yet." />
            ) : (
              <ul className={styles.timelineList} aria-label="Recommendations">
                {overview.data.recommendations.map((item) => (
                  <li className={styles.timelineItem} key={item}>
                    {item}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}
      {!storage.data && !error ? <ChartSkeleton /> : null}
      {storage.data || system.data || photos.data || backup.data ? (
        <section className={styles.chartGrid} aria-label="Forecast charts">
          {storage.data ? (
            <AnalyticsLineChart
              title="Storage Forecast"
              series={storage.data.series}
              color={SERVICE_COLORS.storage}
              unit="B"
            />
          ) : null}
          {system.data ? (
            <AnalyticsLineChart
              title="CPU Forecast"
              series={system.data.series}
              color={SERVICE_COLORS.cpu}
              unit="%"
            />
          ) : null}
          {photos.data ? (
            <AnalyticsLineChart
              title="Photo Forecast"
              series={photos.data.series}
              color={SERVICE_COLORS.immich}
              unit="B"
            />
          ) : null}
          {backup.data ? (
            <AnalyticsLineChart
              title="Backup Forecast"
              series={backup.data.series}
              color={SERVICE_COLORS.backup}
              unit="B"
            />
          ) : null}
        </section>
      ) : null}
    </section>
  )
})
