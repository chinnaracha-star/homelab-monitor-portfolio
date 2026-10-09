export type DateInput = Date | string | number | null | undefined

const TIME_ZONE = 'Asia/Bangkok'
const LOCALE = 'th-TH'

function parseDate(value: DateInput): Date | null {
  if (value == null || value === '') {
    return null
  }
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const date = new Date(`${value}T12:00:00+07:00`)
    return Number.isNaN(date.getTime()) ? null : date
  }
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatThaiDate(value: DateInput): string {
  const date = parseDate(value)
  if (!date) {
    return '—'
  }
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date)
}

export function formatThaiDateShort(value: DateInput): string {
  const date = parseDate(value)
  if (!date) {
    return '—'
  }
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date)
}

export function formatThaiTime(value: DateInput, withSeconds = true): string {
  const date = parseDate(value)
  if (!date) {
    return '—'
  }
  const formatted = new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    second: withSeconds ? '2-digit' : undefined,
    hour12: false,
  }).format(date)
  return `${formatted} น.`
}

export function formatThaiDateTime(value: DateInput, withSeconds = true): string {
  const date = parseDate(value)
  if (!date) {
    return '—'
  }
  return `${formatThaiDate(date)}\n${formatThaiTime(date, withSeconds)}`
}
