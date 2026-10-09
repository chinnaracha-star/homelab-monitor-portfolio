import { describe, expect, it } from 'vitest'
import { formatThaiDate, formatThaiDateTime, formatThaiTime } from './thaiDate'

describe('Thai date formatting', () => {
  const stamp = new Date('2026-09-08T07:29:33Z')

  it('formats a Buddhist Era date', () => {
    expect(formatThaiDate(stamp)).toBe('8 กันยายน 2569')
  })

  it('formats Bangkok time with น.', () => {
    expect(formatThaiTime(stamp)).toBe('14:29:33 น.')
  })

  it('formats date and time together', () => {
    expect(formatThaiDateTime(stamp)).toBe('8 กันยายน 2569\n14:29:33 น.')
  })

  it('formats a date-only forecast', () => {
    expect(formatThaiDate('2026-09-13')).toBe('13 กันยายน 2569')
  })

  it('returns a dash for empty values', () => {
    expect(formatThaiDate(null)).toBe('—')
    expect(formatThaiTime('')).toBe('—')
    expect(formatThaiDateTime(undefined)).toBe('—')
  })
})
