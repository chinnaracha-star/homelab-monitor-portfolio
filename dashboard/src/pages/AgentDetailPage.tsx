import { useCallback, useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getAgent, getLatestAgentReport } from '../api/dashboard'
import { AgentHistorySection } from '../components/AgentHistorySection'
import { EmptyState } from '../components/EmptyState'
import { RenderGuard } from '../components/RenderGuard'
import { LastUpdated } from '../components/LastUpdated'
import { MetricCard } from '../components/MetricCard'
import { MetricSkeleton } from '../components/Skeleton'
import { RelativeTime } from '../components/RelativeTime'
import { SectionError } from '../components/SectionError'
import { StatusBadge } from '../components/StatusBadge'
import { LIVE_PAGE_POLL } from '../constants'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { useNow } from '../hooks/useNow'
import { isApiErrorCode } from '../utils/errors'
import { formatBytes, formatUptime } from '../utils/format'
import {
  getHighestTemperature,
  getSystemMetrics,
  getTemperatureLevel,
  getUsageLevel,
} from '../utils/metrics'
import styles from './Pages.module.css'

const AGENT_DETAIL_EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

export function AgentDetailPage() {
  const { id } = useParams()

  if (!id) {
    return (
      <section className={styles.page}>
        <EmptyState message="The agent ID is missing from the URL." />
      </section>
    )
  }

  return (
    <section className={styles.page}>
      <RenderGuard key={id} fallback={<EmptyState message="Unable to render agent detail." />}>
        <AgentDetailContent id={id} />
      </RenderGuard>
      <RenderGuard
        key={`history-${id}`}
        fallback={
          <section className={styles.section} aria-labelledby="agent-history-title">
            <h2 className={styles.sectionTitle} id="agent-history-title">
              History
            </h2>
            <EmptyState message="Unable to render history." />
          </section>
        }
      >
        <AgentHistorySection agentId={id} agentName="agent" />
      </RenderGuard>
    </section>
  )
}

