import { memo, useCallback, useMemo, useState } from 'react'
import { getActiveAlerts, getAgents, getGroups, getLatestAgentReport } from '../api/dashboard'
import { AgentTable } from '../components/AgentTable'
import { AgentToolbar } from '../components/AgentToolbar'
import { LastUpdated } from '../components/LastUpdated'
import { SectionError } from '../components/SectionError'
import { TableSkeleton } from '../components/Skeleton'
import { LIVE_PAGE_POLL } from '../constants'
import { useLivePolling } from '../hooks/useDashboardSocket'
import { useLocalStorage } from '../hooks/useLocalStorage'
import { useNow } from '../hooks/useNow'
import {
  AGENT_FILTER_STORAGE_KEY,
  deriveAgentTags,
  isAgentFilter,
  type AgentFilter,
} from '../utils/agents'
import { isApiErrorCode } from '../utils/errors'
import { getSystemMetrics } from '../utils/metrics'
import styles from './Pages.module.css'

const AGENT_EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const
const ALERT_EVENTS = ['overview_updated', 'agent_updated', 'alert_updated'] as const

export const AgentsPage = memo(function AgentsPage() {
  const now = useNow()
  const [query, setQuery] = useState('')
  const [groupId, setGroupId] = useState('all')
  const [storedFilter, setStoredFilter] = useLocalStorage(AGENT_FILTER_STORAGE_KEY, 'all')
  const filter: AgentFilter = isAgentFilter(storedFilter) ? storedFilter : 'all'
  const agents = useLivePolling(getAgents, AGENT_EVENTS, LIVE_PAGE_POLL)
  const groups = useLivePolling(getGroups, AGENT_EVENTS, LIVE_PAGE_POLL)
  const alerts = useLivePolling(getActiveAlerts, ALERT_EVENTS, LIVE_PAGE_POLL)

  const loadOsNames = useCallback(async () => {
    const currentAgents = agents.data ?? []
    const entries = await Promise.all(
      currentAgents.map(async (agent) => {
        try {
          const report = await getLatestAgentReport(agent.id)
          return [agent.id, getSystemMetrics(report)?.os?.distribution ?? ''] as const
        } catch (error) {
          if (isApiErrorCode(error, 'latest_report_not_found') || isApiErrorCode(error, 'agent_not_found')) {
            return [agent.id, ''] as const
          }
          return [agent.id, ''] as const
        }
      }),
    )
    return Object.fromEntries(entries)
  }, [agents.data])

  const osNames = useLivePolling(loadOsNames, AGENT_EVENTS, { enabled: Boolean(agents.data) })

  const alertCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const alert of alerts.data ?? []) {
      counts[alert.agent_id] = (counts[alert.agent_id] ?? 0) + 1
    }
    return counts
  }, [alerts.data])

  const labeledAgents = useMemo(() => {
    const membership = new Map<string, string[]>()
    for (const group of groups.data ?? []) {
      for (const agentId of group.agent_ids) {
        membership.set(agentId, [...(membership.get(agentId) ?? []), group.name])
      }
    }
    return (agents.data ?? []).map((agent) => {
      const groupNames = membership.get(agent.id) ?? []
      return {
        ...agent,
        groups: groupNames,
        labels: groupNames,
        tags: deriveAgentTags(agent, osNames.data?.[agent.id] ?? ''),
      }
    })
  }, [agents.data, groups.data, osNames.data])

  const visibleAgents = useMemo(() => {
    if (!agents.data) {
      return []
    }
    if (groupId === 'all') {
      return labeledAgents
    }
    const memberIds = new Set(groups.data?.find((group) => group.id === groupId)?.agent_ids ?? [])
    return labeledAgents.filter((agent) => memberIds.has(agent.id))
  }, [agents.data, groupId, groups.data, labeledAgents])

  const fleet = useMemo(() => {
    const items = agents.data ?? []
    const online = items.filter((agent) => agent.status === 'online').length
    const offline = items.filter((agent) => agent.status === 'offline').length
    const score = items.length === 0 ? 0 : Math.round((online / items.length) * 100)
    return { total: items.length, online, offline, score }
  }, [agents.data])

  const isRefreshing = agents.isRefreshing || alerts.isRefreshing || osNames.isRefreshing || groups.isRefreshing
  const lastUpdated =
    [agents.lastUpdated, alerts.lastUpdated, osNames.lastUpdated, groups.lastUpdated]
      .filter((value): value is Date => value !== null)
      .sort((left, right) => right.getTime() - left.getTime())[0] ?? null

  return (
    <section className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Infrastructure</p>
          <h1 className={styles.title}>Agents</h1>
          <p className={styles.description}>
            Hosts reporting to HomeLab Monitor. Groups, labels, and tags are derived from existing
            agent groups and hostnames without changing the agent protocol.
          </p>
        </div>
        <LastUpdated refreshing={isRefreshing} value={lastUpdated} />
      </header>

      {agents.data ? (
        <section className={styles.fleetGrid} aria-label="Fleet health">
          <article className={styles.fleetCard}>
            <h2>Overall Fleet Health</h2>
            <p className={styles.fleetValue}>{fleet.score}</p>
            <p className={styles.fleetMeta}>0–100 from online agents</p>
          </article>
          <article className={styles.fleetCard}>
            <h2>Online Summary</h2>
            <p className={styles.fleetValue}>{fleet.online}</p>
            <p className={styles.fleetMeta}>of {fleet.total} agents</p>
          </article>
          <article className={styles.fleetCard}>
            <h2>Offline Summary</h2>
            <p className={styles.fleetValue}>{fleet.offline}</p>
            <p className={styles.fleetMeta}>hosts past the offline timeout</p>
          </article>
        </section>
      ) : null}

      <AgentToolbar
        filter={filter}
        groups={groups.data ?? []}
        groupId={groupId}
        query={query}
        onFilterChange={(value) => setStoredFilter(value)}
        onGroupChange={setGroupId}
        onQueryChange={setQuery}
      />

      {agents.error ? (
        <SectionError title="Agents API failed" onRetry={agents.retry} />
      ) : null}
      {alerts.error ? (
        <SectionError title="Alerts API failed" message="Status badges will omit alert counts." onRetry={alerts.retry} />
      ) : null}
      {!agents.data && !agents.error ? <TableSkeleton /> : null}
      {agents.data ? (
        <AgentTable
          agents={visibleAgents}
          alertCounts={alertCounts}
          filter={filter}
          now={now}
          osNames={osNames.data ?? {}}
          query={query}
        />
      ) : null}
    </section>
  )
})
