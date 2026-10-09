import type { AgentHistory, HistoryPoint } from '../types/dashboard'
import { formatThaiDateShort, formatThaiTime } from './thaiDate'

export type HistoryRange = '1h' | '6h' | '24h' | '7d' | '30d'

export const HISTORY_RANGES: { id: HistoryRange; label: string; durationMs: number; interval: AgentHistory['interval'] }[] = [
  { id: '1h', label: '1h', durationMs: 60 * 60 * 1000, interval: '1m' },
  { id: '6h', label: '6h', durationMs: 6 * 60 * 60 * 1000, interval: '5m' },
  { id: '24h', label: '24h', durationMs: 24 * 60 * 60 * 1000, interval: '15m' },
  { id: '7d', label: '7d', durationMs: 7 * 24 * 60 * 60 * 1000, interval: '1h' },
  { id: '30d', label: '30d', durationMs: 30 * 24 * 60 * 60 * 1000, interval: '1h' },
]

export const DEFAULT_HISTORY_RANGE: HistoryRange = '24h'

export interface HistoryChartPoint {
  timestamp: string
  label: string
  cpu: number | null
  memory: number | null
  disk: number | null
  temperature: number | null
}

export function historyWindow(range: HistoryRange, now = new Date()): { from: string; to: string; interval: AgentHistory['interval'] } {
  const selected = HISTORY_RANGES.find((item) => item.id === range) ?? HISTORY_RANGES[2]
  return {
    from: new Date(now.getTime() - selected.durationMs).toISOString(),
    to: now.toISOString(),
    interval: selected.interval,
  }
}

export function toHistoryChartPoints(points: HistoryPoint[]): HistoryChartPoint[] {
  return points.map((point) => ({
    timestamp: point.timestamp,
    label: formatHistoryTick(point.timestamp),
    cpu: point.cpu_percent,
    memory: point.memory_percent,
    disk: point.disk_percent,
    temperature: point.temperature_celsius,
  }))
}

export function formatHistoryTick(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return `${formatThaiDateShort(date)} ${formatThaiTime(date, false)}`
}

export function historyExportFilename(agentName: string, generatedAt = new Date()): string {
  const pad = (part: number) => String(part).padStart(2, '0')
  const stamp = `${generatedAt.getFullYear()}${pad(generatedAt.getMonth() + 1)}${pad(generatedAt.getDate())}-${pad(generatedAt.getHours())}${pad(generatedAt.getMinutes())}`
  const slug = agentName.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'agent'
  return `${slug}-${stamp}.csv`
}

export function historyPointsToCsv(points: HistoryPoint[]): string {
  const header =
    'timestamp,cpu_percent,memory_percent,disk_percent,temperature_celsius,network_rx_bytes,network_tx_bytes'
  const rows = points.map((point) =>
    [
      point.timestamp,
      formatCsvNumber(point.cpu_percent),
      formatCsvNumber(point.memory_percent),
      formatCsvNumber(point.disk_percent),
      formatCsvNumber(point.temperature_celsius),
      formatCsvNumber(point.network_rx_bytes),
      formatCsvNumber(point.network_tx_bytes),
    ].join(','),
  )
  return [header, ...rows].join('\n') + '\n'
}

function formatCsvNumber(value: number | null): string {
  return value === null ? '' : String(value)
}

export function downloadTextFile(filename: string, contents: string, mimeType = 'text/csv'): void {
  const blob = new Blob([contents], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.rel = 'noopener'
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