function AgentDetailContent({ id }: { id: string }) {
  const now = useNow()
  const agentPoll = useLivePolling(() => getAgent(id), AGENT_DETAIL_EVENTS, { ...LIVE_PAGE_POLL, agentId: id })
  const loadReport = useCallback(async () => {
    try {
      return await getLatestAgentReport(id)
    } catch (error) {
      if (isApiErrorCode(error, 'latest_report_not_found')) {
        return null
      }
      throw error
    }
  }, [id])
  const reportPoll = useLivePolling(loadReport, AGENT_DETAIL_EVENTS, { ...LIVE_PAGE_POLL, agentId: id })

  const agent = agentPoll.data
  const report = reportPoll.data
  const metrics = useMemo(() => getSystemMetrics(report ?? undefined), [report])
  const highestTemperature = useMemo(
    () => getHighestTemperature(metrics?.temperatures),
    [metrics],
  )
  const isRefreshing = agentPoll.isRefreshing || reportPoll.isRefreshing
  const lastUpdated =
    [agentPoll.lastUpdated, reportPoll.lastUpdated]
      .filter((value): value is Date => value !== null)
      .sort((left, right) => right.getTime() - left.getTime())[0] ?? null

  return (
    <>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Agent detail</p>
          <h1 className={styles.title}>{agent?.name ?? 'Agent'}</h1>
          <p className={styles.description}>Host information and latest system metrics.</p>
        </div>
        <div>
          <Link className={styles.backLink} to="/agents" aria-label="Back to agents">
            ← Back to agents
          </Link>
          <LastUpdated refreshing={isRefreshing} value={lastUpdated} />
        </div>
      </header>

      <section className={styles.section} aria-labelledby="agent-info-title">
        <div className={styles.statusRow}>
          <h2 className={styles.sectionTitle} id="agent-info-title">
            Agent information
          </h2>
          {agent ? <StatusBadge status={agent.status} /> : null}
        </div>
        {agentPoll.error ? (
          <SectionError title="Agent API failed" onRetry={agentPoll.retry} />
        ) : null}
        {!agent && !agentPoll.error ? <MetricSkeleton /> : null}
        {agent ? (
          <article className={styles.infoPanel} aria-label="Agent information">
            <div className={styles.infoItem}>
              <p className={styles.infoLabel}>Name</p>
              <p className={styles.infoValue}>{agent.name}</p>
            </div>
            <div className={styles.infoItem}>
              <p className={styles.infoLabel}>Hostname</p>
              <p className={styles.infoValue}>{agent.hostname}</p>
            </div>
            <div className={styles.infoItem}>
              <p className={styles.infoLabel}>Version</p>
              <p className={styles.infoValue}>{agent.version}</p>
            </div>
            <div className={styles.infoItem}>
              <p className={styles.infoLabel}>Last seen</p>
              <p className={styles.infoValue}>
                <RelativeTime now={now} value={agent.last_seen_at} />
              </p>
            </div>
            <div className={styles.infoItem}>
              <p className={styles.infoLabel}>Configuration revision</p>
              <p className={styles.infoValue}>{agent.configuration_revision}</p>
            </div>
            <div className={styles.infoItem}>
              <p className={styles.infoLabel}>Capabilities</p>
              <p className={styles.infoValue}>
                {agent.capabilities.length ? agent.capabilities.join(', ') : 'None reported'}
              </p>
            </div>
          </article>
        ) : null}
      </section>

      <section className={styles.section} aria-labelledby="latest-report-title">
        <div>
          <h2 className={styles.sectionTitle} id="latest-report-title">
            Latest report
          </h2>
          {report ? (
            <p className={styles.reportMeta}>
              Observed <RelativeTime now={now} value={report.observed_at} /> · Report {report.report_id}
            </p>
          ) : null}
        </div>

        {reportPoll.error ? (
          <SectionError title="Latest report API failed" onRetry={reportPoll.retry} />
        ) : null}
        {!reportPoll.lastUpdated && !reportPoll.error ? <MetricSkeleton /> : null}
        {reportPoll.lastUpdated && !report && !reportPoll.error ? (
          <EmptyState message="No reports available." />
        ) : null}
        {report && !metrics ? <EmptyState message="No reports available." /> : null}

        {metrics ? (
          <>
            <section className={styles.metricGroup} aria-labelledby="system-metrics-title">
              <h3 className={styles.groupTitle} id="system-metrics-title">
                System
              </h3>
              <section className={styles.metricGrid}>
                <MetricCard
                  title="CPU"
                  value={metrics.cpu ? metrics.cpu.usage_percent.toFixed(1) : '—'}
                  unit={metrics.cpu ? '%' : undefined}
                  subtitle={
                    metrics.cpu
                      ? `${metrics.cpu.logical_count} logical cores`
                      : 'CPU usage unavailable'
                  }
                  level={getUsageLevel(metrics.cpu?.usage_percent)}
                />
                <MetricCard
                  title="Memory"
                  value={metrics.memory ? metrics.memory.usage_percent.toFixed(1) : '—'}
                  unit={metrics.memory ? '%' : undefined}
                  subtitle={
                    metrics.memory
                      ? `${formatBytes(metrics.memory.used_bytes)} of ${formatBytes(metrics.memory.total_bytes)}`
                      : 'Memory usage unavailable'
                  }
                  level={getUsageLevel(metrics.memory?.usage_percent)}
                />
                <MetricCard
                  title="Load"
                  value={
                    metrics.load_average ? metrics.load_average['1_minute'].toFixed(2) : '—'
                  }
                  subtitle={
                    metrics.load_average
                      ? `5m ${metrics.load_average['5_minutes'].toFixed(2)} · 15m ${metrics.load_average['15_minutes'].toFixed(2)}`
                      : 'Load average unavailable'
                  }
                />
                <MetricCard
                  title="Temperature"
                  value={
                    highestTemperature ? highestTemperature.current_celsius.toFixed(1) : '—'
                  }
                  unit={highestTemperature ? '°C' : undefined}
                  subtitle={highestTemperature?.label ?? 'No temperature sensors'}
                  level={getTemperatureLevel(highestTemperature?.current_celsius)}
                />
              </section>
            </section>

            <section className={styles.metricGroup} aria-labelledby="storage-metrics-title">
              <h3 className={styles.groupTitle} id="storage-metrics-title">
                Storage
              </h3>
              <section className={styles.metricGrid}>
                {metrics.disks?.length ? (
                  metrics.disks.map((disk) => (
                    <MetricCard
                      key={`${disk.filesystem}-${disk.mount_point}`}
                      title={`Disk ${disk.mount_point}`}
                      value={disk.usage_percent.toFixed(1)}
                      unit="%"
                      subtitle={`${formatBytes(disk.used_bytes)} of ${formatBytes(disk.total_bytes)} · ${disk.filesystem}`}
                      level={getUsageLevel(disk.usage_percent)}
                    />
                  ))
                ) : (
                  <MetricCard title="Disk" value="—" subtitle="Disk usage unavailable" />
                )}
              </section>
            </section>

            <section className={styles.metricGroup} aria-labelledby="os-metrics-title">
              <h3 className={styles.groupTitle} id="os-metrics-title">
                Operating System
              </h3>
              <section className={styles.metricGrid}>
                <MetricCard
                  title="Hostname"
                  value={metrics.hostname ?? agent?.hostname ?? 'Unavailable'}
                  subtitle="Reported by system collector"
                />
                <MetricCard
                  title="OS"
                  value={metrics.os?.distribution ?? 'Unavailable'}
                  subtitle={metrics.os?.distribution_version}
                />
                <MetricCard
                  title="Kernel"
                  value={metrics.os?.kernel ?? 'Unavailable'}
                  subtitle={metrics.os?.architecture}
                />
                <MetricCard
                  title="Uptime"
                  value={formatUptime(metrics.uptime_seconds)}
                  subtitle="Since last system boot"
                />
              </section>
            </section>
          </>
        ) : null}
      </section>
    </>
  )
}
