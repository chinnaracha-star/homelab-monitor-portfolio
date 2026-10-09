import type { AgentSummary } from '../types/dashboard'

export type AgentFilter = 'all' | 'online' | 'offline' | 'warning'

export const AGENT_FILTER_STORAGE_KEY = 'homelab-monitor.agent-filter'

export function normalizeStatus(status: string, alertCount = 0): 'online' | 'offline' | 'warning' | 'registered' {
  const normalized = status.toLowerCase()
  if (normalized === 'offline') {
    return 'offline'
  }
  if (alertCount > 0 || normalized === 'warning') {
    return 'warning'
  }
  if (normalized === 'online') {
    return 'online'
  }
  return 'registered'
}

export function matchesAgentSearch(
  agent: AgentSummary,
  query: string,
  osName = '',
  displayStatus = '',
): boolean {
  const needle = query.trim().toLowerCase()
  if (!needle) {
    return true
  }

  return [
    agent.name,
    agent.hostname,
    agent.status,
    displayStatus,
    osName,
    ...(agent.groups ?? []),
    ...(agent.labels ?? []),
    ...(agent.tags ?? []),
  ]
    .join(' ')
    .toLowerCase()
    .includes(needle)
}

export function matchesAgentFilter(
  filter: AgentFilter,
  displayStatus: string,
): boolean {
  if (filter === 'all') {
    return true
  }
  return displayStatus === filter
}

export function deriveAgentTags(agent: AgentSummary, osName = ''): string[] {
  const blob = `${agent.hostname} ${agent.name} ${osName}`.toLowerCase()
  const tags: string[] = []
  if (/\bwin|\bwindows/.test(blob)) {
    tags.push('windows')
  }
  if (/\brpi\b|raspberry|raspi/.test(blob)) {
    tags.push('raspberry-pi')
  }
  if (/\bnas\b|qnap|synology/.test(blob)) {
    tags.push('nas')
  }
  if (/\bubuntu\b|\bdebian\b|\blinux\b/.test(blob) || tags.length === 0) {
    tags.push('ubuntu')
  }
  return tags
}

export function isAgentFilter(value: string): value is AgentFilter {
  return value === 'all' || value === 'online' || value === 'offline' || value === 'warning'
}
