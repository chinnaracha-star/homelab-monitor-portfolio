import { describe, expect, it } from 'vitest'
import { formatDuration, formatRelativeTime, liveAlertDurationSeconds } from './time'

describe('formatRelativeTime', () => {
  const now = Date.parse('2026-09-08T08:35:21Z')

  it('formats seconds and minutes', () => {
    expect(formatRelativeTime('2026-09-08T08:35:09Z', now)).toBe('12 seconds ago')
    expect(formatRelativeTime('2026-09-08T08:34:21Z', now)).toBe('1 minute ago')
  })

  it('formats a future report ETA', () => {
    expect(formatRelativeTime('2026-09-08T08:36:21Z', now)).toBe('in 1 minute')
  })

  it('handles empty values', () => {
    expect(formatRelativeTime(null, now)).toBe('Never')
    expect(formatRelativeTime('not-a-date', now)).toBe('Unknown')
  })

  it('formats alert durations', () => {
    expect(formatDuration(null)).toBe('—')
    expect(formatDuration(12)).toBe('12 sec')
    expect(formatDuration(180)).toBe('3 min')
    expect(
      liveAlertDurationSeconds(
        '2026-09-08T08:00:00Z',
        '2026-09-08T08:17:00Z',
        'recovered',
        Date.parse('2026-09-08T09:00:00Z'),
        0,
      ),
    ).toBe(17 * 60)
  })
})
