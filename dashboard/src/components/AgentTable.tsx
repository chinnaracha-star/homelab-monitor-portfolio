import { memo, useMemo, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { AgentSummary } from '../types/dashboard'
import { matchesAgentFilter, matchesAgentSearch, normalizeStatus, type AgentFilter } from '../utils/agents'
import styles from './Components.module.css'
import { EmptyState } from './EmptyState'
import { RelativeTime } from './RelativeTime'
import { StatusBadge } from './StatusBadge'

interface AgentTableProps {
  agents: AgentSummary[]
  alertCounts: Record<string, number>
  osNames: Record<string, string>
  query: string
  filter: AgentFilter
  now: number
}

export const AgentTable = memo(function AgentTable({
  agents,
  alertCounts,
  osNames,
  query,
  filter,
  now,
}: AgentTableProps) {
  const navigate = useNavigate()
  const visibleAgents = useMemo(
    () =>
      agents.filter((agent) => {
        const displayStatus = normalizeStatus(agent.status, alertCounts[agent.id] ?? 0)
        return (
          matchesAgentSearch(agent, query, osNames[agent.id], displayStatus) &&
          matchesAgentFilter(filter, displayStatus)
        )
      }),
    [agents, alertCounts, filter, osNames, query],
  )

  function openAgent(agentId: string) {
    void navigate(`/agents/${agentId}`)
  }

  function handleRowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, index: number) {
    const rows = event.currentTarget.parentElement?.querySelectorAll<HTMLTableRowElement>('tr[tabindex]')
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      rows?.[Math.min(index + 1, (rows.length ?? 1) - 1)]?.focus()
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      rows?.[Math.max(index - 1, 0)]?.focus()
      return
    }
    if (event.key === 'Home') {
      event.preventDefault()
      rows?.[0]?.focus()
      return
    }
    if (event.key === 'End') {
      event.preventDefault()
      rows?.[Math.max((rows.length ?? 1) - 1, 0)]?.focus()
      return
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      openAgent(visibleAgents[index].id)
    }
  }

  if (agents.length === 0) {
    return <EmptyState message="No agents connected." />
  }

  if (visibleAgents.length === 0) {
    return <EmptyState message="No agents connected." />
  }

  return (
    <section className={styles.tableWrapper}>
      <table className={styles.table} aria-label="Monitored agents">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Hostname</th>
            <th scope="col">Version</th>
            <th scope="col">Groups</th>
            <th scope="col">Labels</th>
            <th scope="col">Tags</th>
            <th scope="col">Status</th>
            <th scope="col">Last Seen</th>
          </tr>
        </thead>
        <tbody>
          {visibleAgents.map((agent, index) => (
            <tr
              className={styles.row}
              key={agent.id}
              tabIndex={0}
              aria-label={`Open agent ${agent.name}`}
              onClick={() => openAgent(agent.id)}
              onKeyDown={(event) => handleRowKeyDown(event, index)}
            >
              <td className={styles.agentName}>{agent.name}</td>
              <td>{agent.hostname}</td>
              <td>{agent.version}</td>
              <td>{(agent.groups ?? []).join(', ') || '—'}</td>
              <td>{(agent.labels ?? []).join(', ') || '—'}</td>
              <td>{(agent.tags ?? []).join(', ') || '—'}</td>
              <td>
                <StatusBadge alertCount={alertCounts[agent.id] ?? 0} status={agent.status} />
              </td>
              <td>
                <RelativeTime now={now} value={agent.last_seen_at} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
})
