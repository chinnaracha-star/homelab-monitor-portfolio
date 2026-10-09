export function formatRelativeTime(value: string | null, now: number): string {
  if (!value) {
    return 'Never'
  }

  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) {
    return 'Unknown'
  }

  const delta = Math.floor((now - timestamp) / 1_000)
  if (delta < 0) {
    return formatAhead(-delta)
  }
  return formatAgo(Math.max(0, delta))
}

function formatAgo(seconds: number): string {
  if (seconds < 60) {
    return seconds === 1 ? '1 second ago' : `${seconds} seconds ago`
  }
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) {
    return minutes === 1 ? '1 minute ago' : `${minutes} minutes ago`
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    return hours === 1 ? '1 hour ago' : `${hours} hours ago`
  }
  const days = Math.floor(hours / 24)
  return days === 1 ? '1 day ago' : `${days} days ago`
}

function formatAhead(seconds: number): string {
  if (seconds < 60) {
    return seconds === 1 ? 'in 1 second' : `in ${seconds} seconds`
  }
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) {
    return minutes === 1 ? 'in 1 minute' : `in ${minutes} minutes`
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    return hours === 1 ? 'in 1 hour' : `in ${hours} hours`
  }
  const days = Math.floor(hours / 24)
  return days === 1 ? 'in 1 day' : `in ${days} days`
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) {
    return '—'
  }
  const value = Math.max(0, Math.floor(seconds))
  if (value < 60) {
    return value === 1 ? '1 sec' : `${value} sec`
  }
  const minutes = Math.floor(value / 60)
  if (minutes < 60) {
    return minutes === 1 ? '1 min' : `${minutes} min`
  }
  const hours = Math.floor(minutes / 60)
  return hours === 1 ? '1 hour' : `${hours} hours`
}

export function liveAlertDurationSeconds(
  startedAt: string | null | undefined,
  recoveredAt: string | null | undefined,
  status: string | undefined,
  now: number,
  fallback: number | null | undefined,
): number | null {
  if (!startedAt) {
    return fallback ?? null
  }
  const start = Date.parse(startedAt)
  if (Number.isNaN(start)) {
    return fallback ?? null
  }
  const recovered = (status ?? 'active').toLowerCase()
  if (recovered === 'recovered' || recovered === 'resolved') {
    if (recoveredAt) {
      const end = Date.parse(recoveredAt)
      if (!Number.isNaN(end)) {
        return Math.max(0, Math.floor((end - start) / 1000))
      }
    }
    return fallback ?? null
  }
  return Math.max(0, Math.floor((now - start) / 1000))
}
