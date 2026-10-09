import { memo } from 'react'
import { formatThaiDateTime } from '../utils/thaiDate'
import { formatRelativeTime } from '../utils/time'

interface RelativeTimeProps {
  value: string | null
  now: number
}

export const RelativeTime = memo(function RelativeTime({ value, now }: RelativeTimeProps) {
  const label = formatRelativeTime(value, now)
  return (
    <time dateTime={value ?? undefined} title={value ? formatThaiDateTime(value) : undefined}>
      {label}
    </time>
  )
})
