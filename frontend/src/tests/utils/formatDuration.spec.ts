import { describe, it, expect } from 'vitest'
import { formatDuration, formatPercent } from '@/utils/formatDuration'

describe('formatDuration', () => {
  it('returns "-" for null input', () => {
    expect(formatDuration(null)).toBe('-')
  })

  it('returns "-" for undefined input', () => {
    expect(formatDuration(undefined)).toBe('-')
  })

  it('returns "-" for zero', () => {
    expect(formatDuration(0)).toBe('-')
  })

  it('formats sub-second values as milliseconds', () => {
    expect(formatDuration(0.5)).toBe('500ms')
    expect(formatDuration(0.123)).toBe('123ms')
    expect(formatDuration(0.001)).toBe('1ms')
  })

  it('formats seconds only (< 60s)', () => {
    expect(formatDuration(1)).toBe('1.0s')
    expect(formatDuration(30)).toBe('30.0s')
    expect(formatDuration(59.5)).toBe('59.5s')
    expect(formatDuration(5.75)).toBe('5.8s')
  })

  it('formats minutes and seconds (< 60 min)', () => {
    expect(formatDuration(60)).toBe('1m 0s')
    expect(formatDuration(90)).toBe('1m 30s')
    expect(formatDuration(125)).toBe('2m 5s')
    expect(formatDuration(3599)).toBe('59m 59s')
  })

  it('formats hours and minutes (>= 60 min)', () => {
    expect(formatDuration(3600)).toBe('1h 0m')
    expect(formatDuration(3661)).toBe('1h 1m')
    expect(formatDuration(7200)).toBe('2h 0m')
    expect(formatDuration(7320)).toBe('2h 2m')
  })
})

describe('formatPercent', () => {
  it('returns "-" for null input', () => {
    expect(formatPercent(null)).toBe('-')
  })

  it('returns "-" for undefined input', () => {
    expect(formatPercent(undefined)).toBe('-')
  })

  it('formats zero', () => {
    expect(formatPercent(0)).toBe('0.0%')
  })

  it('formats a whole number percentage', () => {
    expect(formatPercent(100)).toBe('100.0%')
  })

  it('formats a decimal percentage', () => {
    expect(formatPercent(85.67)).toBe('85.7%')
  })

  it('formats a small percentage', () => {
    expect(formatPercent(0.5)).toBe('0.5%')
  })
})
