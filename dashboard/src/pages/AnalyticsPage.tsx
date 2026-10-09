import { memo } from 'react'
import {
  getAnalyticsBackup,
  getAnalyticsCpu,
  getAnalyticsMemory,
  getAnalyticsOverview,
  getAnalyticsPhotos,
  getAnalyticsStorage,
  getAnalyticsTemperature,
} from '../api/dashboard'
import { AnalyticsAreaChart, AnalyticsBarChart, AnalyticsLineChart } from '../components/AnalyticsCharts'
import { ChartSkeleton, OverviewSkeleton } from '../components/Skeleton'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { StatCard } from '../components/StatCard'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { formatBytes, formatPercent } from '../utils/bytes'
import { SERVICE_COLORS } from '../utils/colors'
import styles from './Pages.module.css'

const ANALYTICS_EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

function metricLabel(value: number | null, suffix: string): string {
  if (value == null) {
    return '—'
  }
  return `${value.toFixed(1)}${suffix}`
}

export const AnalyticsPage = memo(function AnalyticsPage() {
  const overview = useLivePolling(getAnalyticsOverview, ANALYTICS_EVENTS)
  const cpu = useLivePolling(getAnalyticsCpu, ANALYTICS_EVENTS)
  const memory = useLivePolling(getAnalyticsMemory, ANALYTICS_EVENTS)
  const storage = useLivePolling(getAnalyticsStorage, ANALYTICS_EVENTS)
  const temperature = useLivePolling(getAnalyticsTemperature, ANALYTICS_EVENTS)
  const photos = useLivePolling(getAnalyticsPhotos, ANALYTICS_EVENTS)
  const backup = useLivePolling(getAnalyticsBackup, ANALYTICS_EVENTS)

  const sections = [overview, cpu, memory, storage, temperature, photos, backup]
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
          <p className={styles.eyebrow}>Read-only trends</p>
          <h1 className={styles.title}>Analytics</h1>
          <p className={styles.description}>Aggregated history, photo growth, and backup outcomes.</p>
        </div>
        <LastUpdated refreshing={isRefreshing} value={lastUpdated} />
      </header>

      <section className={styles.section} aria-labelledby="analytics-summary-title">
        <h2 className={styles.sectionTitle} id="analytics-summary-title">
          Summary
        </h2>
        {overview.error ? (
          <SectionError title="Analytics overview failed" onRetry={overview.retry} />
        ) : null}
        {!overview.data && !overview.error ? <OverviewSkeleton /> : null}
        {overview.data ? (
          <section className={styles.statGrid} aria-label="Analytics summary">
            <StatCard icon="cpu" label="Average CPU" tone="cpu" value={metricLabel(overview.data.cpu_average, '%')} />
            <StatCard icon="memory" label="Average Memory" tone="memory" value={metricLabel(overview.data.memory_average, '%')} />
            <StatCard icon="storage" label="Storage Used" tone="storage" value={formatBytes(overview.data.storage_used)} />
            <StatCard icon="photo" label="Photos Today" tone="photos" value={overview.data.photos_today} />
            <StatCard
              icon="backup"
              label="Backup Success Rate"
              tone="backup"
              value={
                overview.data.backup_success_rate == null
                  ? '—'
                  : formatPercent(overview.data.backup_success_rate)
              }
            />
            <StatCard
              icon="temperature"
              label="Average Temperature"
              tone="temperature"
              value={metricLabel(overview.data.temperature_average, '°C')}
            />
          </section>
        ) : null}
      </section>

      <section className={styles.section} aria-labelledby="analytics-daily-title">
        <h2 className={styles.sectionTitle} id="analytics-daily-title">
          Daily Overview
        </h2>
        {overview.data ? (
          <section className={styles.statGrid} aria-label="Daily overview">
            <StatCard label="Agents Online" value={overview.data.daily.agents_online} />
            <StatCard label="Agents Total" value={overview.data.daily.agents_total} />
            <StatCard label="Alerts Today" value={overview.data.daily.alerts_today} />
            <StatCard label="Notifications Today" value={overview.data.daily.notifications_today} />
            <StatCard label="History Points Today" value={overview.data.daily.history_points_today} />
          </section>
        ) : (
          <EmptyState message="Daily overview is not available yet." />
        )}
      </section>

      <section className={styles.section} aria-labelledby="analytics-charts-title">
        <h2 className={styles.sectionTitle} id="analytics-charts-title">
          Trends
        </h2>
        {hasError ? <SectionError title="Analytics charts failed" onRetry={retryAll} /> : null}
        {!cpu.data && !memory.data && !hasError ? <ChartSkeleton /> : null}
        <section className={styles.chartGrid} aria-label="Analytics charts">
          {cpu.data ? (
            <AnalyticsLineChart title="CPU Trend" series={cpu.data.series} color={SERVICE_COLORS.cpu} unit="%" />
          ) : null}
          {memory.data ? (
            <AnalyticsLineChart
              title="Memory Trend"
              series={memory.data.series}
              color={SERVICE_COLORS.memory}
              unit="%"
            />
          ) : null}
          {storage.data ? (
            <AnalyticsAreaChart title="Storage Trend" series={storage.data.series} color={SERVICE_COLORS.storage} />
          ) : null}
          {temperature.data ? (
            <AnalyticsLineChart
              title="Temperature Trend"
              series={temperature.data.series}
              color={SERVICE_COLORS.temperature}
              unit="°C"
            />
          ) : null}
          {photos.data ? (
            <AnalyticsBarChart title="Photo Growth" series={photos.data.series} color={SERVICE_COLORS.photos} />
          ) : null}
          {backup.data ? (
            <AnalyticsBarChart title="Backup Duration" series={backup.data.series} color={SERVICE_COLORS.backup} />
          ) : null}
        </section>
      </section>
    </section>
  )
})
