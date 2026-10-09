import { memo } from 'react'
import { getInsightsOverview } from '../api/dashboard'
import badgeStyles from '../components/Components.module.css'
import { OverviewSkeleton } from '../components/Skeleton'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { useLivePolling } from '../hooks/useDashboardSocket'
import type { InsightItem } from '../types/dashboard'
import styles from './Pages.module.css'

const INSIGHT_EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

function severityClass(severity: string): string {
  if (severity === 'critical') {
    return badgeStyles.critical
  }
  if (severity === 'warning') {
    return badgeStyles.warning
  }
  if (severity === 'info') {
    return badgeStyles.info
  }
  return badgeStyles.unknown
}

function InsightCard({
  title,
  insight,
  tone,
}: {
  title: string
  insight: InsightItem
  tone?: string
}) {
  const badge = severityClass(insight.severity)
  return (
    <article className={styles.insightCard} data-tone={tone} aria-label={`${title} ${insight.severity}`}>
      <header className={styles.insightHeader}>
        <h3 className={styles.insightTitle}>{title}</h3>
        <p className={`${badgeStyles.badge} ${badge}`} aria-label={`${title} severity ${insight.severity}`}>
          {insight.severity}
        </p>
      </header>
      <p className={styles.insightSummary}>{insight.summary || 'No insight yet.'}</p>
      {insight.recommendation ? (
        <p className={styles.insightRecommendation}>{insight.recommendation}</p>
      ) : null}
    </article>
  )
}

export const InsightsPage = memo(function InsightsPage() {
  const overview = useLivePolling(getInsightsOverview, INSIGHT_EVENTS)

  return (
    <section className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Read-only summaries</p>
          <h1 className={styles.title}>AI Insights</h1>
          <p className={styles.description}>Generated from analytics, trends, and capacity data.</p>
        </div>
        <LastUpdated refreshing={overview.isRefreshing} value={overview.lastUpdated} />
      </header>

      {overview.error ? <SectionError title="Insights failed" onRetry={overview.retry} /> : null}
      {!overview.data && !overview.error ? <OverviewSkeleton /> : null}

      {overview.data ? (
        <section className={styles.section} aria-labelledby="insights-cards-title">
          <h2 className={styles.sectionTitle} id="insights-cards-title">
            Insights
          </h2>
          {!overview.data.overall.summary ? <EmptyState message="No insights yet." /> : null}
          <section className={styles.insightGrid} aria-label="Insight cards">
            <InsightCard title="Overall Summary" insight={overview.data.overall} tone="alerts" />
            <InsightCard title="Infrastructure Insight" insight={overview.data.infrastructure} tone="docker" />
            <InsightCard title="Storage Insight" insight={overview.data.storage} tone="storage" />
            <InsightCard title="CPU Insight" insight={overview.data.cpu} tone="cpu" />
            <InsightCard title="Memory Insight" insight={overview.data.memory} tone="memory" />
            <InsightCard title="Backup Insight" insight={overview.data.backup} tone="backup" />
            <InsightCard title="Photo Insight" insight={overview.data.photos} tone="photos" />
            <InsightCard
              title="Recommendation"
              insight={{
                summary: overview.data.recommendation,
                severity: overview.data.severity,
                recommendation: '',
              }}
            />
          </section>
        </section>
      ) : null}
    </section>
  )
})
