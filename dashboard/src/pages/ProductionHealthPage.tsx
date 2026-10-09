import { memo, useContext, useEffect, useState } from 'react'
import { getOperationHistory, getOperations, getProductionHealthOverview, runOperation } from '../api/dashboard'
import { AuthContext } from '../auth/AuthContext'
import { can } from '../auth/permissions'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { OverviewSkeleton } from '../components/Skeleton'
import { SectionError } from '../components/SectionError'
import { StatusBadge } from '../components/StatusBadge'
import { LIVE_PAGE_POLL } from '../constants'
import { useLivePolling } from '../hooks/useDashboardSocket'
import type { OperationHistoryItem, OperationItem, ProductionHealthCheck } from '../types/dashboard'
import { formatBytes } from '../utils/bytes'
import { formatThaiDateTime } from '../utils/thaiDate'
import pageStyles from './Pages.module.css'
import styles from './ProductionHealthPage.module.css'

const EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

function value(value: string | number | null | undefined): string {
  return value === null || value === undefined || value === '' ? 'Unavailable' : String(value)
}

function timestamp(input: string | null): string {
  return input ? formatThaiDateTime(input, false) : 'Never'
}

const HealthCard = memo(function HealthCard({ check }: { check: ProductionHealthCheck }) {
  return (
    <article className={styles.healthCard} aria-label={`${check.component} ${check.status}`}>
      <header className={styles.healthHeader}>
        <h2>{check.component}</h2>
        <StatusBadge kind="service" status={check.status} />
      </header>
      <p className={styles.meta}>{check.message}</p>
      <p className={styles.meta}>Last check {formatThaiDateTime(check.last_check, false)}</p>
      {check.latency_ms !== null ? <p className={styles.meta}>Latency {check.latency_ms} ms</p> : null}
      {check.warning ? <p className={styles.meta}>Warning: {check.warning}</p> : null}
      {check.error ? <p className={styles.meta}>Error: {check.error}</p> : null}
    </article>
  )
})

