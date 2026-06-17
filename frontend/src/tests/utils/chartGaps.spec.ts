import { describe, it, expect } from 'vitest'
import { fillDailySuccessRate } from '@/utils/chartGaps'
import type { SuccessRatePoint } from '@/types/domain.types'

function pt(date: string, rate: number, runs = 1): SuccessRatePoint {
  return { date, success_rate: rate, total_runs: runs }
}

describe('fillDailySuccessRate', () => {
  it('returns empty for no points', () => {
    expect(fillDailySuccessRate([])).toEqual([])
  })

  it('keeps a single point as one slot', () => {
    const out = fillDailySuccessRate([pt('2026-06-10', 90)])
    expect(out).toHaveLength(1)
    expect(out[0].date).toBe('2026-06-10')
    expect(out[0].point?.success_rate).toBe(90)
  })

  it('inserts bar-less slots for days without executions', () => {
    // 10th and 13th have runs; 11th + 12th are gaps.
    const out = fillDailySuccessRate([pt('2026-06-10', 100), pt('2026-06-13', 50)])
    expect(out.map((s) => s.date)).toEqual([
      '2026-06-10', '2026-06-11', '2026-06-12', '2026-06-13',
    ])
    expect(out[0].point).not.toBeNull()
    expect(out[1].point).toBeNull()
    expect(out[2].point).toBeNull()
    expect(out[3].point?.success_rate).toBe(50)
  })

  it('gives every day the same slot regardless of how many gaps', () => {
    const out = fillDailySuccessRate([pt('2026-01-01', 80), pt('2026-01-08', 80)])
    expect(out).toHaveLength(8) // 1..8 inclusive
    expect(out.filter((s) => s.point === null)).toHaveLength(6)
  })

  it('does not drift across a DST boundary (Europe spring-forward)', () => {
    // 2026 CET→CEST is 2026-03-29. Iterating in local time would skip a day.
    const out = fillDailySuccessRate([pt('2026-03-28', 100), pt('2026-03-31', 100)])
    expect(out.map((s) => s.date)).toEqual([
      '2026-03-28', '2026-03-29', '2026-03-30', '2026-03-31',
    ])
  })

  it('tolerates timestamps with a time component', () => {
    const out = fillDailySuccessRate([
      pt('2026-06-10T07:58:04', 100),
      pt('2026-06-12T23:00:00', 100),
    ])
    expect(out.map((s) => s.date)).toEqual(['2026-06-10', '2026-06-11', '2026-06-12'])
  })

  it('caps the range and degrades gracefully on a reversed range', () => {
    // maxDays guard: a huge span is clamped, never an infinite loop.
    const out = fillDailySuccessRate([pt('2020-01-01', 100), pt('2026-01-01', 100)], 366)
    expect(out.length).toBe(366)
  })

  it('falls back to raw points on malformed dates', () => {
    const out = fillDailySuccessRate([pt('not-a-date', 100), pt('also-bad', 50)])
    expect(out).toHaveLength(2)
    expect(out[0].point?.success_rate).toBe(100)
  })
})
