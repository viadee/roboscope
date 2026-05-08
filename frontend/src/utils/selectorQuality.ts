/**
 * Story EDITOR-1 — shared quality-band thresholds for SelectorPicker and
 * the visual editor's KeywordNode badge. Single source of truth so the
 * two surfaces never drift.
 *
 * AR-7 scoring rubric: testid/aria (>=80) green, pw_locator/text/short-css
 * (50..79) amber, xpath/fragile (<50) red.
 */
export type QualityBand = 'good' | 'ok' | 'poor'

export function qualityBand(score: number): QualityBand {
  if (score >= 80) return 'good'
  if (score >= 50) return 'ok'
  return 'poor'
}
