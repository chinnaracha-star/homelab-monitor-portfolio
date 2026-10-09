import { memo } from 'react'
import { getDeveloperOverview, getRemoteAccess } from '../api/dashboard'
import { AnalyticsBarChart, AnalyticsGaugeChart } from '../components/AnalyticsCharts'
import { OverviewSkeleton } from '../components/Skeleton'
import { EmptyState } from '../components/EmptyState'
import { LastUpdated } from '../components/LastUpdated'
import { RelativeTime } from '../components/RelativeTime'
import { RemoteAccessCard } from '../components/RemoteAccessCard'
import { SectionError } from '../components/SectionError'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import { LIVE_PAGE_POLL } from '../constants'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { useNow } from '../hooks/useNow'
import { useOptionalPwa } from '../pwa/PwaProvider'
import type { DeveloperOverview } from '../types/dashboard'
import { SERVICE_COLORS } from '../utils/colors'
import { formatThaiDateTime } from '../utils/thaiDate'
import styles from './Pages.module.css'

const DEV_EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

function gitDirty(value: boolean | null): string {
  if (value == null) {
    return '—'
  }
  return value ? 'YES' : 'NO'
}

function workingTree(value: string | null): string {
  if (value === 'clean') {
    return 'Clean'
  }
  if (value === 'dirty') {
    return 'Dirty'
  }
  return '—'
}

function versionLabel(value: string): string {
  return value.startsWith('v') ? value : `v${value}`
}

