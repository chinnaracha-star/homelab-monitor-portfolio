import { memo } from 'react'
import {
  getTrendsBackup,
  getTrendsCpu,
  getTrendsMemory,
  getTrendsOverview,
  getTrendsPhotos,
  getTrendsStorage,
} from '../api/dashboard'
import {
  AnalyticsBarChart,
  AnalyticsLineChart,
  AnalyticsPieChart,
} from '../components/AnalyticsCharts'
import { ChartSkeleton, OverviewSkeleton } from '../components/Skeleton'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { StatCard } from '../components/StatCard'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { formatBytes, formatDuration, formatPercent } from '../utils/bytes'
import { SERVICE_COLORS } from '../utils/colors'
import styles from './Pages.module.css'

const TREND_EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

function trendLabel(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export const TrendsPage = memo(function TrendsPage() {
  const overview = useLivePolling(getTrendsOverview, TREND_EVENTS)
  const cpu = useLivePolling(getTrendsCpu, TREND_EVENTS)
  const memory = useLivePolling(getTrendsMemory, TREND_EVENTS)
  const storage = useLivePolling(getTrendsStorage, TREND_EVENTS)
  const photos = useLivePolling(getTrendsPhotos, TREND_EVENTS)
  const backup = useLivePolling(getTrendsBackup, TREND_EVENTS)
  const sections = [overview, cpu, memory, storage, photos, backup]
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
          <p className={styles.eyebrow}>Read-only analysis</p>
          <h1 className={styles.title}>Trend Analysis</h1>
          <p className={styles.description}>Period comparisons, linear forecasts, and health scores.</p>
        </div>
        <LastUpdated refreshing={isRefreshing} value={lastUpdated} />
      </header>

      <section className={styles.section} aria-labelledby="trend-cards-title">
        <h2 className={styles.sectionTitle} id="trend-cards-title">
          Summary
        </h2>
        {overview.error ? <SectionError title="Trend overview failed" onRetry={overview.retry} /> : null}
        {!overview.data && !overview.error ? <OverviewSkeleton /> : null}
        {overview.data ? (
          <section className={styles.statGrid} aria-label="Trend summary">
            <StatCard label="CPU Trend" value={trendLabel(overview.data.cpu_trend)} />
            <StatCard label="Memory Trend" value={trendLabel(overview.data.memory_trend)} />
            <StatCard label="Storage Forecast" value={trendLabel(overview.data.storage_trend)} />
            <StatCard label="Photo Growth" value={trendLabel(overview.data.photo_trend)} />
            <StatCard label="Backup Trend" value={trendLabel(overview.data.backup_trend)} />
            <StatCard
              label="Infrastructure Health"
              value={`${overview.data.health.healthy_count} healthy`}
            />
            <StatCard label="Overall Score" value={overview.data.overall_score} />
          </section>
        ) : null}
      </section>

      <section className={styles.section} aria-labelledby="trend-forecast-title">
        <h2 className={styles.sectionTitle} id="trend-forecast-title">
          Forecast
        </h2>
        {storage.data && photos.data && backup.data ? (
          <section className={styles.statGrid} aria-label="Forecast">
            <StatCard
              label="Storage"
              value={
                storage.data.used_percent == null ? '—' : formatPercent(storage.data.used_percent)
              }
            />
            <StatCard label="Growth / day" value={`+${formatBytes(storage.data.growth_per_day)}/day`} />
            <StatCard
              label="Estimated Full"
              value={
                storage.data.estimated_days_until_full == null
                  ? '—'
                  : `${storage.data.estimated_days_until_full} days`
              }
            />
            <StatCard label="Expected photos next week" value={photos.data.expected_next_week} />
            <StatCard
              label="Expected completion time"
              value={
                backup.data.expected_completion_seconds == null
                  ? '—'
                  : formatDuration(backup.data.expected_completion_seconds)
              }
            />
          </section>
        ) : null}
      </section>

      <section className={styles.section} aria-labelledby="trend-charts-title">
        <h2 className={styles.sectionTitle} id="trend-charts-title">
          Charts
        </h2>
        {hasError ? <SectionError title="Trend charts failed" onRetry={retryAll} /> : null}
        {!cpu.data && !hasError ? <ChartSkeleton /> : null}
        <section className={styles.chartGrid} aria-label="Trend charts">
          {cpu.data ? (
            <AnalyticsLineChart title="CPU Line" series={cpu.data.hourly} color={SERVICE_COLORS.cpu} unit="%" />
          ) : null}
          {memory.data ? (
            <AnalyticsLineChart title="Memory Line" series={memory.data.hourly} color={SERVICE_COLORS.memory} unit="%" />
          ) : null}
          {storage.data ? (
            <AnalyticsLineChart
              title="Storage Forecast Line"
              series={storage.data.series}
              color={SERVICE_COLORS.storage}
              unit="%"
            />
          ) : null}
          {photos.data ? (
            <AnalyticsBarChart title="Photo Growth Bar" series={photos.data.series} color={SERVICE_COLORS.photos} />
          ) : null}
          {backup.data ? (
            <AnalyticsBarChart title="Backup Duration Bar" series={backup.data.series} color={SERVICE_COLORS.backup} />
          ) : null}
          {overview.data ? (
            <AnalyticsPieChart
              title="Health Pie"
              slices={[
                { label: 'Healthy', value: overview.data.health.healthy_count, color: SERVICE_COLORS.healthy },
                { label: 'Warning', value: overview.data.health.warning_count, color: SERVICE_COLORS.warning },
                { label: 'Critical', value: overview.data.health.critical_count, color: SERVICE_COLORS.alerts },
                { label: 'Unknown', value: overview.data.health.unknown_count, color: SERVICE_COLORS.unknown },
              ]}
            />
          ) : null}
        </section>
      </section>
    </section>
  )
})
