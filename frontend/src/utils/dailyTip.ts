/**
 * Daily-tip picker for the dashboard's "Tipp des Tages" card.
 *
 * Tip texts live as i18n keys (`tips.tip01` … `tips.tip30`) so each
 * locale carries its own translation. Picking the index here rather
 * than in the template keeps the choice deterministic across HMR
 * reloads on the same calendar day.
 */

export const TIP_COUNT = 30

/**
 * Day-of-year modulo TIP_COUNT — tips rotate over the 30-tip set
 * regardless of which day of the year it is. Two consecutive days
 * never get the same tip; the cycle resets every 30 days.
 */
export function tipIndexForDate(d: Date = new Date()): number {
  const start = Date.UTC(d.getUTCFullYear(), 0, 0)
  const today = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate())
  const dayOfYear = Math.floor((today - start) / 86_400_000)
  return ((dayOfYear - 1) % TIP_COUNT + TIP_COUNT) % TIP_COUNT
}

/** i18n key for today's tip — `tips.tip01` … `tips.tip30`. */
export function todaysTipKey(d: Date = new Date()): string {
  const idx = tipIndexForDate(d) + 1
  return `tips.tip${String(idx).padStart(2, '0')}`
}
