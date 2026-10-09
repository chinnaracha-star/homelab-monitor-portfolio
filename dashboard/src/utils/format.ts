import { formatThaiDateTime, formatThaiTime } from './thaiDate'

export { formatThaiDate, formatThaiDateTime, formatThaiTime } from './thaiDate'

export function formatDateTime(value: string | null): string {
  if (!value) {
    return 'Never'
  }
  const formatted = formatThaiDateTime(value)
  return formatted === '—' ? 'Unknown' : formatted
}

export function formatLocalDateTime(value: string | null): string {
  if (!value) {
    return 'Never'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return 'Unknown'
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export function formatSuccessRate(value: number): string {
  return `${value.toFixed(1)} %`
}

export function formatAverageDelivery(value: number): string {
  return `${Math.round(value)} ms`
}

export function formatAverageRetry(value: number): string {
  return value.toFixed(2)
}

export function formatSuccessRateTrend(value: number): string {
  if (value >= 95) {
    return '↑ Stable'
  }
  if (value >= 85) {
    return '→ Watch'
  }
  return '↓ Low'
}

export function formatFailedTrend(value: number): string {
  return value === 0 ? 'No failures' : 'Needs attention'
}

export function formatDeliverySpeed(value: number): string {
  if (value <= 200) {
    return 'Fast'
  }
  if (value <= 500) {
    return 'Normal'
  }
  return 'Slow'
}

export function formatRetryQuality(value: number): string {
  if (value <= 0.25) {
    return 'Excellent'
  }
  if (value <= 1) {
    return 'Good'
  }
  return 'High'
}

export function formatDeliveryChannel(channel: string): string {
  if (!channel) {
    return '—'
  }
  return channel.charAt(0).toUpperCase() + channel.slice(1)
}

export function formatDeliveryEvent(event: string): string {
  const normalized = event.toLowerCase()
  if (normalized === 'activated') {
    return '🟠 Activated'
  }
  if (normalized === 'recovered') {
    return '🔵 Recovered'
  }
  if (!event) {
    return '—'
  }
  return event.charAt(0).toUpperCase() + event.slice(1)
}

export function formatDeliveryStatus(success: boolean): string {
  return success ? '🟢 Success' : '🔴 Failed'
}

export function formatDeliveryError(errorMessage: string | null | undefined): string {
  return errorMessage ? errorMessage : '-'
}

export function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value < 0) {
    return 'Unavailable'
  }

  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let amount = value
  let unitIndex = 0

  while (amount >= 1024 && unitIndex < units.length - 1) {
    amount /= 1024
    unitIndex += 1
  }

  const precision = amount >= 10 || unitIndex === 0 ? 0 : 1
  return `${amount.toFixed(precision)} ${units[unitIndex]}`
}

export function formatClock(value: Date): string {
  return formatThaiTime(value)
}

export function formatUptime(value: number | undefined): string {
  if (value === undefined || value < 0) {
    return 'Unavailable'
  }

  const days = Math.floor(value / 86_400)
  const hours = Math.floor((value % 86_400) / 3_600)
  const minutes = Math.floor((value % 3_600) / 60)

  return [days ? `${days}d` : '', hours ? `${hours}h` : '', `${minutes}m`]
    .filter(Boolean)
    .join(' ')
}
