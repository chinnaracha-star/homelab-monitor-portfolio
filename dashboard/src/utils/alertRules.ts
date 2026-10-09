import type { AlertMetric, AlertOperator, AlertSeverity } from '../types/dashboard'

const METRIC_LABEL: Record<AlertMetric, string> = {
  cpu_percent: 'CPU',
  memory_percent: 'memory',
  disk_percent: 'disk',
  temperature_celsius: 'temperature',
  agent_offline: 'agent offline time',
}

const METRIC_UNIT: Record<AlertMetric, string> = {
  cpu_percent: '%',
  memory_percent: '%',
  disk_percent: '%',
  temperature_celsius: '°C',
  agent_offline: 's',
}

const OPERATOR_LABEL: Record<AlertOperator, string> = {
  '>': 'greater than',
  '>=': 'greater than or equal to',
  '<': 'less than',
  '<=': 'less than or equal to',
  '==': 'equal to',
  '!=': 'not equal to',
}

export const METRIC_OPTIONS: { value: AlertMetric; label: string }[] = [
  { value: 'cpu_percent', label: 'CPU percent' },
  { value: 'memory_percent', label: 'Memory percent' },
  { value: 'disk_percent', label: 'Disk percent' },
  { value: 'temperature_celsius', label: 'Temperature' },
  { value: 'agent_offline', label: 'Agent offline' },
]

export const OPERATOR_OPTIONS: { value: AlertOperator; label: string }[] = [
  { value: '>', label: '>' },
  { value: '>=', label: '>=' },
  { value: '<', label: '<' },
  { value: '<=', label: '<=' },
  { value: '==', label: '==' },
  { value: '!=', label: '!=' },
]

export const SEVERITY_OPTIONS: AlertSeverity[] = ['critical', 'high', 'medium', 'low']

export function previewAlertRule(
  metric: AlertMetric,
  operator: AlertOperator,
  threshold: number,
  severity: AlertSeverity,
): string {
  return `If ${METRIC_LABEL[metric]} is ${OPERATOR_LABEL[operator]} ${threshold}${METRIC_UNIT[metric]} create ${capitalize(severity)} alert.`
}

export function formatCooldown(seconds: number): string {
  if (seconds <= 0) {
    return 'No cooldown'
  }
  if (seconds < 60) {
    return `${seconds}s`
  }
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return remainder === 0 ? `${minutes}m` : `${minutes}m ${remainder}s`
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}
