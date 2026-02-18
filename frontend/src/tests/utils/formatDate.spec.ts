import { describe, it, expect } from 'vitest'
import { formatDate, formatDateTime, formatTimeAgo } from '@/utils/formatDate'

describe('formatDate', () => {
  it('formats a valid ISO date string to de-DE format', () => {
    const result = formatDate('2024-03-15T10:30:00Z')
    expect(result).toBe('15.03.2024')
  })

  it('formats another valid date string', () => {
    const result = formatDate('2023-12-01')
    expect(result).toBe('01.12.2023')
  })

  it('formats a date at year boundary', () => {
    const result = formatDate('2025-01-01T00:00:00Z')
    expect(result).toBe('01.01.2025')
  })

  it('returns "-" for null input', () => {
    expect(formatDate(null)).toBe('-')
  })

  it('returns "-" for undefined input', () => {
    expect(formatDate(undefined)).toBe('-')
  })

  it('returns "-" for empty string input', () => {
    expect(formatDate('')).toBe('-')
  })

  it('returns "Invalid Date" output for an invalid date string', () => {
    const result = formatDate('not-a-date')
    // new Date('not-a-date').toLocaleDateString() produces 'Invalid Date'
    expect(result).toContain('Invalid')
  })
})

describe('formatDateTime', () => {
  it('formats a valid ISO date string with date and time', () => {
    const result = formatDateTime('2024-03-15T10:30:00Z')
    // de-DE format: DD.MM.YYYY, HH:MM
    expect(result).toMatch(/15\.03\.2024/)
    expect(result).toMatch(/\d{2}:\d{2}/)
  })

  it('returns "-" for null input', () => {
    expect(formatDateTime(null)).toBe('-')
  })

  it('returns "-" for undefined input', () => {
    expect(formatDateTime(undefined)).toBe('-')
  })

  it('returns "-" for empty string input', () => {
    expect(formatDateTime('')).toBe('-')
  })
})

describe('formatTimeAgo', () => {
  it('returns "-" for null input', () => {
    expect(formatTimeAgo(null)).toBe('-')
  })

  it('returns "-" for undefined input', () => {
    expect(formatTimeAgo(undefined)).toBe('-')
  })

  it('returns "-" for empty string', () => {
    expect(formatTimeAgo('')).toBe('-')
  })

  it('returns "gerade eben" for a date a few seconds ago', () => {
    const now = new Date()
    const fewSecondsAgo = new Date(now.getTime() - 10 * 1000).toISOString()
    expect(formatTimeAgo(fewSecondsAgo)).toBe('gerade eben')
  })

  it('returns minutes ago for a date a few minutes ago', () => {
    const now = new Date()
    const fiveMinAgo = new Date(now.getTime() - 5 * 60 * 1000).toISOString()
    expect(formatTimeAgo(fiveMinAgo)).toBe('vor 5 Min.')
  })

  it('returns hours ago for a date a few hours ago', () => {
    const now = new Date()
    const threeHoursAgo = new Date(now.getTime() - 3 * 60 * 60 * 1000).toISOString()
    expect(formatTimeAgo(threeHoursAgo)).toBe('vor 3 Std.')
  })

  it('returns days ago for a date a few days ago', () => {
    const now = new Date()
    const twoDaysAgo = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000).toISOString()
    expect(formatTimeAgo(twoDaysAgo)).toBe('vor 2 Tagen')
  })

  it('returns formatted date for dates older than a week', () => {
    const now = new Date()
    const tenDaysAgo = new Date(now.getTime() - 10 * 24 * 60 * 60 * 1000).toISOString()
    const result = formatTimeAgo(tenDaysAgo)
    // Should fall back to formatDate (de-DE date format)
    expect(result).toMatch(/\d{2}\.\d{2}\.\d{4}/)
  })
})