export const ProductionHealthPage = memo(function ProductionHealthPage() {
  const snapshot = useLivePolling(getProductionHealthOverview, EVENTS, LIVE_PAGE_POLL)
  const data = snapshot.data
  const unhealthy = data?.health.checks.filter((check) =>
    ['warning', 'critical'].includes(check.status),
  ) ?? []

  return (
    <section className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <div>
          <p className={pageStyles.eyebrow}>Mission Control</p>
          <h1 className={pageStyles.title}>Production Health</h1>
          <p className={pageStyles.description}>
            Live component health, host runtime details, and actionable diagnostics.
          </p>
        </div>
        <LastUpdated refreshing={snapshot.isRefreshing} value={snapshot.lastUpdated} />
      </header>

      {snapshot.error ? <SectionError title="Production health failed" onRetry={snapshot.retry} /> : null}
      {!data && !snapshot.error ? <OverviewSkeleton /> : null}
      {data ? (
        <>
          <article className={styles.scoreCard} aria-label={`Production health score ${data.health.score}`}>
            <div>
              <p className={pageStyles.eyebrow}>Overall Health Score</p>
              <p className={styles.score}>{data.health.score}</p>
              <p className={styles.scoreLabel}>{data.health.status.toUpperCase()}</p>
            </div>
            <StatusBadge kind="service" status={data.health.status === 'excellent' ? 'healthy' : data.health.status} />
          </article>

          <section className={styles.healthGrid} aria-label="Last operational events">
            <DetailCard title="Last Self Check" rows={[['When', timestamp(data.health.last_self_check ?? data.health.generated_at)]]} />
            <DetailCard title="Last Backup" rows={[['When', timestamp(data.health.last_backup ?? null)]]} />
            <DetailCard title="Last Telegram" rows={[['When', timestamp(data.health.last_telegram ?? data.runtime.telegram.last_successful_send)]]} />
            <DetailCard title="Last Photo Scan" rows={[['When', timestamp(data.health.last_photo_scan ?? null)]]} />
            <DetailCard title="Last Agent Check-in" rows={[['When', timestamp(data.health.last_agent_checkin ?? data.runtime.agent.last_heartbeat)]]} />
          </section>

          {data.health.performance ? (
            <section className={pageStyles.section} aria-labelledby="performance-title">
              <h2 className={styles.sectionTitle} id="performance-title">Performance</h2>
              <div className={styles.healthGrid}>
                <article className={styles.detailCard} aria-label="Performance Score">
                  <h3>Performance Score</h3>
                  <p className={styles.score}>{data.health.performance.performance_score}</p>
                </article>
                <article className={styles.detailCard} aria-label="Reliability Score">
                  <h3>Reliability Score</h3>
                  <p className={styles.score}>{data.health.performance.reliability_score}</p>
                </article>
                <DetailCard title="Current" rows={[
                  ['API', ms(data.health.performance.current.api_ms)],
                  ['Database query', ms(data.health.performance.current.query_ms)],
                  ['SQLite size', data.health.performance.current.sqlite_bytes == null ? 'Unavailable' : formatBytes(Number(data.health.performance.current.sqlite_bytes))],
                  ['Photo scan', ms(data.health.performance.current.photo_scan_ms)],
                  ['Backup', sec(data.health.performance.current.backup_seconds)],
                  ['Docker CPU', data.health.performance.current.docker_cpu_percent == null ? 'Unavailable' : `${data.health.performance.current.docker_cpu_percent}%`],
                ]} />
                <DetailCard title="History windows" rows={[
                  ['24h API', ms(data.health.performance.windows['24h']?.api_ms)],
                  ['7d API', ms(data.health.performance.windows['7d']?.api_ms)],
                  ['30d API', ms(data.health.performance.windows['30d']?.api_ms)],
                ]} />
              </div>
            </section>
          ) : null}

          <OperationsPanel />

          {data.health.observability ? (
            <section className={pageStyles.section} aria-labelledby="observability-title">
              <h2 className={styles.sectionTitle} id="observability-title">Observability</h2>
              <div className={styles.detailsGrid}>
                <DetailCard title="Platform" rows={[
                  ['API latency', data.health.observability.api_latency_ms === null ? 'Unavailable' : `${data.health.observability.api_latency_ms} ms`],
                  ['Database size', data.health.observability.database_size_bytes === null ? 'Unavailable' : formatBytes(data.health.observability.database_size_bytes)],
                  ['Database growth', data.health.observability.database_growth_bytes === null ? 'Unavailable' : formatBytes(data.health.observability.database_growth_bytes)],
                  ['Telegram success', data.health.observability.telegram_success_rate === null ? 'Unavailable' : `${data.health.observability.telegram_success_rate}%`],
                  ['Photo Monitor latency', data.health.observability.photo_monitor_latency_ms === null ? 'Unavailable' : `${data.health.observability.photo_monitor_latency_ms} ms`],
                  ['Backup success', data.health.observability.backup_success_rate === null ? 'Unavailable' : `${data.health.observability.backup_success_rate}%`],
                ]} />
                <DetailCard title="History" rows={[
                  ['CPU history', data.health.observability.cpu_history.map((item) => `${item}%`).join(', ') || 'Unavailable'],
                  ['Memory history', data.health.observability.memory_history.map((item) => `${item}%`).join(', ') || 'Unavailable'],
                  ['Disk growth', data.health.observability.disk_history.map((item) => `${item}%`).join(', ') || 'Unavailable'],
                ]} />
              </div>
            </section>
          ) : null}

          <section className={styles.healthGrid} aria-label="Production component health">
            {data.health.checks.map((check) => <HealthCard check={check} key={check.component} />)}
          </section>

          <section className={pageStyles.section} aria-labelledby="runtime-title">
            <h2 className={styles.sectionTitle} id="runtime-title">Runtime</h2>
            <div className={styles.detailsGrid}>
              <DetailCard title="Agent" rows={[
                ['Running', data.runtime.agent.state],
                ['Restart Count', value(data.runtime.agent.restart_count)],
                ['Last Heartbeat', timestamp(data.runtime.agent.last_heartbeat)],
                ['Last Report', timestamp(data.runtime.agent.last_report)],
                ['Last Metrics Upload', timestamp(data.runtime.agent.last_metrics_upload)],
              ]} />
              <DetailCard title="Telegram" rows={[
                ['Bot Connected', data.runtime.telegram.bot_connected === null ? 'Unknown' : data.runtime.telegram.bot_connected ? 'Yes' : 'No'],
                ['Last Successful Send', timestamp(data.runtime.telegram.last_successful_send)],
                ['Last Failed Send', timestamp(data.runtime.telegram.last_failed_send)],
                ['Failure Reason', value(data.runtime.telegram.failure_reason)],
                ['Retry Queue', data.runtime.telegram.retry_queue],
              ]} />
              <DetailCard title="Tailscale" rows={[
                ['Connected', data.runtime.tailscale.connected ? 'Yes' : 'No'],
                ['Tailnet', value(data.runtime.tailscale.tailnet)],
                ['MagicDNS', data.runtime.tailscale.magic_dns === null ? 'Unknown' : data.runtime.tailscale.magic_dns ? 'Enabled' : 'Disabled'],
                ['Relay / Direct', value(data.runtime.tailscale.connection_type)],
                ['Exit Node', value(data.runtime.tailscale.exit_node)],
                ['Remote Access URL', value(data.runtime.tailscale.remote_access_url)],
              ]} />
            </div>
          </section>

          <section className={pageStyles.section} aria-labelledby="docker-title">
            <h2 className={styles.sectionTitle} id="docker-title">Docker</h2>
            {!data.runtime.docker_available ? <EmptyState message="Docker is unavailable to the API process." /> : null}
            {data.runtime.docker_available && data.runtime.containers.length === 0 ? <EmptyState message="Docker is available, but no containers were found." /> : null}
            {data.runtime.containers.length > 0 ? (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead><tr><th>Container</th><th>Status</th><th>Health</th><th>Restart Count</th><th>Image</th><th>Running Since</th></tr></thead>
                  <tbody>{data.runtime.containers.map((container) => (
                    <tr key={container.container}>
                      <td>{container.container}</td><td>{container.status}</td><td>{container.health}</td>
                      <td>{value(container.restart_count)}</td><td>{container.image}</td><td>{value(container.running_since)}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            ) : null}
          </section>

          <section className={pageStyles.section} aria-labelledby="resources-title">
            <h2 className={styles.sectionTitle} id="resources-title">Storage and Network</h2>
            <div className={styles.detailsGrid}>
              <DetailCard title="Storage" rows={[
                ['Disk Usage', data.storage.disk_usage_percent === null ? 'Unavailable' : `${data.storage.disk_usage_percent}%`],
                ['Free Space', data.storage.free_space_bytes === null ? 'Unavailable' : formatBytes(data.storage.free_space_bytes)],
                ['Filesystem', value(data.storage.filesystem)],
                ['Database Size', data.storage.database_size_bytes === null ? 'Unavailable' : formatBytes(data.storage.database_size_bytes)],
                ['Log Size', data.storage.log_size_bytes === null ? 'Unavailable' : formatBytes(data.storage.log_size_bytes)],
                ['Disk Read', data.storage.disk_read_bytes === null ? 'Unavailable' : formatBytes(data.storage.disk_read_bytes)],
                ['Disk Write', data.storage.disk_write_bytes === null ? 'Unavailable' : formatBytes(data.storage.disk_write_bytes)],
                ['IO Wait', data.storage.io_wait_percent === null ? 'Unavailable' : `${data.storage.io_wait_percent}%`],
              ]} />
              <DetailCard title="Network" rows={[
                ['LAN IP', value(data.network.lan_ip)],
                ['Tailscale IP', value(data.network.tailscale_ip)],
                ['Gateway', value(data.network.gateway)],
                ['Internet', data.network.internet],
                ['Latency', data.network.latency_ms === null ? 'Unavailable' : `${data.network.latency_ms} ms`],
                ['DNS', data.network.dns],
                ['Upload', data.network.upload_bytes === null ? 'Unavailable' : formatBytes(data.network.upload_bytes)],
                ['Download', data.network.download_bytes === null ? 'Unavailable' : formatBytes(data.network.download_bytes)],
                ['Network Errors', value(data.network.network_errors)],
              ]} />
            </div>
          </section>

          <section className={pageStyles.section} aria-labelledby="diagnostics-title">
            <h2 className={styles.sectionTitle} id="diagnostics-title">Auto Diagnostics</h2>
            {unhealthy.length === 0 ? <EmptyState message="No unhealthy components require action." /> : (
              <div className={styles.diagnostics}>
                {unhealthy.map((check) => (
                  <article className={styles.diagnostic} key={check.component}>
                    <h3>{check.component}: {check.message}</h3>
                    <p><strong>Possible Cause:</strong> {check.possible_cause ?? 'No cause available.'}</p>
                    <p><strong>Recommended Action:</strong> {check.recommended_action ?? 'Review service logs.'}</p>
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      ) : null}
    </section>
  )
})

function DetailCard({ title, rows }: { title: string; rows: (string | number)[][] }) {
  return (
    <article className={styles.detailCard}>
      <h3>{title}</h3>
      <dl className={styles.detailList}>
        {rows.map(([label, rowValue]) => <div key={label}><dt>{label}</dt><dd>{rowValue}</dd></div>)}
      </dl>
    </article>
  )
}

function ms(value: number | null | undefined): string {
  return value === null || value === undefined ? 'Unavailable' : `${value} ms`
}

function sec(value: number | null | undefined): string {
  return value === null || value === undefined ? 'Unavailable' : `${value} s`
}

function OperationsPanel() {
  const auth = useContext(AuthContext)
  const allowed = can(auth?.user?.role, 'operations')
  const [items, setItems] = useState<OperationItem[]>([])
  const [history, setHistory] = useState<OperationHistoryItem[]>([])
  const [running, setRunning] = useState<string | null>(null)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!allowed) {
      return
    }
    void Promise.all([getOperations(), getOperationHistory()]).then(([ops, rows]) => {
      setItems(ops)
      setHistory(rows)
    })
  }, [allowed])

  if (!allowed) {
    return null
  }

  async function execute(item: OperationItem) {
    const confirmed = window.confirm(`Run ${item.label}? This is an operator action.`)
    if (!confirmed) {
      return
    }
    setRunning(item.id)
    setMessage(`${item.label}: in progress`)
    try {
      const result = await runOperation(item.id)
      setMessage(`${result.label}: ${result.status} — ${result.detail}`)
      setHistory(await getOperationHistory())
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Operation failed')
    } finally {
      setRunning(null)
    }
  }

  return (
    <section className={pageStyles.section} aria-labelledby="operations-title">
      <h2 className={styles.sectionTitle} id="operations-title">Operations Center</h2>
      {message ? <p className={styles.meta}>{message}</p> : null}
      <div className={styles.opsGrid}>
        {items.map((item) => (
          <button
            className={styles.opButton}
            disabled={running !== null || (item.admin_only && auth?.user?.role !== 'admin')}
            key={item.id}
            type="button"
            onClick={() => void execute(item)}
          >
            {running === item.id ? `${item.label}…` : item.label}
          </button>
        ))}
      </div>
      <h3 className={styles.sectionTitle}>Operation History</h3>
      {history.length === 0 ? <EmptyState message="No operations have been run yet." /> : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Time</th>
                <th>Operation</th>
                <th>Actor</th>
                <th>Status</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {history.map((row) => (
                <tr key={row.id}>
                  <td>{formatThaiDateTime(row.started_at, false)}</td>
                  <td>{row.label}</td>
                  <td>{row.actor}</td>
                  <td>{row.status}</td>
                  <td>{row.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