function titleCase(value: string | null | undefined): string {
  if (!value) {
    return 'Unknown'
  }
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function runtimeTone(label: string, value: string): string | undefined {
  if (value === 'healthy') {
    return 'qnap'
  }
  if (value === 'critical') {
    return 'alerts'
  }
  if (label === 'qnap') {
    return 'qnap'
  }
  if (label === 'docker') {
    return 'docker'
  }
  if (label === 'immich') {
    return 'immich'
  }
  if (label === 'qumagie') {
    return 'qumagie'
  }
  if (label === 'backup') {
    return 'backup'
  }
  return undefined
}

function phaseSeries(overview: DeveloperOverview) {
  return overview.progress.phases.map((item) => ({
    timestamp: null,
    label: `Phase ${item.phase}`,
    value: item.percent,
  }))
}

export const DeveloperPage = memo(function DeveloperPage() {
  const now = useNow()
  const overview = useLivePolling(getDeveloperOverview, DEV_EVENTS, LIVE_PAGE_POLL)
  const remote = useLivePolling(getRemoteAccess, DEV_EVENTS, LIVE_PAGE_POLL)
  const pwa = useOptionalPwa()
  const agentService = overview.data?.agent_service
  const runtime = overview.data?.runtime

  return (
    <section className={`${styles.page} ${styles.missionControl}`}>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Developer only</p>
          <h1 className={styles.title}>Mission Control</h1>
          <p className={styles.description}>Read-only project, runtime, git, and health status.</p>
          {pwa?.offline ? (
            <p className={styles.offlineMode} role="status">
              Offline Mode
            </p>
          ) : null}
        </div>
        <LastUpdated refreshing={overview.isRefreshing} value={overview.lastUpdated} />
      </header>

      {overview.error ? <SectionError title="Mission Control failed" onRetry={overview.retry} /> : null}
      {remote.error ? <SectionError title="Remote Access failed" onRetry={remote.retry} /> : null}
      {!overview.data && !overview.error ? <OverviewSkeleton /> : null}

      {overview.data ? (
        <>
          <section className={styles.section} aria-labelledby="developer-project-title">
            <h2 className={styles.sectionTitle} id="developer-project-title">
              Project
            </h2>
            <section className={styles.statGrid} aria-label="Project status">
              <StatCard icon="mission" label="Version" value={versionLabel(overview.data.project.application_version)} />
              <StatCard label="Environment" value={overview.data.project.environment} />
              <StatCard label="Phase" value={overview.data.project.current_phase} />
              <StatCard label="Sprint" value={overview.data.project.current_sprint} />
            </section>
          </section>

          <section className={styles.section} aria-labelledby="developer-git-title">
            <h2 className={styles.sectionTitle} id="developer-git-title">
              Git
            </h2>
            <section className={styles.statGrid} aria-label="Git status">
              <StatCard label="Branch" value={overview.data.project.git.branch ?? '—'} />
              <StatCard label="Commit" value={overview.data.project.git.commit ?? '—'} />
              <StatCard label="Git Dirty" value={gitDirty(overview.data.project.git.dirty)} />
              <StatCard label="Working Tree" value={workingTree(overview.data.project.git.working_tree)} />
            </section>
          </section>

          <section className={styles.section} aria-labelledby="developer-runtime-title">
            <h2 className={styles.sectionTitle} id="developer-runtime-title">
              Runtime
            </h2>
            <section className={styles.statGrid} aria-label="Runtime status">
              {Object.entries(overview.data.runtime).map(([label, value]) => (
                <StatCard key={label} label={label} tone={runtimeTone(label, value)} value={value} />
              ))}
            </section>
          </section>

          {remote.data ? <RemoteAccessCard access={remote.data} /> : null}
          {!remote.data && !remote.error ? (
            <section className={styles.section} aria-labelledby="remote-access-loading">
              <h2 className={styles.sectionTitle} id="remote-access-loading">
                Remote Access
              </h2>
              <OverviewSkeleton />
            </section>
          ) : null}

          <section className={styles.section} aria-labelledby="developer-backend-title">
            <h2 className={styles.sectionTitle} id="developer-backend-title">
              Backend Status
            </h2>
            <section className={styles.statGrid} aria-label="Backend status">
              <StatCard
                label="API Status"
                valueLabel={runtime?.api ?? 'unknown'}
                value={<StatusBadge kind="service" status={runtime?.api ?? 'unknown'} />}
              />
              <StatCard
                label="Database Status"
                valueLabel={runtime?.database ?? 'unknown'}
                value={<StatusBadge kind="service" status={runtime?.database ?? 'unknown'} />}
              />
              <StatCard
                label="Dashboard Status"
                valueLabel={runtime?.dashboard ?? 'unknown'}
                value={<StatusBadge kind="service" status={runtime?.dashboard ?? 'unknown'} />}
              />
              <StatCard
                label="WebSocket Status"
                valueLabel={runtime?.websocket ?? 'unknown'}
                value={<StatusBadge kind="service" status={runtime?.websocket ?? 'unknown'} />}
              />
            </section>
          </section>

          <section className={styles.section} aria-labelledby="developer-agent-service-title">
            <h2 className={styles.sectionTitle} id="developer-agent-service-title">
              Agent Runtime
            </h2>
            <section className={styles.statGrid} aria-label="Agent runtime">
              <StatCard
                icon="agent"
                label="Service Status"
                valueLabel={titleCase(agentService?.state)}
                value={<StatusBadge kind="service" status={agentService?.state ?? 'unknown'} />}
              />
              <StatCard
                label="Agent Status"
                valueLabel={titleCase(agentService?.agent_status)}
                value={<StatusBadge status={agentService?.agent_status ?? 'unknown'} />}
              />
              <StatCard
                label="Last Check-in"
                valueLabel={agentService?.last_check_in ?? 'Never'}
                value={<RelativeTime now={now} value={agentService?.last_check_in ?? null} />}
              />
              <StatCard
                label="Last Report"
                valueLabel={agentService?.last_report ?? 'Never'}
                value={<RelativeTime now={now} value={agentService?.last_report ?? null} />}
              />
              <StatCard
                label="Next Report ETA"
                valueLabel={agentService?.next_report_eta ?? 'Never'}
                value={<RelativeTime now={now} value={agentService?.next_report_eta ?? null} />}
              />
              <StatCard label="PID" value={agentService?.pid ?? '—'} />
              <StatCard label="Restart Counter" value={agentService?.restart_count ?? '—'} />
              <StatCard
                label="Report Interval"
                value={`${agentService?.report_interval_seconds ?? 60}s`}
              />
              <StatCard label="Enabled" value={titleCase(agentService?.enabled)} />
              <StatCard label="Systemd" value={agentService?.systemd_status ?? 'Unknown'} />
            </section>
          </section>

          <section className={styles.section} aria-labelledby="developer-build-title">
            <h2 className={styles.sectionTitle} id="developer-build-title">
              Build
            </h2>
            <section className={styles.statGrid} aria-label="Build status">
              <StatCard label="Last Build" value={overview.data.build.last_build ?? '—'} />
              <StatCard label="Build Status" value={overview.data.build.build_status} />
              <StatCard label="Backend" value={overview.data.build.backend} />
              <StatCard label="Frontend" value={overview.data.build.frontend} />
              <StatCard label="Docker Compose" value={overview.data.build.docker_compose} />
            </section>
          </section>

          <section className={styles.section} aria-labelledby="developer-tests-title">
            <h2 className={styles.sectionTitle} id="developer-tests-title">
              Tests
            </h2>
            <section className={styles.statGrid} aria-label="Test status">
              <StatCard label="Backend Tests" value={overview.data.tests.backend_tests} />
              <StatCard label="Frontend Tests" value={overview.data.tests.frontend_tests} />
              <StatCard label="Lint" value={overview.data.tests.lint} />
              <StatCard label="Ruff" value={overview.data.tests.ruff} />
              <StatCard label="Build" value={overview.data.tests.build} />
              <StatCard label="QA" value={overview.data.tests.qa} />
            </section>
          </section>

          <section className={styles.section} aria-labelledby="developer-stats-title">
            <h2 className={styles.sectionTitle} id="developer-stats-title">
              Statistics
            </h2>
            <section className={styles.statGrid} aria-label="Project statistics">
              <StatCard label="REST APIs" value={overview.data.statistics.rest_apis} />
              <StatCard label="Database Tables" value={overview.data.statistics.database_tables} />
              <StatCard label="Agents" value={overview.data.statistics.agents} />
              <StatCard label="Groups" value={overview.data.statistics.groups} />
              <StatCard label="Users" value={overview.data.statistics.users} />
              <StatCard label="Alert Rules" value={overview.data.statistics.alert_rules} />
              <StatCard label="Notifications" value={overview.data.statistics.notifications} />
              <StatCard label="Photos" value={overview.data.statistics.photos} />
              <StatCard label="Docker Services" value={overview.data.statistics.docker_services} />
              <StatCard label="Frontend Pages" value={overview.data.statistics.frontend_pages} />
              <StatCard label="React Components" value={overview.data.statistics.react_components} />
              <StatCard label="Backend Modules" value={overview.data.statistics.backend_modules} />
              <StatCard label="Test Count" value={overview.data.statistics.test_count} />
              <StatCard label="Frontend Test Count" value={overview.data.statistics.frontend_test_count} />
            </section>
          </section>

          <section className={styles.section} aria-labelledby="developer-health-title">
            <h2 className={styles.sectionTitle} id="developer-health-title">
              System Health
            </h2>
            <section className={styles.statGrid} aria-label="System health">
              <StatCard label="Overall Health" value={overview.data.health.overall_health} />
              <StatCard label="Capacity" value={overview.data.health.overall_capacity} />
              <StatCard label="Trend" value={overview.data.health.overall_trend} />
              <StatCard label="Infrastructure" value={overview.data.health.overall_infrastructure} />
            </section>
          </section>

          <section className={styles.section} aria-labelledby="developer-progress-title">
            <h2 className={styles.sectionTitle} id="developer-progress-title">
              Progress
            </h2>
            <section className={styles.statGrid} aria-label="Development progress">
              <StatCard label="Completed" value={`${overview.data.progress.completed_percent}%`} />
              <StatCard label="Current Sprint" value={overview.data.progress.current_sprint} />
              <StatCard label="Milestone" value={overview.data.progress.current_milestone} />
            </section>
            <p className={styles.reportMeta}>{overview.data.progress.roadmap}</p>
          </section>

          <section className={styles.section} aria-labelledby="developer-activity-title">
            <h2 className={styles.sectionTitle} id="developer-activity-title">
              Recent Activity
            </h2>
            {overview.data.activity.length === 0 ? (
              <EmptyState message="No recent activity yet." />
            ) : (
              <ol className={styles.timelineList} aria-label="Recent timeline">
                {overview.data.activity.map((item) => (
                  <li className={styles.timelineItem} key={`${item.kind}-${item.timestamp}-${item.message}`}>
                    <p className={styles.timelineKind}>{item.kind}</p>
                    <p className={styles.timelineMessage}>{item.message}</p>
                    <p className={styles.timelineTime}>
                      {item.timestamp ? formatThaiDateTime(item.timestamp, false) : '—'}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section className={styles.section} aria-labelledby="developer-charts-title">
            <h2 className={styles.sectionTitle} id="developer-charts-title">
              Charts
            </h2>
            <section className={styles.chartGrid} aria-label="Developer charts">
              <AnalyticsGaugeChart title="Health Gauge" score={overview.data.health.overall_health} />
              <AnalyticsBarChart title="Phase Progress" series={phaseSeries(overview.data)} color={SERVICE_COLORS.docker} />
            </section>
          </section>
        </>
      ) : null}
    </section>
  )
})
