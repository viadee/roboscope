import type { SuccessRatePoint } from '@/types/domain.types'

/** One horizontal slot in the success-rate chart. `point` is null for a
 *  calendar day that had no test executions — the chart renders that slot
 *  bar-less so the time axis stays continuous and evenly spaced. */
export interface DailySlot {
  date: string
  point: SuccessRatePoint | null
}

const DAY_MS = 86_400_000

/**
 * Expand a success-rate series into one slot per calendar day between the
 * earliest and latest data point. Days without a data point get a slot with
 * `point: null` so the chart can render an empty (bar-less) column there
 * instead of collapsing the gap — every day occupies the same width.
 *
 * Dates are pure calendar days (`YYYY-MM-DD`); we iterate in UTC to avoid the
 * local-timezone drift that would otherwise skip or double a day around DST.
 * The `maxDays` cap (default 366 — one year window + 1) is a safety valve
 * against a malformed range producing an unbounded loop.
 */
export function fillDailySuccessRate(
  points: SuccessRatePoint[],
  maxDays = 366,
): DailySlot[] {
  if (points.length === 0) return []

  const byDay = new Map<string, SuccessRatePoint>()
  for (const p of points) byDay.set(p.date.slice(0, 10), p)

  const days = [...byDay.keys()].sort()
  const start = Date.parse(days[0] + 'T00:00:00Z')
  const end = Date.parse(days[days.length - 1] + 'T00:00:00Z')

  // Malformed dates — degrade gracefully to one slot per raw point rather
  // than throwing or looping forever.
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) {
    return points.map((p) => ({ date: p.date.slice(0, 10), point: p }))
  }

  const out: DailySlot[] = []
  for (let ms = start, n = 0; ms <= end && n < maxDays; ms += DAY_MS, n++) {
    const day = new Date(ms).toISOString().slice(0, 10)
    out.push({ date: day, point: byDay.get(day) ?? null })
  }
  return out
}
